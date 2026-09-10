"""Data models for the Actionable Recommendation Engine.

Provides concrete, evidence-backed remediation recommendations with
explicit verification procedures and priority ratings.
"""

from __future__ import annotations

from typing import List
from pydantic import BaseModel, ConfigDict, Field

from src.entity_trust.contracts.schemas import SeverityLevel


class ActionableRecommendation(BaseModel):
    """Rich, actionable remediation recommendation.

    Conforms to the required structure:
      - finding_id: Machine-readable code (e.g. ENG-001, EC-001, TECH-HTTP-404)
      - category: Area of the finding (engagement, entity, freshness, technical, etc.)
      - title: Short description of the recommended fix
      - priority: Priority rating (critical, high, medium, low, info)
      - what_is_wrong: Plain-English diagnosis of the defect
      - where_it_occurs: List of specific affected URLs
      - what_should_be_changed: Prescriptive change instructions
      - why_it_matters: Business, agentic, and SEO impact explanation
      - verification_steps: Exact procedure to verify that the fix succeeded
    """
    model_config = ConfigDict(extra="ignore")

    finding_id: str = Field(..., description="ID of the associated finding")
    category: str = Field(..., description="Category of the finding")
    title: str = Field(..., description="Action-oriented summary title")
    priority: SeverityLevel = Field(..., description="Priority: critical, high, medium, low, info")
    what_is_wrong: str = Field(..., description="Detailed diagnosis of what is broken or missing")
    where_it_occurs: List[str] = Field(default_factory=list, description="URLs where the issue was observed")
    what_should_be_changed: str = Field(..., description="Exact instructions on what needs to be changed")
    why_it_matters: str = Field(..., description="Explanation of impact on AI readiness and user journey")
    verification_steps: str = Field(..., description="Concrete steps to test and verify the fix")
