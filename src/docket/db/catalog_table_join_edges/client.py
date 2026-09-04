import sqlite3
from collections.abc import Sequence
from typing import cast
from uuid import uuid4

from sustained import QueryBuilder

from ...config.logger import get_logger
from .models import (
    CatalogTableJoinEdgeInsert,
    CatalogTableJoinEdgeModel,
    CatalogTableJoinEdgeSelect,
)

logger = get_logger("catalog_table_join_edges")


class CatalogTableJoinEdgeClient:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def delete_edges(self) -> None:
        """
        Delete all join edge records.

        Args:
            None

        Returns:
            None
        """
        count = (
            CatalogTableJoinEdgeModel.query()
            .delete()
            .where(QueryBuilder.raw("1"), "=", 1)
            .run()
        )
        logger.info("deleted %s edge(s) from catalog_table_join_edges", count)

    def delete_job_edges(self, job_ids: Sequence[str]) -> None:
        """
        Delete the join edge records extracted from the given jobs.

        Args:
            job_ids: PKs of the jobs to delete the job edges for

        Returns:
            None

        Raises:
            ValueError: if job_ids is empty
        """
        if not job_ids:
            raise ValueError("job_ids must not be empty")
        count = (
            CatalogTableJoinEdgeModel.query()
            .delete()
            .whereIn("job_id", list(job_ids))
            .run()
        )
        logger.info("deleted %s edge(s) from catalog_table_join_edges", count)

    def insert_edges(
        self, records: Sequence[CatalogTableJoinEdgeInsert]
    ) -> list[CatalogTableJoinEdgeSelect]:
        """
        Insert join edge records.

        Args:
            records: catalog table join edges

        Returns:
            inserted catalog table join edges

        Raises:
            ValueError: if records is empty
        """
        if not records:
            raise ValueError("records must not be empty")
        rows = [{"id": str(uuid4()), **record} for record in records]
        result = CatalogTableJoinEdgeModel.query().insert(rows).returning().run()
        logger.info("inserted %s edge(s) into catalog_table_join_edges", len(result))
        return cast(list[CatalogTableJoinEdgeSelect], result)

    def get_edges(self) -> list[CatalogTableJoinEdgeSelect]:
        """
        Get all join edge records, ordered by left table then right table.

        Args:
            None

        Returns:
            all catalog table join edges
        """
        result = (
            CatalogTableJoinEdgeModel.query()
            .orderBy("left_table")
            .orderBy("right_table")
            .to_dicts()
        )
        logger.info("retrieved %s edge(s) from catalog_table_join_edges", len(result))
        return cast(list[CatalogTableJoinEdgeSelect], result)

    def get_table_edges(self, table_name: str) -> list[CatalogTableJoinEdgeSelect]:
        """
        Get the join edge records where the given table appears on either side.

        Args:
            table_name: the table name to filter on

        Returns:
            list of catalog table join edges
        """
        result = (
            CatalogTableJoinEdgeModel.query()
            .where("left_table", "=", table_name)
            .orWhere("right_table", "=", table_name)
            .orderBy("left_table")
            .orderBy("right_table")
            .to_dicts()
        )
        logger.info("retrieved %s edge(s) from catalog_table_join_edges", len(result))
        return cast(list[CatalogTableJoinEdgeSelect], result)
