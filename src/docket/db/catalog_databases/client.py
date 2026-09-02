import sqlite3
from collections.abc import Sequence
from typing import cast
from uuid import uuid4

from sustained import QueryBuilder

from ...config.logger import get_logger
from ..aws_glue_databases import AwsGlueDatabaseSelect
from .models import CatalogDatabaseModel, CatalogDatabaseSelect

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

    def insert_databases(
        self, records: Sequence[AwsGlueDatabaseSelect]
    ) -> list[CatalogDatabaseSelect]:
        """
        Insert glue database records.

        Args:
            records: Glue databases rows

        Returns:
            The inserted rows

        Raises:
            ValueError: if records is empty
        """
        if not records:
            raise ValueError("records must not be empty")
        rows = [{"id": str(uuid4()), **record} for record in records]
        result = CatalogDatabaseModel.query().insert(rows).returning().run()
        logger.info("inserted %s database(s) into catalog_databases", len(result))
        return cast(list[CatalogDatabaseSelect], result)

    def get_databases(self) -> list[CatalogDatabaseSelect]:
        """
        Get all glue database records, ordered by name.

        Args:
            None

        Returns:
            list[CatalogDatabaseSelect]
        """
        result = CatalogDatabaseModel.query().orderBy("name").to_dicts()
        logger.info("retrieved %s database(s) from catalog_databases", len(result))
        return cast(list[CatalogDatabaseSelect], result)
