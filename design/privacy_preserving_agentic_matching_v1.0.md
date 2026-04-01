# Privacy-Preserving Agentic Matching — Design Document v1.0

## 1. Overview

This document specifies the **privacy-preservation layer** for the chat-based agentic matching system described in `chat_based_agentic_matching_v1.0.md`. Its goal is to ensure that the matching process discloses the minimum amount of user information necessary while still enabling agents to reach high-quality matches.

### 1.1 Privacy Goals

1. **Least-privilege disclosure**: an agent shares only the information that is strictly necessary for the current negotiation step.
2. **Isolation of user data**: raw user data never crosses agent boundaries; only derived, privacy-filtered representations are transmitted.
3. **Fuzzy / coarse-grained signals**: quantitative attributes (income, age, rent budget) are expressed as ranges or categories rather than exact values.
4. **User control**: users can configure their own disclosure level per attribute and per matching domain.
5. **Auditability**: every disclosure event is logged so users can review what was shared and with whom.

### 1.2 Threat Model

| Threat | Mitigation |
|---|---|
| Peer B Agent reconstructs User A's private profile from chat messages | Coarse-grained values + disclosure budgets prevent triangulation |
| Orchestrator or transport layer intercepts raw user data | User data never enters inter-agent messages; server only processes filtered representations |
| Recommendation System learns sensitive attributes from demand queries | Demands submitted to Rec. System use the same coarse-grained, privacy-filtered view |
| User A's agent inadvertently leaks data in free-form text | Output filtering layer scrubs recognised sensitive patterns before any message is sent |
| Inference from negotiation behaviour (e.g., quickly accepting a price reveals budget ceiling) | Negotiation strategy randomisation and minimum-round constraints |

---

## 2. Core Principles

### Principle 1 — Least Data Leakage

Each agent operates under a **disclosure budget**: a per-demand configuration that limits how much information can be shared with any single peer agent in a session, and cumulatively across all sessions for a demand.

- Information is released **incrementally**, round by round, only as needed.
- Once a session is closed (match or reject), the disclosed information is not retained by the peer agent — only the agreed terms and a boolean outcome are stored.

### Principle 2 — Data Isolation at Agent Boundaries

```
┌─────────────────────────────────────────────────────────┐
│                     Peer A Agent                        │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Private Context (User A's data)                  │  │
│  │  - exact age, income, address, ID, phone, …       │  │
│  │  - full requirement list                          │  │
│  │  - negotiation floor/ceiling values               │  │
│  └───────────────────────────────────────────────────┘  │
│                          │                              │
│              Privacy Filter Layer                       │
│                          │                              │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Public / Sharable Context                        │  │
│  │  - coarse age band, income tier, location area    │  │
│  │  - categorical preferences                        │  │
│  │  - negotiation ranges (not exact floors)          │  │
│  └───────────────────────────────────────────────────┘  │
│                          │                              │
└──────────────────────────┼──────────────────────────────┘
                           │  (only filtered content exits)
                     Orchestrator / Network
```

**Rule**: No data object that originates from `private_profile` may appear verbatim in any outbound inter-agent message. The Privacy Filter Layer enforces this at runtime.

---

## 3. Attribute Classification and Coarsening

### 3.1 Sensitivity Levels

| Level | Label | Example Attributes | Default Sharing |
|---|---|---|---|
| 0 | Public | Domain, general location (city), demand status | Always shared |
| 1 | Coarse | Age band, income tier, budget range, job category | Shared as categorical/range |
| 2 | Semi-private | Neighbourhood, employment status, relationship status | Shared only if user enables |
| 3 | Private | Exact address, phone number, income figure, ID number | Never shared via agent messages |

### 3.2 Coarsening Functions

For each Level-1 attribute, a **coarsening function** converts the exact value into a categorical representation before it may appear in any outbound message.

#### Age

| Exact Age | Coarse Band |
|---|---|
| 18 – 24 | "18–24" |
| 25 – 29 | "late 20s" |
| 30 – 34 | "early 30s" |
| 35 – 39 | "late 30s" |
| 40 – 49 | "40s" |
| 50 – 59 | "50s" |
| 60 + | "60 or above" |

#### Annual Income (USD)

| Exact Value | Coarse Tier |
|---|---|
| < 30,000 | "low income" |
| 30,000 – 59,999 | "lower-middle income" |
| 60,000 – 99,999 | "middle income" |
| 100,000 – 149,999 | "upper-middle income" |
| 150,000 – 249,999 | "high income" |
| 250,000 + | "very high income" |

#### Rent Budget (monthly, USD)

| Exact Budget | Coarse Range |
|---|---|
| < 800 | "under $800" |
| 800 – 1,199 | "$800 – $1,200" |
| 1,200 – 1,799 | "$1,200 – $1,800" |
| 1,800 – 2,499 | "$1,800 – $2,500" |
| 2,500 – 3,499 | "$2,500 – $3,500" |
| 3,500 + | "above $3,500" |

#### Occupation / Job Category

The exact job title and employer are never shared. Only a broad occupational category is used (e.g., "technology", "healthcare", "education", "finance", "creative", "other").

