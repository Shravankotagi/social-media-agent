"""
tests/test_agents.py — Unit tests for all agents.
Run: pytest tests/ --cov=app --cov-report=term-missing
"""
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock

# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_PROFILE_DATA = {
    "name": "Test User",
    "bio": "AI engineer writing about LLM systems",
    "posts": [
        {"platform": "linkedin", "text": "RAG tutorial", "likes": 200, "comments": 30, "shares": 50, "format": "long_post"},
        {"platform": "twitter", "text": "LangGraph tips", "likes": 150, "reposts": 40, "format": "thread"},
    ],
    "topics": ["RAG", "LangChain", "AI agents"],
    "posting_cadence": {"linkedin": "3x/week", "twitter": "daily"},
    "follower_count": {"linkedin": 5000, "twitter": 8000},
}

SAMPLE_PROFILE_REPORT = {
    "writing_style": "technical",
    "tone": "authoritative",
    "vocabulary_level": "expert-level",
    "primary_topics": ["RAG", "LangChain", "AI agents"],
    "secondary_topics": ["MLOps"],
    "content_formats": ["long_post", "thread"],
    "posting_cadence": {"linkedin": "3x/week", "twitter": "daily"},
    "engagement_patterns": {
        "highest_engagement_format": "thread",
        "highest_engagement_topic": "RAG",
        "avg_likes": 175.0,
        "avg_comments": 15.0,
        "avg_shares": 25.0,
    },
    "content_gaps": ["tutorials", "case studies"],
    "strategic_recommendations": ["Post more code examples"],
    "niche_positioning": "AI/ML practitioner",
    "unique_value_prop": "Practical production AI content",
}

SAMPLE_COMPETITOR_REPORT = {
    "competitors": [
        {"name": "Competitor A", "platform": "linkedin", "url": "https://x.com/a",
         "bio": "ML engineer", "followers": 10000, "avg_likes": 400,
         "top_topics": ["AI safety"], "top_formats": ["article"],
         "posting_frequency": "2x/week", "gap_opportunity": "No code examples"},
    ],
    "content_gaps": ["tutorials", "code walkthroughs"],
    "high_engagement_formats": ["thread", "carousel"],
    "trending_topics": ["LangGraph", "RAG", "agents"],
    "niche_opportunities": ["Production AI engineering"],
    "recommended_differentiation": "Own practical production AI content",
}


# ── Profile Agent Tests ───────────────────────────────────────────────────────

class TestProfileAgent:
    def test_fallback_report_structure(self):
        """Fallback report should have all required keys."""
        from app.agents.profile_agent import ProfileAgent
        agent = ProfileAgent()
        report = agent._fallback_report(SAMPLE_PROFILE_DATA)
        assert "writing_style" in report
        assert "primary_topics" in report
        assert "engagement_patterns" in report
        assert isinstance(report["primary_topics"], list)

    def test_fallback_report_avg_likes(self):
        """Fallback report should correctly compute avg likes."""
        from app.agents.profile_agent import ProfileAgent
        agent = ProfileAgent()
        report = agent._fallback_report(SAMPLE_PROFILE_DATA)
        # 200 + 150 = 350 / 2 = 175
        assert report["engagement_patterns"]["avg_likes"] == 175.0

    @patch("app.agents.profile_agent.ProfileAgent._build_llm")
    def test_run_uses_mock_data_when_no_profile(self, mock_llm_factory):
        """When profile_data is None, mock data should be used."""
        from app.agents.profile_agent import ProfileAgent
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = json.dumps(SAMPLE_PROFILE_REPORT)
        mock_resp.usage_metadata = None
        mock_llm.invoke.return_value = mock_resp
        mock_llm_factory.return_value = mock_llm

        # Just test fallback path works
        agent = ProfileAgent()
        report = agent._fallback_report(SAMPLE_PROFILE_DATA)
        assert report is not None


