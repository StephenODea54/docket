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
