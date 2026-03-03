import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import models
import schemas
from database import Base, SessionLocal, engine, get_db, run_sqlite_migrations
from routing_agent import RoutingAgent

# Load local backend/.env for tokens and runtime config.

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Create DB tables and run lightweight SQLite migrations.
Base.metadata.create_all(bind=engine)
run_sqlite_migrations()


def _auto_seed():
    """Seed the database with default agents if it is empty. Safe to call on every startup."""
    from seed_db import seed
    seed()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts — before accepting requests.
    _auto_seed()
    yield
    # Runs once when the server shuts down.
    await router.close()


app = FastAPI(
    title="AI Agent Marketplace API",
    description="Register, discover, and invoke open-source LLM agents with intelligent routing.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_required_hf_token() -> str:
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
    if not token:
        raise RuntimeError(
            "Hugging Face token is mandatory. Set HF_TOKEN or HUGGINGFACEHUB_API_TOKEN."
        )
    return token


HF_TOKEN = get_required_hf_token()
router = RoutingAgent(hf_token=HF_TOKEN)


@app.get("/api/")
def read_root():
    return {"message": "Welcome to the AI Agent Marketplace API"}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "huggingface_token_configured": True,
        "huggingface_mode": "mandatory",
    }


@app.post("/api/agents/", response_model=schemas.AgentResponse)
def register_agent(agent: schemas.AgentCreate, db: Session = Depends(get_db)):
    db_agent = db.query(models.Agent).filter(models.Agent.name == agent.name).first()
    if db_agent:
        raise HTTPException(status_code=400, detail="Agent with this name already registered")

    new_agent = models.Agent(**agent.model_dump())
    db.add(new_agent)
    db.commit()
    db.refresh(new_agent)
    return new_agent


@app.get("/api/agents/", response_model=List[schemas.AgentResponse])
def get_agents(
    skip: int = 0,
    limit: int = 100,
    framework: Optional[str] = None,
    provider: Optional[str] = None,
    capability: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Agent).filter(
        models.Agent.is_active.is_(True), models.Agent.provider == "huggingface"
    )
    if framework:
        query = query.filter(models.Agent.framework == framework.lower())
    if provider:
        if provider.lower() != "huggingface":
            raise HTTPException(
                status_code=400,
                detail="Only provider='huggingface' is supported in mandatory Hugging Face mode.",
            )
        query = query.filter(models.Agent.provider == provider.lower())
    if capability:
        query = query.filter(models.Agent.capabilities.ilike(f"%{capability}%"))
    return query.offset(skip).limit(limit).all()


