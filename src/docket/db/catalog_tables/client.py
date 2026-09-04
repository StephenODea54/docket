import sqlite3
from collections.abc import Sequence
from typing import cast
from uuid import uuid4

from sustained import QueryBuilder

from ...config.logger import get_logger
from ..aws_glue_tables import AwsGlueTableSelect
from .models import CatalogTableModel, CatalogTableSelect

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
        self, records: Sequence[AwsGlueTableSelect]
    ) -> list[CatalogTableSelect]:
        """
        Insert glue table records.

        Args:
            records: Glue tables as read from AWS

        Returns:
            The inserted rows

        Raises:
            ValueError: if records is empty
            sqlite3.IntegrityError: if a database_name has no catalog_databases row
        """
        if not records:
            raise ValueError("records must not be empty")
        rows = [{"id": str(uuid4()), **record} for record in records]
        result = CatalogTableModel.query().insert(rows).returning().run()
        logger.info("inserted %s table(s) into catalog_tables", len(result))
        return cast(list[CatalogTableSelect], result)

    def get_tables(self) -> list[CatalogTableSelect]:
        """
        Get all glue table records, ordered by name.

        Returns:
            list[CatalogTableSelect]
        """
        result = CatalogTableModel.query().orderBy("name").to_dicts()
        logger.info("retrieved %s table(s) from catalog_tables", len(result))
        return cast(list[CatalogTableSelect], result)

    def get_tables_by_database(self, database_name: str) -> list[CatalogTableSelect]:
        """
        Get the glue table records for one database, ordered by name.

        Args:
            database_name: the catalog database to filter on

        Returns:
            list[CatalogTableSelect]
        """
        result = (
            CatalogTableModel.query()
            .where("database_name", "=", database_name)
            .orderBy("name")
            .to_dicts()
        )
        logger.info("retrieved %s table(s) from catalog_tables", len(result))
        return cast(list[CatalogTableSelect], result)

    def get_table(self, database_name: str, name: str) -> CatalogTableSelect | None:
        """
        Get one glue table record by database and table name.

        Args:
            database_name: the catalog database the table belongs to
            name: the table name

        Returns:
            The table record, or None when it does not exist
        """
        result = (
            CatalogTableModel.query()
            .where("database_name", "=", database_name)
            .where("name", "=", name)
            .limit(1)
            .to_dicts()
        )
        logger.info("retrieved %s table(s) from catalog_tables", len(result))
        return cast(CatalogTableSelect, result[0]) if result else None

    def get_tables_by_names(self, names: Sequence[str]) -> list[CatalogTableSelect]:
        """
        Get the glue table records matching any of the given names.

        Args:
            names: the table names to filter on

        Returns:
            list[CatalogTableSelect]
        """
        if not names:
            return []
        result = (
            CatalogTableModel.query()
            .whereIn("name", list(names))
            .orderBy("name")
            .to_dicts()
        )
        logger.info("retrieved %s table(s) from catalog_tables", len(result))
        return cast(list[CatalogTableSelect], result)
