# Agentic Matching System — Master Design Document

## 1. Vision: Matching for Everything

### 1.1 The Problem with Search

美团、高德、淘宝、百合网——all dominant platforms are built on the same paradigm: **search-based recommendation**. You type keywords, the platform returns a ranked list of results. This model has fundamental limitations:

1. **Counterparty offline.** Search catalogs static listings. The provider (restaurant owner, landlord, seller) isn't present to negotiate, clarify terms, or adapt offers in real time. You browse, read sparse descriptions, and make decisions with incomplete information—a labor-intensive, high-friction process.

2. **Information sparsity.** "Is this specific dish available tonight? How spicy can they make it? Can I sit by the window?" These questions are unanswerable through search. The platform reduces a rich service offering to a few photos and a star rating, forcing the user to fill the gap with guesswork and phone calls.

3. **Privacy-as-afterthought.** Many real-world needs are inherently privacy-sensitive—booking a sensitive medical consultation, finding a caregiver for a disabled family member, arranging an intimate encounter (one-night stand), seeking mental health support. Traditional platforms expose your query, profile, and transaction history to the platform operator, creating privacy and safety risks that deter honest use.

### 1.2 The Agentic Answer

Agentic Matching replaces search with **negotiation**: autonomous agents that represent both supply and demand sides, engage in multi-turn dialogue, verify claims programmatically, and negotiate terms—all while enforcing privacy boundaries.

| | Search Platform | Agentic Matching |
|---|---|---|
| **Discovery** | Keyword → ranked list | Agent broadcasts demand → matching agents respond |
| **Information depth** | Static listing (photos, rating) | Multi-turn Q&A, structured extraction, real-time availability |
| **Negotiation** | Manual (chat/call) | Agent-to-agent automated negotiation |
| **Verification** | User reviews (vulnerable to fraud) | Programmatic credential verification (health cert, ID, license) |
| **Privacy** | Full exposure to platform | Differential privacy, selective information disclosure |
| **Coverage** | High-volume homogeneous goods only | Any demand with an online counterparty, including niche and private needs |

The ambition is not "another dating app" or "another rental platform." It is a universal matching substrate capable of replacing 美团-level search with agent-driven matching for **any** supply-demand pair.

### 1.3 Privacy-Sensitive Matching as a First-Class Requirement

Consider these scenarios that traditional platforms cannot serve well:

| Scenario | Privacy Challenge | Agentic Solution |
|---|---|---|
| **Intimate encounters** (one-night stand) | Neither party wants a public profile or platform-visible history | Encrypted demand broadcast; health verification without exposing raw medical data; reputation via cryptographically signed attestations |
| **Sensitive medical treatment** | Patients don't want conditions linked to identity | Agent represents patient anonymously; verifies doctor credentials; negotiates confidentiality terms before identity disclosure |
| **Disability care** | Families need trust but have limited network reach | Agent matches caregiver qualifications against care needs; verifies certifications; manages scheduling automatically |
| **Legal/financial advice** | Client-attorney privilege requires confidentiality | Agent establishes secure channel; verifies bar license; destroys conversation records per client instruction |

The core insight: when both parties can be represented by agents, **privacy boundaries can be negotiated and enforced programmatically** rather than left to platform policy.

---

## 2. Reputation & Verification: Trust Without Central Authority

### 2.1 The Reputation Problem

Traditional platforms rely on user reviews and star ratings. These are fragile:
- **Fraud**: Fake reviews, review bombing, paid endorsements
- **Low signal**: "Great service!" carries no verifiable weight
- **Privacy violation**: Leaving a review for a sensitive service exposes the reviewer
- **Cold start**: New providers lack any reputation signal

### 2.2 Agent-Driven Verification

The system treats reputation as a **composable, verifiable signal** rather than a single numerical score. Key design principles:

1. **Credential attestation.** Providers submit verifiable credentials (medical license, health check certificate, ID, property deed) to their agent. The agent cryptographically attests to the validity without exposing raw documents to counterparties. Example: for a one-night encounter, both parties' agents mutually verify a recent STD test certificate signed by a recognized clinic, confirming the result is negative and within validity period—without revealing the individual's identity, clinic name, or test date.

