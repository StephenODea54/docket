from __future__ import annotations

import platform
import sqlite3
import sys
import tarfile
import urllib.request
from contextlib import AbstractContextManager
from pathlib import Path

from sustained import Model
from sustained.migrations import Migrator
from sustained.types import Connection

from ..config import get_logger
from .aws_glue_databases import AwsGlueDatabaseClient
from .aws_glue_jobs import AwsGlueJobClient
from .aws_glue_tables import AwsGlueTableClient
from .aws_lambda_functions import AwsLambdaFunctionClient
from .aws_s3_objects import AwsS3ObjectClient
from .catalog_databases import MODELS as CATALOG_DATABASE_MODELS
from .catalog_databases import CatalogDatabaseClient
from .catalog_job_artifacts import MODELS as CATALOG_JOB_ARTIFACT_MODELS
from .catalog_job_artifacts import CatalogJobArtifactClient
from .catalog_job_extractions import MODELS as CATALOG_JOB_EXTRACTION_MODELS
from .catalog_job_extractions import CatalogJobExtractionClient
from .catalog_job_table_edges import MODELS as CATALOG_JOB_TABLE_EDGE_MODELS
from .catalog_job_table_edges import CatalogJobTableEdgeClient
from .catalog_jobs import MODELS as CATALOG_JOB_MODELS
from .catalog_jobs import CatalogJobClient
from .catalog_table_join_edges import MODELS as CATALOG_TABLE_JOIN_EDGE_MODELS
from .catalog_table_join_edges import CatalogTableJoinEdgeClient
from .catalog_tables import MODELS as CATALOG_TABLE_MODELS
from .catalog_tables import CatalogTableClient

logger = get_logger("db")

DEFAULT_VERSION = "v1.32.0"
DARWIN_ARM64_VERSION = "v1.29.0"

_MACHINES = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64", "aarch64": "arm64"}

ALL_MODELS = [
    *CATALOG_DATABASE_MODELS,
    *CATALOG_TABLE_MODELS,
    *CATALOG_JOB_MODELS,
    *CATALOG_JOB_ARTIFACT_MODELS,
    *CATALOG_JOB_EXTRACTION_MODELS,
    *CATALOG_JOB_TABLE_EDGE_MODELS,
    *CATALOG_TABLE_JOIN_EDGE_MODELS,
]


class UnsupportedPlatformError(RuntimeError):
    """Raised when no steampipe extension build exists for this platform."""


def _get_platform_key() -> str:
    """
    Return the steampipe release asset key for the current OS and architecture.

    Args:
        None

    Returns:
        plaform key

    Raises:
        UnsupportedPlatformError if steampipe is not compatible with the machine
        running it.
    """
    machine = _MACHINES.get(platform.machine().lower())
    if machine is None:
        raise UnsupportedPlatformError(platform.machine())
    if sys.platform.startswith("linux"):
        return f"linux_{machine}"
    if sys.platform == "darwin":
        return f"darwin_{machine}"
    raise UnsupportedPlatformError(sys.platform)


def _get_extension_version(key: str) -> str:
    """
    Returns the pinned plugin version for a platform key.

    darwin_arm64 is pinned to v1.29.0 because upstream stopped publishing
    that build in later releases.

    Args:
        key: platform key for steampipe, depending on the machine

    Returns:
        the steampipe plugin version
    """
    return DARWIN_ARM64_VERSION if key == "darwin_arm64" else DEFAULT_VERSION


def _extension_path() -> Path:
    """
    Return the local cache path for the steampipe sqlite extension.

    Args:
        None

    Returns:
        The path of the steampipe extension
    """
    key = _get_platform_key()
    return (
        Path.home()
        / ".docket"
        / "steampipe"
        / _get_extension_version(key)
        / key
        / "steampipe_sqlite_aws.so"
    )


def _download_steampipe_extension() -> Path:
    """
    Downloads and caches the steampipe sqlite AWS extension, returning its path.

    Args:
        None

    Returns:
        The path of the unzipped steampipe extension
    """
    path = _extension_path()
    if path.exists():
        return path
    key = _get_platform_key()
    version = _get_extension_version(key)
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
    extension = _download_steampipe_extension()
    conn = sqlite3.connect(str(db_path))
    conn.enable_load_extension(True)
    conn.load_extension(str(extension))
    conn.enable_load_extension(False)
    conn.execute("pragma foreign_keys = on")
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
            "aws_glue_jobs": AwsGlueJobClient(self.conn),
            "aws_glue_tables": AwsGlueTableClient(self.conn),
            "aws_lambda_functions": AwsLambdaFunctionClient(self.conn),
            "aws_s3_objects": AwsS3ObjectClient(self.conn),
            "catalog_databases": CatalogDatabaseClient(self.conn),
            "catalog_jobs": CatalogJobClient(self.conn),
            "catalog_job_artifacts": CatalogJobArtifactClient(self.conn),
            "catalog_job_extractions": CatalogJobExtractionClient(self.conn),
            "catalog_job_table_edges": CatalogJobTableEdgeClient(self.conn),
            "catalog_table_join_edges": CatalogTableJoinEdgeClient(self.conn),
            "catalog_tables": CatalogTableClient(self.conn),
        }

    def migrate(self) -> list[str]:
        """
        Diff the database against every registered model and apply the changes.

        Args:
            None

        Returns:
            The ids of the migrations that were applied; empty if up to date
        """
        return Migrator(self.conn, []).up(models=ALL_MODELS)

    def transaction(self) -> AbstractContextManager[Connection]:
        """
        Open a sustained transaction block.

        Usage:
            db = DB(...)
            with db.transaction:
                ...

        Args:
            None

        Returns:
            The sustained transaction
        """
        return Model.transaction()
