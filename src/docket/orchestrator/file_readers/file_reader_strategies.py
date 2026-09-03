from __future__ import annotations

import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, ClassVar, Generic, TypeVar

from ...config.logger import get_logger
from ...db.aws_glue_jobs import AwsGlueJobModel, AwsGlueJobSelect
from ...db.aws_lambda_functions import AwsLambdaFunctionModel, AwsLambdaFunctionSelect
from ...db.aws_s3_objects import AwsS3ObjectClient
from ...db.utils import decode_column
from .filters import extract_zip_sources, is_source_path, parse_s3_uri
from .models import SourceFile

logger = get_logger("file_readers")

DOWNLOAD_TIMEOUT = 60
EXTRA_PY_FILES_ARGUMENT = "--extra-py-files"
SCRIPT_LOCATION_KEY = "ScriptLocation"
ZIP_PACKAGE_TYPE = "Zip"

TRecord = TypeVar("TRecord", bound=Mapping[str, Any])


class FileReaderStrategy(ABC, Generic[TRecord]):
    type: ClassVar[str]

    @abstractmethod
    def get_source_files(self, record: TRecord) -> list[SourceFile]:
        """
        Read the source files a record runs. Only .py and .sql files
        are currently supported.

        Args:
            record: TRecord

        Returns:
            The record's source files, ordered by path
        """


class GlueScriptStrategy(FileReaderStrategy[AwsGlueJobSelect]):
    type: ClassVar[str] = "glue"

    def __init__(self, aws_s3_objects: AwsS3ObjectClient) -> None:
        self.aws_s3_objects = aws_s3_objects

    def get_uris(self, record: AwsGlueJobSelect) -> list[str]:
        """
        Return the s3 uris a glue job runs: its script plus any extra py files.

        Args:
            record: glue job as read from AWS

        Returns:
            The job's artifact uris, in script-then-extras order
        """
        command = decode_column(AwsGlueJobModel, record, "command")
        arguments = decode_column(AwsGlueJobModel, record, "default_arguments")
        uris = [command.get(SCRIPT_LOCATION_KEY) if isinstance(command, dict) else None]
        if isinstance(arguments, dict):
            uris.extend((arguments.get(EXTRA_PY_FILES_ARGUMENT) or "").split(","))
        return [uri.strip() for uri in uris if uri and uri.strip()]

    def get_source_files(self, record: AwsGlueJobSelect) -> list[SourceFile]:
        sources = []
        for uri in self.get_uris(record):
            if not is_source_path(uri):
                logger.info("skipping %s, not a python or sql file", uri)
                continue
            bucket_name, key = parse_s3_uri(uri)
            row = self.aws_s3_objects.get_object(bucket_name, key)
            if row is None or row["body"] is None:
                logger.warning("no body read for %s", uri)
                continue
            sources.append(SourceFile(path=uri, contents=row["body"]))
        logger.info("read %s source file(s) from %s", len(sources), record["name"])
        return sources


class LambdaPackageStrategy(FileReaderStrategy[AwsLambdaFunctionSelect]):
    type: ClassVar[str] = "lambda"

    def get_source_files(self, record: AwsLambdaFunctionSelect) -> list[SourceFile]:
        if record["package_type"] != ZIP_PACKAGE_TYPE:
            logger.info(
                "skipping %s, package type is %s",
                record["name"],
                record["package_type"],
            )
            return []
        code = decode_column(AwsLambdaFunctionModel, record, "code")
        location = code.get("Location") if isinstance(code, dict) else None
        if not location:
            logger.warning("function %s has no code location", record["name"])
            return []
        try:
            with urllib.request.urlopen(
                location, timeout=DOWNLOAD_TIMEOUT
            ) as response:
                data = response.read()
        except (urllib.error.URLError, TimeoutError) as error:
            logger.warning("failed to download %s: %s", record["name"], error)
            return []
        sources = extract_zip_sources(data)
        logger.info("read %s source file(s) from %s", len(sources), record["name"])
        return sources
