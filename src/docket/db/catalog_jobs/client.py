import sqlite3
from collections.abc import Sequence
from typing import cast
from uuid import uuid4

from sustained import QueryBuilder

from ...config.logger import get_logger
from ..aws_glue_jobs import AwsGlueJobSelect
from ..aws_lambda_functions import AwsLambdaFunctionSelect
from .job_row_strategies import GlueJobStrategy, LambdaFunctionStrategy
from .models import CatalogJobModel, CatalogJobSelect

logger = get_logger("catalog_jobs")

GLUE_STRATEGY = GlueJobStrategy()
LAMBDA_STRATEGY = LambdaFunctionStrategy()


class CatalogJobClient:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def delete_jobs(self) -> None:
        """
        Deletes all job records.

        Args:
            None

        Returns:
            None
        """
        count = (
            CatalogJobModel.query().delete().where(QueryBuilder.raw("1"), "=", 1).run()
        )
        logger.info("deleted %s job(s) from catalog_jobs", count)

    def insert_jobs(
        self,
        glue_jobs: Sequence[AwsGlueJobSelect] = (),
        lambda_functions: Sequence[AwsLambdaFunctionSelect] = (),
    ) -> list[CatalogJobSelect]:
        """
        Insert glue job and lambda function records.

        Args:
            glue_jobs: Glue jobs as read from AWS
            lambda_functions: Lambda functions as read from AWS

        Returns:
            The inserted rows

        Raises:
            ValueError: if both glue_jobs and lambda_functions are empty
        """
        if not glue_jobs and not lambda_functions:
            raise ValueError("glue_jobs and lambda_functions must not both be empty")
        inserts = [GLUE_STRATEGY.build_row(record) for record in glue_jobs] + [
            LAMBDA_STRATEGY.build_row(record) for record in lambda_functions
        ]
        rows = [{"id": str(uuid4()), **insert} for insert in inserts]
        result = CatalogJobModel.query().insert(rows).returning().run()
        logger.info("inserted %s job(s) into catalog_jobs", len(result))
        return cast(list[CatalogJobSelect], result)

    def get_jobs(self) -> list[CatalogJobSelect]:
        """
        Get all job records, ordered by type then name.

        Returns:
            list[CatalogJobSelect]
        """
        result = CatalogJobModel.query().orderBy("type").orderBy("name").to_dicts()
        logger.info("retrieved %s job(s) from catalog_jobs", len(result))
        return cast(list[CatalogJobSelect], result)

    def get_jobs_by_ids(self, job_ids: Sequence[str]) -> list[CatalogJobSelect]:
        """
        Get the job records with the given PKs.

        Args:
            job_ids: PKs of the job records to fetch

        Returns:
            list[CatalogJobSelect]
        """
        if not job_ids:
            return []
        result = CatalogJobModel.query().whereIn("id", list(job_ids)).to_dicts()
        logger.info("retrieved %s job(s) from catalog_jobs", len(result))
        return cast(list[CatalogJobSelect], result)
