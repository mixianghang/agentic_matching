# AGENTS.md — Agentic Matching System

## Commands

```bash
./start.sh          # Dev: Vite (5173) + FastAPI (8000) concurrently; creates venv & .env on first run
./deploy.sh         # Prod: builds frontend/dist, FastAPI serves everything on port 8000
./start_memory.sh   # Dev with in-memory storage (ephemeral, for browser testing)
python3 -m pytest   # All tests (asyncio_mode=auto, in-memory storage, dummy API key)
python3 -m pytest tests/test_auth.py -k test_login   # Single test
python3 reset_db.py         # Recreate SQLite DB from scratch
python3 cleanup_tasks.py    # Delete all tasks (--keep-messages to preserve messages; --vacuum)
```

## Architecture

- **Backend**: Python FastAPI, entrypoint `backend/main.py:app`. Uses `pydantic-settings` with `.env`.
- **Frontend**: Vue 3 + Vite + TypeScript + Vant 4 + Pinia. Dev server proxies `/api` → `localhost:8000`.
- **Storage**: Pluggable via `StorageBackend` interface. Three backends: `in_memory`, `sqlite` (default in `.env.example`; uses `threading.Lock` with `@with_lock`), `postgresql`. Set with `STORAGE_TYPE` env var.
- **Matching**: Factory pattern in `backend/matching/factory.py`. Selectable via `MATCHER_TYPE` env var (default `simple`).
- **SSO**: Factory pattern in `backend/sso/factory.py`. WeChat + Alipay providers.
- **Task types**: `dating`, `rental`, `gaming` (constants in `backend/config.py:TaskType`).

## Testing quirks

- `tests/conftest.py` sets `STORAGE_TYPE=in_memory` and `OPENAI_API_KEY=dummy_key_for_testing` — this makes tests use ephemeral storage and skip real LLM calls.
- AgentSystem checks for `dummy_key_for_testing` and returns fallback responses instead of calling the LLM.
- Old SSLKEYLOGFILE env var can cause permission errors; both conftest and startup scripts unset it.

## Design docs

- `design/DESIGN.md` — vision, architecture, core design intents (Matching for Everything, reputation/verification)
- `design/ROADMAP.md` — implementation status, priorities, milestones
- `design/DEVELOPMENT_LOG.md` — bug history, root causes, lessons learned
- `design/README.md` — full document index with reading guide

## Conventions

- After making significant code changes, update the relevant design doc (`design/DESIGN.md`, `design/ROADMAP.md`) and `README.md` if the change affects architecture, status, or developer-facing instructions.
- **Language**: All documentation, design docs, AGENTS.md, README, and code comments must be written in professional English. The only exception is string literals that must remain in their original language (e.g., Chinese UI text, log messages, user-facing content, test fixtures with Chinese input).

## Key gotchas

- `.env` is git-ignored but **required** to start. `.env.example` is the template. `.env.memory` contains a real API key — never commit it.
- `start.sh` force-kills any process on ports 8000 and 5173 before starting.
- SQLite storage uses a `threading.Lock` with 5s timeout; `_get_messages_by_task_internal` avoids deadlock (caller already holds lock).
- In production, FastAPI serves `frontend/dist/index.html` at `/`; falls back to `static/index.html`, then returns JSON. Mounts `/assets` and `/static` separately.
- The `Task.score` and `Task.match_reason` fields are ephemeral — populated by the `/matches` endpoint but **not persisted**.
- Python imports use the `backend.` prefix (e.g., `from backend.storage import storage`).
- `uvicorn` is run as a module: `uvicorn backend.main:app`, NOT `backend.main:app` as a file path.
