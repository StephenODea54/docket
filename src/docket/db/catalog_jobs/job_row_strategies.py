from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar, Generic, TypeVar

from sustained import Model

from ..aws_glue_jobs import AwsGlueJobModel, AwsGlueJobSelect
from ..aws_lambda_functions import AwsLambdaFunctionModel, AwsLambdaFunctionSelect
from ..utils import decode_column, serialize_columns
from .models import CatalogJobInsert

TRecord = TypeVar("TRecord", bound=Mapping[str, Any])


class JobRowStrategy(ABC, Generic[TRecord]):
    """Maps one AWS record shape to a catalog_jobs row."""

    type: ClassVar[str]
    model: ClassVar[type[Model]]
    attribute_columns: ClassVar[Sequence[str]]

    @abstractmethod
    def _get_runtime(self, record: TRecord) -> str | None:
        """
        Return the job's runtime identifier.

        Args:
            record: TRecord

        Returns:
            The artifact runtime, if it exists.
        """

    @abstractmethod
    def _get_last_modified(self, record: TRecord) -> str | None:
        """
        Return the source-side last modified timestamp.

        Args:
            record: TRecord

        Returns:
            Last modified date (str) of the artifact, if it exists.
        """

    def build_row(self, record: TRecord) -> CatalogJobInsert:
        """
        Build a catalog_jobs insert row from a source record.

        Args:
            record: TRecord

        Returns:
            Row used in catalog_job inserts.
        """
        return {
            "type": self.type,
            "name": record["name"],
            "description": record["description"],
            "role": record["role"],
            "runtime": self._get_runtime(record),
            "last_modified": self._get_last_modified(record),
            "attributes": serialize_columns(self.model, record, self.attribute_columns),
        }


class GlueJobStrategy(JobRowStrategy[AwsGlueJobSelect]):
    type: ClassVar[str] = "glue"
    model: ClassVar[type[Model]] = AwsGlueJobModel
    attribute_columns: ClassVar[Sequence[str]] = [
        "command",
        "default_arguments",
        "non_overridable_arguments",
        "connections",
        "glue_version",
        "execution_class",
        "worker_type",
        "number_of_workers",
        "max_capacity",
        "max_retries",
        "timeout",
        "tags",
    ]

    def _get_runtime(self, record: AwsGlueJobSelect) -> str | None:
        command = decode_column(self.model, record, "command") or {}
        return command.get("PythonVersion")

    def _get_last_modified(self, record: AwsGlueJobSelect) -> str | None:
        return record["last_modified_on"]


class LambdaFunctionStrategy(JobRowStrategy[AwsLambdaFunctionSelect]):
    type: ClassVar[str] = "lambda"
    model: ClassVar[type[Model]] = AwsLambdaFunctionModel
    attribute_columns: ClassVar[Sequence[str]] = [
        "handler",
        "code_sha_256",
        "code_size",
        "version",
        "package_type",
        "state",
        "memory_size",
        "timeout",
        "architectures",
        "environment_variables",
        "layers",
        "ephemeral_storage",
        "vpc_id",
        "vpc_security_group_ids",
        "vpc_subnet_ids",
        "tracing_config",
        "logging_config",
        "url_config",
        "tags",
    ]

    def _get_runtime(self, record: AwsLambdaFunctionSelect) -> str | None:
        return record["runtime"]

    def _get_last_modified(self, record: AwsLambdaFunctionSelect) -> str | None:
        return record["last_modified"]
