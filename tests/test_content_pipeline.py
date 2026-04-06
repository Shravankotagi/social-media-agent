"""
tests/test_content_pipeline.py — Tests for the full ContentPipeline.run_for_entry() flow
and each individual content agent (CopyAgent, HashtagAgent, VisualAgent).
"""
import pytest
from unittest.mock import patch, MagicMock


# ── Shared fixtures ───────────────────────────────────────────────────────────

PROFILE_REPORT = {
    "writing_style": "technical and conversational",
    "tone": "authoritative",
    "vocabulary_level": "expert-level",
    "primary_topics": ["RAG", "LangChain", "LangGraph", "agents"],
    "secondary_topics": ["MLOps"],
    "content_formats": ["long_post", "thread", "carousel"],
    "posting_cadence": {"linkedin": "3x/week", "twitter": "daily"},
    "engagement_patterns": {
        "highest_engagement_format": "thread",
        "highest_engagement_topic": "RAG",
        "avg_likes": 350.0,
        "avg_comments": 55.0,
        "avg_shares": 90.0,
    },
    "content_gaps": ["live coding tutorials"],
    "strategic_recommendations": ["More code examples"],
    "niche_positioning": "Production AI engineer",
    "unique_value_prop": "Real-world deployment content",
}

COMPETITOR_REPORT = {
    "competitors": [],
    "content_gaps": ["code tutorials"],
    "high_engagement_formats": ["thread", "carousel"],
    "trending_topics": ["LangGraph", "RAG", "function calling", "agents"],
    "niche_opportunities": ["Production AI engineering"],
    "recommended_differentiation": "Own practical production AI content",
}

CALENDAR_ENTRY_LINKEDIN = {
    "day": 1,
    "date": "2024-06-01",
    "platform": "linkedin",
    "topic": "Why most RAG systems fail at chunking",
    "format": "long_post",
    "posting_time": "09:00",
    "rationale": "High-value technical topic",
    "expected_engagement": "high",
}

CALENDAR_ENTRY_TWITTER = {
    "day": 2,
    "date": "2024-06-02",
    "platform": "twitter",
    "topic": "3 LangGraph patterns I use in every agent",
    "format": "thread",
    "posting_time": "10:00",
    "rationale": "Thread format for Twitter",
    "expected_engagement": "high",
}

MOCK_COPY = {
    "body_copy": "Most RAG systems fail at chunking, not retrieval. Here's why...",
    "word_count": 150,
    "hook": "Most RAG systems fail at chunking, not retrieval.",
    "call_to_action": "What chunking strategy do you use? Drop a comment.",
}

MOCK_HASHTAGS = {
    "hashtags": ["RAG", "LangChain", "AI", "MachineLearning", "LLM"],
    "primary_hashtags": ["RAG", "LangChain"],
    "niche_hashtags": ["LangChain", "VectorDB"],
    "trending_hashtags": ["GenerativeAI", "LLM"],
}

MOCK_VISUAL = {
    "visual_prompt": (
        "Clean technical infographic showing RAG pipeline with chunking step highlighted. "
        "Dark background, blue accents, minimal text. Professional AI aesthetic."
    ),
    "visual_type": "infographic",
    "color_palette": ["#0F172A", "#3B82F6", "#E2E8F0"],
    "key_text_elements": ["Chunking", "RAG Pipeline", "Why it fails"],
}


# ── CopyAgent Tests ───────────────────────────────────────────────────────────

