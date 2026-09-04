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
