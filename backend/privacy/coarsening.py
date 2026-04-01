"""Attribute classification and coarsening functions.

Implements the sensitivity-level taxonomy and coarsening functions from
design/privacy_preserving_agentic_matching_v1.0.md §3.
"""
from enum import IntEnum
from typing import Optional


class SensitivityLevel(IntEnum):
    """Attribute sensitivity levels (§3.1)."""
    PUBLIC = 0       # Always shared: domain, city, demand status
    COARSE = 1       # Shared as categorical/range: age band, income tier, budget range, job category
    SEMI_PRIVATE = 2 # Shared only if user enables: neighbourhood, employment status
    PRIVATE = 3      # Never shared via agent messages: exact address, phone, income, ID


# ---------------------------------------------------------------------------
# Coarsening functions (§3.2)
# ---------------------------------------------------------------------------

def coarsen_age(age: int) -> str:
    """Convert an exact age to a coarse age band."""
    if age < 18:
        raise ValueError(f"Age {age} is below minimum (18)")
    if age <= 24:
        return "18–24"
    if age <= 29:
        return "late 20s"
    if age <= 34:
        return "early 30s"
    if age <= 39:
        return "late 30s"
    if age <= 49:
        return "40s"
    if age <= 59:
        return "50s"
    return "60 or above"


def coarsen_annual_income(income_usd: float) -> str:
    """Convert an exact annual income (USD) to a coarse income tier."""
    if income_usd < 30_000:
        return "low income"
    if income_usd < 60_000:
        return "lower-middle income"
    if income_usd < 100_000:
        return "middle income"
    if income_usd < 150_000:
        return "upper-middle income"
    if income_usd < 250_000:
        return "high income"
    return "very high income"


def coarsen_rent_budget(monthly_usd: float) -> str:
    """Convert an exact monthly rent budget (USD) to a coarse range."""
    if monthly_usd < 800:
        return "under $800"
    if monthly_usd < 1_200:
        return "$800 – $1,200"
    if monthly_usd < 1_800:
        return "$1,200 – $1,800"
    if monthly_usd < 2_500:
        return "$1,800 – $2,500"
    if monthly_usd < 3_500:
        return "$2,500 – $3,500"
    return "above $3,500"


# Canonical occupation category mapping (exact title → broad category)
_JOB_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "technology": ["software", "engineer", "developer", "tech", "it ", "data", "ai", "ml", "programmer"],
    "healthcare": ["doctor", "nurse", "physician", "medical", "hospital", "health", "dentist"],
    "education": ["teacher", "professor", "lecturer", "educator", "school", "university", "tutor"],
    "finance": ["banker", "accountant", "analyst", "finance", "investment", "trader", "auditor"],
    "creative": ["designer", "artist", "writer", "musician", "photographer", "creative", "filmmaker"],
    "legal": ["lawyer", "attorney", "judge", "paralegal", "legal"],
    "retail": ["retail", "sales", "cashier", "store", "shop"],
}


def coarsen_occupation(job_title: str) -> str:
    """Map an exact job title to a broad occupational category."""
    lower = job_title.lower()
    for category, keywords in _JOB_CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return "other"


def coarsen_location(
    city: Optional[str] = None,
    neighbourhood: Optional[str] = None,
    street_address: Optional[str] = None,
    target_level: SensitivityLevel = SensitivityLevel.PUBLIC,
) -> Optional[str]:
    """Return the maximum-shareable location string at the requested level.

    - Level 0 (PUBLIC)     → city only
    - Level 2 (SEMI_PRIVATE) → neighbourhood / district (if provided)
    - Level 3 (PRIVATE)    → never returned (raises ValueError)
    """
    if target_level == SensitivityLevel.PRIVATE:
        raise ValueError("Exact street address (Level 3) must never be shared via agent messages")
    if target_level >= SensitivityLevel.SEMI_PRIVATE and neighbourhood:
        return neighbourhood
    return city
