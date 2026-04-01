"""Tests for the privacy-preserving agentic matching module.

Covers:
- Coarsening functions (age, income, rent budget, occupation, location)
- DisclosureConfig and user controls
- SessionDisclosureBudget
- DisclosureEvent construction
- PrivacyFilterLayer (pattern scanner, coarsening, budget, output validator)
- Negotiation helpers (make_offer, opening_offer, strategy obfuscation)
- AuditLog (append, get, purge)
"""
import random

import pytest

from backend.privacy import (
    AuditLog,
    DisclosureConfig,
    DisclosureEvent,
    DisclosureLevel,
    FilterResult,
    PrivacyFilterLayer,
    SessionDisclosureBudget,
    SensitivityLevel,
    audit_log,
    coarsen_age,
    coarsen_annual_income,
    coarsen_location,
    coarsen_occupation,
    coarsen_rent_budget,
    make_offer,
    opening_offer,
    should_pause_before_accept,
    should_reject_within_range,
)


# ===========================================================================
# Coarsening functions
# ===========================================================================


class TestCoarsenAge:
    def test_young_adult(self):
        assert coarsen_age(20) == "18–24"

    def test_lower_boundary_18(self):
        assert coarsen_age(18) == "18–24"

    def test_upper_boundary_24(self):
        assert coarsen_age(24) == "18–24"

    def test_late_twenties(self):
        assert coarsen_age(27) == "late 20s"

    def test_early_thirties(self):
        assert coarsen_age(31) == "early 30s"

    def test_late_thirties(self):
        assert coarsen_age(38) == "late 30s"

    def test_forties(self):
        assert coarsen_age(45) == "40s"

    def test_fifties(self):
        assert coarsen_age(55) == "50s"

    def test_sixty_plus(self):
        assert coarsen_age(60) == "60 or above"
        assert coarsen_age(75) == "60 or above"

    def test_invalid_age(self):
        with pytest.raises(ValueError):
            coarsen_age(17)


class TestCoarsenAnnualIncome:
    def test_low_income(self):
        assert coarsen_annual_income(20_000) == "low income"

    def test_lower_middle(self):
        assert coarsen_annual_income(45_000) == "lower-middle income"

    def test_middle(self):
        assert coarsen_annual_income(80_000) == "middle income"

    def test_upper_middle(self):
        assert coarsen_annual_income(120_000) == "upper-middle income"

    def test_high(self):
        assert coarsen_annual_income(200_000) == "high income"

    def test_very_high(self):
        assert coarsen_annual_income(300_000) == "very high income"

    def test_boundary_30k(self):
        assert coarsen_annual_income(30_000) == "lower-middle income"

    def test_boundary_60k(self):
        assert coarsen_annual_income(60_000) == "middle income"


class TestCoarsenRentBudget:
    def test_under_800(self):
        assert coarsen_rent_budget(600) == "under $800"

    def test_800_to_1200(self):
        assert coarsen_rent_budget(1_000) == "$800 – $1,200"

    def test_1200_to_1800(self):
        assert coarsen_rent_budget(1_500) == "$1,200 – $1,800"

    def test_1800_to_2500(self):
        assert coarsen_rent_budget(2_000) == "$1,800 – $2,500"

    def test_2500_to_3500(self):
        assert coarsen_rent_budget(3_000) == "$2,500 – $3,500"

    def test_above_3500(self):
        assert coarsen_rent_budget(4_000) == "above $3,500"

    def test_boundary_800(self):
        assert coarsen_rent_budget(800) == "$800 – $1,200"


class TestCoarsenOccupation:
    def test_software_engineer(self):
        assert coarsen_occupation("Software Engineer") == "technology"

    def test_data_scientist(self):
        assert coarsen_occupation("Data Scientist") == "technology"

    def test_doctor(self):
        assert coarsen_occupation("Doctor") == "healthcare"

    def test_nurse(self):
        assert coarsen_occupation("Nurse Practitioner") == "healthcare"

    def test_teacher(self):
        assert coarsen_occupation("High School Teacher") == "education"

    def test_accountant(self):
        assert coarsen_occupation("Certified Accountant") == "finance"

    def test_designer(self):
        assert coarsen_occupation("Graphic Designer") == "creative"

    def test_lawyer(self):
        assert coarsen_occupation("Corporate Lawyer") == "legal"

    def test_unknown(self):
        assert coarsen_occupation("Underwater Basket Weaver") == "other"


