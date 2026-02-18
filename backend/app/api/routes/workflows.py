import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_current_user, get_db
from app.models.user import User
from app.models.workflow import Workflow
from app.models.workflow_version import WorkflowVersion
from app.schemas.workflow import WorkflowCreate, WorkflowEnvelope, WorkflowOut, WorkflowUpdate
from app.services.audit import log_event

router = APIRouter()


def _workflow_to_out(workflow: Workflow) -> WorkflowOut:
    data = json.loads(workflow.data_json)
    return WorkflowOut(
        id=workflow.id,
        owner_id=workflow.owner_id,
        name=workflow.name,
        description=workflow.description,
        is_template=workflow.is_template,
        version=workflow.version,
        data=data,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
    )


def _get_workflow(db: Session, workflow_id: str, user: User) -> Workflow:
    query = db.query(Workflow).filter(Workflow.id == workflow_id)
    if user.role != "admin":
        query = query.filter(Workflow.owner_id == user.id)
    workflow = query.first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.post("", response_model=WorkflowOut)
def create_workflow(
    payload: WorkflowCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workflow = Workflow(
        owner_id=current_user.id,
        name=payload.name,
        description=payload.description,
        is_template=payload.is_template,
        version=1,
        data_json="{}",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    data = payload.data.model_dump()
    data["id"] = workflow.id
    data["name"] = workflow.name
    data["updatedAt"] = datetime.utcnow().isoformat()
    workflow.data_json = json.dumps(data)
    db.add(workflow)
    db.commit()

    version = WorkflowVersion(
        workflow_id=workflow.id,
        version=1,
        data_json=workflow.data_json,
        created_at=datetime.utcnow(),
    )
    db.add(version)
    db.commit()

    log_event(db, action="workflow.create", actor_id=current_user.id, target_type="workflow", target_id=workflow.id)
    return _workflow_to_out(workflow)


@router.get("", response_model=list[WorkflowOut])
def list_workflows(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    templates: str | None = Query(default=None, description="only|exclude"),
):
    query = db.query(Workflow)
    if current_user.role != "admin":
        query = query.filter(Workflow.owner_id == current_user.id)
    if templates == "only":
        query = query.filter(Workflow.is_template.is_(True))
    elif templates == "exclude":
        query = query.filter(Workflow.is_template.is_(False))
    workflows = query.order_by(Workflow.updated_at.desc()).all()
    return [_workflow_to_out(wf) for wf in workflows]


@router.get("/{workflow_id}", response_model=WorkflowOut)
def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workflow = _get_workflow(db, workflow_id, current_user)
    return _workflow_to_out(workflow)


@router.patch("/{workflow_id}", response_model=WorkflowOut)
def update_workflow(
    workflow_id: str,
    payload: WorkflowUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workflow = _get_workflow(db, workflow_id, current_user)

    if payload.name is not None:
        workflow.name = payload.name
    if payload.description is not None:
        workflow.description = payload.description
    if payload.is_template is not None:
        workflow.is_template = payload.is_template
    if payload.data is None and payload.name is not None:
        try:
            data = json.loads(workflow.data_json)
            data["name"] = workflow.name
            data["id"] = workflow.id
            data["updatedAt"] = datetime.utcnow().isoformat()
            workflow.data_json = json.dumps(data)
        except Exception:
            pass
    if payload.data is not None:
        data = payload.data.model_dump()
        data["id"] = workflow.id
        data["name"] = workflow.name
        data["updatedAt"] = datetime.utcnow().isoformat()
        workflow.data_json = json.dumps(data)
        workflow.version += 1
        version = WorkflowVersion(
            workflow_id=workflow.id,
            version=workflow.version,
            data_json=workflow.data_json,
            created_at=datetime.utcnow(),
        )
        db.add(version)

    workflow.updated_at = datetime.utcnow()
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    log_event(db, action="workflow.update", actor_id=current_user.id, target_type="workflow", target_id=workflow.id)
    return _workflow_to_out(workflow)


@router.post("/{workflow_id}/template", response_model=WorkflowOut)
def toggle_template(
    workflow_id: str,
    is_template: bool = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    workflow = _get_workflow(db, workflow_id, current_user)
    workflow.is_template = is_template
    workflow.updated_at = datetime.utcnow()
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    log_event(
        db,
        action="workflow.template",
        actor_id=current_user.id,
        target_type="workflow",
        target_id=workflow.id,
        meta={"is_template": is_template},
    )
    return _workflow_to_out(workflow)


@router.delete("/{workflow_id}")
def delete_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workflow = _get_workflow(db, workflow_id, current_user)
    db.query(WorkflowVersion).filter(WorkflowVersion.workflow_id == workflow.id).delete()
    db.delete(workflow)
    db.commit()
    log_event(db, action="workflow.delete", actor_id=current_user.id, target_type="workflow", target_id=workflow.id)
    return {"ok": True}


@router.post("/{workflow_id}/duplicate", response_model=WorkflowOut)
def duplicate_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workflow = _get_workflow(db, workflow_id, current_user)

    new_workflow = Workflow(
        owner_id=workflow.owner_id,
        name=f"{workflow.name} Copy",
        description=workflow.description,
        version=1,
        data_json=workflow.data_json,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(new_workflow)
    db.commit()
    db.refresh(new_workflow)

    version = WorkflowVersion(
        workflow_id=new_workflow.id,
        version=1,
        data_json=new_workflow.data_json,
        created_at=datetime.utcnow(),
    )
    db.add(version)
    db.commit()

    log_event(db, action="workflow.duplicate", actor_id=current_user.id, target_type="workflow", target_id=new_workflow.id)
    return _workflow_to_out(new_workflow)


@router.post("/{workflow_id}/export", response_model=WorkflowEnvelope)
def export_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workflow = _get_workflow(db, workflow_id, current_user)
    data = json.loads(workflow.data_json)
    log_event(db, action="workflow.export", actor_id=current_user.id, target_type="workflow", target_id=workflow.id)
    return WorkflowEnvelope(
        version=1,
        exportedAt=datetime.utcnow().isoformat(),
        workflow=data,
    )


@router.post("/import", response_model=WorkflowOut)
def import_workflow(
    payload: WorkflowEnvelope,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = payload.workflow
    workflow = Workflow(
        owner_id=current_user.id,
        name=data.name,
        description=None,
        version=1,
        data_json="{}",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    payload_data = data.model_dump()
    payload_data["id"] = workflow.id
    payload_data["name"] = workflow.name
    payload_data["updatedAt"] = datetime.utcnow().isoformat()
    workflow.data_json = json.dumps(payload_data)
    db.add(workflow)
    db.commit()

    version = WorkflowVersion(
        workflow_id=workflow.id,
        version=1,
        data_json=workflow.data_json,
        created_at=datetime.utcnow(),
    )
    db.add(version)
    db.commit()

    log_event(db, action="workflow.import", actor_id=current_user.id, target_type="workflow", target_id=workflow.id)
    return _workflow_to_out(workflow)
