import sqlite3

import pytest
from sustained import Model
from sustained.migrations import Migrator

from docket.config.env import AWS_REGIONS
from docket.db.catalog_audit_events import CatalogAuditEventClient
from docket.db.db import ALL_MODELS, _build_aws_config


def test_build_aws_config_empty(monkeypatch):
    monkeypatch.delenv(AWS_REGIONS, raising=False)
    assert _build_aws_config() is None


def test_build_aws_config_single_region(monkeypatch):
    monkeypatch.setenv(AWS_REGIONS, "us-east-1")
    assert _build_aws_config() == 'regions = ["us-east-1"]'


def test_build_aws_config_multiple_regions(monkeypatch):
    monkeypatch.setenv(AWS_REGIONS, "us-east-1, us-west-2,")
    assert _build_aws_config() == 'regions = ["us-east-1", "us-west-2"]'


@pytest.fixture
def audit_client():
    conn = sqlite3.connect(":memory:")
    conn.execute("pragma foreign_keys = on")
    Model.bind(conn)
    Migrator(conn, []).up(models=ALL_MODELS)
    yield CatalogAuditEventClient(conn)
    conn.close()


def make_audit_event(event_id="evt-1", table_name="orders"):
    return {
        "event_id": event_id,
        "database_name": "raw",
        "table_name": table_name,
        "event_name": "DeleteTable",
        "event_time": "2026-09-04T00:00:00+00:00",
        "username": "alice",
        "region": "us-east-1",
        "flagged": True,
    }


def test_audit_events_round_trip(audit_client):
    with Model.transaction():
        rows = audit_client.insert_events(
            [make_audit_event(), make_audit_event(event_id="evt-2")]
        )

    assert all(row["reported_at"] for row in rows)
    assert audit_client.get_event_ids(["evt-1", "evt-3"]) == {"evt-1"}
    assert audit_client.get_event_ids([]) == set()


def test_audit_events_share_event_id_across_tables(audit_client):
    with Model.transaction():
        audit_client.insert_events(
            [
                make_audit_event(table_name="orders"),
                make_audit_event(table_name="customers"),
            ]
        )

    assert audit_client.get_event_ids(["evt-1"]) == {"evt-1"}


def test_audit_events_reject_duplicate_event_table(audit_client):
    with Model.transaction():
        audit_client.insert_events([make_audit_event()])
    with pytest.raises(sqlite3.IntegrityError):
        with Model.transaction():
            audit_client.insert_events([make_audit_event()])
