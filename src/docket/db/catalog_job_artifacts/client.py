import sqlite3
from collections.abc import Sequence
from typing import cast
from uuid import uuid4

from sustained import QueryBuilder

from ...config.logger import get_logger
from .models import (
    CatalogJobArtifactInsert,
    CatalogJobArtifactModel,
    CatalogJobArtifactSelect,
)

logger = get_logger("catalog_job_artifacts")


class CatalogJobArtifactClient:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def delete_artifacts(self) -> None:
        """
        Deletes all job artifact records.

        Args:
            None

        Returns:
            None
        """
        count = (
            CatalogJobArtifactModel.query()
            .delete()
            .where(QueryBuilder.raw("1"), "=", 1)
            .run()
        )
        logger.info("deleted %s artifact(s) from catalog_job_artifacts", count)

    def insert_artifacts(
        self, records: Sequence[CatalogJobArtifactInsert]
    ) -> list[CatalogJobArtifactSelect]:
        """
        Insert job artifact records.

        Args:
            records: Rows referencing metadata about lambda and glue jobs.
                Glue rows use s3 uri and etag, lambda rows use function arn
                and code sha as location and cache_key

        Returns:
            The inserted rows

        Raises:
            ValueError: if records is empty
        """
        if not records:
            raise ValueError("records must not be empty")
        rows = [{"id": str(uuid4()), **record} for record in records]
        result = CatalogJobArtifactModel.query().insert(rows).returning().run()
        logger.info("inserted %s artifact(s) into catalog_job_artifacts", len(result))
        return cast(list[CatalogJobArtifactSelect], result)

    def get_artifacts(self) -> list[CatalogJobArtifactSelect]:
        """
        Get all job artifact records, ordered by location.

        Returns:
            list[CatalogJobArtifactSelect]
        """
        result = CatalogJobArtifactModel.query().orderBy("location").to_dicts()
        logger.info("retrieved %s artifact(s) from catalog_job_artifacts", len(result))
        return cast(list[CatalogJobArtifactSelect], result)
