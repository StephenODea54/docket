import json
import sqlite3
from contextlib import nullcontext
from datetime import UTC, datetime

from typer.testing import CliRunner

from docket import cli
from docket.orchestrator import LlmEdgeExtractor

runner = CliRunner()


def test_no_command_shows_help():
    result = runner.invoke(cli.app, [])
    assert result.exit_code == 2
    assert "Usage" in result.output


def test_unknown_command_exits():
    result = runner.invoke(cli.app, ["explode"])
    assert result.exit_code == 2


def test_run_without_model_exits(monkeypatch):
    monkeypatch.delenv("DOCKET_LLM_MODEL", raising=False)
    result = runner.invoke(cli.app, ["run"])
    assert result.exit_code == 2
    assert "DOCKET_LLM_MODEL" in result.stderr


def test_run_invokes_pipeline(monkeypatch):
    monkeypatch.setenv("DOCKET_LLM_MODEL", "test/model")
    calls = {}
    monkeypatch.setattr(cli, "DB", lambda: "db")

    def fake_run(db, extractor):
        calls["db"] = db
        calls["extractor"] = extractor
        return ["job-1", "job-2"]

    monkeypatch.setattr(cli, "run_pipeline", fake_run)

    result = runner.invoke(cli.app, ["run"])

    assert result.exit_code == 0
    assert calls["db"] == "db"
    assert isinstance(calls["extractor"], LlmEdgeExtractor)
    assert calls["extractor"].model == "test/model"
    assert "re-extracted 2 jobs" in result.output


def make_report(**overrides):
    report = {
        "database": "raw",
        "table": "orders",
        "in_catalog": True,
        "direct_jobs": [],
        "direct_tables": [],
        "join_refs": [],
        "transitive_jobs": [],
        "transitive_tables": [],
        "layers": [],
        "has_dependents": False,
    }
    report.update(overrides)
    return report


class DummyDB:
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.clients = {}

    def migrate(self):
        return []


def test_check_delete_missing_db_exits(tmp_path):
    missing = tmp_path / "missing.db"
    result = runner.invoke(
        cli.app, ["check-delete", "raw", "orders", "--db-path", str(missing)]
    )
    assert result.exit_code == 2
    assert "docket run" in result.stderr


def test_check_delete_clean_exits_zero(monkeypatch, tmp_path):
    db_file = tmp_path / "docket.db"
    db_file.touch()
    monkeypatch.setattr(cli, "DB", DummyDB)
    monkeypatch.setattr(cli, "_collect_dependents", lambda db, d, t: make_report())

    result = runner.invoke(
        cli.app, ["check-delete", "raw", "orders", "--db-path", str(db_file)]
    )

    assert result.exit_code == 0
    assert "catalog file last written" in result.output
    assert "raw.orders has no dependents" in result.output


def test_check_delete_with_dependents_exits_one(monkeypatch, tmp_path):
    db_file = tmp_path / "docket.db"
    db_file.touch()
    monkeypatch.setattr(cli, "DB", DummyDB)
    report = make_report(
        direct_jobs=[{"id": "job-1", "label": "glue: reporter"}],
        direct_tables=[{"database": "analytics", "table": "summary"}],
        has_dependents=True,
    )
    monkeypatch.setattr(cli, "_collect_dependents", lambda db, d, t: report)

    result = runner.invoke(
        cli.app, ["check-delete", "raw", "orders", "--db-path", str(db_file)]
    )

    assert result.exit_code == 1
    assert "glue: reporter" in result.output
    assert "NOT SAFE" in result.output


def test_check_delete_warns_for_unknown_table(monkeypatch, tmp_path):
    db_file = tmp_path / "docket.db"
    db_file.touch()
    monkeypatch.setattr(cli, "DB", DummyDB)
    monkeypatch.setattr(
        cli, "_collect_dependents", lambda db, d, t: make_report(in_catalog=False)
    )

    result = runner.invoke(
        cli.app, ["check-delete", "raw", "orders", "--db-path", str(db_file)]
    )

    assert result.exit_code == 0
    assert "not in the catalog snapshot" in result.stderr


def make_cloudtrail_row(event_id="evt-1", table="orders"):
    return {
        "event_id": event_id,
        "event_name": "DeleteTable",
        "event_source": "glue.amazonaws.com",
        "event_time": "2026-09-03T22:14:00+00:00",
        "username": "alice",
        "region": "us-east-1",
        "cloud_trail_event": json.dumps(
            {"requestParameters": {"databaseName": "raw", "name": table}}
        ),
    }


class FakeCloudtrail:
    def __init__(self, rows=(), error=None):
        self.rows = list(rows)
        self.error = error
        self.calls = []

    def get_events(self, event_name, start_time):
        self.calls.append((event_name, start_time))
        if self.error:
            raise self.error
        return [row for row in self.rows if row["event_name"] == event_name]


class FakeAuditLog:
    def __init__(self, seen=()):
        self.seen = set(seen)
        self.inserted = []

    def get_event_ids(self, event_ids):
        return {event_id for event_id in event_ids if event_id in self.seen}

    def insert_events(self, records):
        self.inserted += records
        return records


class AuditDB(DummyDB):
    cloudtrail = FakeCloudtrail()
    audit_log = FakeAuditLog()

    def __init__(self, db_path=None):
        super().__init__(db_path)
        self.clients = {
            "aws_cloudtrail_events": type(self).cloudtrail,
            "catalog_audit_events": type(self).audit_log,
        }

    def transaction(self):
        return nullcontext()


