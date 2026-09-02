from typing import ClassVar, TypedDict

from sustained import Model
from sustained.schema import (
    ColumnDef,
    Integer,
    Json,
    String,
    Timestamp,
)


class AwsLambdaFunctionSelect(TypedDict):
    name: str | None
    arn: str | None
    description: str | None
    role: str | None
    runtime: str | None
    handler: str | None
    code_sha_256: str | None
    code_size: int | None
    last_modified: str | None
    version: str | None
    package_type: str | None
    state: str | None
    last_update_status: str | None
    revision_id: str | None
    memory_size: int | None
    timeout: str | None
    reserved_concurrent_executions: int | None
    kms_key_arn: str | None
    dead_letter_config_target_arn: str | None
    vpc_id: str | None
    architectures: str | None
    code: str | None
    environment_variables: str | None
    ephemeral_storage: str | None
    layers: str | None
    logging_config: str | None
    snap_start: str | None
    tracing_config: str | None
    url_config: str | None
    vpc_security_group_ids: str | None
    vpc_subnet_ids: str | None
    tags: str | None


class AwsLambdaFunctionModel(Model):
    tableName: ClassVar[str] = "aws_lambda_function"
    tableColumns: ClassVar[dict[str, ColumnDef]] = {
        "name": String(255),
        "arn": String(2048),
        "description": String(2048),
        "role": String(2048),
        "runtime": String(64),
        "handler": String(255),
        "code_sha_256": String(64),
        "code_size": Integer(),
        "last_modified": Timestamp(),
        "version": String(64),
        "package_type": String(32),
        "state": String(64),
        "last_update_status": String(64),
        "revision_id": String(64),
        "memory_size": Integer(),
        "timeout": String(64),
        "reserved_concurrent_executions": Integer(),
        "kms_key_arn": String(2048),
        "dead_letter_config_target_arn": String(2048),
        "vpc_id": String(255),
        "architectures": Json(),
        "code": Json(),
        "environment_variables": Json(),
        "ephemeral_storage": Json(),
        "layers": Json(),
        "logging_config": Json(),
        "snap_start": Json(),
        "tracing_config": Json(),
        "url_config": Json(),
        "vpc_security_group_ids": Json(),
        "vpc_subnet_ids": Json(),
        "tags": Json(),
    }
