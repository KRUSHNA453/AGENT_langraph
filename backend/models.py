from sqlalchemy import Boolean, Column, Float, Integer, String, DateTime
from sqlalchemy.sql import func
from database import Base

class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    capabilities = Column(String) # Comma separated list of tags e.g. "math,coding"
    cost_per_request = Column(Float, default=0.0)
    average_latency_ms = Column(Float, default=0.0)
    accuracy_score = Column(Float, default=0.0) # 0 to 1 scale
    provider = Column(String, default="huggingface")  # mandatory: "huggingface"
    framework = Column(String, default="custom")  # "langgraph" | "autogen" | "crewai" | "custom"
    api_endpoint = Column(String)
    model_id = Column(String, nullable=True)  # Required for provider="huggingface"
    is_active = Column(Boolean, default=True)
    call_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_query = Column(String)
    routing_preference_cost = Column(Float)
    routing_preference_latency = Column(Float)
    routing_preference_accuracy = Column(Float)
    selected_agent_name = Column(String)
    selected_agent_provider = Column(String, default="huggingface")
    selected_agent_framework = Column(String, default="custom")
    agent_response = Column(String)
    execution_time_ms = Column(Float)
    feedback_score = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
