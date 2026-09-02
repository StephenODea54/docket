import sqlite3

from ...config.logger import get_logger
from .models import AwsGlueTableModel

logger = get_logger("aws_glue_tables")


class AwsGlueTableClient:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get_tables(self) -> list[AwsGlueTableModel]:
        """
        Fetch all Glue tables from AWS

        Returns:
            list[AwsGlueTableModel]
        """
        rows = (
            AwsGlueTableModel.query().select(*AwsGlueTableModel.tableColumns).run()
        )
        logger.info("fetched %s table(s) from aws_glue_catalog_table", len(rows))
        return rows