2. **Multi-dimensional trust.** Reputation is not one number. It decomposes into independently verifiable dimensions:
   - Identity verification (government ID, face match)
   - Credential verification (professional license, property ownership)
   - Health/safety attestation (medical test results, vaccination records)
   - Transaction history (completed matches, dispute rate, response time)
   - Peer attestation (cryptographic endorsements from verified users)

3. **Automated negotiation of trust requirements.** The agent negotiates what verification level is required for a given match. A casual gaming teammate needs no verification. A one-night encounter may require reciprocal health attestation. A rental agreement may require identity + income verification from the tenant and property deed + safety inspection from the landlord.

4. **Privacy-preserving disclosure.** Credentials are verified by the agent but disclosed to counterparties only at the level both parties agree to. The system supports progressive disclosure: start anonymous → exchange verified attributes → reveal identity only when mutual trust is established.

---

## 3. System Architecture

### 3.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                          Presentation Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Web (Vue 3) │  │   WeChat MP  │  │  Telegram    │  (future) │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘           │
└─────────┼─────────────────┼─────────────────┼────────────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │  REST API  ( /api/* )
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                       Application Layer (FastAPI)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  Auth (JWT)  │  │  Task CRUD   │  │  Message / Chat      │   │
│  │  + SSO       │  │  + Matching  │  │  + Demand Progress   │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└────────────────────────────┬─────────────────────────────────────┘
                             │
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│  Agent System    │ │  Storage     │ │  Tools (future)  │
│  ┌────────────┐  │ │  Layer       │ │  ┌────────────┐  │
│  │LLM Gateway │  │ │  ┌────────┐  │ │  │Face Verify │  │
│  │(DeepSeek)  │  │ │  │SQLite  │  │ │  │Doc Scan    │  │
│  ├────────────┤  │ │  │(default│  │ │  │Health Cert │  │
│  │Demand Def  │  │ │  │or      │  │ │  │Geo Filter  │  │
│  │Engine V2   │  │ │  │Postgre)│  │ │  │ASR/Voice   │  │
│  ├────────────┤  │ │  └────────┘  │ │  └────────────┘  │
│  │    ACP     │  │ │              │ │                  │
│  │  Protocol  │  │ │  Pluggable   │ │  Extensible via  │
│  │            │  │ │  via Factory │ │  tool registry   │
│  └────────────┘  │ │              │ │                  │
└──────────────────┘ └──────────────┘ └──────────────────┘
```

### 3.2 Core Subsystems

| Subsystem | Location | Responsibility |
|-----------|----------|----------------|
| **Agent System** | `backend/agent_system.py` | LLM gateway, conversation orchestration, matching dispatch |
| **Demand Engine** | `backend/demand_engine.py` | Schema-on-read demand extraction via dynamic schema registry + ACP protocol |
| **Demand Schemas** | `backend/schema_registry.py` | Dynamic demand type management; schema CRUD with auto-activation |
| **Matching Engine** | `backend/matching/generic_engine.py` | Generic dimension-based matching engine; 6 built-in comparators

### 3.3 Key Architectural Decisions

1. **Factory pattern for pluggable components.** Storage backend, matching algorithm, and SSO providers are all selected via environment variables (`STORAGE_TYPE`, `MATCHER_TYPE`) with run-time factory dispatch. This enables testing with in-memory storage, development with SQLite, and production with PostgreSQL—all sharing the same `StorageBackend` interface.

2. **ACP (AgentComm Protocol) as the internal message contract.** Every LLM interaction uses a structured XML/JSON protocol that separates user-facing responses from system-facing state updates, extracted fields, and pending actions. This makes parsing reliable and prevents LLM output from leaking directly to users.

3. **Two-step confirmation for demand completion.** Users must issue two explicit confirmations to finalize a demand (COLLECTING → CONFIRMING → COMPLETED), preventing accidental submission of incomplete requirements.

4. **Ephemeral match scoring.** `Task.score` and `Task.match_reason` are computed on-demand by the `/matches` endpoint and are never persisted. This keeps the data model clean and avoids stale scores.

5. **Thread-safe SQLite with explicit lock discipline.** `@with_lock` decorator with 5s timeout wraps all write operations. `_get_messages_by_task_internal` avoids re-acquiring the lock when called from within a locked context.

---

## 4. Core Workflow

### 4.1 End-to-End Flow

```
User expresses need                    Agent finds match               Negotiation & Close
(natural language)                     (broadcast + scoring)           (agent-to-agent)

┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ "I want  │   │ Demand   │   │ Matching │   │ Agent A  │   │ "Saturday│
│ to rent  │ → │ Engine   │ → │ Engine   │ → │ ↔        │ → │ 3pm at   │
│ near UoM"│   │ extracts │   │ scores   │   │ Agent B  │   │ café X"  │
│          │   │ 8 fields │   │ candidates│  │ negotiate│   │          │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
  Phase 1:        Phase 2:        Phase 3:       Phase 4:        Phase 5:
  Intent          Demand          Matching       Negotiation     Resolution
  Detection       Definition      & Scoring
```

### 4.2 Task Lifecycle

```
PENDING → ACTIVE → MATCHING → MATCHED → COMPLETED
   │                    │         │
   └── CANCELLED ←──────┴─────────┘
```

Tasks persist until the user explicitly marks them COMPLETED. Agents can proactively notify users of progress (e.g., "Found 3 matching apartments").

---

## 5. Data Model

| Entity | Key Fields | Notes |
|--------|------------|-------|
| **User** | `id`, `username`, `password_hash`, `auth_provider`, `third_party_id`, `preferences`, `private_info` | `private_info` holds verifiable credentials (future) |
| **Agent** | `id`, `user_id`, `role` | Roles: `user_agent`, `task_agent`, `matching_agent` |
| **Task** | `id`, `user_id`, `agent_id`, `task_type`, `description`, `requirements`, `status`, `metadata` | `requirements` is the structured demand dict; `metadata` holds session state |
| **Message** | `id`, `task_id`, `sender_id`, `content`, `message_type`, `is_public` | `message_type`: `agent`, `system`, `user` |

Task types (defined in `backend/config.py:TaskType`):
- `dating` — 婚恋交友
- `rental` — 房屋租赁 (roles: `tenant`, `landlord`)
- `gaming` — 游戏组队

---

## 6. Technology Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.10+, FastAPI, Pydantic v2, `pydantic-settings` |
| **Frontend** | Vue 3, Vite 5, TypeScript, Vant 4, Pinia, Vue Router |
| **LLM** | DeepSeek (via OpenAI-compatible API), configurable base URL |
| **Storage** | SQLite (dev), PostgreSQL (prod target), InMemory (test) |
| **Auth** | bcrypt + JWT (local), WeChat OAuth, Alipay OAuth |
| **ASR** | OpenAI-compatible Whisper endpoint (proxied through backend) |
| **Dev tooling** | pytest + pytest-asyncio, `asyncio_mode=auto` |

---

## 7. Document References

| Document | Contents |
|----------|----------|
| [DASHBOARD.md](./DASHBOARD.md) | Consolidated dashboard: architecture, module index, implementation status, milestones |
| [ROADMAP.md](./ROADMAP.md) | Implementation status, milestones, priorities |
| [DEVELOPMENT_LOG.md](./DEVELOPMENT_LOG.md) | Iteration history, bugs fixed, lessons learned |
| [chat_based_agentic_matching_v1.0.md](./chat_based_agentic_matching_v1.0.md) | Agent-to-agent matching pipeline: 5-step negotiation, shortlist generation |
| [privacy_preserving_agentic_matching_v1.0.md](./privacy_preserving_agentic_matching_v1.0.md) | Privacy layer: coarsening taxonomy, 4-stage filter, disclosure budget, audit |
| [demand_definition_design_v2.0.md](./demand_definition_design_v2.0.md) | Demand extraction V2.0: dynamic schema registry, dimension-based matching, content safety |
| [agent_comm_protocol_v1.0.md](./agent_comm_protocol_v1.0.md) | ACP: structured protocol for agent↔system↔user message exchange |
| [persistence_design.md](./persistence_design.md) | Pluggable storage backend architecture |
| [long_short_memory_design_v1.0.md](./long_short_memory_design_v1.0.md) | Short-term context + long-term user profile memory system |
| [frontend_refactor.md](./frontend_refactor.md) | Vue 3 migration architecture |
| [voice_input_design_v1.0.md](./voice_input_design_v1.0.md) | Browser ASR → backend proxy pipeline |
