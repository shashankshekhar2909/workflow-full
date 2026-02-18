from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    role: str = "user"
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class UserSelfUpdate(BaseModel):
    email: EmailStr | None = None


class UserOut(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None

    class Config:
        from_attributes = True
