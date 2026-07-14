"""Analysis request/response schemas (match the frontend types).

``AnalysisSummary`` backs the Home list; ``AnalysisDetail`` (the frontend's
``Analysis``) adds the chamber constants for the Upload/edit screens.
"""

from datetime import date, datetime

from pydantic import BaseModel


class AnalysisSummary(BaseModel):
    id: str
    name: str
    work_date: date
    spot_count: int
    status: str
    created_at: datetime


class AnalysisDetail(AnalysisSummary):
    chamber_area_m2: float
    chamber_volume_l: float
    time_offset_seconds: float
