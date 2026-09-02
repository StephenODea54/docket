from __future__ import annotations

import platform
import sqlite3
import sys
import tarfile
import urllib.request
from pathlib import Path

from sustained import Model
from sustained.migrations import Migrator

from ..config import get_logger
from .aws_glue_databases import AwsGlueDatabaseClient
from .aws_glue_tables import AwsGlueTableClient
from .catalog_databases import MODELS as CATALOG_DATABASE_MODELS
from .catalog_databases import CatalogDatabaseClient
from .catalog_tables import MODELS as CATALOG_TABLE_MODELS
from .catalog_tables import CatalogTableClient

logger = get_logger("db")

DEFAULT_VERSION = "v1.32.0"
DARWIN_ARM64_VERSION = "v1.29.0"

_MACHINES = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64", "aarch64": "arm64"}

ALL_MODELS = [*CATALOG_DATABASE_MODELS, *CATALOG_TABLE_MODELS]


class UnsupportedPlatformError(RuntimeError):
    """Raised when no steampipe extension build exists for this platform."""


def _platform_key() -> str:
    """Return the steampipe release asset key for the current OS and architecture."""
    machine = _MACHINES.get(platform.machine().lower())
    if machine is None:
        raise UnsupportedPlatformError(platform.machine())
    if sys.platform.startswith("linux"):
        return f"linux_{machine}"
    if sys.platform == "darwin":
        return f"darwin_{machine}"
    raise UnsupportedPlatformError(sys.platform)


def _extension_version(key: str) -> str:
    """
    Return the pinned plugin version for a platform key.

    darwin_arm64 is pinned to v1.29.0 because upstream stopped publishing
    that build in later releases.
    """
    return DARWIN_ARM64_VERSION if key == "darwin_arm64" else DEFAULT_VERSION


def _extension_path() -> Path:
    """Return the local cache path for the steampipe sqlite extension."""
    key = _platform_key()
    return (
        Path.home()
        / ".docket"
        / "steampipe"
        / _extension_version(key)
        / key
        / "steampipe_sqlite_aws.so"
    )


def ensure_extension() -> Path:
    """Download and cache the steampipe sqlite AWS extension, returning its path."""
    path = _extension_path()
    if path.exists():
        return path
    key = _platform_key()
    version = _extension_version(key)
    url = (
        "https://github.com/turbot/steampipe-plugin-aws/releases/download/"
        f"{version}/steampipe_sqlite_aws.{key}.tar.gz"
    )
    logger.info(
        "downloading steampipe extension %s (%s), this can take a while", version, key
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    archive = path.parent / "steampipe_sqlite_aws.tar.gz"
    urllib.request.urlretrieve(url, archive)
    with tarfile.open(archive, "r:gz") as tar:
        member = tar.getmember("steampipe_sqlite_aws.so")
        try:
            tar.extract(member, path.parent, filter="data")
        except TypeError:
            tar.extract(member, path.parent)
    archive.unlink()
    logger.info("cached steampipe extension at %s", path)
    return path


def _connect(
    db_path: str | Path = "docket.db", profile: str | None = None
) -> sqlite3.Connection:
    """
    Open the docket database with the steampipe extension loaded

    Args:
        db_path: path to the sqlite file
        profile: aws profile name

    Returns:
        sqlite3.Connection
    """
    extension = ensure_extension()
    conn = sqlite3.connect(str(db_path))
    conn.enable_load_extension(True)
    conn.load_extension(str(extension))
    conn.enable_load_extension(False)
    if profile:
        conn.execute("select steampipe_configure_aws(?)", (f'profile = "{profile}"',))
    Model.bind(conn)
    return conn


class DB:
    def __init__(
        self, db_path: str | Path = "docket.db", profile: str | None = None
    ) -> None:
        self.conn = _connect(db_path=db_path, profile=profile)
        self.clients = {
            "aws_glue_databases": AwsGlueDatabaseClient(self.conn),
            "aws_glue_tables": AwsGlueTableClient(self.conn),
            "catalog_databases": CatalogDatabaseClient(self.conn),
            "catalog_tables": CatalogTableClient(self.conn),
        }

    def migrate(self) -> list[str]:
        """Diff the database against every registered model and apply the changes."""
        return Migrator(self.conn, []).up(models=ALL_MODELS)

    def transaction(self):
        """Open a sustained transaction block; nested blocks become savepoints."""
        return Model.transaction()
