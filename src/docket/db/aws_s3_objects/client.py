import sqlite3
from typing import cast

from ...config.logger import get_logger
from .models import AwsS3ObjectModel, AwsS3ObjectSelect

logger = get_logger("aws_s3_objects")


class AwsS3ObjectClient:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get_object(self, bucket_name: str, key: str) -> AwsS3ObjectSelect | None:
        """
        Get one s3 object from AWS.

        Args:
            bucket_name: name of the bucket holding the object
            key: full key of the object within the bucket

        Returns:
            The object row, or None when the key does not exist
        """
        rows = (
            AwsS3ObjectModel.query()
            .select(*AwsS3ObjectModel.tableColumns)
            .where("bucket_name", "=", bucket_name)
            .where("key", "=", key)
            .to_dicts()
        )
        logger.info("fetched %s object(s) from aws_s3_object", len(rows))
        if not rows:
            return None
        return cast(AwsS3ObjectSelect, rows[0])
