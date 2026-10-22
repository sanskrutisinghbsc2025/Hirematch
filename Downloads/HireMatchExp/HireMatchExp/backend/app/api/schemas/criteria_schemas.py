
from typing import List, Optional
from pydantic import BaseModel, Field


class CriterionItem(BaseModel):
    id: Optional[str] = None
    job_id: Optional[str] = None
    criterion_name: str = Field(..., min_length=1, max_length=150)
    name: Optional[str] = None
    description: Optional[str] = Field(None, max_length=500)
    weight: float = Field(..., ge=0.0, le=1.0)
    criterion_type: str = Field(default="REQUIRED")
    category: Optional[str] = Field(default="TECHNICAL_SKILL")
    is_enabled: bool = Field(default=True)


class CriteriaBatchSaveRequest(BaseModel):
    criteria: List[CriterionItem]
