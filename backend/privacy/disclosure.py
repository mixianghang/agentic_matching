"""Disclosure configuration and session budget tracking.

Implements DisclosureConfig, SessionDisclosureBudget, and DisclosureEvent
from design/privacy_preserving_agentic_matching_v1.0.md §3.3, §4.3, §9.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, Set


# ---------------------------------------------------------------------------
# Disclosure level choices available to users (§3.3)
# ---------------------------------------------------------------------------

class DisclosureLevel(str, Enum):
    NONE = "none"       # Attribute is never shared
    COARSE = "coarse"   # Share only coarse/category representation (default for Level-1)
    EXACT = "exact"     # Share exact value (allowed only for Level-0 attributes)
    # Location-specific variants
    CITY = "city"
    DISTRICT = "district"
    # Occupation-specific
    CATEGORY = "category"
    # Budget-specific
    RANGE = "range"


# ---------------------------------------------------------------------------
# Per-demand disclosure configuration (§3.3)
# ---------------------------------------------------------------------------

@dataclass
class DisclosureConfig:
    """Per-demand user-controlled disclosure settings."""

    demand_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    age_disclosure: DisclosureLevel = DisclosureLevel.COARSE
    income_disclosure: DisclosureLevel = DisclosureLevel.NONE
    occupation_disclosure: DisclosureLevel = DisclosureLevel.CATEGORY
    location_disclosure: DisclosureLevel = DisclosureLevel.CITY
    budget_disclosure: DisclosureLevel = DisclosureLevel.RANGE
    # Attribute name → DisclosureLevel for domain-specific extras
    custom_overrides: Dict[str, DisclosureLevel] = field(default_factory=dict)

    def get_level(self, attribute_name: str) -> DisclosureLevel:
        """Return the effective disclosure level for an attribute."""
        if attribute_name in self.custom_overrides:
            return self.custom_overrides[attribute_name]
        mapping = {
            "age": self.age_disclosure,
            "income": self.income_disclosure,
            "occupation": self.occupation_disclosure,
            "location": self.location_disclosure,
            "budget": self.budget_disclosure,
        }
        return mapping.get(attribute_name, DisclosureLevel.NONE)

    def tighten(self, attribute_name: str) -> None:
        """Tighten disclosure to NONE for the given attribute (§8.2)."""
        self.custom_overrides[attribute_name] = DisclosureLevel.NONE

    def widen(self, attribute_name: str, level: DisclosureLevel) -> None:
        """Widen disclosure level for the given attribute (§8.2)."""
        self.custom_overrides[attribute_name] = level

    def revoke(self, attribute_name: str) -> None:
        """Revoke a previously widened override, resetting to NONE (§8.2)."""
        self.custom_overrides[attribute_name] = DisclosureLevel.NONE


# ---------------------------------------------------------------------------
# Per-session disclosure budget (§4.3)
# ---------------------------------------------------------------------------

@dataclass
class SessionDisclosureBudget:
    """Tracks how many distinct Level-1 attributes have been revealed in a session."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    max_attributes_revealed: int = 5
    attributes_revealed: Set[str] = field(default_factory=set)

    def can_reveal(self, attribute_name: str) -> bool:
        """Return True if the attribute may be disclosed."""
        if attribute_name in self.attributes_revealed:
            return True  # Already disclosed; repeating is free
        return len(self.attributes_revealed) < self.max_attributes_revealed

    def record_reveal(self, attribute_name: str) -> None:
        """Record that an attribute was disclosed."""
        self.attributes_revealed.add(attribute_name)

    @property
    def budget_exhausted(self) -> bool:
        """Return True when no new attributes may be revealed."""
        return len(self.attributes_revealed) >= self.max_attributes_revealed

    @property
    def remaining_budget(self) -> int:
        """Number of additional attributes that may still be revealed."""
        return max(0, self.max_attributes_revealed - len(self.attributes_revealed))


# ---------------------------------------------------------------------------
# Disclosure event (audit log entry) (§9)
# ---------------------------------------------------------------------------

@dataclass
class DisclosureEvent:
    """Immutable record of a single attribute disclosure."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    demand_id: str = ""
    session_id: str = ""
    peer_agent_id: str = ""   # Recipient agent ID (NOT the user behind it)
    attribute_name: str = ""
    coarse_value: str = ""    # The coarse value actually shared
    round_number: int = 0
