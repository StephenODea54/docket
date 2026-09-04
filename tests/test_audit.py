import json

from docket.audit import find_flagged_deletions, parse_deletion_events


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
