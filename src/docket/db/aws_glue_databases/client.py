import sqlite3
from typing import cast

from ...config.logger import get_logger
from .models import AwsGlueDatabaseModel, AwsGlueDatabaseSelect

logger = get_logger("aws_glue_databases")


class AwsGlueDatabaseClient:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get_databases(self) -> list[AwsGlueDatabaseSelect]:
        """
        Fetch all Glue databases from AWS

        Returns:
            list[AwsGlueDatabaseSelect]
        """
        rows = (
            AwsGlueDatabaseModel.query()
            .select(*AwsGlueDatabaseModel.tableColumns)
            .to_dicts()
        )
        logger.info("fetched %s database(s) from aws_glue_catalog_database", len(rows))
        return cast(list[AwsGlueDatabaseSelect], rows)
