from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class ExecutionRecord(BaseModel):
    """Model representing an execution record"""
    
    id: str = Field(
        default_factory=lambda: f"exec_{uuid.uuid4()}",
        description="Unique identifier for the execution",
        min_length=1,
        max_length=255
    )
    
    timestamp: int = Field(
        default_factory=lambda: int(datetime.now().timestamp()),
        description="Unix timestamp of execution",
        ge=0
    )
    
    status: str = Field(
        description="Execution status (executed, proposed, gated)",
        default="proposed",
        min_length=1
    )
    
    confidence: float = Field(
        description="Confidence score between 0 and 1",
        ge=0,
        le=1,
        default=0.5
    )
    
    tags: list[str] = Field(
        default_factory=list,
        description="Tags associated with this execution"
    )
