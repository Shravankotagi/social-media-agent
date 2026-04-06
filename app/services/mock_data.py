"""
app/services/mock_data.py — Curated mock/sample data for demos and fallbacks (TS-2).

When live API rate limits are hit or keys aren't configured, the system
falls back to this realistic sample data so the pipeline remains demonstrable.
"""
from __future__ import annotations

# ── Sample user profile (LinkedIn + X combined) ──────────────────────────────
MOCK_USER_PROFILE = {
    "name": "Alex Chen",
    "linkedin_url": "https://linkedin.com/in/alexchen-ai",
    "twitter_url": "https://x.com/alexchen_ai",
    "bio": (
        "AI/ML Engineer building production LLM systems. "
        "Writing about LangChain, agents, and the future of AI. "
        "Previously @GoogleBrain @OpenAI. Building in public."
    ),
    "follower_count": {"linkedin": 8400, "twitter": 12300},
    "following_count": {"linkedin": 620, "twitter": 890},
    "posts": [
        {
            "platform": "linkedin",
            "text": (
                "Just shipped a RAG pipeline that reduced hallucinations by 40%. "
                "The key? Semantic chunking + reranking. Thread below 👇"
            ),
            "likes": 342, "comments": 58, "shares": 91, "date": "2024-05-20",
            "format": "thread",
        },
        {
            "platform": "linkedin",
            "text": (
                "LangGraph vs LangChain: which should you use for multi-agent systems? "
                "I've built with both in production. Here's what I learned."
            ),
            "likes": 517, "comments": 83, "shares": 140, "date": "2024-05-14",
            "format": "long_post",
        },
        {
            "platform": "twitter",
            "text": "Hot take: most RAG implementations fail at chunking, not retrieval.",
            "likes": 892, "reposts": 234, "replies": 67, "date": "2024-05-18",
            "format": "short_post",
        },
        {
            "platform": "twitter",
            "text": (
                "Building an AI agent with LangGraph today. "
                "Step 1: define your state schema. Everything else follows from that."
            ),
            "likes": 612, "reposts": 178, "replies": 45, "date": "2024-05-10",
            "format": "short_post",
        },
        {
            "platform": "linkedin",
            "text": (
                "Lessons from deploying 5 LLM systems to production:\n"
                "1. Prompt engineering matters more than model size\n"
                "2. Latency > accuracy for most users\n"
                "3. Evals are non-negotiable\n"
                "4. RAG beats fine-tuning for most tasks\n"
                "5. Monitor everything"
            ),
            "likes": 1243, "comments": 201, "shares": 387, "date": "2024-05-05",
            "format": "carousel",
        },
    ],
    "topics": ["LLM engineering", "RAG", "LangChain", "multi-agent systems", "production AI"],
    "posting_cadence": {"linkedin": "3x/week", "twitter": "daily"},
}

# ── Sample competitor profiles ────────────────────────────────────────────────
MOCK_COMPETITORS = [
    {
        "name": "Sarah Kim",
        "platform": "linkedin",
        "url": "https://linkedin.com/in/sarahkim-ai",
        "bio": "ML Engineer @ Anthropic. Writes about alignment, RLHF, and AI safety.",
        "followers": 15200,
        "avg_likes": 620,
        "top_topics": ["AI safety", "RLHF", "Constitutional AI", "alignment"],
        "top_formats": ["long_post", "article"],
        "posting_frequency": "2x/week",
        "gap_opportunity": "No practical engineering content — high demand from devs",
    },
    {
        "name": "Marcus Rivera",
        "platform": "both",
        "url": "https://linkedin.com/in/marcusrivera-ml",
        "bio": "Founder @VectorDB startup. Writes about embeddings, vector search, MLOps.",
        "followers": 9800,
        "avg_likes": 410,
        "top_topics": ["vector databases", "embeddings", "MLOps", "startup"],
        "top_formats": ["carousel", "short_post"],
        "posting_frequency": "5x/week",
        "gap_opportunity": "Rarely covers LangChain/LangGraph — your strongest area",
    },
    {
        "name": "Priya Nair",
        "platform": "twitter",
        "url": "https://x.com/priya_builds_ai",
        "bio": "Building AI products. Thread writer. Explaining complex AI simply.",
        "followers": 21000,
        "avg_likes": 830,
        "top_topics": ["AI product", "prompt engineering", "tutorials"],
        "top_formats": ["thread", "short_post"],
        "posting_frequency": "daily",
        "gap_opportunity": "Focuses on product side — missing deep technical content",
    },
]

# ── Sample content calendar ───────────────────────────────────────────────────
MOCK_CALENDAR_TEMPLATE = [
    {"day": 1, "platform": "linkedin", "topic": "Why most RAG systems fail at chunking", "format": "long_post", "time": "09:00"},
    {"day": 2, "platform": "twitter", "topic": "3 LangGraph patterns I use in every agent", "format": "thread", "time": "10:00"},
    {"day": 3, "platform": "linkedin", "topic": "Production LLM: latency vs accuracy tradeoffs", "format": "carousel", "time": "09:00"},
    {"day": 4, "platform": "twitter", "topic": "Hot take on fine-tuning vs RAG", "format": "short_post", "time": "11:00"},
    {"day": 5, "platform": "linkedin", "topic": "How I evaluate AI agents (with real metrics)", "format": "long_post", "time": "09:00"},
    {"day": 6, "platform": "twitter", "topic": "Weekend project: multi-agent orchestration", "format": "short_post", "time": "12:00"},
    {"day": 7, "platform": "linkedin", "topic": "Week recap: top AI engineering lessons", "format": "carousel", "time": "10:00"},
    {"day": 8, "platform": "linkedin", "topic": "Semantic chunking deep dive with code", "format": "article", "time": "09:00"},
    {"day": 9, "platform": "twitter", "topic": "LLM latency optimisation — 5 quick wins", "format": "thread", "time": "10:00"},
    {"day": 10, "platform": "linkedin", "topic": "Building your first production agent", "format": "long_post", "time": "09:00"},
    {"day": 11, "platform": "twitter", "topic": "Embeddings model comparison for RAG", "format": "short_post", "time": "11:00"},
    {"day": 12, "platform": "linkedin", "topic": "State management in LangGraph — patterns", "format": "carousel", "time": "09:00"},
    {"day": 13, "platform": "twitter", "topic": "AI agent architecture decision tree", "format": "thread", "time": "10:00"},
    {"day": 14, "platform": "linkedin", "topic": "14-day reflection: what I shipped and learned", "format": "long_post", "time": "09:00"},
]
