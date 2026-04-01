# Chat-Based Agentic Matching — Design Document v1.0

## 1. Overview

This document specifies the design of the **chat-based agentic matching process**, in which autonomous agents represent human users and negotiate matches through multi-turn dialogue instead of static form-based queries.

### 1.1 Goals

- Allow each user to have an agent that fully represents their interests in a matching task.
- Automate the entire matching pipeline — from candidate discovery to shortlist presentation — without requiring constant user involvement.
- Support a broad class of two-sided matching scenarios (tenant ↔ landlord, buyer ↔ seller, dating, co-gaming, etc.).
- Produce a ranked shortlist of confirmed matches for the user to review and act on.

### 1.2 Scope

The primary scenario is **two-agent matching**: one agent represents the requesting party (Peer A) and one represents the responding party (Peer B). The design is extensible to multi-party matching (e.g., group rentals, team formation).

---

## 2. Actors and Roles

| Actor | Description |
|---|---|
| **User** | Human owner of a demand; interacts only with their own agent |
| **Peer A Agent** | Agent that initiates the matching process on behalf of User A |
| **Peer B Agent** | Agent that responds to matching queries on behalf of User B |
| **Recommendation System** | Black-box backend service that returns a ranked candidate list; neither agent can inspect its internals |
| **Orchestrator** | Server-side component that routes inter-agent messages and manages session lifecycle |

---

## 3. Demand Definition

Before matching begins, each user defines their **demand** through a multi-turn conversation with their own agent. The agent progressively refines the demand into a structured representation.

```
Demand {
    demand_id        : UUID
    user_id          : UUID (owner, never exposed to other agents)
    domain           : str          # "rental", "dating", "gaming", …
    created_at       : datetime
    status           : DemandStatus # active | paused | fulfilled | cancelled
    requirements     : Dict         # structured requirements (domain-specific)
    preferences      : Dict         # ranked soft preferences
    private_profile  : Dict         # sensitive user data (never leaves agent boundary)
    public_summary   : str          # agent-generated plain-text summary, privacy-filtered
}
```

The `private_profile` is **never serialised into inter-agent messages**. Only `public_summary` and coarse-grained attributes derived from it are shared externally (see the privacy document for details).

---

## 4. Matching Pipeline

```
┌────────────────────────────────────────────────────────────────┐
│                      Matching Pipeline                         │
│                                                                │
│  Step 1              Step 2              Step 3                │
│  ─────────           ─────────           ─────────             │
│  Demand              Candidate           Agent-to-Agent        │
│  Registration  ───>  Discovery     ───>  Chat Sessions         │
│                      (Rec. System)       (Peer A ↔ Peer B)     │
│                                                   │            │
│                        Step 4 ◄───────────────────┘            │
│                        ─────────                               │
│                        Shortlist                               │
│                        Generation                              │
│                              │                                 │
│                        Step 5 ◄───────────────────             │
│                        ─────────                               │
│                        User Review                             │
└────────────────────────────────────────────────────────────────┘
```

### 4.1 Step 1 — Demand Registration

1. User A chats with Peer A Agent to articulate their demand.
2. Peer A Agent asks clarifying questions until the demand reaches a confidence threshold.
3. The finalised demand (minus `private_profile`) is registered with the Orchestrator.

### 4.2 Step 2 — Candidate Discovery via Recommendation System

1. Peer A Agent sends a **candidate-request** to the Recommendation System containing the coarse-grained, privacy-filtered representation of the demand.
2. The Recommendation System returns a ranked list of up to **N** candidate demands (where N is a system-level configuration, e.g., N = 20).
3. Each candidate entry includes:
   - `candidate_demand_id`
   - `candidate_agent_id`
   - `domain`
   - `coarse_summary` (pre-filtered by Peer B Agent before submission)
   - `match_score` (computed by the Recommendation System)
4. The Recommendation System is a **black box**: neither agent can query its weights, training data, or intermediate outputs.

### 4.3 Step 3 — Pre-Screening by Peer A Agent

Before opening a chat session, Peer A Agent performs a lightweight local evaluation of each candidate:

