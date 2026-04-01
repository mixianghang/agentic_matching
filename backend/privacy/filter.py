"""Privacy Filter Layer.

Implements the four-stage outbound message filter described in
design/privacy_preserving_agentic_matching_v1.0.md §4:

  1. Pattern scanner (regex)
  2. Coarsening transformer
  3. Disclosure-budget checker
  4. Output validator

Usage::

    pfl = PrivacyFilterLayer(
        config=DisclosureConfig(demand_id="d1"),
        budget=SessionDisclosureBudget(session_id="s1"),
    )
    result = pfl.filter(draft_message, context)
    if result.blocked:
        send(result.fallback)
    else:
        send(result.message)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend.privacy.coarsening import (
    SensitivityLevel,
    coarsen_age,
    coarsen_annual_income,
    coarsen_occupation,
    coarsen_rent_budget,
)
from backend.privacy.disclosure import (
    DisclosureConfig,
    DisclosureEvent,
    DisclosureLevel,
    SessionDisclosureBudget,
)


# ---------------------------------------------------------------------------
# Regex patterns for sensitive information detection (§4.2)
# ---------------------------------------------------------------------------

_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(\+?\d[\d\s\-\(\)]{7,}\d)"
    r"(?!\d)"
)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_SSN_RE = re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b")

# Exact currency amounts, e.g. "$45,000" or "45000 USD" or "¥12000"
_EXACT_CURRENCY_RE = re.compile(
    r"(?:[\$¥€£])\s?\d[\d,]*(?:\.\d+)?"
    r"|"
    r"\b\d[\d,]*(?:\.\d+)?\s?(?:USD|CNY|EUR|GBP|dollars?)\b",
    re.IGNORECASE,
)

# Street-level address patterns: "123 Main St", "Suite 4B", etc.
_STREET_RE = re.compile(
    r"\b\d{1,5}\s+\w[\w\s]*(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|court|ct|place|pl)\b",
    re.IGNORECASE,
)

# Numeric ID-like patterns (8+ consecutive digits)
_NUMERIC_ID_RE = re.compile(r"\b\d{8,}\b")

# Exact age statements: "I am 32 years old", "age: 27"
_EXACT_AGE_RE = re.compile(
    r"\b(?:i(?:'m| am)|age[:\s]+|aged?[:\s]+)?\s*(\d{1,3})\s*(?:years?\s*old|yo)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class FilterResult:
    """The outcome of a PrivacyFilterLayer.filter() call."""

    message: str = ""
    blocked: bool = False
    reasons: List[str] = field(default_factory=list)
    fallback: str = "I prefer not to share that detail at this stage."
    disclosed_attributes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main filter class
# ---------------------------------------------------------------------------

class PrivacyFilterLayer:
    """Four-stage outbound message privacy filter (§4).

    Args:
        config: Per-demand :class:`DisclosureConfig` controlling which
                attributes the user has permitted to be shared.
        budget: Per-session :class:`SessionDisclosureBudget` limiting the
                total number of distinct Level-1 attributes that may be
                revealed in a session.
        demand_id: The demand identifier (embedded in DisclosureEvents).
        session_id: The session identifier.
        peer_agent_id: The peer agent's ID (used in DisclosureEvents).
        max_regeneration_attempts: How many times to retry before using the
                                   generic fallback (§4.2).
    """

    def __init__(
        self,
        config: DisclosureConfig,
        budget: SessionDisclosureBudget,
        demand_id: str = "",
        session_id: str = "",
        peer_agent_id: str = "",
        max_regeneration_attempts: int = 3,
    ) -> None:
        self.config = config
        self.budget = budget
        self.demand_id = demand_id
        self.session_id = session_id
        self.peer_agent_id = peer_agent_id
        self.max_regeneration_attempts = max_regeneration_attempts

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def filter(
        self,
        draft_message: str,
        private_values: Optional[Dict[str, object]] = None,
        round_number: int = 1,
    ) -> FilterResult:
        """Run the full four-stage filter pipeline on *draft_message*.

        Args:
            draft_message: The raw text produced by the agent LLM.
            private_values: Optional dict of ``{attribute_name: exact_value}``
                            used to apply coarsening.  If an exact value from
                            this dict appears verbatim in the draft, it is
                            replaced by its coarse equivalent.
            round_number: Current negotiation round (used in DisclosureEvents).

        Returns:
            A :class:`FilterResult` describing the outcome.
        """
        private_values = private_values or {}
        result = FilterResult(message=draft_message)

        # Stage 1: Pattern scanner
        violations = self._scan_patterns(draft_message)
        if violations:
            result.blocked = True
            result.reasons.extend(violations)
            return result

        # Stage 2: Coarsening transformer
        message, disclosed = self._apply_coarsening(draft_message, private_values)
        result.message = message
        result.disclosed_attributes = disclosed

        # Stage 3: Disclosure-budget checker
        budget_blocked = []
        for attr in disclosed:
            if not self.budget.can_reveal(attr):
                budget_blocked.append(attr)
        if budget_blocked:
            result.blocked = True
            result.reasons.append(
                f"Disclosure budget exhausted; cannot reveal: {', '.join(budget_blocked)}"
            )
            return result

        # Record reveals for attributes that pass the budget check
        for attr in disclosed:
            self.budget.record_reveal(attr)

        # Stage 4: Output validator
        validation_errors = self._validate_output(result.message)
        if validation_errors:
            result.blocked = True
            result.reasons.extend(validation_errors)
            return result

        return result

    # ------------------------------------------------------------------
    # Stage 1 — Pattern scanner (§4.2)
    # ------------------------------------------------------------------

    def _scan_patterns(self, text: str) -> List[str]:
        """Return a list of violation descriptions found in *text*."""
        violations: List[str] = []
        if _PHONE_RE.search(text):
            violations.append("Possible phone number detected")
        if _EMAIL_RE.search(text):
            violations.append("Email address detected")
        if _SSN_RE.search(text):
            violations.append("Possible SSN detected")
        if _NUMERIC_ID_RE.search(text):
            violations.append("Long numeric ID detected")
        if _STREET_RE.search(text):
            violations.append("Street address pattern detected")
        return violations

    # ------------------------------------------------------------------
    # Stage 2 — Coarsening transformer (§4)
    # ------------------------------------------------------------------

    def _apply_coarsening(
        self, text: str, private_values: Dict[str, object]
    ) -> tuple[str, List[str]]:
        """Replace exact private values with their coarse equivalents.

        Returns:
            (transformed_text, list_of_attribute_names_coarsened)
        """
        disclosed: List[str] = []

        for attr_name, exact_value in private_values.items():
            level = self.config.get_level(attr_name)
            if level == DisclosureLevel.NONE:
                # If the exact value appears in the text, remove it
                text = text.replace(str(exact_value), "[redacted]")
                continue

            coarse = self._coarsen_value(attr_name, exact_value)
            if coarse and str(exact_value) in text:
                text = text.replace(str(exact_value), coarse)
                disclosed.append(attr_name)

        return text, disclosed

    def _coarsen_value(self, attr_name: str, value: object) -> Optional[str]:
        """Apply the appropriate coarsening function for an attribute."""
        try:
            if attr_name == "age":
                return coarsen_age(int(value))  # type: ignore[arg-type]
            if attr_name == "income":
                return coarsen_annual_income(float(value))  # type: ignore[arg-type]
            if attr_name == "budget":
                return coarsen_rent_budget(float(value))  # type: ignore[arg-type]
            if attr_name == "occupation":
                return coarsen_occupation(str(value))
        except (ValueError, TypeError):
            return None
        return None

    # ------------------------------------------------------------------
    # Stage 4 — Output validator (§4.4)
    # ------------------------------------------------------------------

    def _validate_output(self, text: str) -> List[str]:
        """Check that the filtered message still contains no Level-3 data.

        Returns a list of violation descriptions (empty = OK).
        """
        errors: List[str] = []
        if _EXACT_CURRENCY_RE.search(text):
            errors.append("Exact currency amount found in output message")
        if _EXACT_AGE_RE.search(text):
            errors.append("Exact age statement found in output message")
        return errors

    # ------------------------------------------------------------------
    # Disclosure summary helper (§8.1)
    # ------------------------------------------------------------------

    def build_disclosure_summary(
        self,
        attributes_shared: Dict[str, str],
        attributes_withheld: List[str],
        outcome: str = "inconclusive",
    ) -> str:
        """Generate a human-readable disclosure summary for the user (§8.1).

        Args:
            attributes_shared: ``{attribute_name: coarse_value}`` dict.
            attributes_withheld: List of attribute names that were requested
                                 but not shared.
            outcome: Session outcome string (e.g., "Tentative match").

        Returns:
            Formatted multi-line summary string.
        """
        lines: List[str] = [
            f"Session with Agent [{self.peer_agent_id}] — Disclosure Summary",
            "─" * 50,
            "Attributes shared:",
        ]
        if attributes_shared:
            for name, value in attributes_shared.items():
                lines.append(f"  - {name.capitalize()}: \"{value}\"")
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append("Attributes requested but not shared:")
        if attributes_withheld:
            for name in attributes_withheld:
                lines.append(f"  - {name.capitalize()} (withheld per your privacy settings)")
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append(f"Outcome: {outcome}")
        return "\n".join(lines)
