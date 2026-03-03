"""
seed_db.py — Seeds the database directly (no HTTP server needed).
Run as part of the Render build command so agents are always present on deploy.
"""
import sys
from pathlib import Path

# Ensure the backend directory is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import Base, SessionLocal, engine, run_sqlite_migrations
import models

AGENTS = [
    {
        "name": "HF-MathReasoner",
        "description": "Instruction-tuned model for math and analytical reasoning tasks.",
        "capabilities": "math, algebra, calculus, reasoning, problem-solving",
        "cost_per_request": 0.04,
        "average_latency_ms": 950.0,
        "accuracy_score": 0.90,
        "provider": "huggingface",
        "framework": "langgraph",
        "model_id": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        "api_endpoint": None,
        "is_active": True,
        "call_count": 0,
    },
    {
        "name": "HF-CodeAssistant",
        "description": "Code-focused open-source model for generation and debugging.",
        "capabilities": "code, programming, debugging, python, javascript, software",
        "cost_per_request": 0.06,
        "average_latency_ms": 1250.0,
        "accuracy_score": 0.89,
        "provider": "huggingface",
        "framework": "langgraph",
        "model_id": "Qwen/Qwen2.5-7B-Instruct",
        "api_endpoint": None,
        "is_active": True,
        "call_count": 0,
    },
    {
        "name": "HF-CreativeWriter",
        "description": "Creative writing model for stories, copywriting, and ideation.",
        "capabilities": "writing, creative, story, poetry, marketing",
        "cost_per_request": 0.03,
        "average_latency_ms": 850.0,
        "accuracy_score": 0.84,
        "provider": "huggingface",
        "framework": "crewai",
        "model_id": "meta-llama/Llama-3.1-8B-Instruct",
        "api_endpoint": None,
        "is_active": True,
        "call_count": 0,
    },
    {
        "name": "HF-FastGeneralist",
        "description": "Fast low-cost general model for simple question answering.",
        "capabilities": "general, qa, simple, support, chit-chat",
        "cost_per_request": 0.01,
        "average_latency_ms": 600.0,
        "accuracy_score": 0.74,
        "provider": "huggingface",
        "framework": "autogen",
        "model_id": "Qwen/Qwen2.5-7B-Instruct",
        "api_endpoint": None,
        "is_active": True,
        "call_count": 0,
    },
    {
        "name": "HF-Instruct",
        "description": "Open-source instruction model served by Hugging Face Inference API.",
        "capabilities": "general, reasoning, question-answering, summarization",
        "cost_per_request": 0.02,
        "average_latency_ms": 900.0,
        "accuracy_score": 0.88,
        "provider": "huggingface",
        "framework": "langgraph",
        "model_id": "meta-llama/Llama-3.1-8B-Instruct",
        "api_endpoint": None,
        "is_active": True,
        "call_count": 0,
    },
    {
        "name": "HF-WeatherAssistant",
        "description": "General assistant with real-time weather data injection capability.",
        "capabilities": "weather, general, qa",
        "cost_per_request": 0.02,
        "average_latency_ms": 800.0,
        "accuracy_score": 0.87,
        "provider": "huggingface",
        "framework": "custom",
        "model_id": "meta-llama/Llama-3.1-8B-Instruct",
        "api_endpoint": None,
        "is_active": True,
        "call_count": 0,
    },
]


def seed():
    Base.metadata.create_all(bind=engine)
    run_sqlite_migrations()

    db = SessionLocal()
    seeded = 0
    skipped = 0
    try:
        for data in AGENTS:
            existing = db.query(models.Agent).filter(models.Agent.name == data["name"]).first()
            if existing:
                skipped += 1
                print(f"  Skipped (already exists): {data['name']}")
            else:
                agent = models.Agent(**data)
                db.add(agent)
                seeded += 1
                print(f"  Seeded: {data['name']}")
        db.commit()
    finally:
        db.close()

    print(f"\nDone. Seeded {seeded} agents, skipped {skipped} existing.")


if __name__ == "__main__":
    print("Seeding database with example agents...")
    seed()
