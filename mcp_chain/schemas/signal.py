from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum

class SignalType(str, Enum):
    CLINIC_VISIT = "clinic_visit"
    PHARMACY_SALE = "pharmacy_sale"
    SOCIAL_REPORT = "social_report"
    LAB_RESULT = "lab_result"

class SyndromeCode(str, Enum):
    ILI = "ILI"
    SARI = "SARI"
    AGE = "AGE"
    AFP = "AFP"
    UF = "UF"
    HF = "HF"
    NBI = "NBI"

class GeoPoint(BaseModel):
    type: str = "Point"
    coordinates: List[float]   # [longitude, latitude]

class SignalMetadata(BaseModel):
    signal_type: SignalType
    source_id: str
    region_id: str
    pathogen_suspected: Optional[str] = None

class SeverityDistribution(BaseModel):
    mild: int = 0
    moderate: int = 0
    severe: int = 0

class AgeGroups(BaseModel):
    under5: int = 0
    age_5_17: int = Field(0, alias="5_17")
    age_18_60: int = Field(0, alias="18_60")
    over60: int = 0

class SignalDocument(BaseModel):
    metadata: SignalMetadata
    timestamp: datetime
    location: GeoPoint
    syndrome_codes: List[SyndromeCode]
    case_count: int
    severity_distribution: SeverityDistribution
    age_groups: AgeGroups
    raw_text: str
    normalized_by_agent: bool = False