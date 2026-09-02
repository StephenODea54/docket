import sqlite3
from typing import cast

from ...config.logger import get_logger
from .models import AwsGlueTableModel, AwsGlueTableSelect

logger = get_logger("aws_glue_tables")


class AwsGlueTableClient:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get_tables(self) -> list[AwsGlueTableSelect]:
        """
        Fetch all Glue tables from AWS

        Args:
            None

        Returns:
            list[AwsGlueTableSelect]
        """
        rows = (
            AwsGlueTableModel.query().select(*AwsGlueTableModel.tableColumns).to_dicts()
        )
        logger.info("fetched %s table(s) from aws_glue_catalog_table", len(rows))
        return cast(list[AwsGlueTableSelect], rows)
