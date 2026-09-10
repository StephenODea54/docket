import json

from docket.audit import (
    find_flagged_deletions,
    format_audit_report,
    group_findings,
    parse_deletion_events,
)


def make_row(**overrides):
    row = {
        "event_id": "evt-1",
        "event_name": "DeleteTable",
        "event_source": "glue.amazonaws.com",
        "event_time": "2026-09-03T22:14:00+00:00",
        "username": "alice",
        "region": "us-east-1",
        "cloud_trail_event": json.dumps(
            {"requestParameters": {"databaseName": "raw", "name": "orders"}}
        ),
    }
    row.update(overrides)
    return row


def make_report(has_dependents):
    return {"has_dependents": has_dependents}


def test_parse_delete_table_event():
    events = parse_deletion_events([make_row()])

    assert events == [
        {
            "event_id": "evt-1",
            "database": "raw",
            "table": "orders",
            "event_name": "DeleteTable",
            "event_time": "2026-09-03T22:14:00+00:00",
            "username": "alice",
            "region": "us-east-1",
        }
    ]


def test_parse_batch_delete_fans_out():
    row = make_row(
        event_name="BatchDeleteTable",
        cloud_trail_event=json.dumps(
            {
                "requestParameters": {
                    "databaseName": "raw",
                    "tablesToDelete": ["orders", "customers"],
                }
            }
        ),
    )
    events = parse_deletion_events([row])

    assert [event["table"] for event in events] == ["orders", "customers"]
    assert {event["event_id"] for event in events} == {"evt-1"}


def test_parse_skips_non_glue_sources():
    assert parse_deletion_events([make_row(event_source="s3.amazonaws.com")]) == []


def test_parse_skips_malformed_rows():
    rows = [
        make_row(cloud_trail_event=None),
        make_row(cloud_trail_event="not json"),
        make_row(cloud_trail_event=json.dumps({"requestParameters": None})),
        make_row(cloud_trail_event=json.dumps({"requestParameters": {}})),
        make_row(event_id=None),
    ]
    assert parse_deletion_events(rows) == []


def test_find_flagged_deletions_flags_and_dedupes_collect():
    events = parse_deletion_events(
        [make_row(), make_row(event_id="evt-2"), make_row(event_id="evt-3")]
    )
    events[2]["table"] = "customers"
    calls = []

    def collect(database, table):
        calls.append((database, table))
        return make_report(table == "orders")

    findings = find_flagged_deletions(events, collect)

    assert calls == [("raw", "orders"), ("raw", "customers")]
    assert [finding["event"]["event_id"] for finding in findings] == ["evt-1", "evt-2"]


def test_group_findings_collapses_events_per_table():
    events = parse_deletion_events(
        [
            make_row(event_id="evt-1", event_time="2026-09-08T21:31:00+00:00"),
            make_row(event_id="evt-2", username="GlueJobRunnerSession"),
            make_row(event_id="evt-3"),
        ]
    )
    events[2]["table"] = "customers"
    findings = find_flagged_deletions(events, lambda d, t: make_report(True))

    grouped = group_findings(findings)

    assert [(g["database"], g["table"]) for g in grouped] == [
        ("raw", "orders"),
        ("raw", "customers"),
    ]
    assert [e["event_id"] for e in grouped[0]["events"]] == ["evt-1", "evt-2"]
    assert grouped[0]["report"] is findings[0]["report"]


def test_format_audit_report_renders_one_block_per_table():
    events = parse_deletion_events(
        [
            make_row(event_id="evt-1", event_time="2026-09-08T21:31:00+00:00"),
            make_row(event_id="evt-2", username="GlueJobRunnerSession"),
        ]
    )
    grouped = group_findings(
        find_flagged_deletions(events, lambda d, t: make_report(True))
    )

    text = format_audit_report(grouped, 5, 24, lambda report: "<dependents>")

    assert text.splitlines()[0] == (
        "docket audit: 5 glue deletion(s) in the last 24h, "
        "1 table(s) deleted with dependents"
    )
    assert text.count("DELETED WITH DEPENDENTS: raw.orders") == 1
    assert (
        "2 deletion(s): DeleteTable by alice (1), "
        "DeleteTable by GlueJobRunnerSession (1)"
    ) in text
    assert "when: 2026-09-03T22:14:00+00:00 to 2026-09-08T21:31:00+00:00" in text
    assert "<dependents>" in text


def test_format_audit_report_clean():
    text = format_audit_report([], 3, 24, lambda report: "")
    assert "0 table(s) deleted with dependents" in text
    assert "none had dependents" in text