#### Location

- **City**: always shareable (Level 0).
- **Neighbourhood / district**: Level 2 (user opt-in only).
- **Street address**: Level 3 (never shared via agent messages; shared only after a match is confirmed and the user explicitly authorises it outside the agent channel).

### 3.3 Configurable Disclosure per User

Users configure their disclosure level via the user-agent interface before or during a demand. The configuration is stored per demand (not globally):

```python
class DisclosureConfig:
    demand_id          : UUID
    age_disclosure     : DisclosureLevel       # COARSE | NONE
    income_disclosure  : DisclosureLevel       # COARSE | NONE
    occupation_disclosure : DisclosureLevel    # CATEGORY | NONE
    location_disclosure   : DisclosureLevel    # CITY | DISTRICT | NONE
    budget_disclosure  : DisclosureLevel       # RANGE | EXACT | NONE
    custom_overrides   : Dict[str, DisclosureLevel]
```

Default configuration follows the attribute classification table in §3.1.

---

## 4. Privacy Filter Layer

### 4.1 Architecture

The Privacy Filter Layer sits between the agent's private reasoning context and the outbound message queue. Every message produced by the agent's LLM reasoning engine passes through this layer before being handed to the Orchestrator.

```
Agent LLM (private context)
         │
         │  raw draft message
         ▼
┌─────────────────────────────────┐
│     Privacy Filter Layer        │
│                                 │
│  1. Pattern scanner             │
│     (regex + NER-based)         │
│  2. Coarsening transformer      │
│  3. Disclosure-budget checker   │
│  4. Output validator            │
└─────────────────────────────────┘
         │
         │  filtered message (or BLOCKED)
         ▼
    Outbound message queue → Orchestrator → Peer B Agent
```

### 4.2 Pattern Scanner

Detects and blocks transmission of sensitive patterns using:
- **Regular expressions**: phone numbers, email addresses, numeric IDs, exact currency amounts, street addresses.
- **Named Entity Recognition (NER)**: identifies PERSON names, ORG names, specific location entities (street, building).
- **Context rules**: flags sentences that contain exact numeric values for income, age, or price outside a negotiation offer context.

When a sensitive pattern is detected:
1. The draft message is **not sent**.
2. The agent is instructed to regenerate the message using only approved coarse-grained representations.
3. If regeneration fails after 3 attempts, the message is replaced by a generic fallback (e.g., "I prefer not to share that detail at this stage").

### 4.3 Disclosure Budget Checker

Each session has a **per-session disclosure budget** defined as the maximum number of distinct Level-1 attributes that may be revealed. The budget resets per session (not per round within a session).

```python
class SessionDisclosureBudget:
    session_id              : UUID
    max_attributes_revealed : int = 5       # configurable
    attributes_revealed     : Set[str] = {} # tracks what has been shared

    def can_reveal(self, attribute_name: str) -> bool:
        if attribute_name in self.attributes_revealed:
            return True   # already disclosed; repeating is free
        return len(self.attributes_revealed) < self.max_attributes_revealed

    def record_reveal(self, attribute_name: str):
        self.attributes_revealed.add(attribute_name)
```

When the budget is exhausted, the agent responds to further information requests with a polite refusal: "I've shared what I'm able to at this stage. If you'd like more details, we can continue after a match is confirmed."

### 4.4 Output Validator

A final pass checks that:
1. No exact Level-3 attribute value appears in the outbound message.
2. All numeric values are within expected coarse-range bounds for their attribute type.
3. The message does not contain the `user_id` or `demand_id` of the user (only `agent_id` and `session_id` are permitted in inter-agent messages).

---

## 5. Data Isolation Between Agents

### 5.1 What the Peer B Agent May Learn

At the end of a complete chat session, Peer B Agent may have learned at most:

- Peer A Agent's `agent_id` and `session_id` (system identifiers, not user identifiers).
- The coarse-grained values of up to `max_attributes_revealed` Level-1 attributes.
- The negotiation terms that were put on the table (ranges, not exact floors/ceilings).
- The final outcome: accept / reject / inconclusive.

Peer B Agent **may not** learn:
- User A's identity, contact information, or `user_id`.
- User A's exact income, age, or address.
- User A's negotiation floor/ceiling (only the offered values, which are offset from the floor/ceiling by a random buffer — see §6.2).

### 5.2 What the Peer A Agent May Learn

Symmetrically, Peer A Agent may only learn the same categories of information from Peer B Agent (coarse-grained Level-1 attributes, negotiation proposals, outcome). The privacy rules apply symmetrically.

### 5.3 Session Transcript Retention

- Session transcripts are stored **per-agent** on the server, partitioned by `user_id`.
- Neither agent receives a copy of the other agent's transcript.
- The Orchestrator stores only the agreed terms and outcome (not the full transcript) in a shared location.
- Full transcripts are deleted after a configurable retention period (default: 90 days) or immediately upon user request.

---

## 6. Negotiation Privacy

### 6.1 Range-Based Offers

During negotiation, agents do not reveal their user's exact acceptable floor or ceiling. Offers are constructed as follows:

