"""
tests/conftest.py — Shared pytest fixtures used across all test modules.
"""
import pytest
import json
import os
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Use SQLite for tests — no MySQL needed
TEST_DATABASE_URL = "sqlite:///./test_conftest.db"


@pytest.fixture(scope="session")
def db_engine():
    from app.db.models import Base
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_conftest.db"):
        os.remove("./test_conftest.db")


@pytest.fixture(scope="session")
def db_session_factory(db_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


@pytest.fixture()
def db(db_session_factory):
    session = db_session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="session")
def client(db_engine, db_session_factory):
    from app.db.database import get_db
    from app.main import app

    def override_get_db():
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c


# ── Reusable data fixtures ────────────────────────────────────────────────────

@pytest.fixture()
def sample_profile_report():
    return {
        "writing_style": "technical and educational",
        "tone": "authoritative",
        "vocabulary_level": "expert-level",
        "primary_topics": ["RAG", "LangChain", "LangGraph", "AI agents", "production LLM"],
        "secondary_topics": ["MLOps", "Python"],
        "content_formats": ["long_post", "thread", "carousel"],
        "posting_cadence": {"linkedin": "3x/week", "twitter": "daily"},
        "engagement_patterns": {
            "highest_engagement_format": "thread",
            "highest_engagement_topic": "RAG",
            "avg_likes": 350.0,
            "avg_comments": 55.0,
            "avg_shares": 90.0,
        },
        "content_gaps": ["live coding tutorials", "benchmark comparisons"],
        "strategic_recommendations": [
            "Publish more code-heavy threads",
            "Cross-post LinkedIn articles to Twitter as threads",
        ],
        "niche_positioning": "Production AI engineer",
        "unique_value_prop": "Real-world deployment stories with working code",
    }


@pytest.fixture()
def sample_competitor_report():
    return {
        "competitors": [
            {
                "name": "Competitor A",
                "platform": "linkedin",
                "url": "https://linkedin.com/in/competitor-a",
                "bio": "ML researcher",
                "followers": 12000,
                "avg_likes": 500,
                "top_topics": ["AI safety", "alignment"],
                "top_formats": ["article"],
                "posting_frequency": "2x/week",
                "gap_opportunity": "No practical code content",
            }
        ],
        "content_gaps": ["code tutorials", "production case studies"],
        "high_engagement_formats": ["thread", "carousel"],
        "trending_topics": ["LangGraph", "RAG", "agents", "function calling"],
        "niche_opportunities": ["Production AI engineering", "LangGraph tutorials"],
        "recommended_differentiation": "Own the production AI engineering space",
    }


@pytest.fixture()
def sample_calendar():
    return {
        "title": "14-Day Content Calendar",
        "period_days": 14,
        "entries": [
            {
                "day": i,
                "date": f"2024-06-{i:02d}",
                "platform": "linkedin" if i % 2 == 0 else "twitter",
                "topic": f"Topic about AI and LLMs #{i}",
                "format": "long_post" if i % 3 == 0 else "thread",
                "posting_time": "09:00",
                "rationale": f"High engagement expected for topic {i}",
                "expected_engagement": "high" if i <= 3 else "medium",
            }
            for i in range(1, 15)
        ],
        "strategic_themes": ["RAG", "LangGraph", "production AI"],
        "notes": "Focus on practical content",
    }


@pytest.fixture()
def created_user(client):
    """Creates a user via API and returns the user dict."""
    resp = client.post("/api/v1/users", json={
        "name": "Fixture User",
        "linkedin_url": "https://linkedin.com/in/fixture",
        "twitter_url": "https://x.com/fixture",
    })
    assert resp.status_code == 200
    return resp.json()


@pytest.fixture()
def user_with_profile(client, created_user, sample_profile_report):
    """Creates user + profile report."""
    with patch("app.agents.profile_agent.ProfileAgent.run", return_value=sample_profile_report):
        client.post("/api/v1/profile/analyse", json={
            "user_id": created_user["id"],
            "use_mock": True,
        })
    return created_user


@pytest.fixture()
def user_with_reports(client, user_with_profile, sample_competitor_report):
    """Creates user + profile + competitor reports."""
    with patch("app.agents.competitor_agent.CompetitorAgent.run", return_value=sample_competitor_report):
        client.post("/api/v1/competitors/analyse", json={
            "user_id": user_with_profile["id"],
            "use_mock": True,
        })
    return user_with_profile


@pytest.fixture()
def user_with_calendar(client, user_with_reports, sample_calendar):
    """Creates user + reports + draft calendar."""
    with patch("app.agents.planner_agent.PlannerAgent.run", return_value=sample_calendar):
        resp = client.post("/api/v1/calendar/generate", json={
            "user_id": user_with_reports["id"],
            "days": 14,
        })
    assert resp.status_code == 200
    return user_with_reports, resp.json()["calendar_id"]


@pytest.fixture()
def user_with_locked_calendar(client, user_with_calendar):
    """Creates user + reports + approved/locked calendar."""
    user, calendar_id = user_with_calendar
    client.post("/api/v1/calendar/edit", json={
        "calendar_id": calendar_id,
        "user_id": user["id"],
        "message": "approve",
    })
    return user, calendar_id
