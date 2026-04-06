# Makefile — convenience commands for development

.PHONY: up down build test test-cov logs shell-api shell-db migrate reset-db lint

## ── Docker ──────────────────────────────────────────────────────────────────

up:
	docker-compose up --build

up-detach:
	docker-compose up --build -d

down:
	docker-compose down

down-volumes:
	docker-compose down -v

build:
	docker-compose build

logs:
	docker-compose logs -f api

logs-all:
	docker-compose logs -f

## ── Testing ─────────────────────────────────────────────────────────────────

test:
	docker-compose exec api pytest tests/ -v

test-cov:
	docker-compose exec api pytest tests/ --cov=app --cov-report=term-missing

test-local:
	pytest tests/ --cov=app --cov-report=term-missing

test-fast:
	pytest tests/ -k "not TestAPI" -v

## ── Database ─────────────────────────────────────────────────────────────────

migrate:
	docker-compose exec api alembic upgrade head

migrate-local:
	alembic upgrade head

shell-db:
	docker-compose exec mysql mysql -u agent_user -pagent_password social_agent

reset-db:
	docker-compose down -v
	docker-compose up mysql -d
	sleep 10
	docker-compose up --build

## ── Dev shells ───────────────────────────────────────────────────────────────

shell-api:
	docker-compose exec api bash

shell-chroma:
	docker-compose exec chromadb sh

## ── Linting ──────────────────────────────────────────────────────────────────

lint:
	docker-compose exec api python -m py_compile app/main.py app/agents/*.py app/api/*.py app/services/*.py app/rag/*.py app/orchestrator/*.py

## ── Local dev (no Docker) ────────────────────────────────────────────────────

infra-only:
	docker-compose up mysql chromadb -d

run-api:
	uvicorn app.main:app --reload --port 8000

run-ui:
	streamlit run frontend/app.py --server.port 8501

setup-venv:
	python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
