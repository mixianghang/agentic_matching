# Development Log

## Demand Extraction V3 → DemandEngine (2026-05-10)

### Round 2 — Documentation & Code Comments Sync

**Scope**: Added module-level and class-level comments to all demand-related modules, referencing the V2.0 design doc. Updated ROADMAP.md (V2.0 marked Done, V1.0 marked replaced, migration tasks removed from Phase 1/3). Updated DASHBOARD.md (consolidated redundant status rows, Milestone 6 marked Complete with deliverables summary).

**Files with added comments**: `backend/demand_engine.py` (module docstring + DemandEngine class docstring), `backend/demand_models.py` (module docstring + FieldType/DemandSchema/MatchingDimension/StructuredDemand class docstrings), `backend/schema_registry.py` (module docstring), `backend/content_safety.py` (module docstring), `backend/matching/comparators.py` (module docstring), `backend/matching/generic_engine.py` (module docstring), `backend/matching/__init__.py` (module docstring).

**Design docs synced**: `design/ROADMAP.md`, `design/DASHBOARD.md`

### Round 1 — Full Migration & V1/V2 Cleanup

**Scope**: Rename `DemandExtractionEngineV3` → `DemandEngine` in `backend/demand_engine.py`. Delete `backend/demand_definition_v2.py`, `backend/demand_templates.py`. Move `FieldType` enum into `demand_models.py`. Remove `DEMAND_ENGINE_VERSION` toggle; `AgentSystem` uses `DemandEngine` exclusively. Remove `/api/demand_templates` endpoint; add `/api/schemas` using `SchemaRegistry`.

**Files deleted**: `backend/demand_definition_v2.py` (1549 lines), `backend/demand_templates.py` (453 lines), `tests/test_demand_definition_v2.py` (617 lines)

**Files renamed**: `backend/demand_extraction_v3.py` → `backend/demand_engine.py`, `tests/test_demand_extraction_v3.py` → `tests/test_demand_engine.py`

**Intent classification fix**: `_classify_intent()` now includes full conversation history (last 8 messages) in the prompt, enabling the LLM to derive demand type from accumulated context, not just the current message.

**Result**: 171 tests pass, zero regressions. Codebase reduced by ~2600 lines of legacy code.

### Round 0 — Initial Implementation (2026-05-10)

**Scope**: `backend/demand_models.py`, `backend/demand_extraction_v3.py`, `backend/schema_registry.py`, `backend/content_safety.py`, `backend/matching/comparators.py`, `backend/matching/generic_engine.py`, `backend/agent_system.py`, `tests/test_demand_extraction_v3.py`

**Design**: `design/demand_definition_design_v2.0.md` — schema-on-read, dynamic type discovery, dimension-based generic matching

**Result**: 42 new tests (model roundtrips, schema CRUD, content safety, 6 comparators, generic matching engine, extraction engine), 203 total test suite passes, no regressions. V3 engine runs alongside V2 via `DEMAND_ENGINE_VERSION=v3` env toggle.

### Architecture Decisions

1. **Schema-on-read via Dynamic Schema Registry**: Instead of hardcoding `TaskType` constants and `TEMPLATE_REGISTRY`, demand types are stored as `DemandSchema` records in a `demand_schemas` SQLite table. New types are registered at runtime via `SchemaRegistry.register()` and auto-activated after 3 uses (`pending → active`). This eliminates the code-change requirement for adding new demand types.

2. **Three-layer Extraction Pipeline**: Content safety blocklist → Intent classification (type + role) → Schema-aware field extraction. Safety runs before any LLM call; blocklisted messages (drugs, adult content, gambling, weapons, harassment, self-harm) are rejected immediately.

3. **MatchingDimension as Matching Contract**: Instead of hardcoded `_score_rental()`, `_score_dating()`, `_score_gaming()`, matching is defined declaratively. Each `DemandSchema` contains `List[MatchingDimension]` with comparator type, weight, and field resolution paths. `GenericMatchingEngine` executes comparators without understanding business semantics. Supports 6 built-in comparators: exact, enum_compatible, range_overlap, numeric_compatibility, geo_proximity, semantic_similarity.

