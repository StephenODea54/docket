import sqlite3
from typing import cast

from ...config.logger import get_logger
from .models import AwsGlueJobModel, AwsGlueJobSelect

logger = get_logger("aws_glue_jobs")


class AwsGlueJobClient:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get_jobs(self) -> list[AwsGlueJobSelect]:
        """
        Fetch all Glue jobs from AWS

        Args:
            None

        Returns:
            list[AwsGlueJobSelect]
        """
        rows = AwsGlueJobModel.query().select(*AwsGlueJobModel.tableColumns).to_dicts()
        logger.info("fetched %s job(s) from aws_glue_job", len(rows))
        return cast(list[AwsGlueJobSelect], rows)
