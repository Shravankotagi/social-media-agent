"""
app/db/models.py — SQLAlchemy ORM models matching the MySQL schema.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Text, Integer, DateTime, Date, Time, Enum, ForeignKey, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    twitter_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    profile_reports: Mapped[list["ProfileReport"]] = relationship(back_populates="user")
    competitor_reports: Mapped[list["CompetitorReport"]] = relationship(back_populates="user")
    calendars: Mapped[list["ContentCalendar"]] = relationship(back_populates="user")
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(back_populates="user")


class ProfileReport(Base):
    __tablename__ = "profile_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    report_json: Mapped[str] = mapped_column(Text(length=2**24))
    status: Mapped[str] = mapped_column(Enum("pending", "complete", "failed"), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="profile_reports")


class CompetitorReport(Base):
    __tablename__ = "competitor_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    report_json: Mapped[str] = mapped_column(Text(length=2**24))
    status: Mapped[str] = mapped_column(Enum("pending", "complete", "failed"), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="competitor_reports")


class ContentCalendar(Base):
    __tablename__ = "content_calendars"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    start_date: Mapped[datetime] = mapped_column(Date)
    end_date: Mapped[datetime] = mapped_column(Date)
    calendar_json: Mapped[str] = mapped_column(Text(length=2**24))
    status: Mapped[str] = mapped_column(
        Enum("draft", "under_review", "approved", "locked"), default="draft"
    )
    review_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="calendars")
    entries: Mapped[list["CalendarEntry"]] = relationship(back_populates="calendar", cascade="all, delete-orphan")


class CalendarEntry(Base):
    __tablename__ = "calendar_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    calendar_id: Mapped[str] = mapped_column(String(36), ForeignKey("content_calendars.id", ondelete="CASCADE"))
    day_number: Mapped[int] = mapped_column(Integer)
    scheduled_date: Mapped[datetime] = mapped_column(Date)
    platform: Mapped[str] = mapped_column(Enum("linkedin", "twitter", "both"))
    topic: Mapped[str] = mapped_column(String(500))
    format: Mapped[str | None] = mapped_column(String(100))
    posting_time: Mapped[datetime | None] = mapped_column(Time)
    status: Mapped[str] = mapped_column(
        Enum("planned", "content_generated", "approved", "published", "failed"), default="planned"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    calendar: Mapped["ContentCalendar"] = relationship(back_populates="entries")
    posts: Mapped[list["Post"]] = relationship(back_populates="entry", cascade="all, delete-orphan")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    entry_id: Mapped[str] = mapped_column(String(36), ForeignKey("calendar_entries.id", ondelete="CASCADE"))
    body_copy: Mapped[str | None] = mapped_column(Text(length=2**24))
    hashtags: Mapped[str | None] = mapped_column(Text)
    visual_prompt: Mapped[str | None] = mapped_column(Text(length=2**24))
    visual_url: Mapped[str | None] = mapped_column(String(500))
    copy_status: Mapped[str] = mapped_column(Enum("pending", "approved", "regenerate"), default="pending")
    hashtag_status: Mapped[str] = mapped_column(Enum("pending", "approved", "regenerate"), default="pending")
    visual_status: Mapped[str] = mapped_column(Enum("pending", "approved", "regenerate"), default="pending")
    publish_status: Mapped[str] = mapped_column(Enum("draft", "queued", "posted", "failed"), default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    platform_post_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    entry: Mapped["CalendarEntry"] = relationship(back_populates="posts")
    metrics: Mapped[list["PostMetric"]] = relationship(back_populates="post", cascade="all, delete-orphan")


class PostMetric(Base):
    __tablename__ = "post_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("posts.id", ondelete="CASCADE"))
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    reactions: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    polled_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    post: Mapped["Post"] = relationship(back_populates="metrics")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(Enum("running", "success", "failed"), default="running")
    token_usage: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="pipeline_runs")


class HITLSession(Base):
    __tablename__ = "hitl_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    session_type: Mapped[str] = mapped_column(Enum("calendar_review", "content_review"))
    reference_id: Mapped[str] = mapped_column(String(36))
    messages_json: Mapped[str] = mapped_column(Text(length=2**24))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