4. **Backward Compatibility**: V3 engine coexists with V2. `agent_system.py` routes via `DEMAND_ENGINE_VERSION` env var (default `v2`). V3 StructuredDemands are tagged with `engine_version: "v3"` in task metadata; `find_matching_tasks()` dispatches V3 demands to `GenericMatchingEngine` and V2 demands to the legacy per-type scorers.

### Known Issues

- **Blocklist uses substring match, not regex**: Changed from `\b` word-boundary patterns to simple keyword matching because `\b` does not work with CJK characters.
- **Dating schema lacks user's own gender field**: The dating schema only collects `gender_preference` (what the user wants), not the user's own gender. This means `_score_dating()` cannot perform mutual gender preference matching — the V3 GenericMatchingEngine correctly rejects two seekers with incompatible gender preferences.
- **SchemaRegistry singleton pattern**: `__init__` returns early if `_initialized` is True, making it impossible to create multiple isolated registry instances for testing. Test fixtures work around this by directly manipulating `_schemas`.

### LLM Call Count

V3 does fewer LLM calls per demand cycle than V2:
- V2: Type detection + Role detection + ACP extraction + Response generation = 4 calls/turn typical
- V3: Intent detect (combined type+role) + Extraction + Response = 3 calls/turn typical; safety layer only runs on first message

### Files Changed

| File | Status | Description |
|------|--------|-------------|
| `backend/demand_models.py` | New | 8 dataclasses: DemandSchema, SchemaField, MatchingDimension, FieldValue, Constraint, SemanticRequirement, StructuredDemand, ExtractionState |
| `backend/demand_extraction_v3.py` | New | 3-layer extraction engine with 8-state pipeline |
| `backend/schema_registry.py` | New | Schema CRUD with SQLite persistence, singleton pattern, 3 default schemas |
| `backend/content_safety.py` | New | Content safety filter with blocklist + LLM classifier |
| `backend/matching/comparators.py` | New | 6 built-in comparators with dispatcher |
| `backend/matching/generic_engine.py` | New | Generic matching engine driven by MatchingDimensions |
| `backend/matching/__init__.py` | Modified | Re-exports old matching classes + new V3 classes |
| `backend/agent_system.py` | Modified | Dual-engine support: V2 (default) / V3 (via `DEMAND_ENGINE_VERSION`); `get_demand_progress()` updated; `find_matching_tasks()` dispatches to `GenericMatchingEngine` for V3 demands |
| `tests/test_demand_extraction_v3.py` | New | 42 tests across 5 test classes |
| `design/demand_definition_design_v2.0.md` | New | V2.0 design doc (936 lines) |
| `design/ROADMAP.md` | Modified | Added 4-phase V3 migration plan |
| `design/DASHBOARD.md` | Modified | Added V2.0 design doc + updated status |
| `design/README.md` | Modified | Added V2.0 to document index |
| `AGENTS.md` | Modified | Added V2.0 design doc reference |

---

## Demand Definition Module (3 Rounds)

**Scope**: `backend/demand_definition_v2.py`, `backend/demand_templates.py`, `backend/storage_sqlite.py`
**Test**: `tests/test_demand_integration.py` (5 simulated user personas, HTTP integration)
**Result**: All 5 scenarios reach `completed=True` with structured demand saved.

### Round 1 — Core Bugs

**CRITICAL: Session context lost on every request**
- Root cause: `task.metadata` (containing `demand_session_id`) was stored in-memory but never written to SQLite. Every API call re-fetched the task without metadata → engine created a fresh session → conversation state reset to INITIAL on each turn.
- Fix: Added `metadata TEXT` column to `tasks` table via migration. Updated `_row_to_task()` to deserialize it as JSON and `update_task()` to serialize and persist it.
- Lesson: In-memory state tied to a DB-backed object is fragile. Any ORM-like layer must explicitly cycle all mutable fields through its persistence methods.

**Gaming demand type unrecognized**
- Root cause: `TEMPLATE_REGISTRY` had no gaming entry. `_get_dynamic_type_prompt()` built its candidate list from the registry, so the LLM was never offered GAMING as a valid type.
- Fix: Added `GAMING_PLAYER_TEMPLATE` with fields (`game_name`, `rank`, `play_time`, `play_style`, `preferred_rank`, `voice_chat`) and registered it as `"gaming_player"`.
- Lesson: Type detection is only as good as the template registry. Adding a new domain demands both a template definition and a registry entry.

