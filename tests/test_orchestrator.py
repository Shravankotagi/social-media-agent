"""
tests/test_orchestrator.py — Tests for LangGraph workflow orchestrator.
"""
import pytest
import json
from unittest.mock import patch, MagicMock


MOCK_PROFILE = {
    "writing_style": "technical",
    "tone": "authoritative",
    "vocabulary_level": "expert-level",
    "primary_topics": ["AI", "RAG"],
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
    "content_gaps": [],
    "strategic_recommendations": [],
    "niche_positioning": "AI engineer",
    "unique_value_prop": "Practical AI",
}

MOCK_COMPETITOR = {
    "competitors": [],
    "content_gaps": ["tutorials"],
    "high_engagement_formats": ["thread"],
    "trending_topics": ["RAG", "LangGraph"],
    "niche_opportunities": ["production AI"],
    "recommended_differentiation": "Own production AI content",
}

MOCK_CALENDAR = {
    "title": "14-Day Calendar",
    "period_days": 14,
    "entries": [
        {
            "day": i,
            "date": f"2024-06-{i:02d}",
            "platform": "linkedin",
            "topic": f"AI Topic {i}",
            "format": "long_post",
            "posting_time": "09:00",
            "rationale": "test",
            "expected_engagement": "medium",
        }
        for i in range(1, 15)
    ],
    "strategic_themes": ["AI"],
    "notes": "",
}

MOCK_CONTENT = {
    "copy": {
        "body_copy": "Test post about AI",
        "word_count": 10,
        "hook": "Here's the thing about AI",
        "call_to_action": "Let me know what you think",
    },
    "hashtags": {
        "hashtags": ["AI", "ML"],
        "primary_hashtags": ["AI"],
        "niche_hashtags": ["RAG"],
        "trending_hashtags": ["GenerativeAI"],
    },
    "visual": {
        "visual_prompt": "Clean AI infographic",
        "visual_type": "infographic",
        "color_palette": ["#000", "#fff"],
        "key_text_elements": ["AI"],
    },
}


class TestPipelineState:
    def test_initial_state_structure(self):
        """PipelineState TypedDict has all required keys."""
        from app.orchestrator.workflow import PipelineState
        state: PipelineState = {
            "user_id": "test-user",
            "user_profile_data": {},
            "competitor_data": [],
            "profile_report": {},
            "competitor_report": {},
            "calendar": {},
            "calendar_status": "draft",
            "hitl_messages": [],
            "generated_posts": [],
            "current_stage": "init",
            "errors": [],
            "days": 14,
        }
        assert state["user_id"] == "test-user"
        assert state["current_stage"] == "init"
        assert state["days"] == 14


class TestGraphNodes:
    @patch("app.orchestrator.workflow.ProfileAgent")
    def test_run_profile_agent_node_success(self, mock_agent_class):
        from app.orchestrator.workflow import run_profile_agent
        mock_instance = MagicMock()
        mock_instance.run.return_value = MOCK_PROFILE
        mock_agent_class.return_value = mock_instance

        state = {
            "user_id": "test",
            "user_profile_data": {},
            "competitor_data": [],
            "profile_report": {},
            "competitor_report": {},
            "calendar": {},
            "calendar_status": "draft",
            "hitl_messages": [],
            "generated_posts": [],
            "current_stage": "init",
            "errors": [],
            "days": 14,
        }
        result = run_profile_agent(state)
        assert result["current_stage"] == "profile_complete"
        assert result["profile_report"] == MOCK_PROFILE

    @patch("app.orchestrator.workflow.ProfileAgent")
    def test_run_profile_agent_node_failure(self, mock_agent_class):
        from app.orchestrator.workflow import run_profile_agent
        mock_instance = MagicMock()
        mock_instance.run.side_effect = RuntimeError("LLM error")
        mock_agent_class.return_value = mock_instance

        state = {
            "user_id": "test",
            "user_profile_data": {},
            "competitor_data": [],
            "profile_report": {},
            "competitor_report": {},
            "calendar": {},
            "calendar_status": "draft",
            "hitl_messages": [],
            "generated_posts": [],
            "current_stage": "init",
            "errors": [],
            "days": 14,
        }
        result = run_profile_agent(state)
        assert result["current_stage"] == "profile_failed"
        assert len(result["errors"]) == 1
        assert "LLM error" in result["errors"][0]

    @patch("app.orchestrator.workflow.CompetitorAgent")
    def test_run_competitor_agent_node(self, mock_agent_class):
        from app.orchestrator.workflow import run_competitor_agent
        mock_instance = MagicMock()
        mock_instance.run.return_value = MOCK_COMPETITOR
        mock_agent_class.return_value = mock_instance

        state = {
            "user_id": "test",
            "user_profile_data": {},
            "competitor_data": [],
            "profile_report": MOCK_PROFILE,
            "competitor_report": {},
            "calendar": {},
            "calendar_status": "draft",
            "hitl_messages": [],
            "generated_posts": [],
            "current_stage": "profile_complete",
            "errors": [],
            "days": 14,
        }
        result = run_competitor_agent(state)
        assert result["current_stage"] == "competitor_complete"
        assert result["competitor_report"] == MOCK_COMPETITOR

    @patch("app.orchestrator.workflow.PlannerAgent")
    def test_run_planner_agent_node(self, mock_agent_class):
        from app.orchestrator.workflow import run_planner_agent
        mock_instance = MagicMock()
        mock_instance.run.return_value = MOCK_CALENDAR
        mock_agent_class.return_value = mock_instance

        state = {
            "user_id": "test",
            "user_profile_data": {},
            "competitor_data": [],
            "profile_report": MOCK_PROFILE,
            "competitor_report": MOCK_COMPETITOR,
            "calendar": {},
            "calendar_status": "draft",
            "hitl_messages": [],
            "generated_posts": [],
            "current_stage": "competitor_complete",
            "errors": [],
            "days": 14,
        }
        result = run_planner_agent(state)
        assert result["current_stage"] == "calendar_draft"
        assert result["calendar_status"] == "draft"
        assert len(result["calendar"]["entries"]) == 14


