
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    department: Optional[str] = Field(None, max_length=100)
    original_description: Optional[str] = None
    description: Optional[str] = None
    seniority_level: Optional[str] = None

    def get_description(self) -> str:
        desc = self.original_description or self.description or ""
        if len(desc.strip()) < 5:
            return f"Requisition for {self.title}"
        return desc


class JobResponse(BaseModel):
    id: str
    title: str
    department: Optional[str] = None
    original_description: str
    created_at: str


class JobParseRequest(BaseModel):
    description: Optional[str] = None
    text: Optional[str] = None
    fallback_title: Optional[str] = Field(None, max_length=200)

    def get_text(self) -> str:
        return self.description or self.text or ""


class AutoCriterionItem(BaseModel):
    criterion_name: str
    description: str
    weight: float
    criterion_type: str
    category: str


class JobParseResponse(BaseModel):
    title: str
    department: Optional[str] = None
    min_experience_years: int
    education_level: Optional[str] = None
    required_skills: List[str]
    preferred_skills: List[str]
    responsibilities: List[str]
    auto_criteria: List[AutoCriterionItem]
