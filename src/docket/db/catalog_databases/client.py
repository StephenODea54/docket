import sqlite3
from collections.abc import Sequence
from uuid import uuid4

from sustained import QueryBuilder

from ...config.logger import get_logger
from ..aws_glue_databases import AwsGlueDatabaseModel
from .models import CatalogDatabaseModel

logger = get_logger("catalog_databases")


class CatalogDatabaseClient:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def delete_databases(self) -> None:
        """
        Deletes all glue database records.

        Args:
            None

        Returns:
            None
        """
        count = (
            CatalogDatabaseModel.query()
            .delete()
            .where(QueryBuilder.raw("1"), "=", 1)
            .run()
        )
        logger.info("deleted %s database(s) from catalog_databases", count)

    def insert_databases(self, records: Sequence[AwsGlueDatabaseModel]) -> int:
        """
        Insert glue database records.

        Args:
            records: Glue databases as read from AWS

        Returns:
            Number of rows inserted

        Raises:
            ValueError: if records is empty
        """
        if not records:
            raise ValueError("records must not be empty")
        columns = AwsGlueDatabaseModel.tableColumns
        rows = [
            {
                "id": str(uuid4()),
                **{column: getattr(record, column) for column in columns},
            }
            for record in records
        ]
        count = CatalogDatabaseModel.query().insert(rows).run()
        logger.info("inserted %s database(s) into catalog_databases", count)
        return count

    def get_databases(self) -> list[CatalogDatabaseModel]:
        """
        Get all glue database records, ordered by name.

        Returns:
            list[CatalogDatabaseModel]
        """
        result = CatalogDatabaseModel.query().orderBy("name").run()
        logger.info("retrieved %s database(s) from catalog_databases", len(result))
        return result
