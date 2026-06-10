from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from enum import Enum

class ThreatTier(str, Enum):
    WATCH = "WATCH"
    ALERT = "ALERT"
    EMERGENCY = "EMERGENCY"

class ContributingFactor(BaseModel):
    factor: str
    weight: float
    description: str

class ThreatAssessmentDocument(BaseModel):
    assessment_id: str
    cluster_id: str
    assessed_at: datetime
    threat_tier: ThreatTier
    confidence: float           # 0.0 - 1.0
    contributing_factors: List[ContributingFactor]
    syndromic_score: float      # 0-100
    geo_score: float
    environmental_score: float
    composite_score: float
    recommended_actions: List[str]
    escalation_rationale: str
    agent_session_id: str