class TestRoutingFunctions:
    def test_route_after_profile_success(self):
        from app.orchestrator.workflow import route_after_profile
        state = {"current_stage": "profile_complete"}
        assert route_after_profile(state) == "competitor"

    def test_route_after_profile_failure(self):
        from app.orchestrator.workflow import route_after_profile
        state = {"current_stage": "profile_failed"}
        assert route_after_profile(state) == "end"

    def test_route_after_competitor_success(self):
        from app.orchestrator.workflow import route_after_competitor
        state = {"current_stage": "competitor_complete"}
        assert route_after_competitor(state) == "planner"

    def test_route_after_competitor_failure(self):
        from app.orchestrator.workflow import route_after_competitor
        state = {"current_stage": "competitor_failed"}
        assert route_after_competitor(state) == "end"

    def test_route_after_planner_to_hitl(self):
        from app.orchestrator.workflow import route_after_planner
        state = {"current_stage": "calendar_draft"}
        assert route_after_planner(state) == "hitl"

    def test_route_after_planner_failure(self):
        from app.orchestrator.workflow import route_after_planner
        state = {"current_stage": "planner_failed"}
        assert route_after_planner(state) == "end"

    def test_route_after_hitl_locked_goes_to_content(self):
        from app.orchestrator.workflow import route_after_hitl
        state = {"calendar_status": "locked"}
        assert route_after_hitl(state) == "content"

    def test_route_after_hitl_under_review_stays(self):
        from app.orchestrator.workflow import route_after_hitl
        state = {"calendar_status": "under_review"}
        assert route_after_hitl(state) == "hitl"

    def test_route_after_hitl_draft_stays(self):
        from app.orchestrator.workflow import route_after_hitl
        state = {"calendar_status": "draft"}
        assert route_after_hitl(state) == "hitl"


