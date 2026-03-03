from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any
import asyncio
import random

app = FastAPI(title="Example Agents Server")

class QueryRequest(BaseModel):
    query: str

# 1. Math Agent (Cheap, Fast, Good at Math)
@app.post("/math")
async def math_agent(req: QueryRequest):
    # Simulate latency
    await asyncio.sleep(0.05)
    return {"response": f"[MathAgent] Solved: The answer to '{req.query}' is 42."}

# 2. Coding Agent (Moderate Cost, Moderate Latency, Good at Coding)
@app.post("/code")
async def code_agent(req: QueryRequest):
    await asyncio.sleep(0.3)
    return {"response": f"```python\n# [CodeAgent] Code for '{req.query}'\ndef solve():\n    pass\n```"}

# 3. Creative Writing Agent (Expensive, Slow, General/Creative)
@app.post("/creative")
async def creative_agent(req: QueryRequest):
    await asyncio.sleep(1.2)
    return {"response": f"[CreativeAgent] Once upon a time, regarding '{req.query}'... "}

# 4. Fast General Agent (Cheap, Very Fast, Low Accuracy/General)
@app.post("/fast_general")
async def fast_general_agent(req: QueryRequest):
    await asyncio.sleep(0.01)
    return {"response": f"[FastAgent] Quick thoughts on '{req.query}': It's interesting!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
