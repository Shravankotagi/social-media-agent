# Architecture & Developer Guide

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit UI (port 8501)                    │
│  Setup → Calendar Review (HITL) → Content Review → Publish      │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP (httpx)
┌────────────────────────────▼────────────────────────────────────┐
│               FastAPI Backend (port 8000)                        │
│  OpenAPI 3.0 · Pydantic validation · Structured logging         │
│  /api/v1/{users,profile,competitors,calendar,content,publish}    │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│              LangGraph Orchestrator                              │
│                                                                  │
│  profile ──► competitor ──► planner ──► [HITL loop] ──► content │
│                                                                  │
│  State: PipelineState TypedDict (shared across all nodes)        │
│  Memory: MemorySaver (thread-based checkpointing)                │
└──────────┬──────────────────────────────────┬───────────────────┘
           │                                  │
┌──────────▼──────┐                ┌──────────▼──────┐
│   Agent Layer   │                │   RAG Pipeline  │
│                 │                │                 │
│ ProfileAgent    │◄──────────────►│ ChromaDB        │
│ CompetitorAgent │  retrieve/store│ sentence-        │
│ PlannerAgent    │  context       │ transformers    │
│ CopyAgent       │                │ all-MiniLM-L6   │
│ HashtagAgent    │                └─────────────────┘
│ VisualAgent     │
└──────────┬──────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│                     Data Layer                                   │
│                                                                  │
│  MySQL 8  ─── 8 tables: users, profile_reports,                 │
│               competitor_reports, content_calendars,             │
│               calendar_entries, posts, post_metrics,             │
│               pipeline_runs, hitl_sessions                       │
└─────────────────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│              External APIs (optional — clipboard fallback)       │
│                                                                  │
│  Twitter/X API v2  ·  LinkedIn Share API  ·  Proxycurl          │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Design

### ProfileAgent
- **Input:** Raw profile data (posts, bio, follower count) or mock data
- **Output:** `ProfileIntelligenceReport` — writing style, tone, topics, engagement patterns
- **Model:** `llama3-70b-8192` via Groq (analytical tasks need high reasoning)
- **RAG:** Stores report in ChromaDB collection `profile_reports`

### CompetitorAgent
- **Input:** `ProfileIntelligenceReport` + competitor data (or mock)
- **Output:** `CompetitiveAnalysisReport` — gaps, trending topics, differentiation strategy
- **RAG:** Retrieves profile context to ground competitor analysis; stores in `competitor_reports`

### PlannerAgent
- **Input:** Both reports + calendar parameters
- **Output:** `ContentCalendarOutput` — 14-day calendar with rationale per entry
- **HITL:** `apply_edit()` takes natural language request, updates only affected entries
- **RAG:** Retrieves from both collections for grounding

### CopyAgent
- **Input:** Topic, platform, format, profile report
- **Output:** Platform-calibrated body text (LinkedIn ≤3000 chars, Twitter ≤280)
- **Temperature:** 0.7 (creative but consistent)

### HashtagAgent
- **Input:** Topic, platform, trending topics from competitor report
- **Output:** Primary + niche + trending hashtag sets
- **Temperature:** 0.4 (low — consistency matters for SEO)

### VisualAgent
- **Input:** Topic, platform, body copy summary
- **Output:** Detailed Stable Diffusion/DALL-E compatible prompt + visual type
- **Temperature:** 0.8 (high — creative prompts benefit from variety)

## LangGraph Pipeline

```python
# State flows through all nodes
Profile → Competitor → Planner → [HITL loop] → Content → END

# Routing logic:
profile_failed  → END (don't continue without profile)
calendar_locked → content (only generate after human approval)
calendar_draft  → hitl   (always review before content gen)
```

## HITL Workflow

1. User runs `/api/v1/pipeline/run` → gets `calendar_id`
2. Calendar presented in Streamlit with status `draft`
3. User sends edits via `/api/v1/calendar/edit` with natural language messages
4. `PlannerAgent.apply_edit()` updates **only affected entries**
5. HITL history stored in `hitl_sessions` table
6. User sends `"approve"` → status becomes `locked`
7. Content generation becomes available

## RAG Pipeline

```
Text → chunk_text() [semantic chunking, ~200 tokens, 40 overlap]
     → SentenceTransformer.encode() [all-MiniLM-L6-v2, 384-dim]
     → ChromaDB.upsert() [cosine similarity HNSW index]

Query → embed query → ChromaDB.query() → top-3 chunks returned
      → injected into agent prompts as context
```

## Database Schema

8 tables — see `docker/init.sql` for full DDL.