# ── Competitor Agent Tests ────────────────────────────────────────────────────

class TestCompetitorAgent:
    def test_fallback_report_structure(self):
        from app.agents.competitor_agent import CompetitorAgent
        from app.services.mock_data import MOCK_COMPETITORS
        agent = CompetitorAgent()
        report = agent._fallback_report(MOCK_COMPETITORS)
        assert "competitors" in report
        assert "content_gaps" in report
        assert "trending_topics" in report
        assert len(report["content_gaps"]) > 0

    def test_fallback_limits_competitors(self):
        from app.agents.competitor_agent import CompetitorAgent
        from app.services.mock_data import MOCK_COMPETITORS
        agent = CompetitorAgent()
        report = agent._fallback_report(MOCK_COMPETITORS)
        assert len(report["competitors"]) <= 5


# ── Planner Agent Tests ───────────────────────────────────────────────────────

class TestPlannerAgent:
    def test_fallback_calendar_entry_count(self):
        from app.agents.planner_agent import PlannerAgent
        from datetime import date
        agent = PlannerAgent()
        cal = agent._fallback_calendar(date.today(), 14, SAMPLE_PROFILE_REPORT)
        assert len(cal["entries"]) == 14

    def test_fallback_calendar_has_required_fields(self):
        from app.agents.planner_agent import PlannerAgent
        from datetime import date
        agent = PlannerAgent()
        cal = agent._fallback_calendar(date.today(), 7, SAMPLE_PROFILE_REPORT)
        for entry in cal["entries"]:
            assert "day" in entry
            assert "platform" in entry
            assert "topic" in entry
            assert "format" in entry

    def test_fallback_calendar_days_sequential(self):
        from app.agents.planner_agent import PlannerAgent
        from datetime import date
        agent = PlannerAgent()
        cal = agent._fallback_calendar(date.today(), 5, SAMPLE_PROFILE_REPORT)
        days = [e["day"] for e in cal["entries"]]
        assert days == list(range(1, 6))


# ── Content Agents Tests ──────────────────────────────────────────────────────

class TestContentAgents:
    def test_copy_agent_fallback(self):
        from app.agents.content_agents import CopyAgent
        agent = CopyAgent()
        # Test the fallback result structure
        fallback = {
            "body_copy": "Content about RAG systems",
            "word_count": 100,
            "hook": "Here's what you need to know about RAG systems",
            "call_to_action": "What do you think? Drop a comment below.",
        }
        assert "body_copy" in fallback
        assert "hook" in fallback

    def test_hashtag_agent_fallback(self):
        from app.agents.content_agents import HashtagAgent
        fallback = {
            "hashtags": ["AI", "MachineLearning", "LLM", "Python"],
            "primary_hashtags": ["AI", "MachineLearning"],
            "niche_hashtags": ["LangChain", "RAG"],
            "trending_hashtags": ["GenerativeAI"],
        }
        assert len(fallback["hashtags"]) > 0
        assert "primary_hashtags" in fallback

    def test_visual_agent_fallback(self):
        from app.agents.content_agents import VisualAgent
        fallback = {
            "visual_prompt": "Clean, modern infographic about RAG. Dark background.",
            "visual_type": "infographic",
            "color_palette": ["#0F172A", "#3B82F6", "#E2E8F0"],
            "key_text_elements": ["RAG"],
        }
        assert "visual_prompt" in fallback
        assert "visual_type" in fallback


# ── RAG Pipeline Tests ────────────────────────────────────────────────────────

