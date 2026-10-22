
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    job_id: Optional[str] = Field(None, description="Target Job ID")
    session_name: Optional[str] = Field(None, description="Display name for the screening batch")
    title: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    department: Optional[str] = None
    max_resume_count: Optional[int] = Field(None, ge=1, le=100, description="Max resumes allowed (capped at 100)")


class SessionResponse(BaseModel):
    id: str
    job_id: str
    session_name: str
    status: str
    candidate_count: int
    max_resume_count: int
    created_at: str
    completed_at: Optional[str] = None
    job_title: Optional[str] = None
    job_department: Optional[str] = None
    title: Optional[str] = None
    name: Optional[str] = None
    resume_count: Optional[int] = None
    description: Optional[str] = None
    department: Optional[str] = None



class SessionListResponse(BaseModel):
    items: List[SessionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SessionProgressResponse(BaseModel):
    session_id: str
    total: int
    pending: int
    validating: int
    extracting: int
    completed: int
    failed: int
    duplicate: int
    flagged_quality: int
    evaluated: int
    status: str
    is_finished: bool
