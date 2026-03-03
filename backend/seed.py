import asyncio
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv


# Load local backend/.env for API URL configuration.
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)


async def seed_agents():
    agents = [
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
        },
    ]

    base_url = os.getenv("MARKETPLACE_API_URL", "http://localhost:8000/api").rstrip("/")
    endpoint = f"{base_url}/agents/"

    async with httpx.AsyncClient() as client:
        for agent in agents:
            try:
                response = await client.post(endpoint, json=agent, timeout=20.0)
                if response.status_code == 200:
                    print(f"Registered: {agent['name']}")
                elif response.status_code == 400 and "already registered" in response.text:
                    print(f"Skipped (already exists): {agent['name']}")
                else:
                    print(f"Failed for {agent['name']}: {response.status_code} {response.text}")
            except Exception as exc:
                print(f"Error registering {agent['name']}: {exc}")


if __name__ == "__main__":
    print("Seeding marketplace with example agents...")
    asyncio.run(seed_agents())
    print("Done.")
