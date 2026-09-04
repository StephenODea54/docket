import sqlite3
from datetime import datetime
from typing import cast

from ...config.logger import get_logger
from .models import AwsCloudtrailLookupEventModel, AwsCloudtrailLookupEventSelect

logger = get_logger("aws_cloudtrail_events")


class AwsCloudtrailEventClient:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get_events(
        self, event_name: str, start_time: datetime
    ) -> list[AwsCloudtrailLookupEventSelect]:
        """
        Fetch CloudTrail events with the given name since start_time.

        Args:
            event_name: the CloudTrail event name to look up
            start_time: the inclusive lower bound on event time

        Returns:
            list[AwsCloudtrailLookupEventSelect]
        """
        rows = (
            AwsCloudtrailLookupEventModel.query()
            .select(*AwsCloudtrailLookupEventSelect.__annotations__)
            .where("event_name", "=", event_name)
            .where("start_time", "=", start_time.strftime("%Y-%m-%d %H:%M:%S"))
            .to_dicts()
        )
        logger.info(
            "fetched %s %s event(s) from aws_cloudtrail_lookup_event",
            len(rows),
            event_name,
        )
        return cast(list[AwsCloudtrailLookupEventSelect], rows)
