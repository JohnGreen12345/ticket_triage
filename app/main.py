"""FastAPI application — route, error handling, and telemetry middleware."""

import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.engine import get_recommendations
from app.models import TicketInput, TriageResponse

# ---------------------------------------------------------------------------
# Logging setup (structured-ish, keeps it simple)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("ticket_triage")

# ---------------------------------------------------------------------------
# Telemetry counters (in-memory; swap for Prometheus/StatsD later)
# ---------------------------------------------------------------------------
_metrics: dict[str, int | float] = {
    "request_count": 0,
    "error_count": 0,
    "total_latency_ms": 0.0,
}

app = FastAPI(
    title="Support Ticket Triage",
    description="Returns ranked recommendations for incoming support tickets.",
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Middleware: request telemetry
# ---------------------------------------------------------------------------
@app.middleware("http")
async def telemetry_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000

    _metrics["request_count"] += 1
    _metrics["total_latency_ms"] += elapsed_ms

    if response.status_code >= 400:
        _metrics["error_count"] += 1

    logger.info(
        "method=%s path=%s status=%d latency_ms=%.1f",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.post("/recommendations", response_model=TriageResponse)
async def recommend(ticket: TicketInput) -> TriageResponse:
    """Accept a support ticket and return ranked triage recommendations."""
    recommendations = get_recommendations(
        title=ticket.title,
        description=ticket.description,
        top_n=ticket.top_n,
    )
    return TriageResponse(recommendations=recommendations)


@app.get("/health")
async def health():
    """Simple liveness probe."""
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    """Expose basic telemetry counters."""
    return _metrics
