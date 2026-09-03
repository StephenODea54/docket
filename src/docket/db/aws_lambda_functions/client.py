import sqlite3
from typing import cast

from ...config.logger import get_logger
from .models import AwsLambdaFunctionModel, AwsLambdaFunctionSelect

logger = get_logger("aws_lambda_functions")


class AwsLambdaFunctionClient:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

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
