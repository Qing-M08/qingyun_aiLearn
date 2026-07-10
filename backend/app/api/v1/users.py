from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User, UserProfile
from app.schemas.user import UserProfileSchema, UserSchema, UserUpdate

router = APIRouter()


@router.get("/me")
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    return {
        "user": UserSchema.model_validate(user),
        "profile": UserProfileSchema.model_validate(profile) if profile else None,
    }


@router.patch("/me", response_model=UserSchema)
async def update_me(
    body: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    update_data = body.model_dump(exclude_unset=True)

    # 分离用户字段和画像字段
    profile_fields = {"cognitive_style", "preferred_study_time"}
    user_fields = {k: v for k, v in update_data.items() if k not in profile_fields}
    profile_fields_data = {k: v for k, v in update_data.items() if k in profile_fields}

    # 更新用户
    for field, value in user_fields.items():
        setattr(user, field, value)

    # 更新画像
    if profile_fields_data:
        result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
        profile = result.scalar_one_or_none()
        if profile:
            for field, value in profile_fields_data.items():
                setattr(profile, field, value)

    await db.flush()
    await db.refresh(user)
    return UserSchema.model_validate(user)


@router.get("/me/profile")
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户知识画像摘要"""
    from app.services.user_memory_service import UserMemoryService

    service = UserMemoryService(db)
    mastery_summary = await service.get_mastery_summary(user.id)

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()

    return {
        "mastery_summary": mastery_summary,
        "recent_activity": [],
        "streak_days": profile.streak_days if profile else 0,
        "total_study_hours": profile.total_study_hours if profile else 0.0,
    }
