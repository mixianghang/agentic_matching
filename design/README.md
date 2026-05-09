# Design Documents

## Document Index

| Document | Scope | Status |
|----------|-------|--------|
| [DESIGN.md](./DESIGN.md) | Vision, architecture, core design intents | **Primary reference** |
| [ROADMAP.md](./ROADMAP.md) | Current status, milestones, near/mid/long-term plans | Active |
| [DEVELOPMENT_LOG.md](./DEVELOPMENT_LOG.md) | Implementation history, key bugs & lessons | Passive |
| [demand_definition_design_v1.0.md](./demand_definition_design_v1.0.md) | Demand definition module (template-driven multi-round dialogue) | Reference |
| [agent_comm_protocol_v1.0.md](./agent_comm_protocol_v1.0.md) | ACP — structured agent/user/system message protocol | Reference |
| [persistence_design.md](./persistence_design.md) | Pluggable storage backend design (interface + SQLite + PostgreSQL) | Reference |
| [long_short_memory_design_v1.0.md](./long_short_memory_design_v1.0.md) | Short-term / long-term memory architecture | Reference |
| [frontend_refactor.md](./frontend_refactor.md) | Vue 3 + Vite + Vant 4 migration notes | Reference |
| [voice_input_design_v1.0.md](./voice_input_design_v1.0.md) | Browser ASR → backend proxy architecture | Reference |

## Reading Guide

1. **New to the project?** Start with [DESIGN.md](./DESIGN.md) for vision, architecture, and key design decisions.
2. **Implementing features?** Check [ROADMAP.md](./ROADMAP.md) for current status and priorities.
3. **Debugging / understanding history?** See [DEVELOPMENT_LOG.md](./DEVELOPMENT_LOG.md) for past issues and their root causes.
4. **Deep diving a subsystem?** Pick the relevant detailed design doc above.
