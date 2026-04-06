"""
app/utils/logger.py — Structured logging + metrics for observability (TS-7).
"""
import structlog
import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Generator
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# ── Structlog setup ──────────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()

# ── Prometheus metrics ───────────────────────────────────────────────────────
agent_latency = Histogram(
    "agent_latency_seconds",
    "Time spent running an agent",
    ["agent_name"],
)

token_usage_counter = Counter(
    "agent_token_usage_total",
    "Total tokens consumed",
    ["agent_name"],
)

pipeline_runs_counter = Counter(
    "pipeline_runs_total",
    "Total pipeline runs",
    ["stage", "status"],
)

publish_counter = Counter(
    "publish_attempts_total",
    "Publishing attempts",
    ["platform", "status"],
)

active_pipelines = Gauge(
    "active_pipelines",
    "Number of currently running pipelines",
)


# ── Decorators / context managers ────────────────────────────────────────────

@contextmanager
def track_agent(agent_name: str) -> Generator:
    """Context manager that records agent latency and logs entry/exit."""
    start = time.perf_counter()
    active_pipelines.inc()
    log.info("agent.start", agent=agent_name)
    try:
        yield
        elapsed = time.perf_counter() - start
        agent_latency.labels(agent_name=agent_name).observe(elapsed)
        pipeline_runs_counter.labels(stage=agent_name, status="success").inc()
        log.info("agent.complete", agent=agent_name, latency_ms=round(elapsed * 1000))
    except Exception as exc:
        elapsed = time.perf_counter() - start
        pipeline_runs_counter.labels(stage=agent_name, status="failed").inc()
        log.error("agent.failed", agent=agent_name, error=str(exc), latency_ms=round(elapsed * 1000))
        raise
    finally:
        active_pipelines.dec()


def record_tokens(agent_name: str, tokens: int) -> None:
    token_usage_counter.labels(agent_name=agent_name).inc(tokens)
    log.debug("tokens.used", agent=agent_name, tokens=tokens)


def record_publish(platform: str, success: bool) -> None:
    status = "success" if success else "failed"
    publish_counter.labels(platform=platform, status=status).inc()