class TestCoarsenLocation:
    def test_public_returns_city(self):
        result = coarsen_location(city="New York", neighbourhood="Manhattan", target_level=SensitivityLevel.PUBLIC)
        assert result == "New York"

    def test_semi_private_returns_neighbourhood(self):
        result = coarsen_location(city="New York", neighbourhood="Manhattan", target_level=SensitivityLevel.SEMI_PRIVATE)
        assert result == "Manhattan"

    def test_semi_private_falls_back_to_city(self):
        result = coarsen_location(city="New York", neighbourhood=None, target_level=SensitivityLevel.SEMI_PRIVATE)
        assert result == "New York"

    def test_private_raises(self):
        with pytest.raises(ValueError):
            coarsen_location(city="New York", street_address="123 Main St", target_level=SensitivityLevel.PRIVATE)


# ===========================================================================
# DisclosureConfig
# ===========================================================================


class TestDisclosureConfig:
    def test_defaults(self):
        cfg = DisclosureConfig(demand_id="d1")
        assert cfg.get_level("age") == DisclosureLevel.COARSE
        assert cfg.get_level("income") == DisclosureLevel.NONE
        assert cfg.get_level("occupation") == DisclosureLevel.CATEGORY
        assert cfg.get_level("location") == DisclosureLevel.CITY
        assert cfg.get_level("budget") == DisclosureLevel.RANGE

    def test_unknown_attribute_returns_none(self):
        cfg = DisclosureConfig(demand_id="d1")
        assert cfg.get_level("ssn") == DisclosureLevel.NONE

    def test_tighten(self):
        cfg = DisclosureConfig(demand_id="d1")
        cfg.tighten("age")
        assert cfg.get_level("age") == DisclosureLevel.NONE

    def test_widen(self):
        cfg = DisclosureConfig(demand_id="d1")
        cfg.widen("income", DisclosureLevel.COARSE)
        assert cfg.get_level("income") == DisclosureLevel.COARSE

    def test_revoke(self):
        cfg = DisclosureConfig(demand_id="d1")
        cfg.widen("income", DisclosureLevel.COARSE)
        cfg.revoke("income")
        assert cfg.get_level("income") == DisclosureLevel.NONE

    def test_custom_override_takes_precedence(self):
        cfg = DisclosureConfig(demand_id="d1", custom_overrides={"age": DisclosureLevel.NONE})
        assert cfg.get_level("age") == DisclosureLevel.NONE


# ===========================================================================
# SessionDisclosureBudget
# ===========================================================================


class TestSessionDisclosureBudget:
    def test_can_reveal_new_attribute(self):
        budget = SessionDisclosureBudget(session_id="s1", max_attributes_revealed=5)
        assert budget.can_reveal("age") is True

    def test_repeat_reveal_is_free(self):
        budget = SessionDisclosureBudget(session_id="s1", max_attributes_revealed=1)
        budget.record_reveal("age")
        assert budget.can_reveal("age") is True  # already disclosed

    def test_budget_exhausted(self):
        budget = SessionDisclosureBudget(session_id="s1", max_attributes_revealed=2)
        budget.record_reveal("age")
        budget.record_reveal("income")
        assert budget.budget_exhausted is True
        assert budget.can_reveal("occupation") is False

    def test_remaining_budget(self):
        budget = SessionDisclosureBudget(session_id="s1", max_attributes_revealed=5)
        budget.record_reveal("age")
        assert budget.remaining_budget == 4

    def test_remaining_budget_zero_when_exhausted(self):
        budget = SessionDisclosureBudget(session_id="s1", max_attributes_revealed=1)
        budget.record_reveal("age")
        assert budget.remaining_budget == 0


# ===========================================================================
# DisclosureEvent
# ===========================================================================


class TestDisclosureEvent:
    def test_construction(self):
        event = DisclosureEvent(
            demand_id="d1",
            session_id="s1",
            peer_agent_id="agent-b",
            attribute_name="age",
            coarse_value="late 20s",
            round_number=1,
        )
        assert event.demand_id == "d1"
        assert event.attribute_name == "age"
        assert event.coarse_value == "late 20s"
        assert event.event_id  # auto-generated UUID
        assert event.timestamp  # auto-set


# ===========================================================================
# AuditLog
# ===========================================================================


