from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_db
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogOut

router = APIRouter()


@router.get("", response_model=list[AuditLogOut], dependencies=[Depends(get_current_admin)])
def list_audit_logs(db: Session = Depends(get_db), limit: int = 100):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
