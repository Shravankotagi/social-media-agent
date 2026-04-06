"""
tests/test_api.py — Integration tests for FastAPI endpoints.
Uses TestClient with an in-memory SQLite DB to avoid MySQL dependency.
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── Test DB setup (SQLite in-memory) ─────────────────────────────────────────

TEST_DB_URL = "sqlite:///./test.db"

@pytest.fixture(scope="module")
def test_app():
    """Create app with test database."""
    from app.db.database import Base, get_db
    from app.main import app

    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    Base.metadata.drop_all(bind=engine)
    import os
    if os.path.exists("./test.db"):
        os.remove("./test.db")


# ── Health endpoint ───────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_200(self, test_app):
        resp = test_app.get("/api/v1/health")
        assert resp.status_code == 200

    def test_health_has_required_fields(self, test_app):
        resp = test_app.get("/api/v1/health")
        data = resp.json()
        assert "status" in data
        assert "database" in data
        assert "version" in data

    def test_root_returns_service_info(self, test_app):
        resp = test_app.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "service" in data
        assert "docs" in data


# ── User endpoints ────────────────────────────────────────────────────────────

class TestUserEndpoints:
    def test_create_user(self, test_app):
        resp = test_app.post("/api/v1/users", json={
            "name": "Test User",
            "linkedin_url": "https://linkedin.com/in/test",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test User"
        assert "id" in data

    def test_get_user(self, test_app):
        # Create first
        create_resp = test_app.post("/api/v1/users", json={"name": "Get Test"})
        user_id = create_resp.json()["id"]

        resp = test_app.get(f"/api/v1/users/{user_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == user_id

    def test_get_nonexistent_user(self, test_app):
        resp = test_app.get("/api/v1/users/nonexistent-id")
        assert resp.status_code == 404

    def test_user_has_timestamps(self, test_app):
        resp = test_app.post("/api/v1/users", json={"name": "Timestamp Test"})
        assert "created_at" in resp.json()


# ── Profile endpoints ─────────────────────────────────────────────────────────

MOCK_PROFILE_REPORT = {
    "writing_style": "technical",
    "tone": "authoritative",
    "vocabulary_level": "expert-level",
    "primary_topics": ["AI", "LLM"],
    "secondary_topics": [],
    "content_formats": ["long_post"],
    "posting_cadence": {},
    "engagement_patterns": {
        "highest_engagement_format": "thread",
        "highest_engagement_topic": "AI",
        "avg_likes": 200.0,
        "avg_comments": 30.0,
        "avg_shares": 20.0,
    },
    "content_gaps": ["tutorials"],
    "strategic_recommendations": ["Post more"],
    "niche_positioning": "AI practitioner",
    "unique_value_prop": "Practical AI content",
}


class TestProfileEndpoints:
    @patch("app.agents.profile_agent.ProfileAgent.run", return_value=MOCK_PROFILE_REPORT)
    def test_analyse_profile(self, mock_run, test_app):
        user_resp = test_app.post("/api/v1/users", json={"name": "Profile Test"})
        user_id = user_resp.json()["id"]

        resp = test_app.post("/api/v1/profile/analyse", json={
            "user_id": user_id,
            "use_mock": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == user_id
        assert "report" in data
        assert data["status"] == "complete"

    def test_analyse_profile_unknown_user(self, test_app):
        resp = test_app.post("/api/v1/profile/analyse", json={
            "user_id": "unknown-user",
            "use_mock": True,
        })
        assert resp.status_code == 404

    @patch("app.agents.profile_agent.ProfileAgent.run", return_value=MOCK_PROFILE_REPORT)
    def test_get_latest_profile(self, mock_run, test_app):
        user_resp = test_app.post("/api/v1/users", json={"name": "Latest Profile Test"})
        user_id = user_resp.json()["id"]
        test_app.post("/api/v1/profile/analyse", json={"user_id": user_id, "use_mock": True})

        resp = test_app.get(f"/api/v1/profile/{user_id}/latest")
        assert resp.status_code == 200
        assert "report" in resp.json()


# ── Calendar endpoints ────────────────────────────────────────────────────────

MOCK_CALENDAR = {
    "title": "14-Day Content Calendar",
    "period_days": 14,
    "entries": [
        {"day": i, "date": f"2024-06-{i:02d}", "platform": "linkedin",
         "topic": f"Topic {i}", "format": "long_post", "posting_time": "09:00",
         "rationale": "test", "expected_engagement": "medium"}
        for i in range(1, 15)
    ],
    "strategic_themes": ["AI", "RAG"],
    "notes": "",
}


class TestCalendarEndpoints:
    def _setup_user_with_reports(self, test_app):
        """Helper: creates user + profile + competitor reports."""
        user_resp = test_app.post("/api/v1/users", json={"name": "Calendar Test"})
        user_id = user_resp.json()["id"]

        with patch("app.agents.profile_agent.ProfileAgent.run", return_value=MOCK_PROFILE_REPORT):
            test_app.post("/api/v1/profile/analyse", json={"user_id": user_id, "use_mock": True})

        mock_competitor = {
            "competitors": [], "content_gaps": [], "high_engagement_formats": [],
            "trending_topics": [], "niche_opportunities": [], "recommended_differentiation": "",
        }
        with patch("app.agents.competitor_agent.CompetitorAgent.run", return_value=mock_competitor):
            test_app.post("/api/v1/competitors/analyse", json={"user_id": user_id, "use_mock": True})

        return user_id

    @patch("app.agents.planner_agent.PlannerAgent.run", return_value=MOCK_CALENDAR)
    def test_generate_calendar(self, mock_run, test_app):
        user_id = self._setup_user_with_reports(test_app)
        resp = test_app.post("/api/v1/calendar/generate", json={
            "user_id": user_id, "days": 14,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "calendar_id" in data
        assert data["status"] == "draft"

    def test_generate_calendar_no_reports(self, test_app):
        user_resp = test_app.post("/api/v1/users", json={"name": "No Reports"})
        user_id = user_resp.json()["id"]
        resp = test_app.post("/api/v1/calendar/generate", json={"user_id": user_id, "days": 14})
        assert resp.status_code == 400

    @patch("app.agents.planner_agent.PlannerAgent.run", return_value=MOCK_CALENDAR)
    @patch("app.agents.planner_agent.PlannerAgent.apply_edit", return_value=MOCK_CALENDAR)
    def test_edit_calendar(self, mock_edit, mock_run, test_app):
        user_id = self._setup_user_with_reports(test_app)
        cal_resp = test_app.post("/api/v1/calendar/generate", json={"user_id": user_id, "days": 14})
        cal_id = cal_resp.json()["calendar_id"]

        resp = test_app.post("/api/v1/calendar/edit", json={
            "calendar_id": cal_id,
            "user_id": user_id,
            "message": "Change Day 3 to a post about LangGraph",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] in ("under_review", "locked")

    @patch("app.agents.planner_agent.PlannerAgent.run", return_value=MOCK_CALENDAR)
    def test_approve_calendar(self, mock_run, test_app):
        user_id = self._setup_user_with_reports(test_app)
        cal_resp = test_app.post("/api/v1/calendar/generate", json={"user_id": user_id, "days": 14})
        cal_id = cal_resp.json()["calendar_id"]

        resp = test_app.post("/api/v1/calendar/edit", json={
            "calendar_id": cal_id,
            "user_id": user_id,
            "message": "approve",
        })
        assert resp.status_code == 200
        assert resp.json()["is_locked"] is True
        assert resp.json()["status"] == "locked"


# ── Publish status endpoint ───────────────────────────────────────────────────

class TestPublishEndpoints:
    def test_publish_status(self, test_app):
        resp = test_app.get("/api/v1/publish/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "twitter_api" in data
        assert "linkedin_api" in data