**LLM JSON wrapped in markdown fences → `json.loads()` crash**
- Root cause: DeepSeek occasionally wraps JSON responses in ` ```json ... ``` ` fences. `json.loads()` would throw `JSONDecodeError` and the raw fenced text leaked to the user as the agent reply.
- Fix: Added `_strip_json_fences(text)` helper applied before all `json.loads()` calls.
- Lesson: Never trust LLM output to be clean JSON even when the prompt says "output JSON only". Always sanitize before parsing.

### Round 2 — UX & Extraction Reliability

**Enum field options missing from ACP extraction prompt**
- Root cause: `_build_acp_prompt()` listed pending fields as `name (display_name): prompt_text` but omitted valid enum options. When a user said "单间" (Chinese for single room), the LLM couldn't map it to `property_type="room"` because it didn't know "room" was a valid option.
- Fix: Added `[选项: opt1, opt2, ...]` to each enum field's description in the pending_fields block. Added a system instruction explaining common Chinese-to-enum mappings (e.g. 单间→room, 公寓→apartment).
- Lesson: ACP prompts must expose enum constraints to the LLM; otherwise the LLM hallucinates free-form values and extraction reliability degrades.

**Premature "确认" silently ignored when required fields missing**
- Root cause: When user said "确认" in COLLECTING state but required fields were incomplete, the pipeline fell through to `_generate_pipeline_response()` which asked for more info generically, without acknowledging the user's intent.
- Fix: Added check in `_process_pipeline()`: if `_is_completion_intent_rule_based()` triggers but `_is_required_complete()` is false, return a targeted message enumerating the specific missing required fields by display name, then re-prompt.
- Lesson: Completion-intent detection and required-field validation must be coupled. An unacknowledged "确认" is a trust-breaking UX failure.

**Test design: Single "确认" insufficient for two-step confirmation flow**
- Root cause: The engine's state machine requires two steps — (1) "没有了" / "确认" in COLLECTING triggers CONFIRMING and shows a summary; (2) a second "确认" in CONFIRMING state finalises the demand. Test scenarios only had one "确认" and therefore never reached COMPLETED.
- Fix: Updated all test scenarios to include both a "没有了" turn and a subsequent "确认" turn.
- Lesson: When testing multi-step state machines, explicitly model every required state transition in the test turns.

### Round 3 — Validation

All 5 scenarios pass end-to-end:

| Scenario | Type | Turns | Fields Saved |
|---|---|---|---|
| Rental – dense opener | rental | 4 | 8 |
| Rental – vague opener | rental | 6 | 8 |
| Dating seeker | dating | 5 | 8 |
| Gaming player | gaming | 4 | 4 |
| Rental with field correction | rental | 5 | 6 |

---

## Matching Logic Iterations (5 Rounds)

**Scope**: `backend/agent_system.py`, `backend/demand_definition_v2.py`, tests

### Round 1 — Schema normalization
- Issue: Live landlord flow extracted `location`, `parking`, `min_lease`, but the landlord template requires `address`, `parking_available`, `min_lease_term`.
- Fix: Added post-extraction normalization so LLM outputs are remapped into the active template schema before state progression.

### Round 2 — Price period normalization
- Issue: Rental price semantics were ambiguous; live logs showed weekly prompts but a monthly reply summary.
- Fix: Added `price_period` / `max_price_period` inference from user text and period-aware rental matching with monthly-to-weekly normalization.

### Round 3 — Location matching fallback
- Issue: Rental location matching was too literal and landlord/tenant used different field names (`address` vs `location`).
- Fix: Added city-level extraction and matching fallback across both landlord and tenant location fields. Default remains city-level exact match.

### Round 4 — Game alias & age matching
- Issue: Gaming alias and dating age-window checks were too shallow.
- Fix: Added canonical game-name mapping (`LOL` / `英雄联盟`) and dating age-range overlap validation, while keeping gender preference mutuality.

### Round 5 — Test coverage
- Issue: The previous test set would not catch schema aliasing, price-period conversion, or city-normalized matches.
- Fix: Added focused tests for landlord alias normalization, game alias normalization, monthly-vs-weekly rental compatibility, and dating age-range rejection.