class TestAuditLog:
    def test_append_and_retrieve(self):
        log = AuditLog()
        evt = DisclosureEvent(demand_id="d1", session_id="s1", attribute_name="age", coarse_value="late 20s")
        log.append("user_1", evt)
        events = log.get_events("user_1")
        assert len(events) == 1
        assert events[0].attribute_name == "age"

    def test_empty_user_returns_empty_list(self):
        log = AuditLog()
        assert log.get_events("nonexistent") == []

    def test_filter_by_session(self):
        log = AuditLog()
        e1 = DisclosureEvent(session_id="s1", attribute_name="age", coarse_value="late 20s")
        e2 = DisclosureEvent(session_id="s2", attribute_name="income", coarse_value="middle income")
        log.append("u1", e1)
        log.append("u1", e2)
        assert len(log.get_events("u1", session_id="s1")) == 1
        assert len(log.get_events("u1", session_id="s2")) == 1

    def test_filter_by_demand(self):
        log = AuditLog()
        e1 = DisclosureEvent(demand_id="d1", attribute_name="age", coarse_value="late 20s")
        e2 = DisclosureEvent(demand_id="d2", attribute_name="income", coarse_value="middle income")
        log.append("u1", e1)
        log.append("u1", e2)
        assert len(log.get_events("u1", demand_id="d1")) == 1

    def test_purge(self):
        log = AuditLog()
        log.append("u1", DisclosureEvent(attribute_name="age", coarse_value="late 20s"))
        log.purge("u1")
        assert log.get_events("u1") == []

    def test_event_count(self):
        log = AuditLog()
        for _ in range(3):
            log.append("u1", DisclosureEvent(attribute_name="age", coarse_value="late 20s"))
        assert log.event_count("u1") == 3

    def test_multiple_users_isolated(self):
        log = AuditLog()
        log.append("u1", DisclosureEvent(attribute_name="age", coarse_value="late 20s"))
        log.append("u2", DisclosureEvent(attribute_name="income", coarse_value="middle income"))
        assert log.event_count("u1") == 1
        assert log.event_count("u2") == 1


# ===========================================================================
# PrivacyFilterLayer — pattern scanner
# ===========================================================================


class TestPrivacyFilterLayerPatternScanner:
    @pytest.fixture
    def pfl(self):
        cfg = DisclosureConfig(demand_id="d1")
        budget = SessionDisclosureBudget(session_id="s1", max_attributes_revealed=5)
        return PrivacyFilterLayer(cfg, budget, peer_agent_id="agent-b")

    def test_clean_message_passes(self, pfl):
        result = pfl.filter("Hello, I am looking for a flat in the downtown area.")
        assert not result.blocked

    def test_phone_blocked(self, pfl):
        result = pfl.filter("Call me on +1 800 555 1234.")
        assert result.blocked
        assert any("phone" in r.lower() for r in result.reasons)

    def test_email_blocked(self, pfl):
        result = pfl.filter("My email is alice@example.com")
        assert result.blocked

    def test_street_address_blocked(self, pfl):
        result = pfl.filter("I live at 42 Elm Street.")
        assert result.blocked

    def test_long_numeric_id_blocked(self, pfl):
        result = pfl.filter("My account number is 12345678901234.")
        assert result.blocked


# ===========================================================================
# PrivacyFilterLayer — coarsening transformer
# ===========================================================================


class TestPrivacyFilterLayerCoarsening:
    @pytest.fixture
    def pfl(self):
        cfg = DisclosureConfig(demand_id="d1")
        budget = SessionDisclosureBudget(session_id="s1", max_attributes_revealed=5)
        return PrivacyFilterLayer(cfg, budget, peer_agent_id="agent-b")

    def test_age_replaced_with_coarse_band(self, pfl):
        result = pfl.filter(
            "I am 28 years old.",
            private_values={"age": 28},
        )
        assert not result.blocked
        assert "28" not in result.message
        assert "late 20s" in result.message

    def test_income_redacted_when_none(self, pfl):
        # Default income_disclosure is NONE
        result = pfl.filter(
            "My income is 75000.",
            private_values={"income": 75000},
        )
        assert not result.blocked
        assert "75000" not in result.message
        assert "[redacted]" in result.message

    def test_age_withheld_when_tightened(self, pfl):
        pfl.config.tighten("age")
        result = pfl.filter(
            "I am 28 years old.",
            private_values={"age": 28},
        )
        assert not result.blocked
        # Exact value should be redacted
        assert "28" not in result.message

    def test_disclosed_attributes_tracked(self, pfl):
        result = pfl.filter(
            "I am 28.",
            private_values={"age": 28},
        )
        assert "age" in result.disclosed_attributes


# ===========================================================================
# PrivacyFilterLayer — disclosure budget checker
# ===========================================================================


class TestPrivacyFilterLayerBudget:
    def test_budget_exhausted_blocks_message(self):
        cfg = DisclosureConfig(demand_id="d1")
        budget = SessionDisclosureBudget(session_id="s1", max_attributes_revealed=1)
        budget.record_reveal("income")  # budget = 0 new slots
        pfl = PrivacyFilterLayer(cfg, budget, peer_agent_id="agent-b")

        result = pfl.filter(
            "I am 28.",
            private_values={"age": 28},
        )
        assert result.blocked
        assert any("budget" in r.lower() for r in result.reasons)

    def test_repeated_attribute_does_not_count_against_budget(self):
        cfg = DisclosureConfig(demand_id="d1")
        budget = SessionDisclosureBudget(session_id="s1", max_attributes_revealed=1)
        budget.record_reveal("age")
        pfl = PrivacyFilterLayer(cfg, budget, peer_agent_id="agent-b")

        result = pfl.filter("I am 28.", private_values={"age": 28})
        assert not result.blocked


