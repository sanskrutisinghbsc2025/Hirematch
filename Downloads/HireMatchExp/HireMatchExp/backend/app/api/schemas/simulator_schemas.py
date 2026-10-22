
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, root_validator


class SimulatorRunRequest(BaseModel):
    session_id: str
    simulated_weights: Optional[Dict[str, float]] = None
    weight_adjustments: Optional[Dict[str, float]] = None
    weights: Optional[Dict[str, float]] = None
    threshold_adjustments: Optional[Dict[str, Any]] = None
    thresholds: Optional[Dict[str, Any]] = None

    @root_validator(pre=True)
    def normalize_weights(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        sim_weights = (
            values.get("simulated_weights")
            or values.get("weight_adjustments")
            or values.get("weights")
            or {}
        )
        values["simulated_weights"] = {
            str(k): float(v) for k, v in sim_weights.items()
        }
        return values


class SimulatedCandidateRow(BaseModel):
    candidate_id: str
    filename: str
    candidate_name: Optional[str] = None
    name: Optional[str] = None
    original_rank: int
    simulated_rank: int
    rank_delta: int
    original_score: Optional[float] = None
    simulated_score: Optional[float] = None
    score_delta: float = 0.0


class SimulatorRunResponse(BaseModel):
    success: bool
    session_id: str
    total_simulated: int
    rank_changers_count: int
    volatility_percentage: float
    simulated_candidates: List[SimulatedCandidateRow]
    rank_shifts: Optional[List[SimulatedCandidateRow]] = None
    errors: List[str] = []
