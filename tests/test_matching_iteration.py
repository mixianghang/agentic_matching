# -*- coding: utf-8 -*-
"""Iterative matching module tests.

Scenarios:
  S1 – Rental: tenant seeks 3BR in 合肥 ≤ 400/wk   vs landlord offering 3BR at 400/wk
  S2 – Rental: role-mismatch (two tenants)
  S3 – Rental: same role, different city (should not match)
  S4 – Gaming: two players wanting same game
  S5 – Dating: two users seeking each other's reported gender
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from backend.models import Task, TaskStatus

# ── helpers ────────────────────────────────────────────────────────────────
def make_task(tid, uid, task_type, role, demand_type, values, description=""):
    return Task(
        id=tid, user_id=uid, agent_id="ag-" + uid,
        task_type=task_type, description=description,
        requirements={}, status=TaskStatus.ACTIVE,
        created_at=datetime.now(), matched_task_ids=[],
        messages=[],
        metadata={
            "structured_demand": {
                "role": role,
                "demand_type": demand_type,
                "values": values,
            }
        },
    )


def run_and_report(agent_system, all_tasks, query_task, label):
    """Monkeypatch storage, run matching, return result list."""
    agent_system.storage.get_all_tasks = lambda: all_tasks
    results = agent_system.find_matching_tasks(query_task)
    ids = [t.id for t in results]
    print(f"  {label}: {ids}")
    return results


# ── fixtures ───────────────────────────────────────────────────────────────
tenant_hefei = make_task(
    "rental-tenant-hefei", "u1", "rental", "tenant", "rental",
    {"location": "合肥", "bedrooms": 3, "max_price": 400},
    description="rental tenant hefei 3br 400",
)
landlord_hefei = make_task(
    "rental-landlord-hefei", "u2", "rental", "landlord", "rental",
    {"location": "合肥", "bedrooms": 3, "price": 400},
    description="rental landlord hefei 3br 400",
)
tenant_hefei2 = make_task(
    "rental-tenant-hefei2", "u3", "rental", "tenant", "rental",
    {"location": "合肥", "bedrooms": 3, "max_price": 380},
    description="rental tenant hefei 3br 380",
)
tenant_nanjing = make_task(
    "rental-tenant-nanjing", "u4", "rental", "tenant", "rental",
    {"location": "南京", "bedrooms": 2, "max_price": 500},
    description="rental tenant nanjing 2br 500",
)
landlord_nanjing = make_task(
    "rental-landlord-nanjing", "u5", "rental", "landlord", "rental",
    {"location": "南京", "bedrooms": 2, "price": 480},
    description="rental landlord nanjing 2br 480",
)

gamer1 = make_task(
    "gaming-seek1", "u6", "gaming", "seeker", "gaming",
    {"game_name": "PUBG", "play_style": "competitive", "rank": "gold"},
    description="gaming PUBG competitive gold",
)
gamer2 = make_task(
    "gaming-seek2", "u7", "gaming", "seeker", "gaming",
    {"game_name": "PUBG", "play_style": "competitive", "rank": "gold"},
    description="gaming PUBG competitive gold",
)
gamer3 = make_task(
    "gaming-seek3", "u8", "gaming", "seeker", "gaming",
    {"game_name": "LoL", "play_style": "casual"},
    description="gaming LoL casual",
)

dater1 = make_task(
    "dating-m1", "u9", "dating", "seeker", "dating",
    {"gender": "male", "gender_preference": "female", "age_range": {"min": 25, "max": 35}, "location": "上海"},
    description="dating male seeking female 25-35 Shanghai",
)
dater2 = make_task(
    "dating-f1", "u10", "dating", "seeker", "dating",
    {"gender": "female", "gender_preference": "male", "age_range": {"min": 28, "max": 38}, "location": "上海"},
    description="dating female seeking male 28-38 Shanghai",
)
dater3 = make_task(
    "dating-f2", "u11", "dating", "seeker", "dating",
    {"gender": "female", "gender_preference": "female", "age_range": {"min": 22, "max": 30}, "location": "北京"},
    description="dating female seeking female 22-30 Beijing",
)

ALL_TASKS = [
    tenant_hefei, landlord_hefei, tenant_hefei2, tenant_nanjing, landlord_nanjing,
    gamer1, gamer2, gamer3,
    dater1, dater2, dater3,
]


# ── test runner ────────────────────────────────────────────────────────────
def main():
    from backend.agent_system import agent_system

    print("=" * 60)
    print("ROUND 1 – BASELINE MATCHING EVALUATION")
    print("=" * 60)

    # S1: tenant_hefei should match landlord_hefei (opposite role, same city/price)
    print("\nS1 – Rental tenant vs landlord (should match):")
    s1 = run_and_report(agent_system, ALL_TASKS, tenant_hefei, "tenant_hefei matches")
    s1_pass = any(t.id == "rental-landlord-hefei" for t in s1)
    print(f"  PASS={s1_pass}  (landlord-hefei in results)")

    # S2: tenant_hefei vs tenant_hefei2 (same role – should NOT match in role-aware system)
    print("\nS2 – Two tenants same city (role-mismatch, ideally no match):")
    s2 = run_and_report(agent_system, ALL_TASKS, tenant_hefei, "tenant_hefei all-matches")
    s2_no_same_role = not any(t.id == "rental-tenant-hefei2" for t in s2)
    print(f"  PASS={s2_no_same_role}  (tenant-hefei2 NOT in results)")

    # S3: tenant_hefei vs landlord_nanjing (different city – ideally no match)
    print("\nS3 – Tenant 合肥 vs Landlord 南京 (different city):")
    s3_pass = not any(t.id == "rental-landlord-nanjing" for t in s1)
    print(f"  PASS={s3_pass}  (landlord-nanjing NOT in results for tenant_hefei)")

    # S4: gamer1 should match gamer2 (same game), not gamer3 (different game)
    print("\nS4 – Gaming same-game vs different-game:")
    s4 = run_and_report(agent_system, ALL_TASKS, gamer1, "gamer1 matches")
    s4_same = any(t.id == "gaming-seek2" for t in s4)
    s4_diff = not any(t.id == "gaming-seek3" for t in s4)
    print(f"  PASS_same_game={s4_same}, PASS_no_diff_game={s4_diff}")

    # S5: dater1(male→female) should match dater2(female→male), not dater3(female→female)
    print("\nS5 – Dating mutual gender preference:")
    s5 = run_and_report(agent_system, ALL_TASKS, dater1, "dater1 matches")
    s5_mutual = any(t.id == "dating-f1" for t in s5)
    s5_no_mismatch = not any(t.id == "dating-f2" for t in s5)
    print(f"  PASS_mutual={s5_mutual}, PASS_no_mismatch={s5_no_mismatch}")

    print("\n" + "=" * 60)
    passes = [s1_pass, s2_no_same_role, s3_pass, s4_same, s4_diff, s5_mutual, s5_no_mismatch]
    print(f"SUMMARY: {sum(passes)}/{len(passes)} checks PASS")
    print("=" * 60)

    return passes


def round3(agent_system):
    print("\n" + "=" * 60)
    print("ROUND 3 – EDGE CASES")
    print("=" * 60)

    # E1: Price mismatch – tenant max 300 < landlord 400 → should NOT match
    cheap_tenant = make_task(
        "rental-tenant-cheap", "u20", "rental", "tenant", "rental",
        {"location": "合肥", "bedrooms": 3, "max_price": 300},
        description="rental tenant hefei 3br 300",
    )
    e1 = run_and_report(agent_system, ALL_TASKS + [cheap_tenant], cheap_tenant,
                        "cheap_tenant (max 300) matches")
    e1_pass = not any(t.id == "rental-landlord-hefei" for t in e1)
    print(f"  PASS={e1_pass}  (landlord-hefei at 400 NOT in results when budget is 300)")

    # E2: No structured demand → falls back to type-only (landlord_hefei still appears)
    bare_tenant = Task(
        id="bare-tenant", user_id="u21", agent_id="ag-u21",
        task_type="rental", description="i need somewhere to rent",
        requirements={}, status=TaskStatus.ACTIVE,
        created_at=datetime.now(), matched_task_ids=[], messages=[],
        metadata={},  # no structured_demand
    )
    e2 = run_and_report(agent_system, ALL_TASKS + [bare_tenant], bare_tenant,
                        "bare_tenant (no demand) matches")
    e2_pass = any(t.id == "rental-landlord-hefei" for t in e2)
    print(f"  PASS={e2_pass}  (landlord-hefei in results even without structured demand)")

    # E3: Bedroom mismatch – 3BR tenant vs 1BR landlord (now filtered out)
    landlord_1br = make_task(
        "rental-landlord-1br", "u22", "rental", "landlord", "rental",
        {"location": "合肥", "bedrooms": 1, "price": 300},
        description="rental landlord hefei 1br 300",
    )
    e3 = run_and_report(agent_system, ALL_TASKS + [cheap_tenant, landlord_1br],
                        cheap_tenant, "cheap_tenant (3BR, 300) vs 1BR landlord 300")
    e3_pass = not any(t.id == "rental-landlord-1br" for t in e3)
    print(f"  PASS={e3_pass}  (1BR landlord NOT in results for 3BR tenant)")

    # E4: Gaming – one task missing game_name, other has game_name → permissive match
    gamer_unknown = make_task(
        "gaming-no-game", "u23", "gaming", "seeker", "gaming",
        {"play_style": "casual"},  # no game_name
        description="gaming casual no game specified",
    )
    e4 = run_and_report(agent_system, ALL_TASKS + [gamer_unknown], gamer_unknown,
                        "gamer_unknown (no game_name) matches")
    # Should match all gaming tasks (no game_name means no filter)
    e4_pass = all(t.task_type == "gaming" for t in e4) and len(e4) == 3
    print(f"  PASS={e4_pass}  (gamer with no game_name matches all 3 gaming tasks)")

    print("\n" + "=" * 60)
    passes = [e1_pass, e2_pass, e3_pass, e4_pass]
    print(f"  PASS: {sum(passes)}/{len(passes)} edge cases")
    print("=" * 60)
    return passes


if __name__ == "__main__":
    results = main()
    from backend.agent_system import agent_system as _sys
    extra = round3(_sys)
    all_ok = all(results) and all(extra)
    print("\nOVERALL: all hard checks pass =", all_ok)
    sys.exit(0 if all_ok else 1)
