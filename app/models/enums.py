"""Enumeration types."""
from enum import Enum


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETE = "complete"
    FAILED = "failed"


class Recommendation(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    AVOID = "avoid"
    STRONG_AVOID = "strong_avoid"


class PropertyType(str, Enum):
    APARTMENT = "apartment"
    HOUSE = "house"
    TOWNHOUSE = "townhouse"
    VILLA = "villa"
    STUDIO = "studio"
    OTHER = "other"


class ProjectionType(str, Enum):
    BASE = "base"
    OPTIMISTIC = "optimistic"
    PESSIMISTIC = "pessimistic"
    MONTE_CARLO = "monte_carlo"
