import uuid

from sqlalchemy import select

from app.database import async_session_factory
from app.models.knowledge import KnowledgeNode
from app.models.review import ReviewPlan
from app.services.review_service import ReviewService


async def _tool_get_review_status(user_id: str, limit: int = 5) -> str:
    """查看复习状态工具 handler"""
    async with async_session_factory() as db:
        # 获取复习统计
        import structlog
        logger = structlog.get_logger()

        stats = await ReviewService.get_review_stats(db, uuid.UUID(user_id))

        # 获取待复习列表
        from datetime import datetime
        now = datetime.utcnow()
        pending_result = await db.execute(
            select(ReviewPlan)
            .where(
                ReviewPlan.user_id == uuid.UUID(user_id),
                ReviewPlan.status == "pending",
                ReviewPlan.scheduled_at <= now.replace(hour=23, minute=59, second=59),
            )
            .order_by(ReviewPlan.priority.asc())
            .limit(limit)
        )
        pending = pending_result.scalars().all()

        # 批量获取节点名称
        node_ids = [p.node_id for p in pending]
        node_map = {}
        if node_ids:
            nodes_result = await db.execute(
                select(KnowledgeNode).where(KnowledgeNode.id.in_(node_ids))
            )
            node_map = {n.id: n for n in nodes_result.scalars().all()}

        lines = [
            f"📊 复习统计：本周完成 {stats.get('this_week_completed', 0)} 次，"
            f"今日到期 {stats.get('today_due', 0)} 项，逾期 {stats.get('overdue_count', 0)} 项"
        ]

        if pending:
            lines.append("\n📋 待复习：")
            for p in pending:
                node = node_map.get(p.node_id)
                node_name = node.name if node else str(p.node_id)
                lines.append(f"  - {node_name}（到期 {p.scheduled_at.strftime('%m-%d')}）")
        else:
            lines.append("\n暂无待复习内容。")
        return "\n".join(lines)


async def _tool_schedule_review(user_id: str, node_name: str, review_type: str = "flashcard") -> str:
    """创建复习计划工具 handler"""
    async with async_session_factory() as db:
        # 按名称查找节点
        node_result = await db.execute(
            select(KnowledgeNode).where(KnowledgeNode.name == node_name)
        )
        node = node_result.scalar_one_or_none()
        if not node:
            return f"无法为「{node_name}」创建复习计划，请确认该知识点存在。"

        try:
            plan = await ReviewService.schedule_review(
                db,
                user_id=uuid.UUID(user_id),
                node_id=node.id,
            )
            return (
                f"已创建复习计划：{node_name}\n"
                f"类型: {review_type}\n"
                f"下次复习: {plan.scheduled_at.strftime('%Y-%m-%d')}"
            )
        except Exception as e:
            return f"创建复习计划失败：{str(e)}"
