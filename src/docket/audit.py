import json
from collections.abc import Callable, Sequence
from typing import TypedDict

from .config.logger import get_logger
from .db.aws_cloudtrail_events import AwsCloudtrailLookupEventSelect
from .lineage import DependentsReport

logger = get_logger("audit")

GLUE_EVENT_SOURCE = "glue.amazonaws.com"


class DeletionEvent(TypedDict):
    event_id: str
    database: str | None
    table: str
    event_name: str
    event_time: str | None
    username: str | None
    region: str | None


class AuditFinding(TypedDict):
    event: DeletionEvent
    report: DependentsReport


def _request_parameters(row: AwsCloudtrailLookupEventSelect) -> dict | None:
    """Decode a CloudTrail row's requestParameters, or None when unusable."""
    payload = row["cloud_trail_event"]
    if not payload:
        return None
    try:
        parameters = json.loads(payload).get("requestParameters")
    except (json.JSONDecodeError, AttributeError):
        return None
    return parameters if isinstance(parameters, dict) else None


def parse_deletion_events(
    rows: Sequence[AwsCloudtrailLookupEventSelect],
) -> list[DeletionEvent]:
    """
    Extract per-table deletion events from CloudTrail lookup rows.

    BatchDeleteTable fans out to one event per table, sharing the row's
    event id. Non-glue sources and malformed rows are skipped with a
    warning.
    """
    events: list[DeletionEvent] = []
    for row in rows:
        if row["event_source"] != GLUE_EVENT_SOURCE:
            continue
        parameters = _request_parameters(row)
        event_id = row["event_id"]
        if parameters is None or not event_id:
            logger.warning("skipping malformed cloudtrail event %s", event_id)
            continue
        if row["event_name"] == "DeleteTable":
            tables = [parameters.get("name")]
        else:
            tables = parameters.get("tablesToDelete") or []
        database = parameters.get("databaseName")
        found = False
        for table in tables:
            if not isinstance(table, str) or not table:
                continue
            found = True
            events.append(
                {
                    "event_id": event_id,
                    "database": database,
                    "table": table,
                    "event_name": row["event_name"] or "",
                    "event_time": row["event_time"],
                    "username": row["username"],
                    "region": row["region"],
                }
            )
        if not found:
            logger.warning("skipping cloudtrail event %s with no tables", event_id)
    return events


def find_flagged_deletions(
    events: Sequence[DeletionEvent],
    collect: Callable[[str | None, str], DependentsReport],
) -> list[AuditFinding]:
    """
    Return one finding per deletion event whose table had dependents.

    The collect call is cached per (database, table) so duplicate
    deletions of the same table walk the graph once.
    """
    reports: dict[tuple[str | None, str], DependentsReport] = {}
    findings: list[AuditFinding] = []
    for event in events:
        key = (event["database"], event["table"])
        if key not in reports:
            reports[key] = collect(event["database"], event["table"])
        if reports[key]["has_dependents"]:
            findings.append({"event": event, "report": reports[key]})
    return findings
