from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.security import (
    create_access_token,
    create_refresh_token_value,
    create_reset_token_value,
    get_password_hash,
    verify_password,
)
from app.models.password_reset import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.audit import log_event
from app.schemas.auth import LoginRequest, PasswordChangeRequest, PasswordResetConfirm, PasswordResetRequest, Token

router = APIRouter()

REFRESH_COOKIE_NAME = "refresh_token"


def _set_refresh_cookie(response: Response, token: str, expires_at: datetime) -> None:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        expires=expires_at,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/")


def _issue_refresh_token(db: Session, user_id: str) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    token = create_refresh_token_value()
    db_token = RefreshToken(
        token=token,
        user_id=user_id,
        created_at=datetime.utcnow(),
        expires_at=expires_at,
    )
    db.add(db_token)
    db.commit()
    return token, expires_at


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User inactive")

    user.last_login_at = datetime.utcnow()
    db.add(user)
    db.commit()

    token = create_access_token(subject=user.id)
    refresh_token, expires_at = _issue_refresh_token(db, user.id)
    _set_refresh_cookie(response, refresh_token, expires_at)
    log_event(db, action="auth.login", actor_id=user.id, target_type="user", target_id=user.id)
    return Token(access_token=token)


@router.post("/refresh", response_model=Token)
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
):
    if refresh_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    db_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token == refresh_token, RefreshToken.revoked_at.is_(None))
        .first()
    )
    if not db_token or db_token.expires_at < datetime.utcnow():
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user or not user.is_active:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")

    db_token.revoked_at = datetime.utcnow()
    db.add(db_token)
    db.commit()

    new_refresh, expires_at = _issue_refresh_token(db, db_token.user_id)
    _set_refresh_cookie(response, new_refresh, expires_at)

    token = create_access_token(subject=db_token.user_id)
    log_event(db, action="auth.refresh", actor_id=db_token.user_id, target_type="user", target_id=db_token.user_id)
    return Token(access_token=token)


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
):
    if refresh_token:
        db_token = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
        if db_token and db_token.revoked_at is None:
            db_token.revoked_at = datetime.utcnow()
            db.add(db_token)
            db.commit()
            log_event(db, action="auth.logout", actor_id=db_token.user_id, target_type="user", target_id=db_token.user_id)
    _clear_refresh_cookie(response)
    return {"ok": True}


@router.post("/request-reset")
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return {"ok": True}

    expires_at = datetime.utcnow() + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)
    token = create_reset_token_value()
    entry = PasswordResetToken(
        token=token,
        user_id=user.id,
        created_at=datetime.utcnow(),
        expires_at=expires_at,
    )
    db.add(entry)
    db.commit()
    log_event(db, action="auth.reset.request", actor_id=user.id, target_type="user", target_id=user.id)
    return {"ok": True, "token": token, "expires_at": expires_at.isoformat()}


@router.post("/reset")
def reset_password(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    token = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token == payload.token, PasswordResetToken.used_at.is_(None))
        .first()
    )
    if not token or token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == token.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    user.password_hash = get_password_hash(payload.new_password)
    user.updated_at = datetime.utcnow()
    token.used_at = datetime.utcnow()
    db.add(user)
    db.add(token)
    db.commit()
    log_event(db, action="auth.reset.confirm", actor_id=user.id, target_type="user", target_id=user.id)
    return {"ok": True}


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password invalid")
    current_user.password_hash = get_password_hash(payload.new_password)
    current_user.updated_at = datetime.utcnow()
    db.add(current_user)
    db.commit()
    log_event(db, action="auth.password.change", actor_id=current_user.id, target_type="user", target_id=current_user.id)
    return {"ok": True}