# ===========================================================================
# PrivacyFilterLayer — output validator
# ===========================================================================


class TestPrivacyFilterLayerOutputValidator:
    @pytest.fixture
    def pfl(self):
        cfg = DisclosureConfig(demand_id="d1")
        budget = SessionDisclosureBudget(session_id="s1", max_attributes_revealed=5)
        return PrivacyFilterLayer(cfg, budget, peer_agent_id="agent-b")

    def test_exact_currency_in_output_blocked(self, pfl):
        # A message that slips through the scanner but contains an exact amount
        result = pfl.filter("My budget is $45,000 per year.")
        assert result.blocked
        assert any("currency" in r.lower() for r in result.reasons)

    def test_age_statement_in_output_blocked(self, pfl):
        result = pfl.filter("I am 32 years old.")
        assert result.blocked


# ===========================================================================
# PrivacyFilterLayer — disclosure summary
# ===========================================================================


class TestDisclosureSummary:
    def test_summary_format(self):
        cfg = DisclosureConfig(demand_id="d1")
        budget = SessionDisclosureBudget(session_id="s1")
        pfl = PrivacyFilterLayer(cfg, budget, peer_agent_id="agent-xyz")

        summary = pfl.build_disclosure_summary(
            attributes_shared={"age": "late 20s", "budget": "$1,800 – $2,500"},
            attributes_withheld=["income"],
            outcome="Tentative match",
        )
        assert "agent-xyz" in summary
        assert "late 20s" in summary
        assert "income" in summary.lower()
        assert "Tentative match" in summary


# ===========================================================================
# Negotiation helpers
# ===========================================================================


class TestMakeOffer:
    def test_offer_within_range(self):
        rng = random.Random(42)
        for r in range(1, 5):
            offer = make_offer(1000, 2000, round_number=r, total_rounds=4, rng=rng)
            assert offer >= 10
            # midpoint = 1000 + 1000*(r/4); noise ±5% of range (±50); rounding ±5
            # So offer should be well above floor and below ceiling with headroom
            assert offer >= 900
            assert offer <= 2100

    def test_offer_increases_over_rounds(self):
        rng = random.Random(0)
        offers = [
            make_offer(1000, 2000, round_number=r, total_rounds=4, rng=rng)
            for r in range(1, 5)
        ]
        # Midpoints jump by 250 per round, far exceeding noise (±50),
        # so the sequence must be strictly increasing even with noise.
        for i in range(len(offers) - 1):
            assert offers[i] < offers[i + 1], (
                f"Offer in round {i + 1} ({offers[i]}) should be less than "
                f"offer in round {i + 2} ({offers[i + 1]})"
            )

    def test_offer_rounded_to_10(self):
        rng = random.Random(99)
        for _ in range(20):
            offer = make_offer(100, 1000, round_number=2, total_rounds=4, rng=rng)
            assert offer % 10 == 0

    def test_minimum_offer_is_10(self):
        rng = random.Random(7)
        offer = make_offer(0, 0, round_number=1, total_rounds=1, rng=rng)
        assert offer == 10

    def test_invalid_floor_ceiling(self):
        with pytest.raises(ValueError):
            make_offer(2000, 1000, round_number=1, total_rounds=4)

    def test_invalid_round_number(self):
        with pytest.raises(ValueError):
            make_offer(100, 200, round_number=0, total_rounds=4)


class TestOpeningOffer:
    def test_opening_offer_gte_floor(self):
        rng = random.Random(42)
        for _ in range(20):
            offer = opening_offer(1000, 2000, rng=rng)
            # Opening offer should be at or above the floor (rounded to 10)
            assert offer >= 990  # allow 1 rounding unit below

    def test_opening_offer_not_reveal_ceiling(self):
        rng = random.Random(42)
        for _ in range(20):
            offer = opening_offer(1000, 2000, rng=rng)
            # Opening offer is floor + up to 30% of range → max 1000 + 300 = 1300
            assert offer <= 1400  # with rounding headroom

    def test_invalid_floor_ceiling(self):
        with pytest.raises(ValueError):
            opening_offer(2000, 1000)


class TestNegotiationObfuscation:
    def test_should_pause_probability(self):
        rng = random.Random(0)
        pauses = sum(should_pause_before_accept(rng=rng) for _ in range(1000))
        # Should be roughly 25 % ± some tolerance
        assert 150 < pauses < 400

    def test_should_reject_probability(self):
        rng = random.Random(0)
        rejects = sum(should_reject_within_range(rng=rng) for _ in range(1000))
        # Should be roughly 10 % ± tolerance
        assert 50 < rejects < 200

    def test_deterministic_with_seed(self):
        rng1 = random.Random(123)
        rng2 = random.Random(123)
        assert should_pause_before_accept(rng=rng1) == should_pause_before_accept(rng=rng2)