1. Compare `coarse_summary` against the structured requirements and soft preferences from the demand.
2. Discard candidates whose hard requirements are clearly unmet (e.g., wrong city, budget mismatch beyond tolerance).
3. Rank the remaining candidates to determine the order in which chat sessions are opened.

This reduces unnecessary chat sessions and lowers the information-exchange surface.

### 4.4 Step 4 — Agent-to-Agent Chat Sessions

For each shortlisted candidate, Peer A Agent initiates a **chat session** with Peer B Agent. All sessions are mediated by the Orchestrator.

#### 4.4.1 Session Lifecycle

```
Peer A Agent                Orchestrator               Peer B Agent
     │                           │                           │
     │── OPEN_SESSION ──────────>│                           │
     │                           │── INVITE ────────────────>│
     │                           │<── ACCEPT ────────────────│
     │<── SESSION_READY ─────────│                           │
     │                           │                           │
     │── MSG(question) ─────────>│── forward ───────────────>│
     │                           │<── MSG(answer) ───────────│
     │<── MSG(answer) ───────────│                           │
     │        … (multi-turn) …   │                           │
     │── CLOSE_SESSION ─────────>│── notify ────────────────>│
     │                           │                           │
```

#### 4.4.2 Information Exchange Protocol

Each agent controls **what it discloses** about its user. The exchange follows a structured dialogue schema:

```
Round 1 — Basics:
  Peer A asks about hard requirements (budget range, location, timeline).
  Peer B responds with coarse-grained values (see privacy document).

Round 2 — Soft Preferences:
  Agents exchange preference signals (lifestyle, work schedule, pet policy, etc.)
  using ordered categorical values rather than free-form text where possible.

Round 3 — Negotiation:
  Agents propose and counter-propose terms (price, start date, lease length, etc.)
  Negotiation follows a structured offer/counter-offer protocol.

Round 4 — Verification Triggers (optional):
  Either agent may request a third-party verification (identity, property ownership, etc.)
  via a registered Tool component. The result is a boolean or a trust score, not raw data.
```

#### 4.4.3 Session Termination Conditions

A session is closed when any of the following occurs:

| Condition | Action |
|---|---|
| Hard requirement mismatch detected | Peer A Agent marks candidate as **rejected**; closes session immediately |
| Negotiation reaches agreement | Candidate marked as **tentative match** |
| Max rounds exceeded (configurable, default 10) | Candidate marked as **inconclusive** |
| Peer B Agent declines or does not respond within timeout | Candidate marked as **unresponsive** |

### 4.5 Step 5 — Shortlist Generation and User Notification

1. After all chat sessions are resolved, Peer A Agent compiles the results:
   - **Confirmed matches**: negotiation succeeded on all required terms.
   - **Tentative matches**: soft preferences partially satisfied; user judgment required.
   - **Rejected / Inconclusive**: filtered out.
2. The shortlist is presented to User A via the user-agent interface (web chat, messaging app).
3. For each match, a **negotiation summary** is shown: what was agreed, what is still open, and a recommendation from Peer A Agent.
4. User A reviews the shortlist and selects a final match or requests further negotiation.

---

## 5. Agent Behaviour Specification

### 5.1 Peer A Agent Responsibilities

| Responsibility | Description |
|---|---|
| Demand elicitation | Guide User A through demand definition via multi-turn dialogue |
| Candidate screening | Filter recommendation results before opening sessions |
| Session management | Open, conduct, and close chat sessions with Peer B Agents |
| Negotiation | Propose, evaluate, and respond to terms on behalf of User A |
| Shortlist reporting | Summarise outcomes and present to User A |
| Continuous operation | Run autonomously until demand is fulfilled or cancelled |

### 5.2 Peer B Agent Responsibilities

| Responsibility | Description |
|---|---|
| Availability signalling | Register demand and accept/reject session invitations |
| Information disclosure | Respond to queries using privacy-compliant coarse-grained data |
| Negotiation | Respond to proposals, escalate decisions to User B when needed |
| User notification | Inform User B of tentative matches and agreed terms |

### 5.3 Agent Decision Logic (Peer A)

