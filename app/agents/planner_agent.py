"""
app/agents/planner_agent.py — Content Calendar Orchestrator (FR-3).

Synthesises Profile + Competitor reports into a data-driven content
calendar. Supports HITL review cycles and incremental updates.
"""
from __future__ import annotations
import json
from datetime import date, timedelta
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain.output_parsers import PydanticOutputParser
from app.config import get_settings
from app.rag.pipeline import retrieve_context
from app.utils.logger import log, track_agent, record_tokens

settings = get_settings()


# ── Output schema ────────────────────────────────────────────────────────────

class CalendarEntry(BaseModel):
    day: int
    date: str                 # YYYY-MM-DD
    platform: str             # linkedin | twitter | both
    topic: str
    format: str               # long_post | thread | carousel | article | short_post
    posting_time: str         # HH:MM
    rationale: str = Field(description="Why this topic/format on this day")
    expected_engagement: str  # low | medium | high

class ContentCalendarOutput(BaseModel):
    title: str
    period_days: int
    entries: list[CalendarEntry]
    strategic_themes: list[str]
    notes: str


# ── Prompts ──────────────────────────────────────────────────────────────────

PLAN_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a strategic social media content planner for AI/tech professionals.

Create a data-driven content calendar grounded in:
1. The user's writing style, tone, and strongest topics (from profile report)
2. Competitor gaps and trending topics (from competitive analysis)
3. Platform-specific best practices (LinkedIn: longer, professional; X: punchy, real-time)

Calendar rules:
- Mix formats: don't put the same format on consecutive days
- Lead with strongest topics on Mon/Tue when engagement is highest
- Balance LinkedIn and X across the period
- Every entry MUST have a clear rationale linking it to the analysis

Respond ONLY with valid JSON:
{format_instructions}"""),
    ("human", """Profile Report:
{profile_report}

Competitive Analysis:
{competitor_report}

Calendar Parameters:
- Start Date: {start_date}
- Duration: {days} days
- Platforms: LinkedIn and X (Twitter)

Additional context from RAG:
{rag_context}

Generate the {days}-day content calendar now."""),
])

EDIT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a social media content planner. The user is reviewing their content calendar
and has requested specific changes. Apply ONLY the requested changes. Do not modify other entries.

Return the COMPLETE updated calendar as valid JSON matching the same schema.
{format_instructions}"""),
    ("human", """Current Calendar:
{current_calendar}

User's Requested Change:
"{user_request}"

Apply the change and return the full updated calendar."""),
])


# ── Agent ────────────────────────────────────────────────────────────────────

class PlannerAgent:
    """
    Generates and iteratively refines a content calendar via HITL.
    """

    def __init__(self):
        self._llm = ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.groq_model or "llama3-8b-8192",
            temperature=0.5,
            max_tokens=2048,
        )
        self._parser = PydanticOutputParser(pydantic_object=ContentCalendarOutput)

    def run(
        self,
        profile_report: dict,
        competitor_report: dict,
        start_date: date | None = None,
        days: int = 14,
        user_id: str = "",
    ) -> dict:
        """Generate the initial content calendar."""
        with track_agent("planner_agent"):
            if start_date is None:
                start_date = date.today() + timedelta(days=1)

            # Fetch RAG context
            rag_chunks = []
            for collection in ["profile_reports", "competitor_reports"]:
                chunks = retrieve_context(
                    collection,
                    query="high engagement topics formats content gaps opportunities",
                    n_results=2,
                    where={"user_id": user_id} if user_id else None,
                )
                rag_chunks.extend(chunks)
            rag_context = "\n\n".join(rag_chunks) if rag_chunks else "No additional context."

            log.info("planner_agent.running", user_id=user_id, days=days, start_date=str(start_date))

            prompt = PLAN_PROMPT.format_messages(
                profile_report=json.dumps(profile_report, indent=2),
                competitor_report=json.dumps(competitor_report, indent=2),
                start_date=start_date.strftime("%Y-%m-%d"),
                days=days,
                rag_context=rag_context,
                format_instructions=self._parser.get_format_instructions(),
            )

            response = None
            try:
                response = self._llm.invoke(prompt)
                calendar = self._parser.parse(response.content)
                calendar_dict = calendar.model_dump()

                if response and hasattr(response, "usage_metadata") and response.usage_metadata:
                    record_tokens("planner_agent", response.usage_metadata.get("total_tokens", 0))

            except Exception as exc:
                log.warning("planner_agent.parse_failed_fallback", error=str(exc))
                calendar_dict = self._fallback_calendar(start_date, days, profile_report)

            log.info("planner_agent.complete", entries=len(calendar_dict.get("entries", [])))
            return calendar_dict

    def apply_edit(self, current_calendar: dict, user_request: str) -> dict:
        """
        Apply a HITL edit to the calendar. Only modifies affected entries (TS-4).
        Returns the updated calendar dict.
        """
        with track_agent("planner_agent_edit"):
            log.info("planner_agent.applying_edit", request=user_request[:80])

            prompt = EDIT_PROMPT.format_messages(
                current_calendar=json.dumps(current_calendar, indent=2),
                user_request=user_request,
                format_instructions=self._parser.get_format_instructions(),
            )

            response = None
            try:
                response = self._llm.invoke(prompt)
                updated = self._parser.parse(response.content)

                if response and hasattr(response, "usage_metadata") and response.usage_metadata:
                    record_tokens("planner_agent", response.usage_metadata.get("total_tokens", 0))

                log.info("planner_agent.edit_applied")
                return updated.model_dump()

            except Exception as exc:
                log.error("planner_agent.edit_failed", error=str(exc))
                # Return original unchanged on failure
                return current_calendar

    def _fallback_calendar(self, start_date: date, days: int, profile_report: dict) -> dict:
        """Rule-based calendar fallback."""
        topics = profile_report.get("primary_topics", ["AI", "LLM", "engineering"])
        platforms = ["linkedin", "twitter"] * (days // 2 + 1)
        formats = ["long_post", "thread", "carousel", "short_post", "article"]
        times = ["09:00", "10:00", "11:00", "09:30", "10:30"]

        entries = []
        for i in range(days):
            d = start_date + timedelta(days=i)
            entries.append({
                "day": i + 1,
                "date": d.strftime("%Y-%m-%d"),
                "platform": platforms[i],
                "topic": topics[i % len(topics)],
                "format": formats[i % len(formats)],
                "posting_time": times[i % len(times)],
                "rationale": f"Day {i+1} content to build authority in {topics[i % len(topics)]}",
                "expected_engagement": "medium",
            })

        return {
            "title": f"{days}-Day Content Calendar",
            "period_days": days,
            "entries": entries,
            "strategic_themes": topics[:3],
            "notes": "Generated with fallback engine.",
        }