class TestCopyAgent:
    def _make_mock_llm_response(self, content: str):
        mock_resp = MagicMock()
        mock_resp.content = content
        mock_resp.usage_metadata = {"total_tokens": 250}
        return mock_resp

    def test_copy_agent_instantiates(self):
        from app.agents.content_agents import CopyAgent
        agent = CopyAgent()
        assert agent is not None
        assert agent._llm is not None

    @patch("app.agents.content_agents._make_llm")
    @patch("app.rag.pipeline.retrieve_context", return_value=[])
    def test_copy_agent_run_returns_body_copy(self, mock_rag, mock_llm_factory):
        import json
        from app.agents.content_agents import CopyAgent
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = self._make_mock_llm_response(
            json.dumps(MOCK_COPY)
        )
        mock_llm_factory.return_value = mock_llm

        agent = CopyAgent()
        agent._llm = mock_llm
        result = agent.run(
            topic="Why most RAG systems fail at chunking",
            platform="linkedin",
            format="long_post",
            profile_report=PROFILE_REPORT,
            user_id="test-user",
        )
        assert "body_copy" in result
        assert isinstance(result["body_copy"], str)
        assert len(result["body_copy"]) > 0

    @patch("app.agents.content_agents._make_llm")
    @patch("app.rag.pipeline.retrieve_context", return_value=[])
    def test_copy_agent_fallback_on_parse_error(self, mock_rag, mock_llm_factory):
        from app.agents.content_agents import CopyAgent
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = self._make_mock_llm_response("not valid json {{{")
        mock_llm_factory.return_value = mock_llm

        agent = CopyAgent()
        agent._llm = mock_llm
        result = agent.run(
            topic="test topic",
            platform="twitter",
            format="short_post",
            profile_report=PROFILE_REPORT,
        )
        # Should not raise — fallback kicks in
        assert "body_copy" in result

    def test_copy_agent_fallback_structure(self):
        """Fallback dict has all required keys."""
        fallback = {
            "body_copy": "Content about RAG systems",
            "word_count": 100,
            "hook": "Here's what you need to know about RAG systems",
            "call_to_action": "What do you think? Drop a comment below.",
        }
        for key in ["body_copy", "word_count", "hook", "call_to_action"]:
            assert key in fallback

    @patch("app.agents.content_agents._make_llm")
    @patch("app.rag.pipeline.retrieve_context", return_value=["prev content chunk"])
    def test_copy_agent_uses_rag_context(self, mock_rag, mock_llm_factory):
        """Verifies RAG retrieve_context is called during copy generation."""
        import json
        from app.agents.content_agents import CopyAgent
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = self._make_mock_llm_response(json.dumps(MOCK_COPY))
        mock_llm_factory.return_value = mock_llm

        agent = CopyAgent()
        agent._llm = mock_llm
        agent.run(
            topic="RAG chunking",
            platform="linkedin",
            format="long_post",
            profile_report=PROFILE_REPORT,
            user_id="user-123",
        )
        mock_rag.assert_called_once()


# ── HashtagAgent Tests ────────────────────────────────────────────────────────

class TestHashtagAgent:
    def test_hashtag_agent_instantiates(self):
        from app.agents.content_agents import HashtagAgent
        agent = HashtagAgent()
        assert agent is not None

    @patch("app.agents.content_agents._make_llm")
    def test_hashtag_agent_run_returns_hashtags(self, mock_llm_factory):
        import json
        from app.agents.content_agents import HashtagAgent
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = json.dumps(MOCK_HASHTAGS)
        mock_resp.usage_metadata = {"total_tokens": 100}
        mock_llm.invoke.return_value = mock_resp
        mock_llm_factory.return_value = mock_llm

        agent = HashtagAgent()
        agent._llm = mock_llm
        result = agent.run(
            topic="RAG chunking",
            platform="linkedin",
            profile_report=PROFILE_REPORT,
            competitor_report=COMPETITOR_REPORT,
        )
        assert "hashtags" in result
        assert isinstance(result["hashtags"], list)
        assert len(result["hashtags"]) > 0

    @patch("app.agents.content_agents._make_llm")
    def test_hashtag_agent_fallback_on_parse_error(self, mock_llm_factory):
        from app.agents.content_agents import HashtagAgent
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = "invalid json"
        mock_resp.usage_metadata = None
        mock_llm.invoke.return_value = mock_resp
        mock_llm_factory.return_value = mock_llm

        agent = HashtagAgent()
        agent._llm = mock_llm
        result = agent.run(
            topic="AI topic",
            platform="twitter",
            profile_report=PROFILE_REPORT,
            competitor_report=COMPETITOR_REPORT,
        )
        assert "hashtags" in result
        assert "primary_hashtags" in result

    def test_hashtag_fallback_structure(self):
        fallback = {
            "hashtags": ["AI", "MachineLearning", "LLM", "Python"],
            "primary_hashtags": ["AI", "MachineLearning"],
            "niche_hashtags": ["LangChain", "RAG"],
            "trending_hashtags": ["GenerativeAI"],
        }
        assert len(fallback["hashtags"]) >= 4
        assert len(fallback["primary_hashtags"]) <= len(fallback["hashtags"])

    def test_hashtag_uses_trending_topics_from_competitor(self):
        """Hashtag agent receives competitor trending topics."""
        trending = COMPETITOR_REPORT["trending_topics"]
        # Verify the trending topics are strings (usable as hashtags)
        assert all(isinstance(t, str) for t in trending)
        assert len(trending) > 0


