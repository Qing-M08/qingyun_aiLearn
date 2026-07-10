from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.user import AuthResponse, TokenRefresh, TokenResponse, UserLogin, UserRegister
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/token", response_model=TokenResponse)
async def login_for_swagger(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """OAuth2表单登录（供Swagger UI使用），username填邮箱"""
    result = await AuthService.login(db, form_data.username, form_data.password)
    return TokenResponse(access_token=result["access_token"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    result = await AuthService.register(db, body.email, body.username, body.password)
    return AuthResponse(**result)


@router.post("/login", response_model=AuthResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await AuthService.login(db, body.email, body.password)
    return AuthResponse(**result)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: TokenRefresh, db: AsyncSession = Depends(get_db)):
    access_token = await AuthService.refresh_token(db, body.refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    body: TokenRefresh,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await AuthService.logout(db, user.id, body.refresh_token)
    return MessageResponse(message="logged out")
