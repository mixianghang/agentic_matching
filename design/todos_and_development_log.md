* Try to integrate agent framework, e.g., qwen agent to run our cloud agent, making each agent confiugrable in terms of available tools, etc.
* Frontend: separate dom and business logic, e.g., using vue.js, also decoupling dom from formatting logic, e.g., using css modules
* 配置wechat以及alipay登录
* 支持支付付费功能
* 单Unit的并发机制以及多节点部署机制，实现高并发处理
* 多语言支持，作为底层，自动翻译，不需要改变默认的中文
* Top-1: 资源限制模块, 单个与整体的资源限制，无论用户是免费用户还是付费用户，都需要限制资源使用，防止滥用，防止DOS攻击。

---

## Development Log: Demand Definition Module (3-Round Enhancement)

**Scope**: `backend/demand_definition_v2.py`, `backend/demand_templates.py`, `backend/storage_sqlite.py`
**Test harness**: `tests/test_demand_integration.py` (5 simulated user personas, HTTP integration)
**Outcome**: All 5 scenarios reach `completed=True` with structured demand saved.

---

### Round 1 — Core Bugs

**Issue 1 (CRITICAL): Session context lost on every request**
- Root cause: `task.metadata` (containing `demand_session_id`) was stored in-memory but never written to SQLite. Every API call re-fetched the task without metadata → engine created a fresh session → conversation state reset to INITIAL on each turn.
- Fix: Added `metadata TEXT` column to `tasks` table via migration. Updated `_row_to_task()` to deserialize it as JSON and `update_task()` to serialize and persist it.
- Lesson: In-memory state tied to a DB-backed object is fragile. Any ORM-like layer must explicitly cycle all mutable fields through its persistence methods.

**Issue 2: Gaming demand type unrecognized**
- Root cause: `TEMPLATE_REGISTRY` had no gaming entry. `_get_dynamic_type_prompt()` built its candidate list from the registry, so the LLM was never offered GAMING as a valid type.
- Fix: Added `GAMING_PLAYER_TEMPLATE` with fields (`game_name`, `rank`, `play_time`, `play_style`, `preferred_rank`, `voice_chat`) and registered it as `"gaming_player"`.
- Lesson: Type detection is only as good as the template registry. Adding a new domain demands both a template definition and a registry entry.

**Issue 3: LLM JSON wrapped in markdown fences → `json.loads()` crash**
- Root cause: DeepSeek occasionally wraps JSON responses in ` ```json ... ``` ` fences. `json.loads()` would throw `JSONDecodeError` and the raw fenced text leaked to the user as the agent reply.
- Fix: Added `_strip_json_fences(text)` helper (strips leading/trailing ` ``` ` blocks) applied before all `json.loads()` calls in `_extract_multiple_fields`, `_generate_pipeline_response`, and `_detect_demand_type`.
- Lesson: Never trust LLM output to be clean JSON even when the prompt says "output JSON only". Always sanitize before parsing.

---

### Round 2 — UX & Extraction Reliability

**Issue 4: Enum field options missing from ACP extraction prompt**
- Root cause: `_build_acp_prompt()` listed pending fields as `name (display_name): prompt_text` but omitted valid enum options. When a user said "单间" (Chinese for single room), the LLM couldn't map it to `property_type="room"` because it didn't know "room" was a valid option.
- Fix: Added `[选项: opt1, opt2, ...]` to each enum field's description in the pending_fields block. Added a system instruction explaining common Chinese-to-enum mappings (e.g. 单间→room, 公寓→apartment).
- Lesson: ACP prompts must expose enum constraints to the LLM; otherwise the LLM hallucinates free-form values and extraction reliability degrades.

**Issue 5: UX — premature "确认" silently ignored when required fields missing**
- Root cause: When user said "确认" in COLLECTING state but required fields were incomplete, the pipeline fell through to `_generate_pipeline_response()` which asked for more info generically, without acknowledging the user's intent.
- Fix: Added a check in `_process_pipeline()`: if `_is_completion_intent_rule_based()` triggers but `_is_required_complete()` is false, return a targeted message enumerating the specific missing required fields by display name, then re-prompt.
- Lesson: Completion-intent detection and required-field validation must be coupled. An unacknowledged "确认" is a trust-breaking UX failure.

**Issue 6 (Test design): Single "确认" insufficient for two-step confirmation flow**
- Root cause: The engine's state machine requires two steps — (1) "没有了" / "确认" in COLLECTING triggers CONFIRMING and shows a summary; (2) a second "确认" in CONFIRMING state finalises the demand. Test scenarios only had one "确认" and therefore never reached COMPLETED.
- Fix: Updated all test scenarios to include both a "没有了" turn and a subsequent "确认" turn.
- Lesson: When testing multi-step state machines, explicitly model every required state transition in the test turns.

---

### Round 3 — Validation

All 5 scenarios pass end-to-end:

| Scenario | Type | Turns | Fields Saved |
|---|---|---|---|
| Rental – dense opener | rental | 4 | 8 |
| Rental – vague opener | rental | 6 | 8 |
| Dating seeker | dating | 5 | 8 |
| Gaming player | gaming | 4 | 4 |
| Rental with field correction | rental | 5 | 6 |

No further code fixes required. The module is production-ready for the current set of demand types.

---

### Key Takeaways

1. **Persistence must be explicit.** Any in-memory state that must survive a request boundary needs to be explicitly serialized and written back to the DB in every update path. Assume nothing is implicitly saved.

2. **LLM output is never clean JSON.** Always strip markdown fences and handle `JSONDecodeError` gracefully with a sensible fallback, not a raw dump to the user.

3. **Prompts must encode constraints, not just intent.** Telling the LLM "extract property_type" is insufficient if it doesn't know the valid values. Include enum options in the prompt for reliable structured extraction.

4. **Test multi-turn flows turn-by-turn.** Each test turn should correspond to one state transition. Missing a required transition leads to false negatives that look like bugs in the code but are test design issues.

5. **ACP protocol overhead is acceptable.** Using ACP v1.0 (structured JSON with `extracted`, `to_user`, `next_action`) for every collecting turn costs two LLM calls per turn (extraction + response) but delivers consistent field tracking. This trade-off is worthwhile for the reliability gain.

---

## Development Log: Matching Logic Iterations (5 Rounds)

**Scope**: `backend/agent_system.py`, `backend/demand_definition_v2.py`, `tests/test_agent_system.py`, `tests/test_demand_definition_v2.py`

### Round 1
- Issue: Live landlord flow extracted `location`, `parking`, `min_lease`, but the landlord template requires `address`, `parking_available`, `min_lease_term`.
- Fix: Added post-extraction normalization so LLM outputs are remapped into the active template schema before state progression.

### Round 2
- Issue: Rental price semantics were ambiguous; live logs showed weekly prompts but a monthly reply summary.
- Fix: Added `price_period` / `max_price_period` inference from user text and period-aware rental matching with monthly-to-weekly normalization.

### Round 3
- Issue: Rental location matching was too literal and landlord/tenant used different field names (`address` vs `location`).
- Fix: Added city-level extraction and matching fallback across both landlord and tenant location fields. Default remains city-level exact match.

### Round 4
- Issue: Gaming alias and dating age-window checks were too shallow.
- Fix: Added canonical game-name mapping (`LOL` / `英雄联盟`) and dating age-range overlap validation, while keeping gender preference mutuality.

### Round 5
- Issue: The previous test set would not catch schema aliasing, price-period conversion, or city-normalized matches.
- Fix: Added focused tests for landlord alias normalization, game alias normalization, monthly-vs-weekly rental compatibility, and dating age-range rejection.
