"""Response summary for the match & compute run."""

from pydantic import BaseModel


class MatchSummary(BaseModel):
    status: str
    spots_total: int
    spots_computed: int
    spots_skipped: int
    flux_results: int