Key relationships:
```
users
  ├── profile_reports (1:many)
  ├── competitor_reports (1:many)
  ├── content_calendars (1:many)
  │     └── calendar_entries (1:many)
  │           └── posts (1:many)
  │                 └── post_metrics (1:many)
  ├── pipeline_runs (1:many)
  └── hitl_sessions (1:many)
```

## API Reference

Full OpenAPI 3.0 spec available at `http://localhost:8000/docs`.

Key endpoints:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/pipeline/run` | Full pipeline in one call |
| POST | `/api/v1/profile/analyse` | FR-1: Profile analysis |
| POST | `/api/v1/competitors/analyse` | FR-2: Competitor analysis |
| POST | `/api/v1/calendar/generate` | FR-3: Calendar generation |
| POST | `/api/v1/calendar/edit` | FR-3: HITL edit/approve |
| POST | `/api/v1/content/generate` | FR-4: Content pipeline |
| POST | `/api/v1/content/regenerate` | FR-5: Targeted component regen |
| POST | `/api/v1/content/approve` | FR-5: Approve component |
| POST | `/api/v1/publish` | FR-6: Publish post |
| GET  | `/api/v1/metrics/adapt/{id}` | FR-7: Adaptive suggestions |
| GET  | `/api/v1/health` | All services health check |

## Environment Setup

```bash
# 1. Prerequisites
# Docker + Docker Compose installed
# Groq API key (free at console.groq.com)

# 2. Clone and configure
git clone <repo-url>
cd ai-social-agent
cp .env.example .env
# Edit .env: add GROQ_API_KEY at minimum

# 3. Launch
docker-compose up --build

# 4. Run migrations (if not using auto-create)
docker-compose exec api alembic upgrade head

# 5. Run tests
docker-compose exec api pytest tests/ --cov=app --cov-report=term-missing
```

## Local Development (no Docker)

```bash
# Start MySQL and ChromaDB only
docker-compose up mysql chromadb -d

# Install Python deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Set env vars
export $(cat .env | xargs)
export MYSQL_HOST=localhost
export CHROMA_HOST=localhost

# Run API
uvicorn app.main:app --reload --port 8000

# Run Streamlit (new terminal)
streamlit run frontend/app.py --server.port 8501
```

## Testing

```bash
# All tests with coverage
pytest tests/ --cov=app --cov-report=term-missing

# Specific modules
pytest tests/test_agents.py -v
pytest tests/test_rag.py -v
pytest tests/test_orchestrator.py -v
pytest tests/test_services.py -v
pytest tests/test_api.py -v

# Fast unit tests only (skip integration)
pytest tests/ -k "not TestAPI" -v
```

## Observability

- **Logs:** Structured JSON via structlog (configured in `app/utils/logger.py`)
- **Metrics:** Prometheus counters/histograms exported on port 8001
  - `agent_latency_seconds` — per-agent execution time
  - `agent_token_usage_total` — LLM token consumption
  - `pipeline_runs_total` — success/failure counts
  - `publish_attempts_total` — publishing success rates
- **Health:** `GET /api/v1/health` — checks DB, ChromaDB, platform APIs

## Design Decisions

### Why LangGraph over plain LangChain?
LangGraph's `StateGraph` gives us typed state, explicit routing, and `MemorySaver` checkpointing. This means HITL edits can resume mid-pipeline without losing context — critical for the calendar review loop.

### Why Groq (free tier)?
Groq's `llama3-70b-8192` has 70B parameters and 8K context on the free tier — enough for complex analytical prompts. It's also extremely fast (~500 tokens/sec), keeping agent latency low.

### Why ChromaDB (local) over FAISS?
ChromaDB has a REST API, runs as a Docker service, supports metadata filtering, and has a persistent storage backend. FAISS is in-memory only. For production use where we need `user_id` filters in RAG queries, ChromaDB is the right call.

### Why SQLAlchemy 2.0 mapped columns?
Type-safe ORM with `Mapped[str]` syntax catches most DB schema bugs at IDE/mypy time rather than runtime. Paired with Pydantic schemas at the API layer, the whole stack is type-safe end-to-end.

### Why no full LangGraph pipeline run per HITL edit?
The `apply_edit()` function on `PlannerAgent` takes the current calendar JSON and applies only the requested change — it never re-runs profile or competitor analysis. This satisfies TS-4 requirement ("incremental edits without triggering full pipeline re-runs").

## Production Deployment Notes

For cloud deployment (e.g., Railway, Render, GCP):
1. Replace MySQL Docker container with managed MySQL (Cloud SQL, PlanetScale)
2. Replace ChromaDB Docker container with Chroma Cloud or Pinecone
3. Set environment variables in platform dashboard (never commit `.env`)
4. Use `alembic upgrade head` in deployment pipeline for migrations
5. Set `APP_ENV=production` to disable SQLAlchemy echo
