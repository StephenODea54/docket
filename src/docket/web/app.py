from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .routes import router


def create_app(db: Any) -> FastAPI:
    """
    Build the catalog browser app around an opened DB.

    Args:
        db: local sqlite db

    Returns:
        FastAPI server
    """
    app = FastAPI(title="docket")
    app.state.db = db
    package_dir = Path(__file__).parent
    static_dir = package_dir / "static"
    app.state.templates = Jinja2Templates(directory=package_dir / "templates")
    app.state.templates.env.globals["asset_version"] = int(
        max(path.stat().st_mtime for path in static_dir.iterdir())
    )
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.include_router(router)
    return app