```python
def process_candidate(candidate, session_transcript, user_requirements):
    """
    Returns one of: REJECT | TENTATIVE | CONFIRM | ESCALATE_TO_USER
    """
    # Hard requirement check
    if not meets_hard_requirements(candidate, user_requirements):
        return REJECT

    # Soft preference scoring
    score = compute_preference_score(session_transcript, user_requirements)

    if score >= CONFIRM_THRESHOLD:
        return CONFIRM
    elif score >= TENTATIVE_THRESHOLD:
        return TENTATIVE
    elif requires_user_judgment(session_transcript):
        return ESCALATE_TO_USER
    else:
        return REJECT
```

---

## 6. Negotiation Protocol

### 6.1 Offer / Counter-Offer Schema

```json
{
  "session_id": "<uuid>",
  "round": 3,
  "type": "OFFER | COUNTER_OFFER | ACCEPT | REJECT",
  "terms": {
    "price": { "value": 2500, "unit": "USD/month", "negotiable": true },
    "start_date": { "value": "2026-06-01", "flexible_days": 14 },
    "lease_duration": { "value": 12, "unit": "months", "min": 6 }
  },
  "conditions": ["no_smoking", "no_pets"]
}
```

### 6.2 Negotiation Rules

1. Each round, Peer A Agent may adjust its offer by up to a configurable percentage (default ±10 %).
2. If Peer B Agent makes a counter-offer outside the acceptable range, Peer A Agent either rejects or escalates to User A.
3. Agreed terms are locked: neither agent may re-negotiate a locked term in a subsequent round.
4. Negotiation transcripts are stored per session and are visible only to the respective user (not cross-shared).

---

## 7. Scenario Walkthroughs

### 7.1 Rental: Tenant Agent ↔ Landlord Agent

```
Tenant (User A)            Tenant Agent (A)        Landlord Agent (B)      Landlord (User B)
      │                          │                          │                       │
      │── "Find me a 1BR         │                          │                       │
      │    near downtown,        │                          │                       │
      │    max $2000/mo" ───────>│                          │                       │
      │                          │── [elicit details]       │                       │
      │<── "Pet-friendly? ───────│                          │                       │
      │     Move-in date?" ──────│                          │                       │
      │── "Yes, cats. June 1" ──>│                          │                       │
      │                          │── [register demand]      │                       │
      │                          │── [query Rec. System]    │                       │
      │                          │<── [top 15 candidates]   │                       │
      │                          │── [screen: 8 pass]       │                       │
      │                          │                          │                       │
      │                          │── OPEN_SESSION ─────────>│                       │
      │                          │<── [Round 1: basics] ────│                       │
      │                          │── [Round 2: prefs] ─────>│                       │
      │                          │── [Round 3: offer:       │                       │
      │                          │    $1900/mo, June 1] ───>│                       │
      │                          │<── [counter: $2000,      │                       │
      │                          │    June 15] ─────────────│                       │
      │                          │── [ACCEPT June 15,       │                       │
      │                          │    $1950 compromise] ───>│                       │
      │                          │<── [ACCEPT] ─────────────│                       │
      │                          │── CLOSE_SESSION          │                       │
      │                          │                          │                       │
      │<── "Found 2 matches.     │                          │                       │
      │     Best: $1950/mo,      │                          │                       │
      │     June 15, pet-OK" ────│                          │                       │
      │── "Show details" ───────>│                          │                       │
      │<── [negotiation summary] │                          │                       │
      │── "Confirm!" ───────────>│                          │── notify User B ─────>│
```

### 7.2 Dating: Agent A ↔ Agent B

```
User A                    Agent A                    Agent B                  User B
  │                          │                          │                       │
  │── "Help me find          │                          │                       │
  │    someone who ..." ────>│                          │                       │
  │                          │── [elicit preferences]   │                       │
  │                          │── [register demand]      │                       │
  │                          │── [query Rec. System]    │                       │
  │                          │<── [N candidates]        │                       │
  │                          │                          │                       │
  │                          │── OPEN_SESSION ─────────>│                       │
  │                          │<── [Round 1: age range,  │                       │
  │                          │    location, interests]──│                       │
  │                          │── [Round 2: lifestyle,   │                       │
  │                          │    relationship goals]──>│                       │
  │                          │<── [compatible signals] ─│                       │
  │                          │── CLOSE: TENTATIVE_MATCH │                       │
  │                          │                          │                       │
  │<── "3 good matches —     │                          │                       │
  │     review summaries?" ──│                          │                       │
  │── "Yes" ────────────────>│                          │                       │
  │<── [per-match summaries] │                          │                       │
  │── "Interested in #1" ───>│                          │── notify User B ─────>│
```

