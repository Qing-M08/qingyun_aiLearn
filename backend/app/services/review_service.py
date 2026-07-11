import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.models.review import ReviewPlan
from app.models.knowledge import KnowledgeNode, UserKnowledgeMastery
from app.services.knowledge_service import KnowledgeService
from app.ai.llm_client import get_llm_client
from app.ai.prompts.review import REVIEW_GENERATION_PROMPT
from app.core.exceptions import NotFoundException

logger = structlog.get_logger()


class ReviewService:

    @classmethod
    def as_tools(cls) -> list:
        """暴露复习相关工具供 Agent 调用"""
        from app.services.agent.tool_schemas import ToolParameter, ToolSchema
        return [
            ToolSchema(
                name="get_review_status",
                display_name="查看复习状态",
                description="获取用户当前待复习的知识点列表和复习统计",
                parameters={
                    "limit": ToolParameter(type="integer", description="返回数量", required=False, default=5),
                },
                category="read",
                module="review",
                icon="redo",
            ),
            ToolSchema(
                name="schedule_review",
                display_name="创建复习计划",
                description="为指定知识点创建复习计划",
                parameters={
                    "node_name": ToolParameter(type="string", description="知识点名称"),
                    "review_type": ToolParameter(
                        type="string",
                        description="复习类型",
                        enum=["flashcard", "quiz", "explanation"],
                        default="flashcard",
                    ),
                },
                category="write",
                module="review",
                icon="schedule",
            ),
        ]

    # ==================== SM-2 间隔重复算法 ====================

    @staticmethod
    def calculate_next_review(
        mastery: UserKnowledgeMastery,
        quality_rating: int,
    ) -> tuple[datetime, float, int]:
        """
        SM-2间隔重复算法。

        参数：
            mastery: 当前掌握度记录
            quality_rating: 0-5，本次复习质量评分
                0-2: 完全不会
                3: 勉强记住
                4: 有些犹豫
                5: 轻松记住

        返回：
            (next_review_time, new_ease_factor, new_interval_days)
        """
        ef = mastery.ease_factor
        interval = mastery.interval_days

        if quality_rating >= 3:
            # 回答正确
            if interval == 0:
                interval = 1
            elif interval == 1:
                interval = 6
            else:
                interval = round(interval * ef)

            # 更新难度因子（EF）
            ef = ef + (0.1 - (5 - quality_rating) * (0.08 + (5 - quality_rating) * 0.02))
            ef = max(1.3, ef)
        else:
            # 回答错误，重置间隔
            interval = 1
            ef = max(1.3, ef - 0.2)

        next_review = datetime.utcnow() + timedelta(days=interval)
        return next_review, ef, interval

    @staticmethod
    def quality_from_performance(performance: float) -> int:
        """将0.0~1.0的表现分数转换为SM-2的0~5质量评分"""
        if performance >= 0.9:
            return 5
        elif performance >= 0.75:
            return 4
        elif performance >= 0.6:
            return 3
        elif performance >= 0.4:
            return 2
        elif performance >= 0.2:
            return 1
        else:
            return 0

    # ==================== 复习计划管理 ====================

    @staticmethod
    async def schedule_review(
        db: AsyncSession,
        user_id: uuid.UUID,
        node_id: uuid.UUID,
        initial_mastery: float = 0.0,
    ) -> ReviewPlan:
        """创建或更新复习计划"""
        mastery = await KnowledgeService.get_or_create_mastery(db, user_id, node_id)

        # 检查是否已有pending的复习计划
        existing = await db.execute(
            select(ReviewPlan).where(
                ReviewPlan.user_id == user_id,
                ReviewPlan.node_id == node_id,
                ReviewPlan.status == "pending",
            )
        )
        plan = existing.scalar_one_or_none()

        if plan:
            interval = max(1, mastery.interval_days)
            plan.scheduled_at = datetime.utcnow() + timedelta(days=interval)
            plan.priority = ReviewService._calculate_priority(mastery.mastery_score)
        else:
            interval = max(1, mastery.interval_days)
            plan = ReviewPlan(
                user_id=user_id,
                node_id=node_id,
                review_type="spaced",
                scheduled_at=datetime.utcnow() + timedelta(days=interval),
                status="pending",
                priority=ReviewService._calculate_priority(mastery.mastery_score),
            )
            db.add(plan)

        await db.flush()
        await db.refresh(plan)
        return plan

    @staticmethod
    def _calculate_priority(mastery_score: float) -> int:
        """根据掌握度计算复习优先级"""
        if mastery_score < 0.3:
            return 1  # 高优先
        elif mastery_score < 0.6:
            return 3  # 中优先
        else:
            return 5  # 低优先

    @staticmethod
    async def get_review_plans(
        db: AsyncSession,
        user_id: uuid.UUID,
        status: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """获取复习计划列表（含节点名称）"""
        query = select(ReviewPlan).where(ReviewPlan.user_id == user_id)
        count_query = select(func.count()).select_from(ReviewPlan).where(
            ReviewPlan.user_id == user_id
        )

        if status:
            query = query.where(ReviewPlan.status == status)
            count_query = count_query.where(ReviewPlan.status == status)
        if from_date:
            query = query.where(ReviewPlan.scheduled_at >= from_date)
            count_query = count_query.where(ReviewPlan.scheduled_at >= from_date)
        if to_date:
            query = query.where(ReviewPlan.scheduled_at <= to_date)
            count_query = count_query.where(ReviewPlan.scheduled_at <= to_date)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(ReviewPlan.priority.asc(), ReviewPlan.scheduled_at.asc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        plans = list(result.scalars().all())

        # 批量获取节点名称
        node_ids = [p.node_id for p in plans]
        node_map = {}
        if node_ids:
            nodes_result = await db.execute(
                select(KnowledgeNode).where(KnowledgeNode.id.in_(node_ids))
            )
            node_map = {n.id: n for n in nodes_result.scalars().all()}

        # 组装响应
        items = []
        for plan in plans:
            plan_dict = {
                "id": plan.id,
                "user_id": plan.user_id,
                "node_id": plan.node_id,
                "review_type": plan.review_type,
                "scheduled_at": plan.scheduled_at,
                "completed_at": plan.completed_at,
                "status": plan.status,
                "priority": plan.priority,
                "metadata": plan.metadata_,
                "created_at": plan.created_at,
                "updated_at": plan.updated_at,
                "node_name": node_map.get(plan.node_id).name if plan.node_id in node_map else None,
                "node_subject": node_map.get(plan.node_id).subject if plan.node_id in node_map else None,
            }
            items.append(plan_dict)

        return items, total

    @staticmethod
    async def complete_review(
        db: AsyncSession,
        plan_id: uuid.UUID,
        user_id: uuid.UUID,
        performance: float | None = None,
        notes: str | None = None,
    ) -> dict:
        """
        完成一次复习。
        1. 标记复习计划为completed
        2. 使用SM-2算法计算下次复习时间
        3. 更新掌握度
        4. 创建下一次复习计划
        """
        result = await db.execute(
            select(ReviewPlan).where(
                ReviewPlan.id == plan_id,
                ReviewPlan.user_id == user_id,
            )
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise NotFoundException("复习计划不存在")

        # 标记完成
        plan.status = "completed"
        plan.completed_at = datetime.utcnow()
        if notes:
            plan.metadata_ = {**(plan.metadata_ or {}), "notes": notes, "performance": performance}

        # 更新掌握度
        mastery = await KnowledgeService.get_or_create_mastery(db, user_id, plan.node_id)

        # 计算质量评分
        if performance is not None:
            quality = ReviewService.quality_from_performance(performance)
        else:
            quality = 3  # 默认中等

        # SM-2算法计算下次复习时间
        next_review, new_ef, new_interval = ReviewService.calculate_next_review(mastery, quality)

        # 更新掌握度记录
        mastery.ease_factor = new_ef
        mastery.interval_days = new_interval
        mastery.next_review_at = next_review
        mastery.last_reviewed_at = datetime.utcnow()
        mastery.review_count += 1

        if quality >= 3:
            mastery.correct_count += 1
            mastery.mastery_score += (1.0 - mastery.mastery_score) * 0.2
        else:
            mastery.mastery_score *= 0.8

        mastery.mastery_score = max(0.0, min(1.0, mastery.mastery_score))

        await db.flush()

        # 自动创建下一次复习计划
        next_plan = ReviewPlan(
            user_id=user_id,
            node_id=plan.node_id,
            review_type="spaced",
            scheduled_at=next_review,
            status="pending",
            priority=ReviewService._calculate_priority(mastery.mastery_score),
        )
        db.add(next_plan)
        await db.flush()
        await db.refresh(plan)
        await db.refresh(mastery)

        return {
            "plan": plan,
            "mastery": mastery,
            "next_review_at": next_review,
            "next_interval_days": new_interval,
        }

    # ==================== 复习统计 ====================

    @staticmethod
    async def get_review_stats(db: AsyncSession, user_id: uuid.UUID) -> dict:
        """获取复习统计"""
        now = datetime.utcnow()
        week_start = now - timedelta(days=now.weekday())

        # 今日到期
        today_end = now.replace(hour=23, minute=59, second=59)
        today_result = await db.execute(
            select(func.count()).select_from(ReviewPlan).where(
                ReviewPlan.user_id == user_id,
                ReviewPlan.status == "pending",
                ReviewPlan.scheduled_at <= today_end,
            )
        )
        today_due = today_result.scalar() or 0

        # 本周完成
        week_result = await db.execute(
            select(func.count()).select_from(ReviewPlan).where(
                ReviewPlan.user_id == user_id,
                ReviewPlan.status == "completed",
                ReviewPlan.completed_at >= week_start,
            )
        )
        this_week_completed = week_result.scalar() or 0

        # 逾期
        overdue_result = await db.execute(
            select(func.count()).select_from(ReviewPlan).where(
                ReviewPlan.user_id == user_id,
                ReviewPlan.status == "pending",
                ReviewPlan.scheduled_at < now,
            )
        )
        overdue_count = overdue_result.scalar() or 0

        # 掌握度分布
        mastery_result = await db.execute(
            select(UserKnowledgeMastery).where(
                UserKnowledgeMastery.user_id == user_id,
            )
        )
        masteries = mastery_result.scalars().all()

        distribution = {
            "not_started": 0,
            "learning": 0,
            "familiar": 0,
            "mastered": 0,
        }
        for m in masteries:
            if m.mastery_score == 0:
                distribution["not_started"] += 1
            elif m.mastery_score < 0.4:
                distribution["learning"] += 1
            elif m.mastery_score < 0.7:
                distribution["familiar"] += 1
            else:
                distribution["mastered"] += 1

        return {
            "today_due": today_due,
            "this_week_completed": this_week_completed,
            "overdue_count": overdue_count,
            "mastery_distribution": distribution,
        }

    # ==================== 复习内容生成 ====================

    @staticmethod
    async def generate_review_content(
        db: AsyncSession,
        node_id: uuid.UUID,
        user_id: uuid.UUID,
        review_type: str | None = None,
    ) -> dict:
        """
        生成复习内容。
        根据掌握度自动选择复习形式。
        """
        node = await KnowledgeService.get_node(db, node_id)
        mastery = await KnowledgeService.get_or_create_mastery(db, user_id, node_id)

        # 自动选择复习类型
        if not review_type:
            if mastery.mastery_score > 0.7:
                review_type = "flashcard"
            elif mastery.mastery_score > 0.4:
                review_type = "quiz"
            else:
                review_type = "explanation"

        strategy_map = {
            "flashcard": "生成3-5张闪卡，每张包含正面（问题）和背面（答案）。问题要简洁，答案要准确。适合快速回顾。",
            "quiz": "生成3-5道选择题/填空题，包含答案和详细解析。题目应有一定难度，考查理解深度。",
            "explanation": "重新讲解核心概念，使用新的类比和生活例子。讲解后附2-3道基础练习题。适合基础薄弱的学生。",
        }
        review_strategy = strategy_map.get(review_type, strategy_map["quiz"])

        # 构建Prompt
        prompt = REVIEW_GENERATION_PROMPT.format(
            node_name=node.name,
            mastery_score=f"{mastery.mastery_score:.2f}",
            review_count=mastery.review_count,
            last_performance="未知",
            review_strategy=review_strategy,
        )

        # 调用LLM
        try:
            llm = get_llm_client()
            response = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=3000,
            )

            return {
                "content": response.content,
                "type": review_type,
                "node_name": node.name,
            }
        except Exception as e:
            logger.error("review_content_generation_failed", error=str(e))
            return {
                "content": f"生成复习内容失败：{str(e)}",
                "type": review_type,
                "node_name": node.name,
            }

    # ==================== 复习提醒（Celery Beat） ====================

    @staticmethod
    async def check_due_reviews(db: AsyncSession) -> list[ReviewPlan]:
        """
        检查到期的复习计划。
        由Celery Beat定时调用（每5分钟一次）。
        """
        now = datetime.utcnow()
        result = await db.execute(
            select(ReviewPlan)
            .where(
                ReviewPlan.status == "pending",
                ReviewPlan.scheduled_at <= now,
            )
            .order_by(ReviewPlan.priority.asc(), ReviewPlan.scheduled_at.asc())
            .limit(50)
        )
        due_plans = list(result.scalars().all())
        return due_plans