@app.get("/api/agents/{agent_id}", response_model=schemas.AgentResponse)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.put("/api/agents/{agent_id}", response_model=schemas.AgentResponse)
def update_agent(agent_id: int, agent_data: schemas.AgentCreate, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.name = agent_data.name
    agent.description = agent_data.description
    agent.capabilities = agent_data.capabilities
    agent.model_id = agent_data.model_id
    
    db.commit()
    db.refresh(agent)
    return agent


@app.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    db.delete(agent)
    db.commit()
    return {"status": "success", "detail": f"Agent {agent_id} deleted"}


def log_query_to_db(query_data: schemas.QueryRequest, result: schemas.QueryResultResponse, agent_id: Optional[int] = None):
    """Background task that opens its own DB session for safe async execution.
       Also computes new EMA latency and increments call count."""
    db = SessionLocal()
    try:
        log_entry = models.QueryLog(
            user_query=query_data.query,
            routing_preference_cost=query_data.pref_cost,
            routing_preference_latency=query_data.pref_latency,
            routing_preference_accuracy=query_data.pref_accuracy,
            selected_agent_name=result.selected_agent,
            selected_agent_provider=result.selected_agent_provider,
            selected_agent_framework=result.selected_agent_framework,
            agent_response=result.response,
            execution_time_ms=result.execution_time_ms,
        )
        db.add(log_entry)
        
        # Exponential moving average weighting for latency (e.g. 10% new, 90% historic)
        # Only counted as true latency if the call did not error out.
        if agent_id and "Error calling agent:" not in result.response:
            agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
            if agent:
                agent.call_count = (agent.call_count or 0) + 1
                current_lat = agent.average_latency_ms or result.execution_time_ms
                new_lat = (0.9 * current_lat) + (0.1 * result.execution_time_ms)
                agent.average_latency_ms = new_lat
                
        db.commit()
        db.refresh(log_entry)
        return log_entry.id
    finally:
        db.close()


@app.post("/api/query/", response_model=schemas.QueryResultResponse)
async def process_query(
    query_req: schemas.QueryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    start_time = time.time()

    def fetch_agents():
        return db.query(models.Agent).filter(
            models.Agent.is_active.is_(True), models.Agent.provider == "huggingface"
        ).all()

    agents = await run_in_threadpool(fetch_agents)

    if not agents:
        raise HTTPException(
            status_code=503, detail="No agents currently registered in the marketplace."
        )

    candidate_agents = [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "capabilities": a.capabilities,
            "cost_per_request": a.cost_per_request,
            "average_latency_ms": a.average_latency_ms,
            "accuracy_score": a.accuracy_score,
            "provider": a.provider,
            "framework": a.framework,
            "api_endpoint": a.api_endpoint,
            "model_id": a.model_id,
            "call_count": a.call_count
        }
        for a in agents
    ]

    prefs = {
        "cost": query_req.pref_cost,
        "latency": query_req.pref_latency,
        "accuracy": query_req.pref_accuracy,
    }

    final_state = await router.aselect_best_agent_and_invoke(query_req.query, candidate_agents, prefs)
    selected_agent = final_state.get("selected")
    
    if not selected_agent:
        err_msg = final_state.get("error", "Routing failed to select an agent.")
        raise HTTPException(status_code=500, detail=err_msg)

    agent_text_response = final_state.get("response", "No response generated")
    if final_state.get("error"):
        agent_text_response = f"Error calling agent: {final_state['error']}"

    execution_time_ms = (time.time() - start_time) * 1000
    result = schemas.QueryResultResponse(
        selected_agent=selected_agent["name"],
        selected_agent_provider=selected_agent.get("provider", "huggingface"),
        selected_agent_framework=selected_agent.get("framework", "custom"),
        response=agent_text_response,
        execution_time_ms=execution_time_ms,
    )
    
    # Offload the synchronous DB insert to a threadpool thread to avoid blocking the event loop
    log_id = await run_in_threadpool(log_query_to_db, query_req, result, selected_agent.get("id"))
    result.log_id = log_id
    
    return result


@app.get("/api/history/", response_model=List[schemas.QueryLogResponse])
def get_query_history(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return (
        db.query(models.QueryLog)
        .order_by(models.QueryLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@app.delete("/api/history/bulk")
def delete_history_bulk(req: schemas.BulkDeleteRequest, db: Session = Depends(get_db)):
    # Perform a bulk delete using synchronize_session=False for efficiency
    deleted_count = db.query(models.QueryLog).filter(models.QueryLog.id.in_(req.ids)).delete(synchronize_session=False)
    db.commit()
    return {"status": "success", "detail": f"Deleted {deleted_count} logs"}


@app.post("/api/history/{log_id}/feedback")
def submit_query_feedback(
    log_id: int, req: schemas.FeedbackRequest, db: Session = Depends(get_db)
):
    log_entry = db.query(models.QueryLog).filter(models.QueryLog.id == log_id).first()
    if not log_entry:
        raise HTTPException(status_code=404, detail="Log entry not found")
        
    log_entry.feedback_score = 1 if req.is_positive else -1
    
    agent = db.query(models.Agent).filter(models.Agent.name == log_entry.selected_agent_name).first()
    if agent:
        # Dynamic accuracy adjustment 
        adjustment = 0.05 if req.is_positive else -0.05
        new_accuracy = (agent.accuracy_score or 0.8) + adjustment
        agent.accuracy_score = max(0.0, min(1.0, new_accuracy))
        
    db.commit()
    return {"status": "success", "detail": "Feedback saved and accuracy updated"}


frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
