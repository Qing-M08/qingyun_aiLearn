import hashlib
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ConflictException, UnauthorizedException
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models.auth import RefreshToken
from app.models.user import User, UserProfile


class AuthService:

    @staticmethod
    async def register(db: AsyncSession, email: str, username: str, password: str) -> dict:
        # 检查邮箱是否已注册
        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            raise ConflictException("邮箱已注册")

        # 检查用户名是否已存在
        result = await db.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none():
            raise ConflictException("用户名已存在")

        # 创建用户
        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
        )
        db.add(user)
        await db.flush()

        # 创建用户画像
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        await db.flush()

        # 生成token
        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})

        # 存储refresh_token hash
        token_record = RefreshToken(
            user_id=user.id,
            token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(token_record)
        await db.commit()
        await db.refresh(user)

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    @staticmethod
    async def login(db: AsyncSession, email: str, password: str) -> dict:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedException("邮箱或密码错误")

        if not user.is_active:
            raise UnauthorizedException("账号已被禁用")

        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})

        token_record = RefreshToken(
            user_id=user.id,
            token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(token_record)
        await db.commit()

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    @staticmethod
    async def refresh_token(db: AsyncSession, refresh_token_str: str) -> str:
        try:
            payload = decode_token(refresh_token_str)
            user_id = payload.get("sub")
            token_type = payload.get("type")
            if not user_id or token_type != "refresh":
                raise UnauthorizedException("无效的刷新令牌")
        except Exception:
            raise UnauthorizedException("无效的刷新令牌")

        # 验证token hash
        token_hash = hashlib.sha256(refresh_token_str.encode()).hexdigest()
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked == False,  # noqa: E712
                RefreshToken.expires_at > datetime.utcnow(),
            )
        )
        token_record = result.scalar_one_or_none()
        if not token_record:
            raise UnauthorizedException("刷新令牌已失效")

        # 生成新access_token
        new_access_token = create_access_token(data={"sub": user_id})
        return new_access_token

    @staticmethod
    async def logout(db: AsyncSession, user_id: uuid.UUID, refresh_token_str: str):
        token_hash = hashlib.sha256(refresh_token_str.encode()).hexdigest()
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.user_id == user_id,
            )
        )
        token_record = result.scalar_one_or_none()
        if token_record:
            token_record.revoked = True
            await db.commit()
