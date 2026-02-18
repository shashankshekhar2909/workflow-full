import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User
from app.models.refresh_token import RefreshToken  # noqa: F401
from app.models.workflow import Workflow  # noqa: F401
from app.models.workflow_version import WorkflowVersion  # noqa: F401


app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(api_router, prefix=settings.API_V1_STR)

origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.on_event("startup")
def on_startup():
    os.makedirs("data", exist_ok=True)
    if settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD:
        db = SessionLocal()
        try:
            existing = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
            if not existing:
                admin = User(
                    email=settings.ADMIN_EMAIL,
                    password_hash=get_password_hash(settings.ADMIN_PASSWORD),
                    role="admin",
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(admin)
                db.commit()
            if settings.TEST_USERS:
                entries = [item.strip() for item in settings.TEST_USERS.split(";") if item.strip()]
                for entry in entries:
                    parts = [p.strip() for p in entry.split(":")]
                    if len(parts) < 2:
                        continue
                    email = parts[0]
                    password = parts[1]
                    role = parts[2] if len(parts) > 2 else "user"
                    existing_user = db.query(User).filter(User.email == email).first()
                    if existing_user:
                        continue
                    user = User(
                        email=email,
                        password_hash=get_password_hash(password),
                        role=role,
                        is_active=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    db.add(user)
                db.commit()
        finally:
            db.close()


@app.get("/health")
def health():
    return {"ok": True}
