import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.schemas.workflow import GenerateRequest, GenerateResponse
from app.services.generate import generate_workflow
from app.services.audit import log_event

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=GenerateResponse)
def generate(payload: GenerateRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        workflow = generate_workflow(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Workflow generation failed")
        raise HTTPException(status_code=500, detail="Generation failed") from exc

    log_event(db, action="workflow.generate", actor_id=user.id, target_type="workflow", target_id=workflow.id)
    return GenerateResponse(workflow=workflow)
