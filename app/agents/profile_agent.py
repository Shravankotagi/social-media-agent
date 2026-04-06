"""
app/agents/profile_agent.py — Profile Intelligence Agent (FR-1).

Analyses a user's LinkedIn and X profile to produce a structured
Profile Intelligence Report covering writing style, tone, topics,
cadence, formats, and engagement patterns.
"""
from __future__ import annotations
import json
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from app.config import get_settings
from app.rag.pipeline import store_context
from app.utils.logger import log, track_agent, record_tokens
from app.services.mock_data import MOCK_USER_PROFILE

settings = get_settings()


# ── Output schema ────────────────────────────────────────────────────────────

class EngagementPatterns(BaseModel):
    highest_engagement_format: str
    highest_engagement_topic: str
    avg_likes: float
    avg_comments: float
    avg_shares: float

class ProfileIntelligenceReport(BaseModel):
    writing_style: str = Field(description="Overall writing style: formal, conversational, technical, etc.")
    tone: str = Field(description="Emotional tone: inspiring, analytical, humorous, authoritative, etc.")
    vocabulary_level: str = Field(description="Vocabulary complexity: beginner-friendly, expert-level, etc.")
    primary_topics: list[str] = Field(description="Top 5 content themes/niches")
    secondary_topics: list[str] = Field(description="Occasional secondary topics")
    content_formats: list[str] = Field(description="Formats used: long_post, thread, carousel, article, etc.")
    posting_cadence: dict = Field(description="Posting frequency per platform")
    engagement_patterns: EngagementPatterns
    content_gaps: list[str] = Field(description="Topics the user hasn't covered but their audience likely wants")
    strategic_recommendations: list[str] = Field(description="3-5 actionable growth recommendations")
    niche_positioning: str = Field(description="How this person is positioned in their niche")
    unique_value_prop: str = Field(description="What makes their content uniquely valuable")


# ── LLM setup ────────────────────────────────────────────────────────────────

def _build_llm() -> ChatGroq:
    model = settings.groq_model or "llama3-8b-8192"
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=model,
        temperature=0.3,
        max_tokens=1024,
    )


PROFILE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert social media analyst and content strategist.
Your task is to analyse a user's social media profile data and produce a
comprehensive, actionable Profile Intelligence Report.

Be specific and data-driven. Ground every insight in the actual post data provided.
Do not invent information not present in the input.

Respond ONLY with valid JSON matching this schema exactly:
{format_instructions}"""),
    ("human", """Analyse this social media profile and generate a structured report:

Profile Data:
{profile_data}

Generate the Profile Intelligence Report now."""),
])


# ── Agent class ──────────────────────────────────────────────────────────────

class ProfileAgent:
    """
    Analyses user's social media profile and produces a structured report.
    Falls back to mock data if live API is unavailable.
    """

    def __init__(self):
        self._llm = _build_llm()
        self._parser = PydanticOutputParser(pydantic_object=ProfileIntelligenceReport)

    def run(self, profile_data: dict | None = None, user_id: str = "") -> dict:
        """
        Main entry point. Returns the report as a dict.
        profile_data: dict with name, bio, posts, follower_count, etc.
                      If None, falls back to MOCK_USER_PROFILE.
        """
        with track_agent("profile_agent"):
            data = profile_data or MOCK_USER_PROFILE
            log.info("profile_agent.running", user_id=user_id, using_mock=(profile_data is None))

            prompt = PROFILE_PROMPT.format_messages(
                profile_data=json.dumps(data, indent=2),
                format_instructions=self._parser.get_format_instructions(),
            )

            response = None
            try:
                response = self._llm.invoke(prompt)
                report = self._parser.parse(response.content)
                report_dict = report.model_dump()
            except Exception as exc:
                log.warning("profile_agent.parse_failed_fallback", error=str(exc))
                report_dict = self._fallback_report(data)

            # Record token usage if available
            if response and hasattr(response, "usage_metadata") and response.usage_metadata:
                record_tokens("profile_agent", response.usage_metadata.get("total_tokens", 0))

            # Store in RAG for downstream agents
            if user_id:
                store_context(
                    collection_name="profile_reports",
                    doc_id=f"profile_{user_id}",
                    text=json.dumps(report_dict),
                    metadata={"user_id": user_id, "type": "profile_intelligence"},
                )

            log.info("profile_agent.complete", user_id=user_id)
            return report_dict

    def _fallback_report(self, data: dict) -> dict:
        """Basic rule-based report when LLM parsing fails."""
        posts = data.get("posts", [])
        avg_likes = sum(p.get("likes", 0) for p in posts) / max(len(posts), 1)
        topics = data.get("topics", ["AI", "technology"])
        return {
            "writing_style": "technical and educational",
            "tone": "authoritative and helpful",
            "vocabulary_level": "expert-level",
            "primary_topics": topics[:5],
            "secondary_topics": [],
            "content_formats": list({p.get("format", "short_post") for p in posts}),
            "posting_cadence": data.get("posting_cadence", {}),
            "engagement_patterns": {
                "highest_engagement_format": "long_post",
                "highest_engagement_topic": topics[0] if topics else "AI",
                "avg_likes": round(avg_likes, 1),
                "avg_comments": 0,
                "avg_shares": 0,
            },
            "content_gaps": ["tutorials", "case studies"],
            "strategic_recommendations": ["Post more consistently", "Engage with comments"],
            "niche_positioning": "AI/ML practitioner",
            "unique_value_prop": "Practical, production-focused AI content",
        }