from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum

class ClusterStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    ESCALATED = "escalated"

class SyndromeProfile(BaseModel):
    primary: str
    secondary: List[str] = []

class CaseCounts(BaseModel):
    total: int
    last_24h: int
    last_7d: int

class ClusterDocument(BaseModel):
    cluster_id: str
    detected_at: datetime
    last_updated: datetime
    status: ClusterStatus = ClusterStatus.ACTIVE
    centroid: dict          # GeoJSON Point
    radius_km: float
    affected_facilities: List[str]
    affected_population_estimate: int
    syndrome_profile: SyndromeProfile
    case_counts: CaseCounts
    doubling_time_days: Optional[float] = None
    r_estimate: Optional[float] = None
    agent_session_ids: List[str] = []