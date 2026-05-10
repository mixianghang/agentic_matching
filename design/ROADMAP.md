# Agentic Matching System — Roadmap & Status

## Current Status (May 2026)

| Module | Status | Notes |
|--------|--------|-------|
| **Backend framework** | ✅ Done | FastAPI with lifespan, logging, structured error handling |
| **Data models** | ✅ Done | User, Agent, Task, Message, Token (Pydantic v2) |
| **Storage layer** | ✅ Done | InMemory (test), SQLite (dev), PostgreSQL interface defined |
| **Agent system** | ✅ Done | LLM gateway, fallback for missing API key, ACP protocol integration |
| **Demand definition (V1.0)** | ✅ Done (replaced) | Template-driven, 3 types, 5-scenario tested; superseded by V2.0 |
| **Demand Engine (V2.0)** | ✅ Done | Schema-on-read, dynamic SchemaRegistry, 3-layer extraction, content safety, GenericMatchingEngine with 6 comparators (see design/demand_definition_design_v2.0.md) |
| **Matching algorithm** | ✅ Done | GenericMatchingEngine with 6 built-in comparators; per-type scoring removed |
| **Auth** | ✅ Done | Local (bcrypt + JWT), WeChat SSO, Alipay SSO |
| **ASR / Voice input** | ✅ Done | Browser recording → backend proxy → Whisper-compatible endpoint |
| **Frontend** | ✅ Done | Vue 3 + Vite + Vant 4 + Pinia, login, chat, task list, info panel |
| **Privacy layer** | ✅ Done | `backend/privacy/`: coarsening, 4-stage filter, disclosure budget, negotiation obfuscation, audit log (83 tests) |
| **Privacy filter integration** | ⚠️ Pending | `PrivacyFilterLayer` not yet wired into `agent_system.py` live path |
| **Multi-agent negotiation** | ❌ Not started | Agent-to-agent dialogue pipeline designed but not implemented |
| **Reputation system** | ❌ Not started | Agent-driven verification design written, implementation pending |
| **Memory system** | ❌ Not started | Long/short-term memory design written, not implemented |

---

## Phase 1: Production Readiness (Next 2–4 weeks)

| Priority | Task | Effort | Why |
|----------|------|--------|-----|
| P0 | Wire PrivacyFilterLayer into agent message path | 3d | Privacy module is implemented but not connected to live path |
| P0 | A2A negotiation (agent-to-agent chat pipeline) | 5d | Core differentiator; per `chat_based_agentic_matching_v1.0.md` design |
| P0 | PostgreSQL production deployment | 3d | SQLite cannot scale to concurrent production loads |
| P1 | Rate limiting & resource quotas | 3d | Prevent abuse, enable metered usage for free/paid tiers |
| P1 | WebSocket real-time updates | 3d | Users need push notifications for match progress |
| P1 | Disclosure config REST API | 2d | Expose `DisclosureConfig` controls for user self-service |
| P2 | CI/CD pipeline | 2d | Automated test + deploy for faster iteration |

---

## Phase 2: Trust & Verification (1–2 months)

| Priority | Task | Effort | Why |
|----------|------|--------|-----|
| P0 | Credential attestation framework | 7d | Foundation for verified reputation; cryptographic signing of credentials |
| P0 | Health certificate verification | 5d | Critical for intimate/medical use cases; STD test verification flow |
| P1 | Identity verification (government ID + face match) | 5d | Required for high-trust transactions (rental, legal, medical) |
| P1 | Multi-dimensional reputation model | 5d | Replace star ratings with composable trust signals |
| P1 | Progressive disclosure protocol | 5d | Negotiate what information to reveal and when during agent dialogue |
| P2 | Differential privacy implementation | 5d | Protect sensitive attributes during matching and negotiation |

---

## Phase 3: Platform Scale (2–4 months)

| Priority | Task | Effort | Why |
|----------|------|--------|-----|
| P0 | Distributed agent runtime (multi-node) | 10d | Horizontal scaling for agent processing |
| P1 | Long/short memory system | 7d | Vector-based user profiling for smarter matching and prefilling |
| P1 | Tool registry & plugin system | 7d | Extensible tools: face verify, document scan, property lookup, geo-filter |
| P1 | Payment & billing integration | 5d | Support paid tiers, per-match fees, premium verification |
| P2 | WeChat Mini Program | 7d | Primary distribution channel in China |
| P2 | Data import pipeline | 5d | Batch import from offline sources (e.g., 相亲角 paper ads) |
| P2 | Multi-language support | 3d | English + auto-translation layer |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| API response time | < 500ms p95 |
| Concurrent users | > 1000 (Phase 2) |
| Matching precision@5 | > 60% user-accepted matches |
| Credential verification accuracy | > 99% |
| Test coverage | > 80% |
| Deployment time | < 5 min (CI/CD) |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM API rate limits / cost | Blocks all agent functionality | Caching, tiered models (small local for simple tasks), fallback to rule-based |
| Privacy regulation compliance | Legal liability | Differential privacy, data minimization, right-to-deletion |
| Fraudulent credential submissions | Undermines reputation system | Require third-party attestation (clinics, government APIs), manual audit for high-stakes transactions |
| Cold start (empty user base) | No matches possible | Seed data, synthetic demand generation, focus on high-retention niche first |
| Multi-language LLM quality | Poor UX for non-Chinese users | English prompt templates, model selection by language |
