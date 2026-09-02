from __future__ import annotations

import io
import zipfile

from .models import SourceFile

SOURCE_SUFFIXES = (".py", ".sql")
TEST_SUFFIXES = ("_test.py", "_test.sql")
TEST_FILENAMES = ("conftest.py",)
TEST_DIRECTORIES = ("test", "tests")
VENDOR_DIRECTORIES = ("site-packages",)
VENDOR_ROOTS = ("bin", "lib", "lib64", "venv", "python")
METADATA_SUFFIXES = (".dist-info", ".egg-info")
RECORD_SUFFIX = ".dist-info/RECORD"


def is_source_path(path: str) -> bool:
    """
    Return whether a path names a python or sql source file.

    Args:
        path: file path, s3 uri or zip member name

    Returns:
        True when the path ends in a supported source suffix
    """
    return path.endswith(SOURCE_SUFFIXES)


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """
    Split an s3 uri into its bucket name and key.

    Args:
        uri: uri in the form s3://bucket/key

    Returns:
        The bucket name and the key

    Raises:
        ValueError: if the uri is not an s3 uri or names no key
    """
    if not uri.startswith("s3://"):
        raise ValueError(f"not an s3 uri: {uri}")
    bucket_name, _, key = uri[len("s3://") :].partition("/")
    if not bucket_name or not key:
        raise ValueError(f"s3 uri is missing a bucket or key: {uri}")
    return bucket_name, key


def _get_dependency_paths(archive: zipfile.ZipFile) -> set[str]:
    """
    Return every member path claimed by an installed distribution's RECORD.

    Args:
        archive: open zip archive

    Returns:
        Member paths that belong to installed dependencies
    """
    paths: set[str] = set()
    for name in archive.namelist():
        if not name.endswith(RECORD_SUFFIX):
            continue
        root = f"{name.rsplit('/', 2)[0]}/" if name.count("/") > 1 else ""
        record = archive.read(name).decode("utf-8", "replace")
        for line in record.splitlines():
            entry = line.split(",", 1)[0].strip()
            if entry:
                paths.add(f"{root}{entry}")
    return paths


def _is_authored_path(path: str) -> bool:
    """
    Return whether a zip member looks like a file the developer wrote.

    Args:
        path: zip member name

    Returns:
        False for caches, hidden files, packaging metadata, vendored
        dependency trees and tests
    """
    *directories, filename = path.split("/")
    if any(part.startswith(".") or part == "__pycache__" for part in path.split("/")):
        return False
    if any(part.endswith(METADATA_SUFFIXES) for part in directories):
        return False
    if any(part in VENDOR_DIRECTORIES for part in directories):
        return False
    if directories and directories[0] in VENDOR_ROOTS:
        return False
    if any(part in TEST_DIRECTORIES for part in directories):
        return False
    return not (
        filename in TEST_FILENAMES
        or filename.startswith("test_")
        or filename.endswith(TEST_SUFFIXES)
    )


def extract_zip_sources(data: bytes) -> list[SourceFile]:
    """
    Return the developer written python and sql files inside a zip archive.

    Dependencies, packaging metadata, caches and tests are dropped.

    Args:
        data: raw bytes of the zip archive

    Returns:
        The source files, ordered by path

    Raises:
        zipfile.BadZipFile: if data is not a readable zip archive
    """
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        dependencies = _get_dependency_paths(archive)
        sources = [
            SourceFile(
                path=name,
                contents=archive.read(name).decode("utf-8", "replace"),
            )
            for name in archive.namelist()
            if not name.endswith("/")
            and name not in dependencies
            and is_source_path(name)
            and _is_authored_path(name)
        ]
    return sorted(sources, key=lambda source: source["path"])
