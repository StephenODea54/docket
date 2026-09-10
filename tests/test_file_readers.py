import io
import zipfile

from docket.orchestrator.file_readers.file_reader_strategies import (
    LambdaPackageStrategy,
)


class FakeLambdaClient:
    def __init__(self, locations):
        self.locations = list(locations)
        self.requested = []

    def get_code_location(self, name):
        self.requested.append(name)
        return self.locations.pop(0) if self.locations else None


def make_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, body in files.items():
            archive.writestr(path, body)
    return buffer.getvalue()


def make_record(code=None):
    return {"name": "handler-fn", "package_type": "Zip", "code": code}


def fake_downloads(monkeypatch, responses):
    calls = []

    def download(self, location):
        calls.append(location)
        return responses.pop(0)

    monkeypatch.setattr(LambdaPackageStrategy, "_download", download)
    return calls


def test_uses_location_from_record_when_present(monkeypatch):
    client = FakeLambdaClient([])
    calls = fake_downloads(monkeypatch, [make_zip({"app.py": "print(1)"})])
    record = make_record('{"Location": "https://record-url"}')

    sources = LambdaPackageStrategy(client).get_source_files(record)

    assert calls == ["https://record-url"]
    assert client.requested == []
    assert [source["path"] for source in sources] == ["app.py"]


def test_falls_back_to_get_function_when_record_lacks_location(monkeypatch):
    client = FakeLambdaClient(["https://fresh-url"])
    calls = fake_downloads(monkeypatch, [make_zip({"app.py": "print(1)"})])
    record = make_record('{"RepositoryType": "S3"}')

    sources = LambdaPackageStrategy(client).get_source_files(record)

    assert client.requested == ["handler-fn"]
    assert calls == ["https://fresh-url"]
    assert len(sources) == 1


def test_refreshes_location_after_failed_download(monkeypatch):
    client = FakeLambdaClient(["https://second-url"])
    calls = fake_downloads(monkeypatch, [None, make_zip({"app.py": "x = 1"})])
    record = make_record('{"Location": "https://expired-url"}')

    sources = LambdaPackageStrategy(client).get_source_files(record)

    assert calls == ["https://expired-url", "https://second-url"]
    assert len(sources) == 1


def test_gives_up_without_any_location(monkeypatch):
    client = FakeLambdaClient([None])
    calls = fake_downloads(monkeypatch, [])
    record = make_record('{"RepositoryType": "S3"}')

    assert LambdaPackageStrategy(client).get_source_files(record) == []
    assert calls == []


def test_skips_image_packages(monkeypatch):
    calls = fake_downloads(monkeypatch, [])
    record = {"name": "img-fn", "package_type": "Image", "code": None}

    assert LambdaPackageStrategy(FakeLambdaClient([])).get_source_files(record) == []
    assert calls == []
