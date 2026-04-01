"""Append-only per-user audit log of disclosure events.

Implements the audit log described in
design/privacy_preserving_agentic_matching_v1.0.md §9.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from backend.privacy.disclosure import DisclosureEvent


class AuditLog:
    """In-process, append-only audit log partitioned by user_id.

    Events can only be appended; individual entries cannot be modified or
    deleted (only a full purge on account deletion is supported).

    Usage::

        log = AuditLog()
        log.append("user_123", event)
        events = log.get_events("user_123")
    """

    def __init__(self) -> None:
        self._store: Dict[str, List[DisclosureEvent]] = {}

    def append(self, user_id: str, event: DisclosureEvent) -> None:
        """Append a disclosure event to the user's audit log.

        Args:
            user_id: The owning user's identifier (kept server-side only).
            event: The immutable DisclosureEvent to record.
        """
        if user_id not in self._store:
            self._store[user_id] = []
        self._store[user_id].append(event)

    def get_events(
        self,
        user_id: str,
        *,
        session_id: Optional[str] = None,
        demand_id: Optional[str] = None,
    ) -> List[DisclosureEvent]:
        """Retrieve events for a user, optionally filtered.

        Args:
            user_id: The user whose log to read.
            session_id: If provided, only return events for this session.
            demand_id: If provided, only return events for this demand.

        Returns:
            Ordered list of matching DisclosureEvent objects (oldest first).
        """
        events = list(self._store.get(user_id, []))
        if session_id is not None:
            events = [e for e in events if e.session_id == session_id]
        if demand_id is not None:
            events = [e for e in events if e.demand_id == demand_id]
        return events

    def purge(self, user_id: str) -> None:
        """Remove the entire audit log for a user (account deletion only).

        Args:
            user_id: The user whose log to purge.
        """
        self._store.pop(user_id, None)

    def event_count(self, user_id: str) -> int:
        """Return the total number of logged events for a user."""
        return len(self._store.get(user_id, []))


# Module-level singleton (can be replaced in tests)
audit_log = AuditLog()
