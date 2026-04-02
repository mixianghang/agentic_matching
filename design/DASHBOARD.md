# Agentic Matching System — Design Dashboard

> **Purpose**: Single entry-point for all design documentation. Start here to understand system goals, architecture, and where to read more.

---

## Table of Contents

1. [System Vision](#1-system-vision)
2. [Key Design Principles](#2-key-design-principles)
3. [Architecture at a Glance](#3-architecture-at-a-glance)
4. [Module Index — Design Docs](#4-module-index--design-docs)
5. [Implementation Status](#5-implementation-status)
6. [Next Milestones](#6-next-milestones)

---

## 1. System Vision

Agentic Matching replaces form-based marketplaces (dating, rental, gaming, etc.) with an **agent-mediated conversation model**: each user is represented online by one or more intelligent agents that collect requirements, discover candidates, negotiate details, and close matches — all autonomously.

**Supported domains today**: rental, dating, gaming  
**Designed to extend to**: property trading, ride-sharing/carpool, second-hand goods, and any structured two-sided market

---

## 2. Key Design Principles

| # | Principle | Description |
|---|-----------|-------------|
| 1 | **Agent-per-user** | Every user has ≥1 agent that acts as their persistent online representative across tasks |
| 2 | **Conversation over forms** | Demands are captured through natural-language multi-turn dialogue; no static forms |
| 3 | **Structured extraction via ACP** | Agent Communication Protocol v1.0 separates user-facing replies from structured field extraction and system metadata in a single LLM call |
| 4 | **Privacy-first disclosure** | User data is coarsened to the minimum sensitivity level required before any agent-to-agent exchange; each session has a disclosure budget |
| 5 | **Pluggable storage** | A `StorageBackend` abstraction allows swapping InMemory → SQLite → PostgreSQL without touching business logic |
| 6 | **Domain-aware matching** | Each task type (rental, dating, gaming) has its own scoring function; a factory pattern selects the correct scorer |
| 7 | **Continuous task lifecycle** | A task runs indefinitely until the user marks it complete; the agent can re-negotiate or update requirements at any time |
| 8 | **Extensible tool system** | Agents can invoke domain-specific tools (ID verification, face recognition, property validation) as plugins |
| 9 | **Offline data import** | Supports bulk import of offline data (e.g., paper matchmaking ads from public parks) into the agent system |

---

## 3. Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                          Frontend Layer                         │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Web (Vue 3)     │  │ WeChat OA    │  │  Telegram Bot    │  │
│  │  3-col desktop   │  │  (planned)   │  │   (planned)      │  │
│  │  mobile tabs     │  └──────────────┘  └──────────────────┘  │
│  └──────────────────┘                                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST API + WebSocket (planned)
┌───────────────────────────▼─────────────────────────────────────┐
│                        FastAPI Backend                          │
│  Auth · Task CRUD · Message routing · SSO (WeChat/Alipay)      │
│  Voice ASR proxy · Demand progress API · Matches API           │
└──────────┬────────────────────────────┬────────────────────────┘
           │                            │
  ┌────────▼────────┐         ┌────────▼────────────────────────┐
  │  Agent System   │         │         Storage Layer           │
  │                 │         │  InMemory / SQLite / Postgres   │
  │ • Demand engine │         └────────────────────────────────┘
  │   (ACP v1.0)   │
  │ • Matching      │         ┌─────────────────────────────────┐
  │   (per-type)   │         │         Privacy Layer           │
  │ • Negotiation  │────────>│  Coarsening · Filter · Budget   │
  │ • Memory       │         │  Disclosure audit log           │
  │   (planned)    │         └─────────────────────────────────┘
  └─────────────────┘
           │
  ┌────────▼────────┐
  │  Tool Plugins   │
  │  (planned)      │
  │ • ID verify     │
  │ • Face recog.   │
  │ • Property cert │
  └─────────────────┘
```

---

## 4. Module Index — Design Docs

### Core System

| Document | What it covers |
|----------|---------------|
| [DESIGN.md](DESIGN.md) | Overall system architecture, data models (User/Agent/Task/Message), frontend layout, tech stack, and workflow sequence diagrams |
| [ROADMAP.md](ROADMAP.md) | Milestone table, priority matrix, success metrics, risk assessment, and phased tech-stack evolution |
| [design_overview.md](design_overview.md) | High-level design overview and system summary |

### Agent & Conversation

| Document | What it covers |
|----------|---------------|
| [agent_comm_protocol_v1.0.md](agent_comm_protocol_v1.0.md) | **ACP v1.0** — structured XML/JSON message format that fuses multi-source inputs (user, system, memory) and separates outputs (to_user, to_system, extracted fields). Demand state machine: INITIAL → COLLECTING → CONFIRMING → COMPLETED |
| [demand_definition_design_v1.0.md](demand_definition_design_v1.0.md) | 5-phase demand collection flow; template registry (rental/dating/gaming/carpool/property/etc.); progressive refinement; smart prefilling from history |
| [chat_based_agentic_matching_v1.0.md](chat_based_agentic_matching_v1.0.md) | End-to-end matching pipeline: demand registration → candidate discovery → agent pre-screening → **agent-to-agent negotiation chat** → shortlist generation |

### Memory

| Document | What it covers |
|----------|---------------|
| [long_short_memory_design_v1.0.md](long_short_memory_design_v1.0.md) | Dual-layer memory: **short-term** (Redis, 24 h TTL) for conversation context and entity extraction; **long-term** (DB) for user profile, history, learned preferences; intent recognition and sentiment analysis |

### Privacy

| Document | What it covers |
|----------|---------------|
| [privacy_preserving_agentic_matching_v1.0.md](privacy_preserving_agentic_matching_v1.0.md) | 4-level sensitivity taxonomy (PUBLIC → COARSE → SEMI-PRIVATE → PRIVATE); coarsening functions for age/income/budget/occupation/location; 4-stage privacy filter pipeline; disclosure budget; negotiation obfuscation; user controls; audit trail |

### Storage

| Document | What it covers |
|----------|---------------|
| [persistence_design.md](persistence_design.md) | `StorageBackend` abstraction with pluggable backends (InMemory, SQLite, PostgreSQL); interface contract for User/Agent/Task/Message/Token CRUD |

### Frontend

| Document | What it covers |
|----------|---------------|
| [frontend_refactor.md](frontend_refactor.md) | Vue 3 + TypeScript + Vite + Pinia + Vant 4 architecture; component hierarchy (TaskList, ChatArea, InfoPanel, MessageBubble); responsive layout strategy (desktop 3-column ↔ mobile tab panel) |
| [voice_input_design_v1.0.md](voice_input_design_v1.0.md) | MediaRecorder API → backend ASR proxy (OpenAI-compatible) → auto-populated chat input; max 60-second recordings |

### Development Log

| Document | What it covers |
|----------|---------------|
| [todos_and_development_log.md](todos_and_development_log.md) | Chronological implementation log with bug analysis and lessons learned: demand definition (3 rounds), matching logic (5 rounds), privacy module (83 tests). Also contains backlog TODOs |

---

## 5. Implementation Status

| Module | Status | Notes |
|--------|--------|-------|
| FastAPI backend + CRUD | ✅ Complete | Auth, tasks, messages, SSO, voice ASR |
| SQLite storage | ✅ Complete | Task metadata persistence, pluggable backend |
| Demand definition (ACP v1.0) | ✅ Complete | Rental, dating, gaming templates; full state machine |
| Matching algorithm | ✅ Complete | Per-type scorers (rental/dating/gaming) with test coverage |
| Privacy layer | ✅ Complete | Coarsening, 4-stage filter, disclosure budget, audit log (83 tests) |
| Vue 3 frontend | ✅ Complete | TaskList, ChatArea, InfoPanel, MessageBubble, mobile responsive |
| Voice input | ✅ Complete | MediaRecorder → ASR proxy |
| SSO (WeChat / Alipay) | ✅ Complete | OAuth callback handlers |
| **Privacy filter → agent path integration** | ✅ Complete | `PrivacyFilterLayer` wired into `create_user_agent_interaction`; events persisted to SQLite |
| **Disclosure config REST API** | ✅ Complete | `GET/PUT /api/tasks/{id}/privacy`; `GET /api/tasks/{id}/disclosure_events` |
| **Resource rate limiting** | ✅ Complete | Sliding-window per-user (60 req/min) + global (600 req/min) middleware |
| **WebSocket real-time comms** | ⚠️ Pending | Currently polling; WebSocket endpoint planned |
| **Agent-to-agent negotiation** | ⚠️ Pending | Scoring only; live A2A chat pipeline not implemented |
| **Long/short-term memory** | ⚠️ Pending | Design exists; Redis + vector DB integration not started |
| **Tool plugin system** | ⚠️ Pending | Interface designed; no concrete tool implemented |
| WeChat OA / Telegram Bot messaging | ⚠️ Pending | SSO done; pub-account messaging integration not done |
| Additional task types | ⚠️ Pending | Carpool, property, second-hand templates defined; not wired |
| PostgreSQL backend | ⚠️ Pending | Abstraction ready; production backend not configured |
| Native mobile app | ❌ Not started | See Milestone 4 below |
| Document auto-verification | ❌ Not started | See Milestone 5 below |
| Payment support | ❌ Not started | — |
| Multi-language / i18n | ❌ Not started | — |
| Data analytics & recommendations | ❌ Not started | — |

---

## 6. Next Milestones

Ordered by dependency and impact. Each milestone builds on the previous one.

---

### ~~Milestone 1 — Privacy Filter Integration & Resource Rate Limiting~~ ✅ COMPLETE

**Completed**: 2026-04-02

See [Development Log](todos_and_development_log.md) for implementation details.

---

### Milestone 2 — Agent-to-Agent Negotiation & Real-Time Communication

**Why second**: Agent-to-agent chat is the core differentiator described in [chat_based_agentic_matching_v1.0.md](chat_based_agentic_matching_v1.0.md) but only scoring exists today.

**Deliverables**:
- Implement the 5-step matching pipeline: demand registration → candidate discovery → agent pre-screening → A2A negotiation chat → shortlist
- Add WebSocket endpoint for real-time push of agent messages and match updates to the frontend
- Integrate negotiation privacy obfuscation (`negotiation.py`) into the A2A chat turns
- Add session-scoped A2A conversation history to SQLite

---

### Milestone 3 — Long/Short-Term Memory Module

**Why third**: Without memory, agents cannot reference past conversations or user preferences, making them feel stateless. Required for the "continuous task" principle.

**Deliverables**:
- Implement short-term memory store (Redis or SQLite-backed for smaller deployments, TTL 24 h): conversation context, extracted entities, negotiation state
- Implement long-term memory store (DB-backed): user profile summary, preference vectors, task history
- Add entity extraction and preference learning from completed task outcomes
- Connect memory layer to `create_user_agent_interaction` so agents can reference prior context

---

### Milestone 4 — Native Mobile App via uni-app

**Why**: The existing web frontend is responsive but not a native mobile experience. A uni-app shell enables iOS and Android distribution from a single codebase and unlocks WeChat Mini Program deployment — a critical channel for the primary user base.

**Deliverables**:
- Scaffold a uni-app project sharing the same REST API surface as the Vue 3 web frontend
- Port core views: Login, TaskList, ChatArea (with voice input), InfoPanel (demand progress + matches)
- Implement push notification support (WeChat push or APNs/FCM depending on platform)
- Package and publish to WeChat Mini Program and optionally iOS/Android app stores
- Document any backend changes needed to support the mobile auth flow

---

### Milestone 5 — Automated Document Verification by Agent

**Why**: Trust is essential for rental and dating use cases. Agents need to verify that a landlord actually owns the property or that a user's stated identity matches their documents — without exposing raw document data.

**Deliverables**:

#### 5a — Photo ID Verification
- Integrate an OCR + face-liveness service (e.g., Aliyun Real-Name Verification, or an open-source alternative) as a tool plugin
- Agent prompts user to upload a government-issued ID and a selfie during the demand-collection phase (when required by task type)
- Tool plugin validates ID authenticity, extracts name/DOB, and returns a `verified: true/false` signal without storing raw document images beyond the verification call
- Store verification result (boolean + expiry timestamp) on the user profile, not the raw document

#### 5b — Real Estate Certificate Verification
- Integrate with a property-records data source (e.g., government open data API or a title-search service) as a tool plugin
- Agent requests property address from landlord and queries the registry to confirm ownership matches the registered user
- Return a `property_verified: true/false` signal and surface it in the InfoPanel for the tenant's agent to use during matching
- All queries go through the privacy filter to avoid leaking exact addresses to tenants before a match is confirmed

#### 5c — Tool Plugin Framework
- Define a `BaseTool` abstract class and registration mechanism so future verification tools (business license, gaming rank APIs, driving record for carpool, etc.) can be added without modifying core agent logic
- Expose tool results through the ACP `to_system` output block so they feed back into demand state without requiring extra LLM calls

---

### Milestone 6 — Additional Task Types & Offline Data Import

**Why**: Rental/dating/gaming templates exist; unlocking carpool, property trading, and second-hand goods expands the addressable market significantly. Offline import (park matchmaking boards, paper ads) is a unique differentiator described in the original design.

**Deliverables**:
- Add templates for: carpool (driver/rider roles), property buying/selling, second-hand goods
- Implement type-specific matching scorers for each new type
- Build an offline data import pipeline: structured CSV/image → OCR → demand template auto-fill → agent-managed task creation
- Add bulk-import API endpoint (`POST /api/import`) with preview and confirmation flow

---

*Document version: 1.0 — Created 2026-04-01*