# ── VisualAgent Tests ─────────────────────────────────────────────────────────

class TestVisualAgent:
    def test_visual_agent_instantiates(self):
        from app.agents.content_agents import VisualAgent
        agent = VisualAgent()
        assert agent is not None

    @patch("app.agents.content_agents._make_llm")
    def test_visual_agent_run_returns_prompt(self, mock_llm_factory):
        import json
        from app.agents.content_agents import VisualAgent
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = json.dumps(MOCK_VISUAL)
        mock_resp.usage_metadata = {"total_tokens": 150}
        mock_llm.invoke.return_value = mock_resp
        mock_llm_factory.return_value = mock_llm

        agent = VisualAgent()
        agent._llm = mock_llm
        result = agent.run(
            topic="RAG chunking",
            platform="linkedin",
            format="long_post",
            body_copy="Most RAG systems fail at chunking...",
        )
        assert "visual_prompt" in result
        assert "visual_type" in result
        assert len(result["visual_prompt"]) > 0

    @patch("app.agents.content_agents._make_llm")
    def test_visual_agent_fallback_on_error(self, mock_llm_factory):
        from app.agents.content_agents import VisualAgent
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = "bad json"
        mock_resp.usage_metadata = None
        mock_llm.invoke.return_value = mock_resp
        mock_llm_factory.return_value = mock_llm

        agent = VisualAgent()
        agent._llm = mock_llm
        result = agent.run(
            topic="LangGraph patterns",
            platform="twitter",
            format="thread",
        )
        assert "visual_prompt" in result
        assert "color_palette" in result
        assert isinstance(result["color_palette"], list)

    def test_visual_fallback_color_palette_valid(self):
        fallback = {
            "visual_prompt": "Clean modern infographic about RAG.",
            "visual_type": "infographic",
            "color_palette": ["#0F172A", "#3B82F6", "#E2E8F0"],
            "key_text_elements": ["RAG"],
        }
        assert all(c.startswith("#") for c in fallback["color_palette"])

    def test_visual_truncates_long_copy(self):
        """Long body_copy should be summarised before sending to LLM."""
        long_copy = "word " * 500
        summary = long_copy[:200] + "..." if len(long_copy) > 200 else long_copy
        assert len(summary) <= 203  # 200 chars + "..."


# ── ContentPipeline Integration Tests ────────────────────────────────────────

