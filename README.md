# Autonomous Social Media Growth Agent

A production-grade multi-agent AI system for social media content strategy, planning, and publishing.

## Architecture

```
Streamlit UI  →  FastAPI Backend  →  LangGraph Orchestrator
                                           ↓
                              Agents (Profile | Competitor | Planner | Content)
                                           ↓
                              ChromaDB (RAG) + MySQL (State)
                                           ↓
                              External APIs (X/Twitter, LinkedIn)
```

## Quick Start

```bash
# 1. Clone and enter project
git clone <repo-url> && cd ai-social-agent

# 2. Copy env and fill in your keys
cp .env.example .env

# 3. Launch everything
docker-compose up --build

# 4. Open UI
open http://localhost:8501   # Streamlit
open http://localhost:8000/docs  # FastAPI Swagger
```

## Stack
- **Agents**: LangGraph + LangChain
- **LLM**: Groq (free tier) — llama3-70b
- **Embeddings**: sentence-transformers (local)
- **Vector DB**: ChromaDB (local)
- **Database**: MySQL 8
- **API**: FastAPI + OpenAPI 3.0
- **UI**: Streamlit
- **Deploy**: Docker + docker-compose

## Project Structure

```
app/
  api/          FastAPI routes
  agents/       Profile, Competitor, Planner, Content agents
  orchestrator/ LangGraph workflow
  services/     Business logic
  db/           MySQL models & queries
  rag/          Vector DB + embeddings
  utils/        Logging, monitoring, helpers
frontend/       Streamlit app
tests/          pytest test suite
docker/         Dockerfiles
```

## Environment Variables

See `.env.example` for all required variables. Key ones:
- `GROQ_API_KEY` — free at console.groq.com
- `MYSQL_*` — database credentials
- `TWITTER_*` — X API v2 keys (optional, fallback to clipboard)
- `LINKEDIN_*` — LinkedIn API keys (optional)

## Testing

```bash
docker-compose exec api pytest tests/ --cov=app --cov-report=term-missing
```

## API Docs

Available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`.