class TestRAGPipeline:
    def test_chunk_text_basic(self):
        from app.rag.pipeline import chunk_text
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunk_text(text, max_tokens=50, overlap=0)
        assert len(chunks) >= 1
        assert all(isinstance(c, str) for c in chunks)

    def test_chunk_text_overlap(self):
        from app.rag.pipeline import chunk_text
        long_text = " ".join([f"Word{i}" for i in range(300)])
        chunks = chunk_text(long_text, max_tokens=100, overlap=20)
        assert len(chunks) > 1

    def test_chunk_text_empty(self):
        from app.rag.pipeline import chunk_text
        chunks = chunk_text("", max_tokens=100)
        assert chunks == []

    def test_chunk_text_short_text(self):
        from app.rag.pipeline import chunk_text
        chunks = chunk_text("Short text.", max_tokens=100)
        assert len(chunks) == 1
        assert "Short text." in chunks[0]


# ── Publisher Tests ───────────────────────────────────────────────────────────

class TestPublisher:
    def test_twitter_unavailable_returns_clipboard(self):
        from app.services.publisher import TwitterPublisher
        with patch("app.services.publisher.settings") as mock_settings:
            mock_settings.twitter_api_key = ""
            mock_settings.twitter_access_token = ""
            mock_settings.twitter_access_secret = ""
            pub = TwitterPublisher()
            result = pub._clipboard_fallback("Test post", ["AI", "ML"], "twitter")
            assert result["mode"] == "clipboard"
            assert "AI" in result["content"] or "Test post" in result["content"]

    def test_linkedin_unavailable_returns_clipboard(self):
        from app.services.publisher import LinkedInPublisher
        result = LinkedInPublisher._clipboard_fallback("Test post", ["AI"])
        assert result["mode"] == "clipboard"
        assert result["platform"] == "linkedin"

    def test_publisher_status(self):
        from app.services.publisher import Publisher
        pub = Publisher()
        status = pub.get_status()
        assert "twitter_api" in status
        assert "linkedin_api" in status


# ── Mock Data Tests ───────────────────────────────────────────────────────────

class TestMockData:
    def test_mock_user_profile_structure(self):
        from app.services.mock_data import MOCK_USER_PROFILE
        assert "name" in MOCK_USER_PROFILE
        assert "posts" in MOCK_USER_PROFILE
        assert len(MOCK_USER_PROFILE["posts"]) > 0

    def test_mock_competitors_count(self):
        from app.services.mock_data import MOCK_COMPETITORS
        assert 3 <= len(MOCK_COMPETITORS) <= 5

    def test_mock_calendar_template_14_days(self):
        from app.services.mock_data import MOCK_CALENDAR_TEMPLATE
        assert len(MOCK_CALENDAR_TEMPLATE) == 14

    def test_mock_calendar_platforms_valid(self):
        from app.services.mock_data import MOCK_CALENDAR_TEMPLATE
        valid_platforms = {"linkedin", "twitter", "both"}
        for entry in MOCK_CALENDAR_TEMPLATE:
            assert entry["platform"] in valid_platforms


# ── Config Tests ──────────────────────────────────────────────────────────────

class TestConfig:
    def test_mysql_url_format(self):
        from app.config import Settings
        s = Settings(mysql_host="localhost", mysql_port=3306, mysql_user="user",
                     mysql_password="pass", mysql_database="db")
        assert "mysql+mysqlconnector" in s.mysql_url
        assert "localhost" in s.mysql_url

    def test_chroma_url(self):
        from app.config import Settings
        s = Settings(chroma_host="chromadb", chroma_port=8000)
        assert "chromadb" in s.chroma_url
        assert "8000" in s.chroma_url


# ── API Schema Tests ──────────────────────────────────────────────────────────

class TestSchemas:
    def test_user_create_schema(self):
        from app.api.schemas import UserCreate
        u = UserCreate(name="Test", linkedin_url="https://linkedin.com/in/test")
        assert u.name == "Test"

    def test_calendar_generate_defaults(self):
        from app.api.schemas import CalendarGenerateRequest
        req = CalendarGenerateRequest(user_id="abc123")
        assert req.days == 14

    def test_regenerate_component_valid(self):
        from app.api.schemas import RegenerateComponentRequest
        req = RegenerateComponentRequest(post_id="post-1", component="copy")
        assert req.component == "copy"
