from typing import ClassVar, TypedDict

from sustained import Model
from sustained.schema import (
    ColumnDef,
    Float,
    Integer,
    Json,
    String,
    Timestamp,
)


class AwsGlueJobSelect(TypedDict):
    name: str | None
    arn: str | None
    description: str | None
    role: str | None
    created_on: str | None
    last_modified_on: str | None
    glue_version: str | None
    execution_class: str | None
    worker_type: str | None
    number_of_workers: int | None
    max_capacity: float | None
    max_retries: int | None
    timeout: int | None
    log_uri: str | None
    security_configuration: str | None
    command: str | None
    connections: str | None
    default_arguments: str | None
    non_overridable_arguments: str | None
    execution_property: str | None
    notification_property: str | None
    job_bookmark: str | None
    source_control_details: str | None
    tags: str | None


class AwsGlueJobModel(Model):
    tableName: ClassVar[str] = "aws_glue_job"
    tableColumns: ClassVar[dict[str, ColumnDef]] = {
        "name": String(255),
        "arn": String(2048),
        "description": String(2048),
        "role": String(2048),
        "created_on": Timestamp(),
        "last_modified_on": Timestamp(),
        "glue_version": String(64),
        "execution_class": String(64),
        "worker_type": String(64),
        "number_of_workers": Integer(),
        "max_capacity": Float(),
        "max_retries": Integer(),
        "timeout": Integer(),
        "log_uri": String(2048),
        "security_configuration": String(255),
        "command": Json(),
        "connections": Json(),
        "default_arguments": Json(),
        "non_overridable_arguments": Json(),
        "execution_property": Json(),
        "notification_property": Json(),
        "job_bookmark": Json(),
        "source_control_details": Json(),
        "tags": Json(),
    }
