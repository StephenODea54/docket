from __future__ import annotations

import os
import tempfile
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

from ..config.logger import get_logger

logger = get_logger("store")

_MISSING_CODES = {"404", "NoSuchKey", "NotFound"}


class CatalogStoreStrategy(ABC):
    type: ClassVar[str]

    def __init__(self, location: str) -> None:
        self.location = location

    @classmethod
    @abstractmethod
    def handles(cls, location: str) -> bool:
        """
        Whether this strategy knows how to store a catalog at location.

        Args:
            location: a local path or remote uri

        Returns:
            True when the strategy should be used for it
        """

    @property
    @abstractmethod
    def path(self) -> str:
        """The local sqlite file DB() should open once pulled."""

    @abstractmethod
    def pull(self) -> bool:
        """
        Bring the catalog to `path`.

        Args:
            None

        Returns:
            True when a catalog is now at `path`, False when none exists at
            the location yet
        """

    @abstractmethod
    def push(self) -> None:
        """
        Publish the local file at `path` back to `location`.

        Args:
            None

        Returns:
            None
        """

    def exists(self) -> bool:
        """
        Whether a local copy is present at `path`.

        Args:
            None

        Returns:
            True when the local sqlite file exists
        """
        return Path(self.path).exists()

    def last_modified(self) -> datetime | None:
        """
        When the catalog at `location` was last written.

        Args:
            None

        Returns:
            An aware UTC datetime, or None when no catalog exists there
        """
        if not self.exists():
            return None
        return datetime.fromtimestamp(os.path.getmtime(self.path), tz=UTC)

    def __repr__(self) -> str:
        """Return the strategy name and location, e.g. S3CatalogStore('s3://...')."""
        return f"{type(self).__name__}({self.location!r})"


class LocalCatalogStore(CatalogStoreStrategy):
    type: ClassVar[str] = "local"

    @classmethod
    def handles(cls, location: str) -> bool:
        """
        Claim every location; this is the fallback strategy.

        Args:
            location: a local path

        Returns:
            Always True
        """
        return True

    @property
    def path(self) -> str:
        """The location itself; the file is opened in place."""
        return self.location

    def pull(self) -> bool:
        """
        Nothing to download; reports whether the file exists.

        Args:
            None

        Returns:
            True when the file exists at `path`
        """
        return self.exists()

    def push(self) -> None:
        """
        No-op; the file is already where it lives.

        Args:
            None

        Returns:
            None
        """


def _cache_root() -> Path:
    """
    The directory local copies of remote catalogs live under.

    Prefers ~/.docket/cache; falls back to the system temp dir when home is
    not writable (e.g. inside AWS Lambda, where only /tmp is).

    Args:
        None

    Returns:
        The cache directory, created if needed
    """
    preferred = Path.home() / ".docket" / "cache"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        return preferred
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "docket" / "cache"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


class S3CatalogStore(CatalogStoreStrategy):
    """
    A catalog whose home is an s3://bucket/key object, cached on local disk.

    Tracks the ETag of the last object it pulled or pushed.
    """

    type: ClassVar[str] = "s3"

    def __init__(
        self,
        location: str,
        client: Any | None = None,
        cache_dir: str | Path | None = None,
    ) -> None:
        """
        Parse the uri and pick the cache path.

        Args:
            location: an s3://bucket/key uri
            client: a boto3 s3 client; created lazily when omitted
            cache_dir: where to keep the local copy; defaults to _cache_root()

        Raises:
            ValueError: if location is not an s3://bucket/key uri
        """
        parsed = urlparse(location)
        if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.strip("/"):
            raise ValueError(f"{location} is not an s3://bucket/key uri")
        super().__init__(location)
        self.bucket = parsed.netloc
        self.key = parsed.path.lstrip("/")
        root = Path(cache_dir) if cache_dir is not None else _cache_root()
        self._path = str(root / self.bucket / self.key)
        self._client = client
        self.etag: str | None = None

    @classmethod
    def handles(cls, location: str) -> bool:
        """
        Claim s3:// uris.

        Args:
            location: a local path or remote uri

        Returns:
            True when location starts with s3://
        """
        return location.startswith("s3://")

    @property
    def path(self) -> str:
        """The cached copy under the cache root: <root>/<bucket>/<key>."""
        return self._path

    @property
    def client(self) -> Any:
        """The boto3 s3 client, created on first use."""
        if self._client is None:
            self._client = boto3.client("s3")
        return self._client

    def _head(self) -> dict[str, Any] | None:
        """
        Fetch the remote object's metadata.

        Args:
            None

        Returns:
            The HeadObject response, or None when the object does not exist

        Raises:
            botocore.exceptions.ClientError: for any error other than a
                missing object (e.g. access denied)
        """
        try:
            return self.client.head_object(Bucket=self.bucket, Key=self.key)
        except ClientError as error:
            if error.response["Error"]["Code"] in _MISSING_CODES:
                return None
            raise

    def head(self) -> str | None:
        """
        Look up the remote object's ETag.

        Args:
            None

        Returns:
            The ETag, or None when the object does not exist
        """
        response = self._head()
        return response["ETag"] if response else None

    def last_modified(self) -> datetime | None:
        """
        When the remote object was last written.

        Args:
            None

        Returns:
            The object's LastModified as an aware UTC datetime, or None when
            it does not exist
        """
        response = self._head()
        if not response:
            return None
        return response["LastModified"].astimezone(UTC)

    def pull(self) -> bool:
        """
        Download the remote object over the cache path.

        Downloads to a sibling temp file and renames so readers never see a
        partial file. The cache directory is created either way so a cold
        `docket run` can create the sqlite file at `path`.

        Args:
            None

        Returns:
            True when downloaded, False when the object does not exist yet
        """
        target = Path(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        etag = self.head()
        if etag is None:
            logger.info("no catalog at %s", self.location)
            return False
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
            temp_path = Path(handle.name)
        try:
            self.client.download_file(self.bucket, self.key, str(temp_path))
            os.replace(temp_path, target)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
        self.etag = etag
        logger.info("pulled %s to %s", self.location, target)
        return True

    def push(self) -> None:
        """
        Upload the cached file to the remote object and record its new ETag.

        Args:
            None

        Returns:
            None
        """
        self.client.upload_file(self.path, self.bucket, self.key)
        self.etag = self.head()
        logger.info("pushed %s to %s", self.path, self.location)


STRATEGIES: list[type[CatalogStoreStrategy]] = [S3CatalogStore, LocalCatalogStore]


def catalog_store(location: str) -> CatalogStoreStrategy:
    """
    Pick the store for a location.

    Tries STRATEGIES in order; LocalCatalogStore handles anything the remote
    strategies do not claim.

    Args:
        location: a local path or remote uri, e.g. from DOCKET_DB_PATH

    Returns:
        The matching store, ready to pull
    """
    strategy = next(cls for cls in STRATEGIES if cls.handles(location))
    return strategy(location)