def setup_audit(monkeypatch, tmp_path, rows=(), error=None, seen=(), reports=None):
    db_file = tmp_path / "docket.db"
    db_file.touch()
    AuditDB.cloudtrail = FakeCloudtrail(rows, error)
    AuditDB.audit_log = FakeAuditLog(seen)
    monkeypatch.setattr(cli, "DB", AuditDB)
    monkeypatch.setattr(
        cli,
        "_collect_dependents",
        lambda db, database, table: make_report(
            table=table, has_dependents=table in (reports or ())
        ),
    )
    return db_file


def test_audit_credentials_error_exits_two(monkeypatch, tmp_path):
    db_file = setup_audit(
        monkeypatch, tmp_path, error=sqlite3.OperationalError("expired token")
    )

    result = runner.invoke(cli.app, ["audit", "--db-path", str(db_file)])

    assert result.exit_code == 2
    assert "check AWS credentials" in result.stderr


def test_audit_flags_deletion_with_dependents(monkeypatch, tmp_path):
    db_file = setup_audit(
        monkeypatch, tmp_path, rows=[make_cloudtrail_row()], reports=("orders",)
    )

    result = runner.invoke(cli.app, ["audit", "--db-path", str(db_file)])

    assert result.exit_code == 1
    assert "DELETED WITH DEPENDENTS: raw.orders" in result.stderr
    assert "DeleteTable by alice" in result.stderr
    assert AuditDB.audit_log.inserted[0]["flagged"] is True


def test_audit_clean_run_persists_and_exits_zero(monkeypatch, tmp_path):
    db_file = setup_audit(monkeypatch, tmp_path, rows=[make_cloudtrail_row()])

    result = runner.invoke(cli.app, ["audit", "--db-path", str(db_file)])

    assert result.exit_code == 0
    assert "1 new glue deletion(s)" in result.output
    assert "none had dependents" in result.output
    assert AuditDB.audit_log.inserted[0]["flagged"] is False


def test_audit_skips_seen_events_unless_all(monkeypatch, tmp_path):
    db_file = setup_audit(
        monkeypatch,
        tmp_path,
        rows=[make_cloudtrail_row()],
        seen=("evt-1",),
        reports=("orders",),
    )

    result = runner.invoke(cli.app, ["audit", "--db-path", str(db_file)])

    assert result.exit_code == 0
    assert "0 new glue deletion(s)" in result.output
    assert AuditDB.audit_log.inserted == []

    result = runner.invoke(cli.app, ["audit", "--all", "--db-path", str(db_file)])

    assert result.exit_code == 1
    assert "DELETED WITH DEPENDENTS: raw.orders" in result.stderr
    assert AuditDB.audit_log.inserted == []


def test_audit_hours_bounds_lookup(monkeypatch, tmp_path):
    db_file = setup_audit(monkeypatch, tmp_path)

    result = runner.invoke(
        cli.app, ["audit", "--hours", "48", "--db-path", str(db_file)]
    )

    assert result.exit_code == 0
    names = [name for name, _ in AuditDB.cloudtrail.calls]
    assert names == ["DeleteTable", "BatchDeleteTable"]
    start = AuditDB.cloudtrail.calls[0][1]
    lookback = (datetime.now(UTC) - start).total_seconds() / 3600
    assert 47.9 < lookback < 48.1


def test_serve_missing_db_exits(tmp_path):
    missing = tmp_path / "missing.db"
    result = runner.invoke(cli.app, ["serve", "--db-path", str(missing)])
    assert result.exit_code == 2
    assert "docket run" in result.stderr


def test_serve_unknown_adapter_exits(tmp_path):
    result = runner.invoke(cli.app, ["serve", "--adapter", "carrier-pigeon"])
    assert result.exit_code == 2
    assert "uvicorn" in result.stderr
    assert "lambda" in result.stderr


def fake_adapter(calls):
    class FakeAdapter:
        def serve(self, app, host, port):
            calls["app"] = app
            calls["host"] = host
            calls["port"] = port

    return FakeAdapter


def test_serve_runs_default_adapter(monkeypatch, tmp_path):
    db_file = tmp_path / "docket.db"
    db_file.touch()
    monkeypatch.delenv("DOCKET_SERVE_ADAPTER", raising=False)
    calls = {}
    monkeypatch.setattr(cli, "DB", lambda db_path: f"db:{db_path}")
    monkeypatch.setattr(cli, "create_app", lambda db: f"app:{db}")
    monkeypatch.setitem(cli.ADAPTERS, "uvicorn", fake_adapter(calls))

    result = runner.invoke(
        cli.app,
        ["serve", "--db-path", str(db_file), "--host", "0.0.0.0", "--port", "9000"],
    )

    assert result.exit_code == 0
    assert calls["app"] == f"app:db:{db_file}"
    assert calls["host"] == "0.0.0.0"
    assert calls["port"] == 9000


def test_serve_reads_env_defaults(monkeypatch, tmp_path):
    db_file = tmp_path / "docket.db"
    db_file.touch()
    monkeypatch.setenv("DOCKET_DB_PATH", str(db_file))
    monkeypatch.setenv("DOCKET_SERVE_HOST", "0.0.0.0")
    monkeypatch.setenv("DOCKET_SERVE_PORT", "9100")
    monkeypatch.setenv("DOCKET_SERVE_ADAPTER", "lambda")
    calls = {}
    monkeypatch.setattr(cli, "DB", lambda db_path: f"db:{db_path}")
    monkeypatch.setattr(cli, "create_app", lambda db: f"app:{db}")
    monkeypatch.setitem(cli.ADAPTERS, "lambda", fake_adapter(calls))

    result = runner.invoke(cli.app, ["serve"])

    assert result.exit_code == 0
    assert calls["host"] == "0.0.0.0"
    assert calls["port"] == 9100
