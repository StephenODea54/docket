import sqlite3
from collections.abc import Sequence
from typing import cast
from uuid import uuid4

from sustained import QueryBuilder

from ...config.logger import get_logger
from .models import (
    CatalogJobTableEdgeInsert,
    CatalogJobTableEdgeModel,
    CatalogJobTableEdgeSelect,
)

logger = get_logger("catalog_job_table_edges")


class CatalogJobTableEdgeClient:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def delete_edges(self) -> None:
        """
        Delete all job table edge records.

        Args:
            None

        Returns:
            None
        """
        count = (
            CatalogJobTableEdgeModel.query()
            .delete()
            .where(QueryBuilder.raw("1"), "=", 1)
            .run()
        )
        logger.info("deleted %s edge(s) from catalog_job_table_edges", count)

    def delete_job_edges(self, job_ids: Sequence[str]) -> None:
        """
        Delete the edge records for the given jobs.

        Args:
            job_ids: PKs of the job records to delete the edges for

        Returns:
            None

        Raises:
            ValueError: if job_ids is empty
        """
        if not job_ids:
            raise ValueError("job_ids must not be empty")
        count = (
            CatalogJobTableEdgeModel.query()
            .delete()
            .whereIn("job_id", list(job_ids))
            .run()
        )
        logger.info("deleted %s edge(s) from catalog_job_table_edges", count)

    def insert_edges(
        self, records: Sequence[CatalogJobTableEdgeInsert]
    ) -> list[CatalogJobTableEdgeSelect]:
        """
        Insert job table edge records.

        Args:
            records: catalog job table edge records

        Returns:
            list of the inserted catalog job table edge records

        Raises:
            ValueError: if records is empty
        """
        if not records:
            raise ValueError("records must not be empty")
        rows = [{"id": str(uuid4()), **record} for record in records]
        result = CatalogJobTableEdgeModel.query().insert(rows).returning().run()
        logger.info("inserted %s edge(s) into catalog_job_table_edges", len(result))
        return cast(list[CatalogJobTableEdgeSelect], result)

    def get_edges(self) -> list[CatalogJobTableEdgeSelect]:
        """
        Get all job table edge records, ordered by job id then table name.

        Args:
            None

        Returns:
            list of catalog job table edges
        """
        result = (
            CatalogJobTableEdgeModel.query()
            .orderBy("job_id")
            .orderBy("table_name")
            .to_dicts()
        )
        logger.info("retrieved %s edge(s) from catalog_job_table_edges", len(result))
        return cast(list[CatalogJobTableEdgeSelect], result)
