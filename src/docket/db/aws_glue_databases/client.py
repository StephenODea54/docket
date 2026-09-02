import sqlite3

from ...config.logger import get_logger
from .models import AwsGlueDatabaseModel

logger = get_logger("aws_glue_databases")


class AwsGlueDatabaseClient:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get_databases(self) -> list[AwsGlueDatabaseModel]:
        """
        Fetch all Glue databases from AWS

        Returns:
            list[AwsGlueDatabaseModel]
        """
        rows = (
            AwsGlueDatabaseModel.query()
            .select(*AwsGlueDatabaseModel.tableColumns)
            .run()
        )
        logger.info("fetched %s database(s) from aws_glue_catalog_database", len(rows))
        return rows