---

## Key Takeaways

1. **Persistence must be explicit.** Any in-memory state that must survive a request boundary needs to be explicitly serialized and written back to the DB in every update path. Assume nothing is implicitly saved.

2. **LLM output is never clean JSON.** Always strip markdown fences and handle `JSONDecodeError` gracefully with a sensible fallback, not a raw dump to the user.

3. **Prompts must encode constraints, not just intent.** Telling the LLM "extract property_type" is insufficient if it doesn't know the valid values. Include enum options in the prompt for reliable structured extraction.

4. **Test multi-turn flows turn-by-turn.** Each test turn should correspond to one state transition. Missing a required transition leads to false negatives that look like bugs in the code but are test design issues.

5. **ACP protocol overhead is acceptable.** Using ACP v1.0 (structured JSON with `extracted`, `to_user`, `next_action`) for every collecting turn costs two LLM calls per turn (extraction + response) but delivers consistent field tracking. This trade-off is worthwhile for the reliability gain.

---

## Privacy-Preserving Agentic Matching Module

**Scope**: `backend/privacy/` (new package), `tests/test_privacy.py`
**Design reference**: `design/privacy_preserving_agentic_matching_v1.0.md`
**Test harness**: 83 unit tests across 6 test classes, all passing.

---

### Implementation Design

The module is structured as five focused sub-modules under `backend/privacy/`:

| Sub-module | Responsibility |
|---|---|
| `coarsening.py` | Attribute sensitivity taxonomy + coarsening functions |
| `disclosure.py` | `DisclosureConfig`, `SessionDisclosureBudget`, `DisclosureEvent` |
| `filter.py` | `PrivacyFilterLayer` (4-stage pipeline) |
| `negotiation.py` | `make_offer`, `opening_offer`, strategy-obfuscation helpers |
| `audit.py` | `AuditLog` append-only per-user audit log |

#### `coarsening.py` — Attribute Coarsening (§3)

Implements the 4-level sensitivity taxonomy and all coarsening functions exactly as specified in the design document:

- `coarsen_age(age)` → age band string ("18–24", "late 20s", …)
- `coarsen_annual_income(income_usd)` → income tier string
- `coarsen_rent_budget(monthly_usd)` → rent range string
- `coarsen_occupation(job_title)` → broad category via keyword mapping (technology, healthcare, education, finance, creative, legal, retail, other)
- `coarsen_location(city, neighbourhood, street_address, target_level)` → max-shareable location at the requested level; raises `ValueError` for Level-3 (street address)

#### `disclosure.py` — Disclosure Controls (§3.3, §4.3, §9)

- `DisclosureLevel` enum: NONE, COARSE, EXACT, CITY, DISTRICT, CATEGORY, RANGE
- `DisclosureConfig(demand_id)`: per-demand disclosure settings with defaults from the sensitivity table (age→COARSE, income→NONE, occupation→CATEGORY, location→CITY, budget→RANGE). Supports `tighten()`, `widen()`, `revoke()` user controls (§8.2).
- `SessionDisclosureBudget(session_id, max_attributes_revealed=5)`: tracks distinct Level-1 attributes revealed per session. `can_reveal()` returns True for already-disclosed attributes (free repeat). `budget_exhausted` and `remaining_budget` properties.
- `DisclosureEvent`: immutable dataclass with UUID event_id, UTC timestamp, demand_id, session_id, peer_agent_id, attribute_name, coarse_value, round_number.

#### `filter.py` — Privacy Filter Layer (§4)

`PrivacyFilterLayer` runs a 4-stage pipeline on every outbound agent message:

1. **Pattern scanner** (§4.2): regex detection of phone numbers, email addresses, SSNs, long numeric IDs, and street addresses. Any match → `FilterResult(blocked=True)`.
2. **Coarsening transformer**: replaces exact private values from a `private_values` dict with their coarse equivalents; redacts values whose disclosure level is NONE.
3. **Disclosure-budget checker** (§4.3): blocks the message if any newly-coarsened attribute would exceed the session budget.
4. **Output validator** (§4.4): final pass blocking exact currency amounts and exact age statements that may have slipped through.

Returns a `FilterResult(message, blocked, reasons, fallback, disclosed_attributes)`. Also provides `build_disclosure_summary()` for the post-session disclosure summary (§8.1).

