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


class TableFinding(TypedDict):
    database: str | None
    table: str
    events: list[DeletionEvent]
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


def group_findings(findings: Sequence[AuditFinding]) -> list[TableFinding]:
    """
    Collapse per-event findings into one entry per deleted table.

    Order follows first appearance; each table keeps every deletion event
    and the single dependents report they share.
    """
    grouped: dict[tuple[str | None, str], TableFinding] = {}
    for finding in findings:
        event = finding["event"]
        key = (event["database"], event["table"])
        if key not in grouped:
            grouped[key] = {
                "database": event["database"],
                "table": event["table"],
                "events": [],
                "report": finding["report"],
            }
        grouped[key]["events"].append(event)
    return list(grouped.values())


def _table_name(finding: TableFinding) -> str:
    """Render database.table, or just table when the database is unknown."""
    if finding["database"]:
        return f"{finding['database']}.{finding['table']}"
    return finding["table"]


def format_table_finding(finding: TableFinding, format_report: Callable) -> str:
    """
    Render one deleted table: who deleted it, when, and what depends on it.

    Deletions are counted per (event name, principal); the time span covers
    the earliest and latest event.
    """
    events = finding["events"]
    actors: dict[str, int] = {}
    for event in events:
        label = f"{event['event_name']} by {event['username'] or 'unknown'}"
        actors[label] = actors.get(label, 0) + 1
    times = sorted(event["event_time"] for event in events if event["event_time"])
    regions = sorted({event["region"] for event in events if event["region"]})
    lines = [f"DELETED WITH DEPENDENTS: {_table_name(finding)}"]
    lines.append(
        f"  {len(events)} deletion(s): "
        + ", ".join(f"{label} ({count})" for label, count in actors.items())
    )
    if times:
        span = times[0] if times[0] == times[-1] else f"{times[0]} to {times[-1]}"
        lines.append(
            f"  when: {span}" + (f" ({', '.join(regions)})" if regions else "")
        )
    lines.append("")
    lines.append(format_report(finding["report"]))
    return "\n".join(lines)


def format_audit_report(
    findings: Sequence[TableFinding],
    deletion_count: int,
    hours: int,
    format_report: Callable,
) -> str:
    """
    Render the whole audit as one text report, one block per flagged table.

    Args:
        findings: grouped findings from group_findings
        deletion_count: every deletion considered, flagged or not
        hours: the lookback window that was scanned
        format_report: renders a DependentsReport (docket.lineage.format_report)

    Returns:
        The report text, ending with a newline
    """
    header = (
        f"docket audit: {deletion_count} glue deletion(s) in the last {hours}h, "
        f"{len(findings)} table(s) deleted with dependents"
    )
    blocks = [header, ""]
    for finding in findings:
        blocks.append(format_table_finding(finding, format_report))
        blocks.append("")
    if not findings:
        blocks.append("none had dependents")
        blocks.append("")
    return "\n".join(blocks)
