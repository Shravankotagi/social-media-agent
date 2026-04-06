"""
app/agents/competitor_agent.py — Competitive Landscape Agent (FR-2).

Uses the Profile Intelligence Report to discover and analyse 3-5
competitor profiles, highlighting content gaps and opportunities.
"""
from __future__ import annotations
import json
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain.output_parsers import PydanticOutputParser
from app.config import get_settings
from app.rag.pipeline import store_context, retrieve_context
from app.utils.logger import log, track_agent, record_tokens
from app.services.mock_data import MOCK_COMPETITORS

settings = get_settings()


# ── Output schema ────────────────────────────────────────────────────────────

class CompetitorProfile(BaseModel):
    name: str
    platform: str
    url: str
    bio: str
    followers: int
    avg_likes: float
    top_topics: list[str]
    top_formats: list[str]
    posting_frequency: str
    gap_opportunity: str = Field(description="Specific opportunity for the user based on this competitor's gaps")

class CompetitiveAnalysisReport(BaseModel):
    competitors: list[CompetitorProfile]
    content_gaps: list[str] = Field(description="Topics competitors miss that user could own")
    high_engagement_formats: list[str] = Field(description="Formats driving most engagement in this niche")
    trending_topics: list[str] = Field(description="Currently trending topics in this niche")
    niche_opportunities: list[str] = Field(description="Strategic whitespace the user can occupy")
    recommended_differentiation: str = Field(description="How the user should position relative to competitors")


# ── Agent ────────────────────────────────────────────────────────────────────

COMPETITOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert competitive intelligence analyst for social media content strategy.

Given a user's Profile Intelligence Report and sample competitor data, produce
a thorough Competitive Analysis Report. Focus on:
- Identifying real content gaps competitors are not covering
- Finding format/topic combinations with high engagement but low competition
- Recommending specific differentiation strategies

Be concrete and actionable. Ground insights in the data provided.
Respond ONLY with valid JSON matching this schema:
{format_instructions}"""),
    ("human", """User Profile Report:
{profile_report}

Competitor Data (use this as the basis — analyse these competitors):
{competitor_data}

Generate the Competitive Analysis Report now."""),
])


class CompetitorAgent:
    """
    Discovers and analyses competitor profiles.
    Uses mock data if live scraping is unavailable.
    """

    def __init__(self):
        self._llm = ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.groq_model or "llama3-8b-8192",
            temperature=0.3,
            max_tokens=1024,
        )
        self._parser = PydanticOutputParser(pydantic_object=CompetitiveAnalysisReport)

    def run(
        self,
        profile_report: dict,
        competitor_data: list[dict] | None = None,
        user_id: str = "",
    ) -> dict:
        """
        profile_report: output from ProfileAgent.run()
        competitor_data: list of competitor profile dicts (or None to use mock)
        """
        with track_agent("competitor_agent"):
            # Enrich with RAG context from profile
            rag_context = retrieve_context(
                "profile_reports",
                query="writing style tone topics engagement",
                n_results=2,
                where={"user_id": user_id} if user_id else None,
            )
            if rag_context:
                log.debug("competitor_agent.rag_context_loaded", chunks=len(rag_context))

            competitors = competitor_data or MOCK_COMPETITORS
            log.info("competitor_agent.running", user_id=user_id, competitors=len(competitors))

            prompt = COMPETITOR_PROMPT.format_messages(
                profile_report=json.dumps(profile_report, indent=2),
                competitor_data=json.dumps(competitors, indent=2),
                format_instructions=self._parser.get_format_instructions(),
            )

            response = None
            try:
                response = self._llm.invoke(prompt)
                report = self._parser.parse(response.content)
                report_dict = report.model_dump()

                if response and hasattr(response, "usage_metadata") and response.usage_metadata:
                    record_tokens("competitor_agent", response.usage_metadata.get("total_tokens", 0))

            except Exception as exc:
                log.warning("competitor_agent.parse_failed_fallback", error=str(exc))
                report_dict = self._fallback_report(competitors)

            # Store in RAG for content generation
            if user_id:
                store_context(
                    collection_name="competitor_reports",
                    doc_id=f"competitor_{user_id}",
                    text=json.dumps(report_dict),
                    metadata={"user_id": user_id, "type": "competitive_analysis"},
                )

            log.info("competitor_agent.complete", user_id=user_id)
            return report_dict

    def _fallback_report(self, competitors: list[dict]) -> dict:
        return {
            "competitors": competitors[:5],
            "content_gaps": ["practical tutorials", "code walkthroughs", "real-world case studies"],
            "high_engagement_formats": ["thread", "carousel", "long_post"],
            "trending_topics": ["LLM fine-tuning", "RAG optimization", "AI agents", "LangGraph"],
            "niche_opportunities": [
                "Production-ready code examples nobody else publishes",
                "Benchmark comparisons between agent frameworks",
                "Real-world deployment lessons",
            ],
            "recommended_differentiation": (
                "Own the 'practical production AI' space — combine deep technical depth "
                "with real-world deployment stories that others shy away from."
            ),
        }