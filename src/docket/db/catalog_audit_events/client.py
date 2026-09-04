import sqlite3
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import cast
from uuid import uuid4

from ...config.logger import get_logger
from .models import (
    CatalogAuditEventInsert,
    CatalogAuditEventModel,
    CatalogAuditEventSelect,
)

logger = get_logger("catalog_audit_events")


class CatalogAuditEventClient:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def insert_events(
        self, records: Sequence[CatalogAuditEventInsert]
    ) -> list[CatalogAuditEventSelect]:
        """
        Insert audit event records, stamping reported_at.

        Args:
            records: catalog audit event records

        Returns:
            list of the inserted catalog audit event records

        Raises:
            ValueError: if records is empty
        """
        if not records:
            raise ValueError("records must not be empty")
        now = datetime.now(timezone.utc)
        rows = [{"id": str(uuid4()), "reported_at": now, **record} for record in records]
        result = CatalogAuditEventModel.query().insert(rows).returning().run()
        logger.info("inserted %s event(s) into catalog_audit_events", len(result))
        return cast(list[CatalogAuditEventSelect], result)

    def get_event_ids(self, event_ids: Sequence[str]) -> set[str]:
        """
        Return the subset of the given CloudTrail event ids already stored.

        Args:
            event_ids: CloudTrail event ids to look up

        Returns:
            the event ids that already have audit records
        """
        if not event_ids:
            return set()
        rows = (
            CatalogAuditEventModel.query()
            .select("event_id")
            .whereIn("event_id", list(event_ids))
            .to_dicts()
        )
        logger.info("matched %s event(s) in catalog_audit_events", len(rows))
        return {row["event_id"] for row in rows}
