from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

AgentProvider = Literal["huggingface"]
AgentFramework = Literal["langgraph", "autogen", "crewai", "custom"]


class AgentBase(BaseModel):
    name: str
    description: str
    capabilities: str = Field(
        description="Comma-separated capability tags. Example: 'math, coding, reasoning'"
    )
    cost_per_request: float = Field(ge=0.0)
    average_latency_ms: float = Field(ge=0.0)
    accuracy_score: float = Field(ge=0.0, le=1.0)
    provider: AgentProvider = "huggingface"
    framework: AgentFramework = "custom"
    api_endpoint: Optional[str] = None
    model_id: Optional[str] = None
    is_active: bool = True
    call_count: int = 0

    @model_validator(mode="after")
    def validate_provider_requirements(self) -> "AgentBase":
        if self.provider == "huggingface" and not self.model_id:
            raise ValueError("`model_id` is required when provider='huggingface'.")
        return self


class AgentCreate(AgentBase):
    pass


class AgentResponse(AgentBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QueryRequest(BaseModel):
    query: str
    pref_cost: float = Field(default=0.33, ge=0.0, le=1.0, description="Weight for cost (0-1)")
    pref_latency: float = Field(default=0.33, ge=0.0, le=1.0, description="Weight for latency (0-1)")
    pref_accuracy: float = Field(default=0.34, ge=0.0, le=1.0, description="Weight for accuracy (0-1)")


class QueryResultResponse(BaseModel):
    selected_agent: str
    selected_agent_provider: str
    selected_agent_framework: str
    response: str
    execution_time_ms: float
    log_id: Optional[int] = None


class QueryLogResponse(BaseModel):
    id: int
    user_query: str
    routing_preference_cost: float
    routing_preference_latency: float
    routing_preference_accuracy: float
    selected_agent_name: str
    selected_agent_provider: Optional[str] = None
    selected_agent_framework: Optional[str] = None
    agent_response: str
    execution_time_ms: float
    feedback_score: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkDeleteRequest(BaseModel):
    ids: list[int]


class FeedbackRequest(BaseModel):
    is_positive: bool

