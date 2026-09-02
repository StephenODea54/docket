import sqlite3
from collections.abc import Sequence
from typing import cast
from uuid import uuid4

from sustained import QueryBuilder

from ...config.logger import get_logger
from .models import (
    CatalogJobExtractionInsert,
    CatalogJobExtractionModel,
    CatalogJobExtractionSelect,
)

logger = get_logger("catalog_job_extractions")


class CatalogJobExtractionClient:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def delete_extractions(self) -> None:
        """
        Delete all extraction records.

        Args:
            None

        Returns:
            None
        """
        count = (
            CatalogJobExtractionModel.query()
            .delete()
            .where(QueryBuilder.raw("1"), "=", 1)
            .run()
        )
        logger.info("deleted %s extraction(s) from catalog_job_extractions", count)

    def delete_extractions_by_jobs(self, job_ids: Sequence[str]) -> None:
        """
        Delete the extraction records for the given jobs.

        Args:
            job_ids: PKs of the jobs to delete the extraction for

        Returns:
            None

        Raises:
            ValueError: if job_ids is empty
        """
        if not job_ids:
            raise ValueError("job_ids must not be empty")
        count = (
            CatalogJobExtractionModel.query()
            .delete()
            .whereIn("job_id", list(job_ids))
            .run()
        )
        logger.info("deleted %s extraction(s) from catalog_job_extractions", count)

    def insert_extractions(
        self, records: Sequence[CatalogJobExtractionInsert]
    ) -> list[CatalogJobExtractionSelect]:
        """
        Insert extraction records, one per job.

        Args:
            records: catalog job extraction rows

        Returns:
            the inserted catalog job extraction rows

        Raises:
            ValueError: if records is empty
        """
        if not records:
            raise ValueError("records must not be empty")
        rows = [{"id": str(uuid4()), **record} for record in records]
        result = CatalogJobExtractionModel.query().insert(rows).returning().run()
        logger.info(
            "inserted %s extraction(s) into catalog_job_extractions", len(result)
        )
        return cast(list[CatalogJobExtractionSelect], result)

    def get_extractions(self) -> list[CatalogJobExtractionSelect]:
        """
        Get all extraction records, ordered by job id.

        Args:
            None

        Returns:
            list of catalog job extractions
        """
        result = CatalogJobExtractionModel.query().orderBy("job_id").to_dicts()
        logger.info(
            "retrieved %s extraction(s) from catalog_job_extractions", len(result)
        )
        return cast(list[CatalogJobExtractionSelect], result)

    def get_cache_keys(self) -> dict[str, str]:
        """
        Get the stored cache key for every extracted job, keyed by job id.

        Args:
            None

        Returns:
            A dict of job_id to cache_key mappings
        """
        result = (
            CatalogJobExtractionModel.query().select("job_id", "cache_key").to_dicts()
        )
        return {row["job_id"]: row["cache_key"] for row in result}
