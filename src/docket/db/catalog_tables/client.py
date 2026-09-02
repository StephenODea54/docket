import sqlite3
from collections.abc import Mapping, Sequence
from uuid import uuid4

from sustained import QueryBuilder

from ...config.logger import get_logger
from ..aws_glue_tables import AwsGlueTableModel
from .models import CatalogTableModel

logger = get_logger("catalog_tables")


class CatalogTableClient:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def delete_tables(self) -> None:
        """
        Deletes all glue table records.

        Args:
            None

        Returns:
            None
        """
        count = (
            CatalogTableModel.query()
            .delete()
            .where(QueryBuilder.raw("1"), "=", 1)
            .run()
        )
        logger.info("deleted %s table(s) from catalog_tables", count)

    def insert_tables(
        self,
        records: Sequence[AwsGlueTableModel],
        database_ids: Mapping[str, str],
    ) -> int:
        """
        Insert glue table records

        Args:
            records: Glue tables as read from AWS
            database_ids: Map of catalog database name to catalog_databases id

        Returns:
            Number of rows inserted

        Raises:
            ValueError: if records is empty or a database_name has no id
        """
        if not records:
            raise ValueError("records must not be empty")
        columns = [
            column
            for column in AwsGlueTableModel.tableColumns
            if column != "database_name"
        ]
        rows = []
        for record in records:
            database_name = record.database_name
            if database_name not in database_ids:
                raise ValueError(f"unknown database_name: {database_name}")
            rows.append(
                {
                    "id": str(uuid4()),
                    "database_id": database_ids[database_name],
                    **{column: getattr(record, column) for column in columns},
                }
            )
        count = CatalogTableModel.query().insert(rows).run()
        logger.info("inserted %s table(s) into catalog_tables", count)
        return count

    def get_tables(self) -> list[CatalogTableModel]:
        """
        Get all glue table records, ordered by name.

        Returns:
            list[CatalogTableModel]
        """
        result = CatalogTableModel.query().orderBy("name").run()
        logger.info("retrieved %s table(s) from catalog_tables", len(result))
        return result
