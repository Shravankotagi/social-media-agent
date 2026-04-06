"""
app/orchestrator/workflow.py — LangGraph Orchestrator (TS-1).

Defines the full pipeline as a stateful graph:
  Profile → Competitor → Planner → [HITL Review] → Content Generation

State is maintained across all nodes. Dynamic routing based on pipeline stage.
"""
from __future__ import annotations
import json
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.agents.profile_agent import ProfileAgent
from app.agents.competitor_agent import CompetitorAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.content_agents import ContentPipeline
from app.utils.logger import log


# ── Pipeline State ────────────────────────────────────────────────────────────

class PipelineState(TypedDict):
    """Shared state passed between all nodes in the graph."""
    user_id: str
    user_profile_data: dict          # raw input profile
    competitor_data: list[dict]      # raw competitor data (or None for mock)
    profile_report: dict             # output of ProfileAgent
    competitor_report: dict          # output of CompetitorAgent
    calendar: dict                   # output of PlannerAgent
    calendar_status: str             # draft | under_review | approved | locked
    hitl_messages: list[dict]        # conversation history for calendar review
    generated_posts: list[dict]      # list of {entry, copy, hashtags, visual}
    current_stage: str               # tracks where we are
    errors: list[str]                # accumulated non-fatal errors
    days: int                        # calendar duration


# ── Node functions ────────────────────────────────────────────────────────────

def run_profile_agent(state: PipelineState) -> PipelineState:
    log.info("graph.node", node="profile_agent", user_id=state["user_id"])
    agent = ProfileAgent()
    try:
        report = agent.run(
            profile_data=state.get("user_profile_data") or None,
            user_id=state["user_id"],
        )
        return {**state, "profile_report": report, "current_stage": "profile_complete"}
    except Exception as exc:
        log.error("graph.node_failed", node="profile_agent", error=str(exc))
        return {**state, "errors": state.get("errors", []) + [str(exc)], "current_stage": "profile_failed"}


def run_competitor_agent(state: PipelineState) -> PipelineState:
    log.info("graph.node", node="competitor_agent", user_id=state["user_id"])
    agent = CompetitorAgent()
    try:
        report = agent.run(
            profile_report=state["profile_report"],
            competitor_data=state.get("competitor_data") or None,
            user_id=state["user_id"],
        )
        return {**state, "competitor_report": report, "current_stage": "competitor_complete"}
    except Exception as exc:
        log.error("graph.node_failed", node="competitor_agent", error=str(exc))
        return {**state, "errors": state.get("errors", []) + [str(exc)], "current_stage": "competitor_failed"}


def run_planner_agent(state: PipelineState) -> PipelineState:
    log.info("graph.node", node="planner_agent", user_id=state["user_id"])
    from datetime import date, timedelta
    agent = PlannerAgent()
    try:
        calendar = agent.run(
            profile_report=state["profile_report"],
            competitor_report=state["competitor_report"],
            start_date=date.today() + timedelta(days=1),
            days=state.get("days", 14),
            user_id=state["user_id"],
        )
        return {
            **state,
            "calendar": calendar,
            "calendar_status": "draft",
            "current_stage": "calendar_draft",
        }
    except Exception as exc:
        log.error("graph.node_failed", node="planner_agent", error=str(exc))
        return {**state, "errors": state.get("errors", []) + [str(exc)], "current_stage": "planner_failed"}


def apply_calendar_edit(state: PipelineState) -> PipelineState:
    """
    Applies the latest HITL message as a calendar edit.
    Only runs when calendar_status == 'under_review' and a new message is present.
    """
    messages = state.get("hitl_messages", [])
    if not messages:
        return state

    last_msg = messages[-1]
    if last_msg.get("role") != "user":
        return state

    user_request = last_msg["content"]
    log.info("graph.hitl_edit", request=user_request[:80])

    agent = PlannerAgent()
    updated_calendar = agent.apply_edit(state["calendar"], user_request)

    assistant_msg = {
        "role": "assistant",
        "content": (
            f"I've applied your change: '{user_request}'. "
            "Here is the updated calendar. Review the changes and let me know "
            "if you'd like further adjustments, or say 'approve' to lock it."
        ),
    }

    return {
        **state,
        "calendar": updated_calendar,
        "hitl_messages": messages + [assistant_msg],
        "current_stage": "calendar_under_review",
    }


