from typing import cast

import boto3

from ...config.logger import get_logger
from .models import AwsS3ObjectSelect

logger = get_logger("aws_s3_objects")


class AwsS3ObjectClient:
    """
    Reads s3 object bodies directly through boto3.

    Steampipe's per-query overhead makes it unsuitable for bulk file
    fetches; inventory reads stay on the virtual tables.
    """

    def __init__(self, region: str | None = None) -> None:
        self.s3 = boto3.Session().client("s3", region_name=region)

    def get_object(self, bucket_name: str, key: str) -> AwsS3ObjectSelect | None:
        """
        Get one s3 object's body from AWS.

        Args:
            bucket_name: name of the bucket holding the object
            key: full key of the object within the bucket

        Returns:
            The object row (bucket_name, key, body only), or None when the
            key does not exist
        """
        try:
            response = self.s3.get_object(Bucket=bucket_name, Key=key)
        except self.s3.exceptions.NoSuchKey:
            logger.warning("s3://%s/%s does not exist", bucket_name, key)
            return None
        body = response["Body"].read().decode("utf-8", "replace")
        logger.info("fetched s3://%s/%s (%s chars)", bucket_name, key, len(body))
        return cast(
            AwsS3ObjectSelect,
            {"bucket_name": bucket_name, "key": key, "body": body},
        )
