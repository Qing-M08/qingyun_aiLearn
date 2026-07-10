import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenRefresh(BaseModel):
    refresh_token: str


class UserSchema(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    role: str
    avatar_url: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfileSchema(BaseModel):
    cognitive_style: str = "visual"
    preferred_study_time: str | None = None
    total_study_hours: float = 0.0
    streak_days: int = 0

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    username: str | None = Field(None, min_length=3, max_length=100)
    avatar_url: str | None = None
    cognitive_style: str | None = Field(None, pattern="^(visual|auditory|kinesthetic)$")
    preferred_study_time: str | None = Field(None, pattern="^(morning|afternoon|evening)$")


class AuthResponse(BaseModel):
    user: UserSchema
    access_token: str
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