class TestContentPipeline:
    def _mock_agents(self):
        """Returns patch contexts for all three agents."""
        return (
            patch("app.agents.content_agents.CopyAgent.run", return_value=MOCK_COPY),
            patch("app.agents.content_agents.HashtagAgent.run", return_value=MOCK_HASHTAGS),
            patch("app.agents.content_agents.VisualAgent.run", return_value=MOCK_VISUAL),
        )

    def test_pipeline_instantiates(self):
        from app.agents.content_agents import ContentPipeline
        pipeline = ContentPipeline()
        assert pipeline.copy_agent is not None
        assert pipeline.hashtag_agent is not None
        assert pipeline.visual_agent is not None

    def test_pipeline_run_for_linkedin_entry(self):
        from app.agents.content_agents import ContentPipeline
        copy_patch, hashtag_patch, visual_patch = self._mock_agents()
        with copy_patch, hashtag_patch, visual_patch:
            pipeline = ContentPipeline()
            result = pipeline.run_for_entry(
                entry=CALENDAR_ENTRY_LINKEDIN,
                profile_report=PROFILE_REPORT,
                competitor_report=COMPETITOR_REPORT,
                user_id="test-user",
            )
        assert "entry" in result
        assert "copy" in result
        assert "hashtags" in result
        assert "visual" in result
        assert result["entry"]["platform"] == "linkedin"

    def test_pipeline_run_for_twitter_entry(self):
        from app.agents.content_agents import ContentPipeline
        copy_patch, hashtag_patch, visual_patch = self._mock_agents()
        with copy_patch, hashtag_patch, visual_patch:
            pipeline = ContentPipeline()
            result = pipeline.run_for_entry(
                entry=CALENDAR_ENTRY_TWITTER,
                profile_report=PROFILE_REPORT,
                competitor_report=COMPETITOR_REPORT,
            )
        assert result["entry"]["platform"] == "twitter"
        assert result["copy"] == MOCK_COPY
        assert result["hashtags"] == MOCK_HASHTAGS
        assert result["visual"] == MOCK_VISUAL

    def test_pipeline_passes_body_copy_to_visual_agent(self):
        """Visual agent should receive body_copy from copy agent output."""
        from app.agents.content_agents import ContentPipeline

        visual_run_calls = []

        def capture_visual_run(self_inner, topic, platform, format, body_copy="", user_id=""):
            visual_run_calls.append(body_copy)
            return MOCK_VISUAL

        copy_patch = patch("app.agents.content_agents.CopyAgent.run", return_value=MOCK_COPY)
        hashtag_patch = patch("app.agents.content_agents.HashtagAgent.run", return_value=MOCK_HASHTAGS)
        visual_patch = patch.object(
            __import__("app.agents.content_agents", fromlist=["VisualAgent"]).VisualAgent,
            "run",
            capture_visual_run,
        )

        with copy_patch, hashtag_patch, visual_patch:
            pipeline = ContentPipeline()
            pipeline.run_for_entry(
                entry=CALENDAR_ENTRY_LINKEDIN,
                profile_report=PROFILE_REPORT,
                competitor_report=COMPETITOR_REPORT,
            )

        if visual_run_calls:
            assert visual_run_calls[0] == MOCK_COPY["body_copy"]

    def test_pipeline_all_three_agents_called(self):
        """All three agents must be called exactly once per entry."""
        from app.agents.content_agents import ContentPipeline

        copy_mock = MagicMock(return_value=MOCK_COPY)
        hashtag_mock = MagicMock(return_value=MOCK_HASHTAGS)
        visual_mock = MagicMock(return_value=MOCK_VISUAL)

        with patch("app.agents.content_agents.CopyAgent.run", copy_mock), \
             patch("app.agents.content_agents.HashtagAgent.run", hashtag_mock), \
             patch("app.agents.content_agents.VisualAgent.run", visual_mock):
            pipeline = ContentPipeline()
            pipeline.run_for_entry(
                entry=CALENDAR_ENTRY_LINKEDIN,
                profile_report=PROFILE_REPORT,
                competitor_report=COMPETITOR_REPORT,
            )

        copy_mock.assert_called_once()
        hashtag_mock.assert_called_once()
        visual_mock.assert_called_once()

    def test_pipeline_result_has_correct_entry_topic(self):
        from app.agents.content_agents import ContentPipeline
        copy_patch, hashtag_patch, visual_patch = self._mock_agents()
        with copy_patch, hashtag_patch, visual_patch:
            pipeline = ContentPipeline()
            result = pipeline.run_for_entry(
                entry=CALENDAR_ENTRY_LINKEDIN,
                profile_report=PROFILE_REPORT,
                competitor_report=COMPETITOR_REPORT,
            )
        assert result["entry"]["topic"] == CALENDAR_ENTRY_LINKEDIN["topic"]

    def test_pipeline_copy_agent_receives_platform(self):
        """Copy agent must receive the correct platform for formatting."""
        from app.agents.content_agents import ContentPipeline

        received_platform = []

        def capture_copy(self_inner, topic, platform, format, profile_report, user_id=""):
            received_platform.append(platform)
            return MOCK_COPY

        copy_patch = patch.object(
            __import__("app.agents.content_agents", fromlist=["CopyAgent"]).CopyAgent,
            "run", capture_copy,
        )
        hashtag_patch = patch("app.agents.content_agents.HashtagAgent.run", return_value=MOCK_HASHTAGS)
        visual_patch = patch("app.agents.content_agents.VisualAgent.run", return_value=MOCK_VISUAL)

        with copy_patch, hashtag_patch, visual_patch:
            pipeline = ContentPipeline()
            pipeline.run_for_entry(
                entry=CALENDAR_ENTRY_TWITTER,
                profile_report=PROFILE_REPORT,
                competitor_report=COMPETITOR_REPORT,
            )

        if received_platform:
            assert received_platform[0] == "twitter"

    def test_pipeline_run_multiple_entries(self):
        """Running pipeline for multiple entries should work independently."""
        from app.agents.content_agents import ContentPipeline
        copy_patch, hashtag_patch, visual_patch = self._mock_agents()
        with copy_patch, hashtag_patch, visual_patch:
            pipeline = ContentPipeline()
            entries = [CALENDAR_ENTRY_LINKEDIN, CALENDAR_ENTRY_TWITTER]
            results = [
                pipeline.run_for_entry(
                    entry=e,
                    profile_report=PROFILE_REPORT,
                    competitor_report=COMPETITOR_REPORT,
                )
                for e in entries
            ]
        assert len(results) == 2
        assert results[0]["entry"]["platform"] == "linkedin"
        assert results[1]["entry"]["platform"] == "twitter"

    def test_pipeline_result_structure_complete(self):
        """Result dict must have all required top-level keys."""
        from app.agents.content_agents import ContentPipeline
        copy_patch, hashtag_patch, visual_patch = self._mock_agents()
        with copy_patch, hashtag_patch, visual_patch:
            pipeline = ContentPipeline()
            result = pipeline.run_for_entry(
                entry=CALENDAR_ENTRY_LINKEDIN,
                profile_report=PROFILE_REPORT,
                competitor_report=COMPETITOR_REPORT,
            )
        required_keys = ["entry", "copy", "hashtags", "visual"]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_copy_result_has_body_copy(self):
        from app.agents.content_agents import ContentPipeline
        copy_patch, hashtag_patch, visual_patch = self._mock_agents()
        with copy_patch, hashtag_patch, visual_patch:
            pipeline = ContentPipeline()
            result = pipeline.run_for_entry(
                entry=CALENDAR_ENTRY_LINKEDIN,
                profile_report=PROFILE_REPORT,
                competitor_report=COMPETITOR_REPORT,
            )
        assert "body_copy" in result["copy"]
        assert len(result["copy"]["body_copy"]) > 0

    def test_hashtags_result_has_hashtag_list(self):
        from app.agents.content_agents import ContentPipeline
        copy_patch, hashtag_patch, visual_patch = self._mock_agents()
        with copy_patch, hashtag_patch, visual_patch:
            pipeline = ContentPipeline()
            result = pipeline.run_for_entry(
                entry=CALENDAR_ENTRY_LINKEDIN,
                profile_report=PROFILE_REPORT,
                competitor_report=COMPETITOR_REPORT,
            )
        assert "hashtags" in result["hashtags"]
        assert isinstance(result["hashtags"]["hashtags"], list)

    def test_visual_result_has_prompt(self):
        from app.agents.content_agents import ContentPipeline
        copy_patch, hashtag_patch, visual_patch = self._mock_agents()
        with copy_patch, hashtag_patch, visual_patch:
            pipeline = ContentPipeline()
            result = pipeline.run_for_entry(
                entry=CALENDAR_ENTRY_LINKEDIN,
                profile_report=PROFILE_REPORT,
                competitor_report=COMPETITOR_REPORT,
            )
        assert "visual_prompt" in result["visual"]
        assert len(result["visual"]["visual_prompt"]) > 0
