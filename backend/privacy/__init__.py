"""Privacy-preserving agentic matching module.

Public API surface for the privacy layer:

    from backend.privacy import (
        # Attribute coarsening
        SensitivityLevel,
        coarsen_age,
        coarsen_annual_income,
        coarsen_rent_budget,
        coarsen_occupation,
        coarsen_location,
        # Disclosure config / budget / events
        DisclosureLevel,
        DisclosureConfig,
        SessionDisclosureBudget,
        DisclosureEvent,
        # Filter layer
        PrivacyFilterLayer,
        FilterResult,
        # Negotiation helpers
        make_offer,
        opening_offer,
        should_pause_before_accept,
        should_reject_within_range,
        # Audit log
        AuditLog,
        audit_log,
    )
"""

from backend.privacy.coarsening import (
    SensitivityLevel,
    coarsen_age,
    coarsen_annual_income,
    coarsen_location,
    coarsen_occupation,
    coarsen_rent_budget,
)
from backend.privacy.disclosure import (
    DisclosureConfig,
    DisclosureEvent,
    DisclosureLevel,
    SessionDisclosureBudget,
)
from backend.privacy.filter import FilterResult, PrivacyFilterLayer
from backend.privacy.negotiation import (
    make_offer,
    opening_offer,
    should_pause_before_accept,
    should_reject_within_range,
)
from backend.privacy.audit import AuditLog, audit_log

__all__ = [
    # coarsening
    "SensitivityLevel",
    "coarsen_age",
    "coarsen_annual_income",
    "coarsen_rent_budget",
    "coarsen_occupation",
    "coarsen_location",
    # disclosure
    "DisclosureLevel",
    "DisclosureConfig",
    "SessionDisclosureBudget",
    "DisclosureEvent",
    # filter
    "PrivacyFilterLayer",
    "FilterResult",
    # negotiation
    "make_offer",
    "opening_offer",
    "should_pause_before_accept",
    "should_reject_within_range",
    # audit
    "AuditLog",
    "audit_log",
]
