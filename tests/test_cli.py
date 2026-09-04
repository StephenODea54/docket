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


def test_serve_missing_db_exits(tmp_path):
    missing = tmp_path / "missing.db"
    result = runner.invoke(cli.app, ["serve", "--db-path", str(missing)])
    assert result.exit_code == 2
    assert "docket run" in result.stderr


def test_serve_runs_uvicorn(monkeypatch, tmp_path):
    db_file = tmp_path / "docket.db"
    db_file.touch()
    calls = {}
    monkeypatch.setattr(cli, "DB", lambda db_path: f"db:{db_path}")
    monkeypatch.setattr(cli, "create_app", lambda db: f"app:{db}")

    def fake_run(app, host, port):
        calls["app"] = app
        calls["host"] = host
        calls["port"] = port

    monkeypatch.setattr(cli.uvicorn, "run", fake_run)

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
    calls = {}
    monkeypatch.setattr(cli, "DB", lambda db_path: f"db:{db_path}")
    monkeypatch.setattr(cli, "create_app", lambda db: f"app:{db}")

    def fake_run(app, host, port):
        calls["host"] = host
        calls["port"] = port

    monkeypatch.setattr(cli.uvicorn, "run", fake_run)

    result = runner.invoke(cli.app, ["serve"])

    assert result.exit_code == 0
    assert calls["host"] == "0.0.0.0"
    assert calls["port"] == 9100
