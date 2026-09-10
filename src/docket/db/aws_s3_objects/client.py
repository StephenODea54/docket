from typing import Any, cast

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
        self.region = region
        self._s3: Any | None = None

    @property
    def s3(self) -> Any:
        """
        The boto3 s3 client, created on first use.

        Deferred so opening the catalog without AWS access (`DB(aws=False)`)
        never needs a region or credentials.
        """
        if self._s3 is None:
            self._s3 = boto3.Session().client("s3", region_name=self.region)
        return self._s3

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
