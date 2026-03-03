# AI Agent Marketplace (LangGraph + Hugging Face)

This project is a local marketplace that can:

- Register open-source LLM-powered agents.
- Discover agents by framework/provider/capability.
- Route user queries to the most suitable agent using **cost + latency + accuracy**.
- Invoke **Hugging Face hosted open-source models** (mandatory mode).

## Architecture

- `backend/main.py`
  - FastAPI API for registry, discovery, query routing, and history.
- `backend/routing_agent.py`
  - LangGraph routing pipeline:
    1. Normalize preferences.
    2. Filter by capability relevance.
    3. Score by cost/latency/accuracy (+ capability signal).
    4. Select best agent.
- `frontend/`
  - Static dashboard for registry, query submission, and history.

## Run

From `backend/`:

```powershell
notepad .env
venv\Scripts\python -m uvicorn main:app --port 8000
```

Put your token in `backend/.env`:

```env
HF_TOKEN=hf_xxx
```

Seed sample agents (new terminal, from `backend/`):

```powershell
venv\Scripts\python seed.py
```

Open:

- `http://localhost:8000/`

## Hugging Face Token

Set one of these env vars. This is required at startup:

- `HF_TOKEN`
- `HUGGINGFACEHUB_API_TOKEN`

PowerShell example:

```powershell
$env:HF_TOKEN="hf_xxx"
```
