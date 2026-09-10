from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from docket.store import (
    STRATEGIES,
    CatalogStoreStrategy,
    LocalCatalogStore,
    S3CatalogStore,
    catalog_store,
)
from docket.store import catalog_store_strategies as strategies


class FakeS3:
    def __init__(self, body=None, etag='"v1"'):
        self.body = body
        self.etag = etag
        self.uploads = []
        self.heads = 0

    def head_object(self, Bucket, Key):
        self.heads += 1
        if self.body is None:
            raise ClientError(
                {"Error": {"Code": "404", "Message": "gone"}}, "HeadObject"
            )
        return {"ETag": self.etag}

    def download_file(self, Bucket, Key, Filename):
        Path(Filename).write_bytes(self.body)

    def upload_file(self, Filename, Bucket, Key):
        self.uploads.append((Filename, Bucket, Key))
        self.body = Path(Filename).read_bytes()
        self.etag = '"uploaded"'


def test_every_strategy_declares_a_type():
    assert [cls.type for cls in STRATEGIES] == ["s3", "local"]
    assert all(issubclass(cls, CatalogStoreStrategy) for cls in STRATEGIES)


def test_catalog_store_picks_s3_for_s3_uris(tmp_path, monkeypatch):
    monkeypatch.setattr(strategies, "_cache_root", lambda: tmp_path)
    store = catalog_store("s3://bucket/docket.db")
    assert isinstance(store, S3CatalogStore)
    assert store.location == "s3://bucket/docket.db"


def test_catalog_store_picks_local_otherwise(tmp_path):
    store = catalog_store(str(tmp_path / "docket.db"))
    assert isinstance(store, LocalCatalogStore)
    assert store.path == str(tmp_path / "docket.db")
    assert store.location == store.path


def test_local_pull_reports_existence(tmp_path):
    target = tmp_path / "docket.db"
    store = LocalCatalogStore(str(target))

    assert store.pull() is False
    assert store.exists() is False
    target.touch()
    assert store.pull() is True
    assert store.exists() is True
    assert repr(store) == f"LocalCatalogStore({str(target)!r})"


def test_local_push_is_a_noop(tmp_path):
    target = tmp_path / "docket.db"
    target.write_bytes(b"sqlite")

    LocalCatalogStore(str(target)).push()

    assert target.read_bytes() == b"sqlite"


def test_s3_rejects_non_s3_uri(tmp_path):
    with pytest.raises(ValueError):
        S3CatalogStore("https://bucket/key", cache_dir=tmp_path)
    with pytest.raises(ValueError):
        S3CatalogStore("s3://bucket", cache_dir=tmp_path)


def test_s3_parses_bucket_and_key_into_cache_path(tmp_path):
    store = S3CatalogStore(
        "s3://bucket/docket/docket.db", client=FakeS3(), cache_dir=tmp_path
    )
    assert store.bucket == "bucket"
    assert store.key == "docket/docket.db"
    assert store.path == str(tmp_path / "bucket" / "docket" / "docket.db")


def test_s3_cache_root_falls_back_to_tempdir_when_home_unwritable(
    tmp_path, monkeypatch
):
    blocker = tmp_path / "home"
    blocker.write_text("not a directory")
    monkeypatch.setattr(strategies.Path, "home", classmethod(lambda cls: blocker))
    monkeypatch.setattr(
        strategies.tempfile, "gettempdir", lambda: str(tmp_path / "tmp")
    )

    assert strategies._cache_root() == tmp_path / "tmp" / "docket" / "cache"


def test_s3_pull_writes_cache_file_and_records_etag(tmp_path):
    client = FakeS3(body=b"sqlite")
    store = S3CatalogStore(
        "s3://bucket/nested/docket.db", client=client, cache_dir=tmp_path
    )

    assert store.pull() is True
    target = Path(store.path)
    assert target.read_bytes() == b"sqlite"
    assert store.etag == '"v1"'
    assert list(target.parent.iterdir()) == [target]


def test_s3_pull_missing_object_returns_false(tmp_path):
    store = S3CatalogStore("s3://bucket/docket.db", client=FakeS3(), cache_dir=tmp_path)

    assert store.pull() is False
    assert not Path(store.path).exists()
    assert Path(store.path).parent.is_dir()
    assert store.etag is None


def test_s3_head_reraises_other_errors(tmp_path):
    class Denied(FakeS3):
        def head_object(self, Bucket, Key):
            raise ClientError(
                {"Error": {"Code": "403", "Message": "denied"}}, "HeadObject"
            )

    store = S3CatalogStore("s3://bucket/docket.db", client=Denied(), cache_dir=tmp_path)
    with pytest.raises(ClientError):
        store.head()


def test_s3_push_uploads_cache_file_and_tracks_new_etag(tmp_path):
    client = FakeS3(body=b"old")
    store = S3CatalogStore("s3://bucket/docket.db", client=client, cache_dir=tmp_path)
    Path(store.path).parent.mkdir(parents=True)
    Path(store.path).write_bytes(b"new")

    store.push()

    assert client.uploads == [(store.path, "bucket", "docket.db")]
    assert client.body == b"new"
    assert store.etag == '"uploaded"'
