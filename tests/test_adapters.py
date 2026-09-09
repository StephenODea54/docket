import sys
import types

import pytest
from fastapi import FastAPI

from docket.web.adapters import (
    ADAPTERS,
    STRATEGIES,
    LambdaAdapter,
    ServeAdapterStrategy,
    UvicornAdapter,
)
from docket.web.adapters import serve_adapter_strategies as strategies


def test_registry_is_keyed_by_strategy_type():
    assert dict(ADAPTERS) == {"uvicorn": UvicornAdapter, "lambda": LambdaAdapter}
    assert all(issubclass(cls, ServeAdapterStrategy) for cls in STRATEGIES)


def test_uvicorn_adapter_binds_host_and_port(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        strategies.uvicorn,
        "run",
        lambda app, host, port: calls.update(app=app, host=host, port=port),
    )
    app = FastAPI()

    UvicornAdapter().serve(app, "0.0.0.0", 9000)

    assert calls == {"app": app, "host": "0.0.0.0", "port": 9000}


def test_lambda_adapter_refuses_to_run_outside_lambda(monkeypatch):
    monkeypatch.delenv("AWS_LAMBDA_RUNTIME_API", raising=False)
    with pytest.raises(RuntimeError, match="AWS_LAMBDA_RUNTIME_API"):
        LambdaAdapter().serve(FastAPI(), "0.0.0.0", 8000)


def test_lambda_adapter_explains_missing_extra(monkeypatch):
    monkeypatch.setenv("AWS_LAMBDA_RUNTIME_API", "127.0.0.1:9001")
    monkeypatch.setitem(sys.modules, "awslambdaric", None)
    monkeypatch.setitem(sys.modules, "awslambdaric.__main__", None)
    with pytest.raises(RuntimeError, match="lambda"):
        LambdaAdapter().serve(FastAPI(), "0.0.0.0", 8000)


def test_lambda_adapter_wraps_app_and_starts_runtime_client(monkeypatch):
    monkeypatch.setenv("AWS_LAMBDA_RUNTIME_API", "127.0.0.1:9001")
    calls = {}

    class FakeMangum:
        def __init__(self, app, lifespan):
            calls["app"] = app
            calls["lifespan"] = lifespan

    fake_mangum = types.ModuleType("mangum")
    fake_mangum.Mangum = FakeMangum
    fake_ric = types.ModuleType("awslambdaric")
    fake_ric_main = types.ModuleType("awslambdaric.__main__")
    fake_ric_main.main = lambda argv: calls.update(argv=argv)
    monkeypatch.setitem(sys.modules, "mangum", fake_mangum)
    monkeypatch.setitem(sys.modules, "awslambdaric", fake_ric)
    monkeypatch.setitem(sys.modules, "awslambdaric.__main__", fake_ric_main)
    monkeypatch.setattr(strategies, "handler", None)
    app = FastAPI()

    LambdaAdapter().serve(app, "ignored", 0)

    assert calls["app"] is app
    assert calls["lifespan"] == "off"
    assert calls["argv"] == [
        "awslambdaric",
        "docket.web.adapters.serve_adapter_strategies.handler",
    ]
    assert isinstance(strategies.handler, FakeMangum)