```
actual_floor = user's minimum acceptable value
actual_ceiling = user's maximum acceptable value
offer_value = actual_floor + random_offset(0, 0.3 * (actual_ceiling - actual_floor))
```

This ensures the opening offer does not reveal the floor, and successive offers do not linearly converge to it in a predictable way.

### 6.2 Offer Randomisation

A small random perturbation is added to each numerical offer to prevent statistical inference over multiple sessions:

```python
def make_offer(floor, ceiling, round_number, total_rounds):
    midpoint = floor + (ceiling - floor) * (round_number / total_rounds)
    noise = random.uniform(-0.05, 0.05) * (ceiling - floor)
    raw = midpoint + noise
    # Round to nearest 10 to reduce precision, but keep at least 10 to avoid zeroing small values
    return max(round(raw, -1), 10)
```

### 6.3 Negotiation Strategy Obfuscation

The agent does not follow a purely rational, deterministic concession strategy (which would allow Peer B Agent to infer the user's reservation value via repeated interaction). Instead:
- Concession speed is randomised within bounds.
- The agent occasionally makes strategic pauses before accepting a counter-offer, even when it is within range.
- The agent may reject offers that are technically within range with a low probability (mimicking human negotiation behaviour).

---

## 7. Recommendation System Privacy

The Recommendation System is a black box, but it receives demand data from each agent. To protect privacy:

1. **Coarse-grained query**: the demand query sent to the Recommendation System uses only Level-0 and Level-1 (coarse) attributes. Exact values are never included.
2. **Query anonymisation**: the query includes `demand_id` but not `user_id`. The Recommendation System cannot link a demand to a specific user.
3. **Result blinding**: the Recommendation System returns a ranked list with candidate `demand_id`s and coarse summaries. It does not return any personally identifiable information.

---

## 8. User Consent and Transparency

### 8.1 Disclosure Summary

After each session, the user may request a **disclosure summary** from their agent:

```
Session with Agent [B-xxx] — Disclosure Summary
────────────────────────────────────────────────
Attributes shared:
  - Age: "late 20s"
  - Budget: "$1,800 – $2,500/month"
  - Job category: "technology"
  - Location: "downtown area"

Attributes requested but not shared:
  - Exact income (withheld per your privacy settings)
  - Exact move-in date (not yet disclosed; round 2)

Outcome: Tentative match
```

### 8.2 User Controls

Users can at any time:
- **Tighten** their disclosure level (e.g., stop sharing job category going forward).
- **Widen** their disclosure level if they decide to share more to improve match quality.
- **Revoke** a specific disclosure retroactively (the peer agent is instructed to discard it, and it is removed from the peer agent's session context).
- **Opt out** of all data sharing beyond Level-0 (this will significantly reduce match quality; the agent warns the user accordingly).

### 8.3 Consent Before First Disclosure

Before Peer A Agent shares any Level-1 attribute for the first time in a new session, the user is notified (via the user-agent interface) of what is about to be shared and given the option to block it. Subsequent sessions within the same demand proceed with the same settings unless the user changes them.

---

## 9. Audit Log

Every disclosure event is appended to an append-only audit log stored in the user's private partition on the server:

```python
class DisclosureEvent:
    event_id        : UUID
    timestamp       : datetime
    demand_id       : UUID
    session_id      : UUID
    peer_agent_id   : UUID        # recipient, not the user behind it
    attribute_name  : str
    coarse_value    : str         # the value actually shared
    round_number    : int
```

The audit log is:
- **Read-only** by the user via the user-agent interface.
- **Immutable**: events cannot be deleted (only the full log can be purged on user account deletion).
- **Never shared** with peer agents, the Recommendation System, or any third party.

---

## 10. Implementation Checklist

| Component | Privacy Control | Status |
|---|---|---|
| Demand registration | Coarse-grained query to Rec. System | Design |
| Pre-screening | No inter-agent contact; local evaluation only | Design |
| Session open | Only `agent_id` exchanged, not `user_id` | Design |
| Round 1 messages | Pattern scanner + NER filter active | Design |
| Offer generation | Range-based + randomised offers | Design |
| Session close | Only agreed terms stored in shared space | Design |
| Shortlist | User-facing only; not shared with peer | Design |
| Audit log | Per-user append-only log | Design |
| User controls | Disclosure config UI | Design |

---

## 11. Open Questions and Future Work

- **Differential privacy for aggregate statistics**: if usage statistics (match rates, average budget ranges) are published, apply formal differential privacy guarantees.
- **Homomorphic encryption**: explore whether certain matching computations (e.g., budget overlap check) can be performed on encrypted values so neither the Recommendation System nor the Orchestrator learns exact figures.
- **Federated demand profiles**: investigate whether demand profiles can be kept on the user's device (edge) and only coarse representations sent to the server, reducing server-side exposure.
- **Coarsening granularity by domain**: calibrate coarsening functions per matching domain (rental budgets have different sensitivity than dating age ranges).
- **Third-party privacy audit**: define an audit interface that allows external privacy auditors to verify that the Privacy Filter Layer is functioning correctly without accessing user data.