class TestHITLNode:
    def test_hitl_ignores_empty_messages(self):
        from app.orchestrator.workflow import apply_calendar_edit
        state = {
            "user_id": "test",
            "user_profile_data": {},
            "competitor_data": [],
            "profile_report": MOCK_PROFILE,
            "competitor_report": MOCK_COMPETITOR,
            "calendar": MOCK_CALENDAR,
            "calendar_status": "under_review",
            "hitl_messages": [],
            "generated_posts": [],
            "current_stage": "calendar_under_review",
            "errors": [],
            "days": 14,
        }
        result = apply_calendar_edit(state)
        # Should return unchanged state
        assert result["calendar"] == MOCK_CALENDAR

    def test_hitl_ignores_assistant_message(self):
        from app.orchestrator.workflow import apply_calendar_edit
        state = {
            "user_id": "test",
            "user_profile_data": {},
            "competitor_data": [],
            "profile_report": MOCK_PROFILE,
            "competitor_report": MOCK_COMPETITOR,
            "calendar": MOCK_CALENDAR,
            "calendar_status": "under_review",
            "hitl_messages": [{"role": "assistant", "content": "Calendar ready"}],
            "generated_posts": [],
            "current_stage": "calendar_under_review",
            "errors": [],
            "days": 14,
        }
        result = apply_calendar_edit(state)
        assert result["calendar"] == MOCK_CALENDAR

    @patch("app.orchestrator.workflow.PlannerAgent")
    def test_hitl_applies_user_edit(self, mock_agent_class):
        from app.orchestrator.workflow import apply_calendar_edit
        updated_cal = {**MOCK_CALENDAR, "notes": "Updated"}
        mock_instance = MagicMock()
        mock_instance.apply_edit.return_value = updated_cal
        mock_agent_class.return_value = mock_instance

        state = {
            "user_id": "test",
            "user_profile_data": {},
            "competitor_data": [],
            "profile_report": MOCK_PROFILE,
            "competitor_report": MOCK_COMPETITOR,
            "calendar": MOCK_CALENDAR,
            "calendar_status": "under_review",
            "hitl_messages": [{"role": "user", "content": "Change Day 3 topic to LangGraph"}],
            "generated_posts": [],
            "current_stage": "calendar_under_review",
            "errors": [],
            "days": 14,
        }
        result = apply_calendar_edit(state)
        assert result["calendar"]["notes"] == "Updated"
        assert len(result["hitl_messages"]) == 2  # user + assistant
        assert result["hitl_messages"][1]["role"] == "assistant"


class TestGraphConstruction:
    def test_graph_builds_without_error(self):
        from app.orchestrator.workflow import build_graph
        graph = build_graph()
        assert graph is not None

    def test_compiled_graph_exists(self):
        from app.orchestrator.workflow import compiled_graph
        assert compiled_graph is not None

    def test_graph_has_all_nodes(self):
        from app.orchestrator.workflow import build_graph
        graph = build_graph()
        # Access graph nodes
        compiled = graph.compile()
        assert compiled is not None


class TestContentPipelineNode:
    @patch("app.orchestrator.workflow.ContentPipeline")
    def test_content_pipeline_runs_for_all_entries(self, mock_pipeline_class):
        from app.orchestrator.workflow import run_content_pipeline
        mock_instance = MagicMock()
        mock_instance.run_for_entry.return_value = {
            "entry": {}, "copy": MOCK_CONTENT["copy"],
            "hashtags": MOCK_CONTENT["hashtags"], "visual": MOCK_CONTENT["visual"],
        }
        mock_pipeline_class.return_value = mock_instance

        state = {
            "user_id": "test",
            "user_profile_data": {},
            "competitor_data": [],
            "profile_report": MOCK_PROFILE,
            "competitor_report": MOCK_COMPETITOR,
            "calendar": MOCK_CALENDAR,
            "calendar_status": "locked",
            "hitl_messages": [],
            "generated_posts": [],
            "current_stage": "calendar_locked",
            "errors": [],
            "days": 14,
        }
        result = run_content_pipeline(state)
        assert result["current_stage"] == "content_generated"
        assert len(result["generated_posts"]) == 14
        assert mock_instance.run_for_entry.call_count == 14

    @patch("app.orchestrator.workflow.ContentPipeline")
    def test_content_pipeline_handles_entry_failure(self, mock_pipeline_class):
        from app.orchestrator.workflow import run_content_pipeline
        mock_instance = MagicMock()
        mock_instance.run_for_entry.side_effect = RuntimeError("Content gen failed")
        mock_pipeline_class.return_value = mock_instance

        state = {
            "user_id": "test",
            "user_profile_data": {},
            "competitor_data": [],
            "profile_report": MOCK_PROFILE,
            "competitor_report": MOCK_COMPETITOR,
            "calendar": {**MOCK_CALENDAR, "entries": [MOCK_CALENDAR["entries"][0]]},
            "calendar_status": "locked",
            "hitl_messages": [],
            "generated_posts": [],
            "current_stage": "calendar_locked",
            "errors": [],
            "days": 14,
        }
        result = run_content_pipeline(state)
        # Should not raise — errors are captured per entry
        assert result["current_stage"] == "content_generated"
        assert "error" in result["generated_posts"][0]
