
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_orchestrator
from backend.app.api.schemas.simulator_schemas import (
    SimulatedCandidateRow,
    SimulatorRunRequest,
    SimulatorRunResponse,
)
from core.services.session_orchestrator import ScreeningOrchestrator
from core.utils.logger import logger

router = APIRouter(prefix="/simulator", tags=["Sensitivity Simulator"])


class SaveConfigPayload(BaseModel):
    session_id: str
    weights: Optional[Dict[str, float]] = None
    simulated_weights: Optional[Dict[str, float]] = None
    thresholds: Optional[Dict[str, Any]] = None


@router.post("/run", response_model=SimulatorRunResponse)
def run_simulation(
    payload: SimulatorRunRequest,
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        session = orchestrator.session_repo.get(payload.session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{payload.session_id}' not found")

        weights = dict(payload.simulated_weights or {})
        if not weights:
            crit_list = orchestrator.crit_repo.list_by_job(session.job_id)
            weights = {c.id: c.weight for c in crit_list}

        result = orchestrator.simulate_ranking_sensitivity(
            session_id=payload.session_id,
            new_weights=weights,
        )

        if not result.get("success", False):
            return SimulatorRunResponse(
                success=False,
                session_id=payload.session_id,
                total_simulated=0,
                rank_changers_count=0,
                volatility_percentage=0.0,
                simulated_candidates=[],
                rank_shifts=[],
                errors=result.get("errors", ["Simulation failed"]),
            )

        sim_cands = result.get("simulated_candidates", [])
        rows = [
            SimulatedCandidateRow(
                candidate_id=c["candidate_id"],
                filename=c.get("filename", "Resume.pdf"),
                candidate_name=c.get("candidate_name") or c.get("filename", "Candidate"),
                name=c.get("candidate_name") or c.get("filename", "Candidate"),
                original_rank=c["original_rank"],
                simulated_rank=c["simulated_rank"],
                rank_delta=c["rank_delta"],
                original_score=c.get("original_score"),
                simulated_score=c.get("simulated_score"),
                score_delta=c.get("score_delta", 0.0),
            )
            for c in sim_cands
        ]

        total_sim = len(rows)
        changers = result.get("rank_changers_count", 0)
        volatility = round((changers / max(1, total_sim)) * 100.0, 1)

        return SimulatorRunResponse(
            success=True,
            session_id=payload.session_id,
            total_simulated=total_sim,
            rank_changers_count=changers,
            volatility_percentage=volatility,
            simulated_candidates=rows,
            rank_shifts=rows,
            errors=[],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing ranking simulation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation execution failed: {str(e)}",
        )


@router.post("/save-config")
def save_simulated_config(
    payload: SaveConfigPayload,
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        session = orchestrator.session_repo.get(payload.session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        weights = payload.weights or payload.simulated_weights or {}
        criteria = orchestrator.crit_repo.list_by_job(session.job_id)
        updated_count = 0
        for crit in criteria:
            w_val = None
            if crit.id in weights:
                w_val = weights[crit.id]
            elif crit.criterion_name in weights:
                w_val = weights[crit.criterion_name]

            if w_val is not None:
                crit.weight = max(0.0, float(w_val))
                orchestrator.crit_repo.update(crit)
                updated_count += 1

        return {
            "status": "success",
            "message": f"Updated weights for {updated_count} criteria.",
            "session_id": payload.session_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying simulated weights: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply simulated configuration: {str(e)}",
        )
