"""
app/agents/content_agents.py — Multi-Agent Content Generation Pipeline (FR-4).
Simplified, reliable implementation with direct text generation.
"""
from __future__ import annotations
import re
from langchain_groq import ChatGroq
from app.config import get_settings
from app.utils.logger import log, track_agent, record_tokens

settings = get_settings()


def _make_llm(temperature: float = 0.7) -> ChatGroq:
    model = settings.groq_model or "llama3-8b-8192"
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=model,
        temperature=temperature,
        max_tokens=1024,
    )


# ── Copy Agent ────────────────────────────────────────────────────────────────

class CopyAgent:
    def __init__(self):
        self._llm = _make_llm(temperature=0.8)

    def run(self, topic: str, platform: str, format: str, profile_report: dict, user_id: str = "") -> dict:
        with track_agent("copy_agent"):
            if platform == "twitter" or platform == "x":
                if format == "thread":
                    prompt = f"""Write a Twitter thread of exactly 4 tweets about: {topic}

Rules:
- Each tweet must be under 240 characters
- Separate tweets with the line: ---TWEET---
- First tweet must be a hook/bold statement
- Last tweet must have a call to action
- Make it specific and insightful about {topic}
- Do NOT include hashtags in the tweets

Write the thread now:"""
                else:
                    prompt = f"""Write a single Twitter post about: {topic}

Rules:
- Maximum 220 characters total
- Make it punchy and specific to {topic}
- Start with a strong insight or hot take
- Do NOT include hashtags

Write the tweet now (just the text, nothing else):"""
            else:
                # LinkedIn
                prompt = f"""Write a LinkedIn post about: {topic}

Rules:
- 150 to 250 words
- Start with a bold hook sentence on its own line
- Use short paragraphs with line breaks
- Include 3 specific insights about {topic}
- End with a question to spark comments
- Professional but conversational tone
- Do NOT include hashtags in the post body

Write the LinkedIn post now:"""

            try:
                response = self._llm.invoke(prompt)
                if response is None or not response.content:
                    raise ValueError("Empty response")
                body = response.content.strip()
                hook = body.split('\n')[0][:100]
                return {
                    "body_copy": body,
                    "word_count": len(body.split()),
                    "hook": hook,
                    "call_to_action": "Share your thoughts in the comments.",
                }
            except Exception as exc:
                log.warning("copy_agent.failed", error=str(exc), topic=topic)
                if platform == "twitter":
                    body = f"Key insight about {topic}: The fundamentals matter more than the hype. Focus on what actually works in production. What's your experience?"
                else:
                    body = f"Let's talk about {topic}.\n\nThis is one of the most important topics in AI engineering right now.\n\nHere are 3 things you need to know:\n\n1. The fundamentals still matter\n2. Real-world application beats theory\n3. Iteration is the only path forward\n\nWhat's your take on {topic}?"
                return {
                    "body_copy": body,
                    "word_count": len(body.split()),
                    "hook": f"Let's talk about {topic}.",
                    "call_to_action": "Share your thoughts.",
                }


# ── Hashtag Agent ─────────────────────────────────────────────────────────────

class HashtagAgent:
    def __init__(self):
        self._llm = _make_llm(temperature=0.3)

    def run(self, topic: str, platform: str, profile_report: dict, competitor_report: dict, user_id: str = "") -> dict:
        with track_agent("hashtag_agent"):
            count = "3 to 5" if platform == "linkedin" else "2 to 3"
            prompt = f"""Generate {count} hashtags for a {platform} post about: {topic}

Rules:
- Return ONLY the hashtags, one per line
- No # symbol, just the word
- Make them specific to {topic}
- Mix 1 broad tag (AI or MachineLearning) with niche tags specific to this exact topic
- No spaces in hashtags

Hashtags:"""

            try:
                response = self._llm.invoke(prompt)
                if response is None or not response.content:
                    raise ValueError("Empty response")
                lines = [l.strip().lstrip('#').replace(' ', '') for l in response.content.strip().split('\n') if l.strip()]
                hashtags = [h for h in lines if h and len(h) > 1][:5]
                if not hashtags:
                    raise ValueError("No hashtags parsed")
                return {
                    "hashtags": hashtags,
                    "primary_hashtags": hashtags[:2],
                    "niche_hashtags": hashtags[2:],
                    "trending_hashtags": [],
                }
            except Exception as exc:
                log.warning("hashtag_agent.failed", error=str(exc), topic=topic)
                # Generate topic-specific fallback hashtags
                topic_word = topic.split()[0].replace('-', '').replace(' ', '') if topic else "AI"
                fallback = ["AI", "MachineLearning", topic_word, "LLM", "TechContent"]
                return {
                    "hashtags": fallback[:4],
                    "primary_hashtags": fallback[:2],
                    "niche_hashtags": fallback[2:4],
                    "trending_hashtags": [],
                }


