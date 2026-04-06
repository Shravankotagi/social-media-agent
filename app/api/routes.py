"""
app/api/routes.py — All FastAPI route handlers (TS-6).

Covers:
  /users           — user management
  /profile         — profile analysis (FR-1)
  /competitors     — competitor analysis (FR-2)
  /calendar        — calendar generation + HITL (FR-3)
  /content         — content generation + regeneration (FR-4, FR-5)
  /publish         — publishing (FR-6)
  /metrics         — engagement + adaptive re-planning (FR-7)
  /health          — health check
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.database import get_db, check_db_health
from app.db import models
from app.api.schemas import (
    UserCreate, UserResponse,
    ProfileAnalysisRequest, ProfileAnalysisResponse,
    CompetitorAnalysisRequest, CompetitorAnalysisResponse,
    CalendarGenerateRequest, CalendarResponse,
    CalendarEditRequest, CalendarEditResponse,
    ContentGenerateRequest, RegenerateComponentRequest, PostResponse,
    ApproveComponentRequest,
    PublishRequest, PublishResponse,
    EngagementMetrics, AdaptiveSuggestion,
    HealthResponse, FullPipelineRequest,
)
from app.agents.profile_agent import ProfileAgent
from app.agents.competitor_agent import CompetitorAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.content_agents import ContentPipeline, CopyAgent, HashtagAgent, VisualAgent
from app.services.publisher import Publisher
from app.db.database import check_db_health
from app.utils.logger import log

router = APIRouter()
publisher = Publisher()


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """Health check endpoint for all core services."""
    try:
        import httpx
        from app.config import get_settings
        settings = get_settings()
        # Try multiple endpoints for compatibility
        for endpoint in ["/api/v1/heartbeat", "/api/v1", "/"]:
            try:
                r = httpx.get(f"http://{settings.chroma_host}:{settings.chroma_port}{endpoint}", timeout=3)
                if r.status_code < 500:
                    chroma_ok = True
                    break
            except Exception:
                continue
        else:
            chroma_ok = False
    except Exception:
        chroma_ok = False

    pub_status = publisher.get_status()

    return HealthResponse(
        status="ok" if check_db_health() else "degraded",
        database=check_db_health(),
        chromadb=chroma_ok,
        twitter_api=pub_status["twitter_api"],
        linkedin_api=pub_status["linkedin_api"],
    )


# ── Users ─────────────────────────────────────────────────────────────────────

@router.post("/users", response_model=UserResponse, tags=["Users"])
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    """Create a new user."""
    user = models.User(
        id=str(uuid.uuid4()),
        name=payload.name,
        linkedin_url=payload.linkedin_url,
        twitter_url=payload.twitter_url,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log.info("user.created", user_id=user.id)
    return user


@router.get("/users/{user_id}", response_model=UserResponse, tags=["Users"])
def get_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── Profile Analysis ──────────────────────────────────────────────────────────

@router.post("/profile/analyse", response_model=ProfileAnalysisResponse, tags=["Profile"])
def analyse_profile(payload: ProfileAnalysisRequest, db: Session = Depends(get_db)):
    """
    Run Profile Intelligence Agent (FR-1).
    Returns a structured profile analysis report.
    """
    _assert_user_exists(payload.user_id, db)

    agent = ProfileAgent()
    report = agent.run(
        profile_data=None if payload.use_mock else payload.profile_data,
        user_id=payload.user_id,
    )

    record = models.ProfileReport(
        id=str(uuid.uuid4()),
        user_id=payload.user_id,
        report_json=json.dumps(report),
        status="complete",
    )
    db.add(record)
    db.commit()

    return ProfileAnalysisResponse(
        user_id=payload.user_id,
        report_id=record.id,
        report=report,
        status="complete",
    )


@router.get("/profile/{user_id}/latest", tags=["Profile"])
def get_latest_profile(user_id: str, db: Session = Depends(get_db)):
    """Get the most recent profile report for a user."""
    report = (
        db.query(models.ProfileReport)
        .filter(models.ProfileReport.user_id == user_id)
        .order_by(models.ProfileReport.created_at.desc())
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="No profile report found. Run /profile/analyse first.")
    return {"report_id": report.id, "report": json.loads(report.report_json), "status": report.status}


# ── Competitor Analysis ───────────────────────────────────────────────────────

@router.post("/competitors/analyse", response_model=CompetitorAnalysisResponse, tags=["Competitors"])
def analyse_competitors(payload: CompetitorAnalysisRequest, db: Session = Depends(get_db)):
    """Run Competitive Landscape Agent (FR-2)."""
    _assert_user_exists(payload.user_id, db)

    profile_report_row = (
        db.query(models.ProfileReport)
        .filter(models.ProfileReport.user_id == payload.user_id)
        .order_by(models.ProfileReport.created_at.desc())
        .first()
    )
    if not profile_report_row:
        raise HTTPException(status_code=400, detail="Run profile analysis first.")

    profile_report = json.loads(profile_report_row.report_json)
    agent = CompetitorAgent()
    report = agent.run(
        profile_report=profile_report,
        competitor_data=None if payload.use_mock else payload.competitor_data,
        user_id=payload.user_id,
    )

    record = models.CompetitorReport(
        id=str(uuid.uuid4()),
        user_id=payload.user_id,
        report_json=json.dumps(report),
        status="complete",
    )
    db.add(record)
    db.commit()

    return CompetitorAnalysisResponse(
        user_id=payload.user_id,
        report_id=record.id,
        report=report,
        status="complete",
    )


# ── Content Calendar ──────────────────────────────────────────────────────────

@router.post("/calendar/generate", response_model=CalendarResponse, tags=["Calendar"])
def generate_calendar(payload: CalendarGenerateRequest, db: Session = Depends(get_db)):
    """
    Generate a data-driven content calendar (FR-3).
    Requires profile and competitor reports to exist.
    """
    _assert_user_exists(payload.user_id, db)

    profile_row = _get_latest_report(db, models.ProfileReport, payload.user_id)
    competitor_row = _get_latest_report(db, models.CompetitorReport, payload.user_id)

    if not profile_row:
        raise HTTPException(status_code=400, detail="Run /profile/analyse first.")
    if not competitor_row:
        raise HTTPException(status_code=400, detail="Run /competitors/analyse first.")

    profile_report = json.loads(profile_row.report_json)
    competitor_report = json.loads(competitor_row.report_json)

    agent = PlannerAgent()
    calendar_data = agent.run(
        profile_report=profile_report,
        competitor_report=competitor_report,
        start_date=payload.start_date or date.today(),
        days=payload.days,
        user_id=payload.user_id,
    )

    start = payload.start_date or date.today()
    from datetime import timedelta
    end = start + timedelta(days=payload.days - 1)

    calendar_record = models.ContentCalendar(
        id=str(uuid.uuid4()),
        user_id=payload.user_id,
        title=calendar_data.get("title", f"{payload.days}-Day Content Calendar"),
        start_date=start,
        end_date=end,
        calendar_json=json.dumps(calendar_data),
        status="draft",
    )
    db.add(calendar_record)
    db.flush()

    # Store individual entries
    for entry in calendar_data.get("entries", []):
        db.add(models.CalendarEntry(
            id=str(uuid.uuid4()),
            calendar_id=calendar_record.id,
            day_number=entry["day"],
            scheduled_date=entry.get("date", str(start)),
            platform=entry["platform"],
            topic=entry["topic"],
            format=entry.get("format"),
            status="planned",
        ))

    db.commit()
    db.refresh(calendar_record)

    return CalendarResponse(
        calendar_id=calendar_record.id,
        user_id=payload.user_id,
        title=calendar_record.title,
        status=calendar_record.status,
        entries=calendar_data.get("entries", []),
        created_at=calendar_record.created_at,
    )


@router.post("/calendar/edit", response_model=CalendarEditResponse, tags=["Calendar"])
def edit_calendar(payload: CalendarEditRequest, db: Session = Depends(get_db)):
    """
    HITL calendar editing (FR-3, TS-4).
    Send a natural language edit request or 'approve' to lock the calendar.
    """
    calendar = _get_calendar(payload.calendar_id, db)
    calendar_data = json.loads(calendar.calendar_json)

    is_approve = payload.message.lower().strip() in ("approve", "approved", "looks good", "lock it")

    if is_approve:
        calendar.status = "locked"
        db.commit()
        return CalendarEditResponse(
            calendar_id=calendar.id,
            status="locked",
            updated_calendar=calendar_data,
            assistant_response="Calendar approved and locked! Ready to generate content.",
            is_locked=True,
        )

    # Apply edit
    agent = PlannerAgent()
    updated = agent.apply_edit(calendar_data, payload.message)

    # Save HITL session
    session = db.query(models.HITLSession).filter(
        models.HITLSession.reference_id == payload.calendar_id,
        models.HITLSession.session_type == "calendar_review",
    ).first()

    messages = []
    if session:
        messages = json.loads(session.messages_json)
    messages += [
        {"role": "user", "content": payload.message},
        {"role": "assistant", "content": f"Applied: {payload.message}"},
    ]

    if session:
        session.messages_json = json.dumps(messages)
    else:
        db.add(models.HITLSession(
            id=str(uuid.uuid4()),
            user_id=payload.user_id,
            session_type="calendar_review",
            reference_id=payload.calendar_id,
            messages_json=json.dumps(messages),
        ))

    calendar.calendar_json = json.dumps(updated)
    calendar.status = "under_review"
    db.commit()

    return CalendarEditResponse(
        calendar_id=calendar.id,
        status="under_review",
        updated_calendar=updated,
        assistant_response=(
            f"I've applied your change: '{payload.message}'. "
            "Review the updated calendar and send more edits, or say 'approve' to lock it."
        ),
        is_locked=False,
    )


@router.get("/calendar/{calendar_id}", tags=["Calendar"])
def get_calendar(calendar_id: str, db: Session = Depends(get_db)):
    cal = _get_calendar(calendar_id, db)
    return {"calendar_id": cal.id, "status": cal.status, "calendar": json.loads(cal.calendar_json)}


# ── Content Generation ────────────────────────────────────────────────────────

@router.post("/content/generate", tags=["Content"])
def generate_content(payload: ContentGenerateRequest, db: Session = Depends(get_db)):
    """
    Run the multi-agent content pipeline for all (or specified) calendar entries (FR-4).
    Calendar must be approved/locked first.
    """
    calendar = _get_calendar(payload.calendar_id, db)
    if calendar.status not in ("approved", "locked"):
        raise HTTPException(
            status_code=400,
            detail="Calendar must be approved/locked before generating content. Use /calendar/edit to approve."
        )

    # Use calendar's user_id as fallback if payload user_id is empty
    user_id = payload.user_id or calendar.user_id

    profile_row = _get_latest_report(db, models.ProfileReport, user_id)
    competitor_row = _get_latest_report(db, models.CompetitorReport, user_id)

    # Use mock reports if none found — still generate content
    from app.services.mock_data import MOCK_USER_PROFILE, MOCK_COMPETITORS
    from app.agents.profile_agent import ProfileAgent
    from app.agents.competitor_agent import CompetitorAgent

    if not profile_row:
        profile_report = ProfileAgent()._fallback_report(MOCK_USER_PROFILE)
    else:
        profile_report = json.loads(profile_row.report_json)

    if not competitor_row:
        competitor_report = CompetitorAgent()._fallback_report(MOCK_COMPETITORS)
    else:
        competitor_report = json.loads(competitor_row.report_json)

    calendar_data = json.loads(calendar.calendar_json)
    entries = calendar_data.get("entries", [])

    # Filter entries if specific ones requested
    entry_rows = db.query(models.CalendarEntry).filter(
        models.CalendarEntry.calendar_id == payload.calendar_id
    ).all()

    if payload.entry_ids:
        entry_rows = [e for e in entry_rows if e.id in payload.entry_ids]

    pipeline = ContentPipeline()
    results = []

    for entry_row in entry_rows:
        # Find matching entry data
        entry_data = next(
            (e for e in entries if e.get("day") == entry_row.day_number),
            {"topic": entry_row.topic, "platform": entry_row.platform, "format": entry_row.format or "short_post", "day": entry_row.day_number}
        )

        result = pipeline.run_for_entry(
            entry=entry_data,
            profile_report=profile_report,
            competitor_report=competitor_report,
            user_id=user_id,
        )

        # Persist post
        hashtags_str = " ".join(f"#{h}" for h in result["hashtags"].get("hashtags", []))
        post = models.Post(
            id=str(uuid.uuid4()),
            entry_id=entry_row.id,
            body_copy=result["copy"].get("body_copy"),
            hashtags=hashtags_str,
            visual_prompt=result["visual"].get("visual_prompt"),
            copy_status="pending",
            hashtag_status="pending",
            visual_status="pending",
            publish_status="draft",
        )
        db.add(post)
        entry_row.status = "content_generated"
        results.append({"entry_id": entry_row.id, "post_id": post.id, "day": entry_row.day_number})

    db.commit()
    return {"message": "Content generated", "posts": results, "count": len(results)}


@router.post("/content/regenerate", tags=["Content"])
def regenerate_component(payload: RegenerateComponentRequest, db: Session = Depends(get_db)):
    """
    Regenerate a specific component (copy | hashtags | visual) for a post (FR-5).
    Does NOT trigger a full pipeline re-run.
    """
    post = db.query(models.Post).filter(models.Post.id == payload.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    entry = post.entry
    calendar = entry.calendar

    profile_row = _get_latest_report(db, models.ProfileReport, calendar.user_id)
    competitor_row = _get_latest_report(db, models.CompetitorReport, calendar.user_id)
    profile_report = json.loads(profile_row.report_json)
    competitor_report = json.loads(competitor_row.report_json)

    instruction = payload.instruction or ""

    if payload.component == "copy":
        agent = CopyAgent()
        result = agent.run(
            topic=entry.topic + (f" ({instruction})" if instruction else ""),
            platform=entry.platform,
            format=entry.format or "short_post",
            profile_report=profile_report,
            user_id=calendar.user_id,
        )
        post.body_copy = result.get("body_copy", post.body_copy)
        post.copy_status = "pending"

    elif payload.component == "hashtags":
        agent = HashtagAgent()
        result = agent.run(
            topic=entry.topic,
            platform=entry.platform,
            profile_report=profile_report,
            competitor_report=competitor_report,
            user_id=calendar.user_id,
        )
        post.hashtags = " ".join(f"#{h}" for h in result.get("hashtags", []))
        post.hashtag_status = "pending"

    elif payload.component == "visual":
        agent = VisualAgent()
        result = agent.run(
            topic=entry.topic + (f" ({instruction})" if instruction else ""),
            platform=entry.platform,
            format=entry.format or "short_post",
            body_copy=post.body_copy or "",
            user_id=calendar.user_id,
        )
        post.visual_prompt = result.get("visual_prompt", post.visual_prompt)
        post.visual_status = "pending"

    else:
        raise HTTPException(status_code=400, detail="component must be 'copy', 'hashtags', or 'visual'")

    db.commit()
    log.info("content.regenerated", post_id=payload.post_id, component=payload.component)
    return {"message": f"{payload.component} regenerated", "post_id": post.id}


@router.post("/content/approve", tags=["Content"])
def approve_component(payload: ApproveComponentRequest, db: Session = Depends(get_db)):
    """Approve a post component or the whole post."""
    post = db.query(models.Post).filter(models.Post.id == payload.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if payload.component in ("copy", "all"):
        post.copy_status = "approved"
    if payload.component in ("hashtags", "all"):
        post.hashtag_status = "approved"
    if payload.component in ("visual", "all"):
        post.visual_status = "approved"

    # If all components approved, update entry status
    if post.copy_status == post.hashtag_status == post.visual_status == "approved":
        post.entry.status = "approved"

    db.commit()
    return {"message": "Approved", "post_id": post.id}


@router.get("/content/post/{post_id}", response_model=PostResponse, tags=["Content"])
def get_post(post_id: str, db: Session = Depends(get_db)):
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.get("/content/calendar/{calendar_id}/posts", tags=["Content"])
def list_calendar_posts(calendar_id: str, db: Session = Depends(get_db)):
    """List all generated posts for a calendar."""
    entries = db.query(models.CalendarEntry).filter(
        models.CalendarEntry.calendar_id == calendar_id
    ).all()
    result = []
    for entry in entries:
        for post in entry.posts:
            result.append({
                "day": entry.day_number,
                "platform": entry.platform,
                "topic": entry.topic,
                "post_id": post.id,
                "body_copy": post.body_copy,
                "hashtags": post.hashtags,
                "visual_prompt": post.visual_prompt,
                "copy_status": post.copy_status,
                "hashtag_status": post.hashtag_status,
                "visual_status": post.visual_status,
                "publish_status": post.publish_status,
            })
    return {"calendar_id": calendar_id, "posts": result}


# ── Publishing ────────────────────────────────────────────────────────────────

@router.post("/publish", response_model=PublishResponse, tags=["Publish"])
def publish_post(payload: PublishRequest, db: Session = Depends(get_db)):
    """Publish a post to its platform (FR-6). Falls back to clipboard mode."""
    post = db.query(models.Post).filter(models.Post.id == payload.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    entry = post.entry
    platform = payload.platform or entry.platform
    hashtags = [h.lstrip("#") for h in (post.hashtags or "").split() if h]

    results = publisher.publish(
        platform=platform,
        body_copy=post.body_copy or "",
        hashtags=hashtags,
        format=entry.format or "short_post",
    )

    # Determine overall status
    all_success = all(r.get("success") for r in results.values())
    any_clipboard = any(r.get("mode") == "clipboard" for r in results.values())
    status = "posted" if all_success else ("clipboard" if any_clipboard else "failed")

    post.publish_status = "posted" if all_success else "failed"
    if all_success:
        post.published_at = datetime.now()
        entry.status = "published"
    db.commit()

    return PublishResponse(post_id=post.id, results=results, publish_status=status)


@router.get("/publish/status", tags=["Publish"])
def publishing_status():
    """Check which publishing APIs are available."""
    return publisher.get_status()


# ── Engagement Metrics / Adaptive Re-planner (FR-7) ──────────────────────────

@router.post("/metrics/record", tags=["Metrics"])
def record_engagement(payload: EngagementMetrics, db: Session = Depends(get_db)):
    """Record engagement metrics for a published post."""
    post = db.query(models.Post).filter(models.Post.id == payload.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    metric = models.PostMetric(
        id=str(uuid.uuid4()),
        post_id=payload.post_id,
        impressions=payload.impressions,
        reactions=payload.reactions,
        comments=payload.comments,
        shares=payload.shares,
    )
    db.add(metric)
    db.commit()
    return {"message": "Metrics recorded", "metric_id": metric.id}


@router.get("/metrics/adapt/{calendar_id}", tags=["Metrics"])
def get_adaptive_suggestions(calendar_id: str, db: Session = Depends(get_db)):
    """
    Analyse post performance and suggest calendar adaptations (FR-7 bonus).
    """
    entries = db.query(models.CalendarEntry).filter(
        models.CalendarEntry.calendar_id == calendar_id
    ).all()

    high_performers = []
    for entry in entries:
        for post in entry.posts:
            if post.metrics:
                latest = post.metrics[-1]
                score = latest.reactions + latest.comments * 3 + latest.shares * 5
                high_performers.append((entry, post, score))

    if not high_performers:
        return {"suggestions": [], "message": "No engagement data available yet."}

    top = sorted(high_performers, key=lambda x: x[2], reverse=True)[:3]
    suggestions = []
    for entry, post, score in top:
        suggestions.append({
            "topic": entry.topic,
            "platform": entry.platform,
            "engagement_score": score,
            "suggestion": f"High engagement on '{entry.topic}' — consider more content on this theme.",
        })

    return {"calendar_id": calendar_id, "suggestions": suggestions}


# ── Full Pipeline (convenience endpoint) ─────────────────────────────────────

@router.post("/pipeline/run", tags=["Pipeline"])
def run_full_pipeline(payload: FullPipelineRequest, db: Session = Depends(get_db)):
    """
    Convenience endpoint: runs Profile → Competitor → Calendar in one call.
    Returns all three reports and the draft calendar for HITL review.
    """
    _assert_user_exists(payload.user_id, db)

    # Profile
    profile_agent = ProfileAgent()
    profile_report = profile_agent.run(
        profile_data=None if payload.use_mock else payload.profile_data,
        user_id=payload.user_id,
    )
    profile_row = models.ProfileReport(
        id=str(uuid.uuid4()), user_id=payload.user_id,
        report_json=json.dumps(profile_report), status="complete",
    )
    db.add(profile_row)

    # Competitor
    comp_agent = CompetitorAgent()
    competitor_report = comp_agent.run(
        profile_report=profile_report,
        competitor_data=None if payload.use_mock else payload.competitor_data,
        user_id=payload.user_id,
    )
    comp_row = models.CompetitorReport(
        id=str(uuid.uuid4()), user_id=payload.user_id,
        report_json=json.dumps(competitor_report), status="complete",
    )
    db.add(comp_row)

    # Calendar
    planner = PlannerAgent()
    calendar_data = planner.run(
        profile_report=profile_report,
        competitor_report=competitor_report,
        days=payload.days,
        user_id=payload.user_id,
    )
    from datetime import timedelta
    start = date.today() + timedelta(days=1)
    end = start + timedelta(days=payload.days - 1)

    cal_row = models.ContentCalendar(
        id=str(uuid.uuid4()), user_id=payload.user_id,
        title=calendar_data.get("title", "Content Calendar"),
        start_date=start, end_date=end,
        calendar_json=json.dumps(calendar_data), status="draft",
    )
    db.add(cal_row)
    db.flush()

    for entry in calendar_data.get("entries", []):
        db.add(models.CalendarEntry(
            id=str(uuid.uuid4()), calendar_id=cal_row.id,
            day_number=entry["day"], scheduled_date=entry.get("date", str(start)),
            platform=entry["platform"], topic=entry["topic"],
            format=entry.get("format"), status="planned",
        ))

    db.commit()

    return {
        "profile_report_id": profile_row.id,
        "competitor_report_id": comp_row.id,
        "calendar_id": cal_row.id,
        "calendar_status": "draft",
        "calendar": calendar_data,
        "message": "Pipeline complete. Review the calendar and use /calendar/edit to refine or approve.",
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _assert_user_exists(user_id: str, db: Session):
    if not db.query(models.User).filter(models.User.id == user_id).first():
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")


def _get_latest_report(db: Session, model_class, user_id: str):
    return (
        db.query(model_class)
        .filter(model_class.user_id == user_id)
        .order_by(model_class.created_at.desc())
        .first()
    )


def _get_calendar(calendar_id: str, db: Session) -> models.ContentCalendar:
    cal = db.query(models.ContentCalendar).filter(models.ContentCalendar.id == calendar_id).first()
    if not cal:
        raise HTTPException(status_code=404, detail="Calendar not found")
    return cal