#### `negotiation.py` — Negotiation Privacy (§6)

- `opening_offer(floor, ceiling)`: first offer at floor + uniform random offset in [0%, 30%] of the range, rounded to nearest $10.
- `make_offer(floor, ceiling, round_number, total_rounds)`: offer converges from floor toward midpoint over rounds with ±5% noise and rounding to $10. Minimum value is always $10.
- `should_pause_before_accept(pause_probability=0.25)`: 25% chance of strategic pause before accepting.
- `should_reject_within_range(reject_probability=0.10)`: 10% chance of rejecting a technically-acceptable offer.

All functions accept an optional `rng` parameter for reproducible testing.

#### `audit.py` — Audit Log (§9)

`AuditLog`: in-process append-only store partitioned by `user_id`. Supports:
- `append(user_id, event)`: O(1) insert.
- `get_events(user_id, session_id=None, demand_id=None)`: filtered read.
- `purge(user_id)`: full deletion (account deletion only).
- Module-level singleton `audit_log` for production use.

---

### Testing Results

**Test file**: `tests/test_privacy.py` — 83 tests, 0 failures.

| Test class | Tests | Coverage |
|---|---|---|
| `TestCoarsenAge` | 10 | All age bands + boundary + invalid |
| `TestCoarsenAnnualIncome` | 8 | All income tiers + boundaries |
| `TestCoarsenRentBudget` | 7 | All rent ranges + boundary |
| `TestCoarsenOccupation` | 9 | All categories + fallback |
| `TestCoarsenLocation` | 4 | Public / semi-private / private guard |
| `TestDisclosureConfig` | 6 | Defaults + tighten/widen/revoke + custom override |
| `TestSessionDisclosureBudget` | 5 | Reveal, repeat, exhaustion, remaining |
| `TestDisclosureEvent` | 1 | Construction + auto-fields |
| `TestAuditLog` | 7 | Append, filter, purge, count, isolation |
| `TestPrivacyFilterLayerPatternScanner` | 5 | Clean + phone + email + street + ID |
| `TestPrivacyFilterLayerCoarsening` | 4 | Age replace, income redact, tighten, tracking |
| `TestPrivacyFilterLayerBudget` | 2 | Exhausted blocks, repeat free |
| `TestPrivacyFilterLayerOutputValidator` | 2 | Currency + age statement |
| `TestDisclosureSummary` | 1 | Summary format |
| `TestMakeOffer` | 6 | Range, monotonicity, rounding, minimum, errors |
| `TestOpeningOffer` | 3 | Floor bound, ceiling bound, error |
| `TestNegotiationObfuscation` | 3 | Pause prob, reject prob, deterministic seed |

Full test suite (original 81 + new 83): **164 passed, 0 failed**.

---

### Key Design Decisions

1. **No external NER dependency**: The pattern scanner uses regex only, keeping the module dependency-free. NER-based scanning is noted as a future enhancement.

2. **Coarsening is attribute-name-keyed**: The `_apply_coarsening` step in the filter uses a `private_values: Dict[str, value]` dict so callers never need to invoke coarsening functions directly; the filter dispatches automatically.

3. **Repeating an already-disclosed attribute is free**: The `SessionDisclosureBudget.can_reveal()` short-circuits for attributes already in `attributes_revealed`. This matches the design spec and avoids penalising agents for natural conversation repetition.

4. **All randomisation accepts an optional `rng` parameter**: Every negotiation function accepts an optional `random.Random` instance, making the entire negotiation layer deterministically testable without monkey-patching.

5. **Audit log is in-process only**: The current `AuditLog` stores events in memory. Persistence to SQLite can be added by extending `StorageSQLite` following the same pattern as the existing `tasks` table.

---

### Open Items / Future Work

- Integrate `PrivacyFilterLayer` into the live agent message path in `agent_system.py` (requires wrapping `create_user_agent_interaction` output).
- Persist `DisclosureEvent` records via `storage_sqlite.py` for durability across restarts.
- Add NER-based scanner (e.g., spaCy `en_core_web_sm`) as an optional enhancement once the dependency cost is acceptable.
- Expose `DisclosureConfig` controls through the REST API so users can adjust settings via the frontend.
