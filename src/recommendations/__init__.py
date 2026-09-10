"""Actionable Recommendation Engine Module (Member 3).

Transforms audit findings across technical, trust, and engagement areas
into concrete remediation roadmaps with explicit verification procedures.
"""

from .models import ActionableRecommendation
from .engine import RecommendationEngine

__all__ = [
    "ActionableRecommendation",
    "RecommendationEngine",
]
