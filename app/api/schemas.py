"""
app/api/schemas.py — Pydantic schemas for all API request and response models.
"""
from __future__ import annotations
from datetime import datetime, date
from typing import Any, Optional
from pydantic import BaseModel, Field, HttpUrl


# ── User ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    name: str
    linkedin_url: Optional[str]
    twitter_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Profile Analysis ──────────────────────────────────────────────────────────

class ProfileAnalysisRequest(BaseModel):
    user_id: str
    use_mock: bool = Field(default=True, description="Use mock data if live API unavailable")
    profile_data: Optional[dict] = Field(default=None, description="Raw profile data to analyse")

class ProfileAnalysisResponse(BaseModel):
    user_id: str
    report_id: str
    report: dict
    status: str


# ── Competitor Analysis ───────────────────────────────────────────────────────

class CompetitorAnalysisRequest(BaseModel):
    user_id: str
    use_mock: bool = True
    competitor_data: Optional[list[dict]] = None

class CompetitorAnalysisResponse(BaseModel):
    user_id: str
    report_id: str
    report: dict
    status: str


# ── Calendar ──────────────────────────────────────────────────────────────────

class CalendarGenerateRequest(BaseModel):
    user_id: str
    days: int = Field(default=14, ge=1, le=30)
    start_date: Optional[date] = None

class CalendarResponse(BaseModel):
    calendar_id: str
    user_id: str
    title: str
    status: str
    entries: list[dict]
    created_at: datetime

    class Config:
        from_attributes = True


# ── HITL Calendar Review ──────────────────────────────────────────────────────

class CalendarEditRequest(BaseModel):
    calendar_id: str
    user_id: str
    message: str = Field(..., description="Natural language edit request or 'approve' to lock")

class CalendarEditResponse(BaseModel):
    calendar_id: str
    status: str
    updated_calendar: dict
    assistant_response: str
    is_locked: bool


# ── Content Generation ────────────────────────────────────────────────────────

class ContentGenerateRequest(BaseModel):
    calendar_id: str
    user_id: str
    entry_ids: Optional[list[str]] = Field(
        default=None,
        description="Generate only for specific entries. None = all entries.",
    )

class RegenerateComponentRequest(BaseModel):
    post_id: str
    component: str = Field(..., description="copy | hashtags | visual")
    instruction: Optional[str] = Field(default=None, description="Optional specific instruction")

class PostResponse(BaseModel):
    post_id: str
    entry_id: str
    body_copy: Optional[str]
    hashtags: Optional[str]
    visual_prompt: Optional[str]
    copy_status: str
    hashtag_status: str
    visual_status: str
    publish_status: str

    class Config:
        from_attributes = True


# ── Review ────────────────────────────────────────────────────────────────────

class ApproveComponentRequest(BaseModel):
    post_id: str
    component: str  # copy | hashtags | visual | all


# ── Publishing ────────────────────────────────────────────────────────────────

class PublishRequest(BaseModel):
    post_id: str
    platform: Optional[str] = Field(
        default=None,
        description="Override platform. None = use calendar entry platform.",
    )

class PublishResponse(BaseModel):
    post_id: str
    results: dict        # platform → {success, mode, post_id / content}
    publish_status: str  # posted | failed | clipboard


# ── Metrics / Engagement (FR-7) ───────────────────────────────────────────────

class EngagementMetrics(BaseModel):
    post_id: str
    impressions: int = 0
    reactions: int = 0
    comments: int = 0
    shares: int = 0

class AdaptiveSuggestion(BaseModel):
    post_id: str
    performance_summary: str
    suggestions: list[str]
    affected_calendar_entries: list[int]  # day numbers


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    database: bool
    chromadb: bool
    twitter_api: bool
    linkedin_api: bool
    version: str = "1.0.0"


# ── Full Pipeline (convenience) ───────────────────────────────────────────────

class FullPipelineRequest(BaseModel):
    user_id: str
    days: int = 14
    use_mock: bool = True
    profile_data: Optional[dict] = None
    competitor_data: Optional[list[dict]] = None
