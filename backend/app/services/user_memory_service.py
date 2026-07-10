import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeNode, UserKnowledgeMastery
from app.models.user import PersonalHabitProfile, UserProfile
from app.services.memory.user_memory import UserMemory


class UserMemoryService:
    """用户记忆服务 — 业务逻辑层"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_memory(self, user_id: uuid.UUID) -> UserMemory:
        """获取用户的UserMemory对象（供Agent调用）"""
        memory = UserMemory(user_id, self.db)
        await memory.load_index()
        return memory

    async def update_knowledge_mastery(
        self,
        user_id: uuid.UUID,
        node_id: uuid.UUID,
        mastery_score: float,
        correct: bool = False,
    ):
        """更新知识掌握度，同步更新记忆系统"""
        # 1. 更新user_knowledge_mastery
        result = await self.db.execute(
            select(UserKnowledgeMastery).where(
                UserKnowledgeMastery.user_id == user_id,
                UserKnowledgeMastery.node_id == node_id,
            )
        )
        mastery = result.scalar_one_or_none()

        if mastery:
            mastery.mastery_score = mastery_score
            mastery.total_count += 1
            if correct:
                mastery.correct_count += 1
        else:
            mastery = UserKnowledgeMastery(
                user_id=user_id,
                node_id=node_id,
                mastery_score=mastery_score,
                total_count=1,
                correct_count=1 if correct else 0,
            )
            self.db.add(mastery)

        await self.db.flush()

        # 2. 获取知识点名称
        node_result = await self.db.execute(select(KnowledgeNode).where(KnowledgeNode.id == node_id))
        node = node_result.scalar_one_or_none()
        node_name = node.name if node else str(node_id)

        # 3. 同步更新记忆系统
        memory = UserMemory(user_id, self.db)
        await memory.update("knowledge", {
            "topic": node_name,
            "node_id": str(node_id),
            "mastery_score": mastery_score,
            "total_count": mastery.total_count,
            "correct_count": mastery.correct_count,
        })

    async def update_learning_behavior(self, user_id: uuid.UUID, duration_seconds: int, activity_type: str):
        """更新学习行为统计"""
        result = await self.db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        profile = result.scalar_one_or_none()
        if profile:
            profile.total_study_hours += duration_seconds / 3600.0
            profile.last_active_at = datetime.utcnow()
            await self.db.flush()

        # 更新个人习惯画像
        habit_result = await self.db.execute(
            select(PersonalHabitProfile).where(PersonalHabitProfile.user_id == user_id)
        )
        habit = habit_result.scalar_one_or_none()
        if habit:
            # 简单更新平均时长
            if habit.avg_session_minutes:
                habit.avg_session_minutes = (habit.avg_session_minutes + duration_seconds // 60) // 2
            else:
                habit.avg_session_minutes = duration_seconds // 60
            # 清除摘要缓存
            habit.summary_cache = None
            await self.db.flush()

    async def get_mastery_summary(self, user_id: uuid.UUID) -> dict:
        """获取知识掌握度统计"""
        result = await self.db.execute(
            select(UserKnowledgeMastery).where(UserKnowledgeMastery.user_id == user_id)
        )
        all_mastery = result.scalars().all()

        total = len(all_mastery)
        mastered = sum(1 for m in all_mastery if m.mastery_score > 0.7)
        learning = sum(1 for m in all_mastery if 0.3 < m.mastery_score <= 0.7)
        not_started = total - mastered - learning

        return {
            "total_nodes": total,
            "mastered": mastered,
            "learning": learning,
            "not_started": not_started,
        }