# ── Visual Agent ──────────────────────────────────────────────────────────────

class VisualAgent:
    def __init__(self):
        self._llm = _make_llm(temperature=0.7)

    def run(self, topic: str, platform: str, format: str, body_copy: str = "", user_id: str = "") -> dict:
        with track_agent("visual_agent"):
            prompt = f"""Create an image generation prompt for a {platform} post about: {topic}

Requirements:
- Describe a specific visual that represents {topic}
- Style: clean, modern, professional tech aesthetic
- No generic robots or humanoid AI figures
- Include: composition, colors, mood, specific visual elements
- Make it directly relevant to {topic}
- Keep it under 100 words

Image prompt:"""

            try:
                response = self._llm.invoke(prompt)
                if response is None or not response.content:
                    raise ValueError("Empty response")
                visual_prompt = response.content.strip()
                # Pick color based on topic keywords
                if any(w in topic.lower() for w in ["security", "risk", "error", "fail"]):
                    colors = ["#1a1a2e", "#e94560", "#ffffff"]
                elif any(w in topic.lower() for w in ["rag", "data", "database", "vector"]):
                    colors = ["#0f172a", "#3b82f6", "#e2e8f0"]
                elif any(w in topic.lower() for w in ["agent", "workflow", "pipeline", "graph"]):
                    colors = ["#064e3b", "#10b981", "#f0fdf4"]
                else:
                    colors = ["#1e1b4b", "#8b5cf6", "#f5f3ff"]
                return {
                    "visual_prompt": visual_prompt,
                    "visual_type": "infographic",
                    "color_palette": colors,
                    "key_text_elements": [topic],
                }
            except Exception as exc:
                log.warning("visual_agent.failed", error=str(exc), topic=topic)
                return {
                    "visual_prompt": f"Clean minimal infographic about {topic}. Dark navy background, white typography, subtle geometric shapes representing data flow. Professional tech aesthetic. 16:9 ratio.",
                    "visual_type": "infographic",
                    "color_palette": ["#0f172a", "#3b82f6", "#e2e8f0"],
                    "key_text_elements": [topic],
                }


# ── Content Pipeline ──────────────────────────────────────────────────────────

class ContentPipeline:
    def __init__(self):
        self.copy_agent = CopyAgent()
        self.hashtag_agent = HashtagAgent()
        self.visual_agent = VisualAgent()

    def run_for_entry(self, entry: dict, profile_report: dict, competitor_report: dict, user_id: str = "") -> dict:
        topic = entry["topic"]
        platform = entry["platform"]
        format_ = entry.get("format", "short_post")

        log.info("content_pipeline.start", topic=topic, platform=platform, day=entry.get("day"))

        copy_result = self.copy_agent.run(topic, platform, format_, profile_report, user_id)
        hashtag_result = self.hashtag_agent.run(topic, platform, profile_report, competitor_report, user_id)
        visual_result = self.visual_agent.run(topic, platform, format_, copy_result.get("body_copy", ""), user_id)

        log.info("content_pipeline.complete", topic=topic)
        return {
            "entry": entry,
            "copy": copy_result,
            "hashtags": hashtag_result,
            "visual": visual_result,
        }