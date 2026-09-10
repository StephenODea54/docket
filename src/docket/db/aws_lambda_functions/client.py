import sqlite3
from typing import cast

import boto3

from ...config.logger import get_logger
from .models import AwsLambdaFunctionModel, AwsLambdaFunctionSelect

logger = get_logger("aws_lambda_functions")


class AwsLambdaFunctionClient:
    """
    Reads Lambda functions from the steampipe virtual table.

    Code download urls come straight from boto3: steampipe's `code` column
    stopped carrying `Location` in plugin v1.32.
    """

    def __init__(self, conn: sqlite3.Connection, region: str | None = None) -> None:
        self.conn = conn
        self.lambda_client = boto3.Session().client("lambda", region_name=region)

    def get_functions(self) -> list[AwsLambdaFunctionSelect]:
        """
        Fetch all Lambda functions from AWS

        Args:
            None

        Returns:
            list[AwsLambdaFunctionSelect]
        """
        rows = (
            AwsLambdaFunctionModel.query()
            .select(*AwsLambdaFunctionModel.tableColumns)
            .to_dicts()
        )
        logger.info("fetched %s function(s) from aws_lambda_function", len(rows))
        return cast(list[AwsLambdaFunctionSelect], rows)

    def get_function(self, name: str) -> AwsLambdaFunctionSelect | None:
        """
        Fetch one Lambda function from AWS by name.

        Args:
            name: the function name

        Returns:
            The function row, or None when the name does not exist
        """
        rows = (
            AwsLambdaFunctionModel.query()
            .select(*AwsLambdaFunctionModel.tableColumns)
            .where("name", "=", name)
            .to_dicts()
        )
        logger.info("fetched %s function(s) from aws_lambda_function", len(rows))
        if not rows:
            return None
        return cast(AwsLambdaFunctionSelect, rows[0])

    def get_code_location(self, name: str) -> str | None:
        """
        Fetch a function's presigned code download url through GetFunction.

        Args:
            name: the function name

        Returns:
            The url, valid for about ten minutes, or None when the function
            does not exist or has no downloadable package
        """
        try:
            response = self.lambda_client.get_function(FunctionName=name)
        except self.lambda_client.exceptions.ResourceNotFoundException:
            logger.warning("function %s does not exist", name)
            return None
        return response.get("Code", {}).get("Location") or None
