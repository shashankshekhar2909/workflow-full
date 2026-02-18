from fastapi import APIRouter

from app.api.routes import auth, users, workflows, generate, audit

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(generate.router, prefix="/workflows", tags=["generate"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
