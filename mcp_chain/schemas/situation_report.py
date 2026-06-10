from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from enum import Enum

class SitRepStatus(str, Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class ReportContent(BaseModel):
    executive_summary: str
    situation_overview: str
    epidemiological_analysis: str
    environmental_context: str
    risk_assessment: str
    recommended_actions: List[str]
    surveillance_gaps: List[str]
    next_review: datetime

class SituationReportDocument(BaseModel):
    sitrep_id: str
    cluster_id: str
    assessment_id: str
    generated_at: datetime
    threat_tier: str
    report: ReportContent
    status: SitRepStatus = SitRepStatus.DRAFT
    reviewed_by: Optional[str] = None