---

## 8. System Configuration Parameters

| Parameter | Default | Description |
|---|---|---|
| `max_candidates_per_demand` | 20 | Max candidates returned by Recommendation System |
| `max_chat_rounds_per_session` | 10 | Max negotiation rounds before session is marked inconclusive |
| `session_timeout_seconds` | 300 | Inactivity timeout per session |
| `confirm_score_threshold` | 0.85 | Preference score above which a match is auto-confirmed |
| `tentative_score_threshold` | 0.60 | Preference score above which a match is tentative |
| `max_concurrent_sessions` | 5 | Max simultaneous chat sessions per Peer A Agent |
| `negotiation_flex_pct` | 10 | Max % adjustment per negotiation round |

---

## 9. Data Models

### 9.1 MatchingSession

```python
class MatchingSession:
    session_id       : UUID
    peer_a_agent_id  : UUID
    peer_b_agent_id  : UUID
    demand_a_id      : UUID
    demand_b_id      : UUID
    status           : SessionStatus   # open | closed | timed_out
    outcome          : SessionOutcome  # confirmed | tentative | rejected | inconclusive
    rounds           : List[DialogueRound]
    opened_at        : datetime
    closed_at        : Optional[datetime]
```

### 9.2 DialogueRound

```python
class DialogueRound:
    round_number  : int
    sender_agent  : UUID
    message_type  : MessageType  # question | answer | offer | counter_offer | accept | reject
    content       : str          # privacy-filtered text
    timestamp     : datetime
```

### 9.3 Shortlist

```python
class Shortlist:
    shortlist_id     : UUID
    demand_id        : UUID
    generated_at     : datetime
    entries          : List[ShortlistEntry]

class ShortlistEntry:
    rank             : int
    candidate_demand_id  : UUID
    outcome          : SessionOutcome
    agreed_terms     : Dict
    agent_recommendation : str
    session_id       : UUID
```

---

## 10. Interfaces

### 10.1 Recommendation System API (Consumed by Peer A Agent)

```
POST /recommendations
Request:
  {
    "demand_id": "<uuid>",
    "domain": "rental",
    "coarse_requirements": { ... },   // privacy-filtered
    "max_results": 20
  }
Response:
  {
    "candidates": [
      {
        "candidate_demand_id": "<uuid>",
        "candidate_agent_id": "<uuid>",
        "coarse_summary": "...",
        "match_score": 0.91
      },
      ...
    ]
  }
```

### 10.2 Inter-Agent Messaging API (Orchestrator)

```
POST /sessions/open
POST /sessions/{session_id}/message
POST /sessions/{session_id}/close
GET  /sessions/{session_id}/transcript
```

### 10.3 User-Agent API

```
POST /agent/demand           # create / update demand
GET  /agent/shortlist        # retrieve shortlist
POST /agent/shortlist/select # user selects a match
GET  /agent/sessions         # list ongoing sessions and status
```

---

## 11. Open Questions and Future Work

- **Multi-party matching**: extend the protocol to support group rentals, team formation, or many-to-one matching (one landlord, multiple tenant agents competing).
- **Asynchronous sessions**: allow Peer B Agent to respond on its own schedule (e.g., User B is offline), without blocking Peer A Agent from continuing with other candidates.
- **Trust and verification**: integrate third-party verification tools (identity, property ownership) as optional negotiation steps.
- **Feedback loop**: route user final decisions back into the Recommendation System to improve future match quality.
- **Domain-specific negotiation templates**: define structured offer schemas per domain (rental, dating, gaming) to reduce free-form negotiation ambiguity.
