"""Shared Pydantic models — the contract between API and engine."""

from pydantic import BaseModel, Field


class TicketInput(BaseModel):
    """Incoming support ticket."""

    title: str = Field(..., min_length=1, description="Short summary of the issue")
    description: str = Field(
        ..., min_length=1, description="Detailed description of the issue"
    )
    top_n: int = Field(default=3, ge=1, le=10, description="Number of recommendations")


class Recommendation(BaseModel):
    """A single ranked recommendation."""

    action: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    why: str


class TriageResponse(BaseModel):
    """Response wrapper for the recommendations endpoint."""

    recommendations: list[Recommendation]