def run_content_pipeline(state: PipelineState) -> PipelineState:
    """Generates copy, hashtags, and visuals for each approved calendar entry."""
    log.info("graph.node", node="content_pipeline", user_id=state["user_id"])
    pipeline = ContentPipeline()
    entries = state["calendar"].get("entries", [])
    generated = []

    for entry in entries:
        try:
            result = pipeline.run_for_entry(
                entry=entry,
                profile_report=state["profile_report"],
                competitor_report=state["competitor_report"],
                user_id=state["user_id"],
            )
            generated.append(result)
        except Exception as exc:
            log.error("graph.content_pipeline_entry_failed", day=entry.get("day"), error=str(exc))
            generated.append({"entry": entry, "error": str(exc)})

    return {**state, "generated_posts": generated, "current_stage": "content_generated"}


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_profile(state: PipelineState) -> Literal["competitor", "end"]:
    if state.get("current_stage") == "profile_failed":
        return "end"
    return "competitor"


def route_after_competitor(state: PipelineState) -> Literal["planner", "end"]:
    if state.get("current_stage") == "competitor_failed":
        return "end"
    return "planner"


def route_after_planner(state: PipelineState) -> Literal["hitl", "content", "end"]:
    stage = state.get("current_stage")
    if stage == "planner_failed":
        return "end"
    # Always go to HITL first — calendar must be reviewed before content gen
    return "hitl"


def route_after_hitl(state: PipelineState) -> Literal["content", "hitl", "end"]:
    """Route based on calendar approval status."""
    status = state.get("calendar_status", "draft")
    if status == "locked":
        return "content"
    if status == "under_review":
        return "hitl"
    return "hitl"


# ── Build graph ───────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("profile", run_profile_agent)
    graph.add_node("competitor", run_competitor_agent)
    graph.add_node("planner", run_planner_agent)
    graph.add_node("hitl", apply_calendar_edit)
    graph.add_node("content", run_content_pipeline)

    # Entry point
    graph.set_entry_point("profile")

    # Edges with routing
    graph.add_conditional_edges("profile", route_after_profile, {"competitor": "competitor", "end": END})
    graph.add_conditional_edges("competitor", route_after_competitor, {"planner": "planner", "end": END})
    graph.add_conditional_edges("planner", route_after_planner, {"hitl": "hitl", "content": "content", "end": END})
    graph.add_conditional_edges("hitl", route_after_hitl, {"content": "content", "hitl": "hitl", "end": END})
    graph.add_edge("content", END)

    return graph


# ── Compiled app (with memory checkpointing) ─────────────────────────────────

_memory = MemorySaver()
compiled_graph = build_graph().compile(checkpointer=_memory)


def run_pipeline(
    user_id: str,
    profile_data: dict | None = None,
    competitor_data: list[dict] | None = None,
    days: int = 14,
    thread_id: str | None = None,
) -> dict:
    """
    Run the full pipeline from profile → content generation.
    Returns the final state dict.
    """
    initial_state: PipelineState = {
        "user_id": user_id,
        "user_profile_data": profile_data or {},
        "competitor_data": competitor_data or [],
        "profile_report": {},
        "competitor_report": {},
        "calendar": {},
        "calendar_status": "draft",
        "hitl_messages": [],
        "generated_posts": [],
        "current_stage": "init",
        "errors": [],
        "days": days,
    }

    config = {"configurable": {"thread_id": thread_id or user_id}}
    final_state = compiled_graph.invoke(initial_state, config=config)
    return final_state


def send_hitl_message(
    user_id: str,
    thread_id: str,
    message: str,
    calendar_status: str = "under_review",
) -> dict:
    """
    Inject a HITL message into an existing pipeline thread and resume.
    Used for calendar review and content edits.
    """
    config = {"configurable": {"thread_id": thread_id}}

    # Get current state
    current = compiled_graph.get_state(config)
    if not current or not current.values:
        raise ValueError(f"No active pipeline for thread {thread_id}")

    state = dict(current.values)
    state["hitl_messages"] = state.get("hitl_messages", []) + [
        {"role": "user", "content": message}
    ]
    state["calendar_status"] = calendar_status

    # Update state and resume
    compiled_graph.update_state(config, state)
    final_state = compiled_graph.invoke(None, config=config)
    return final_state
