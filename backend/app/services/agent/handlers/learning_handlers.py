import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.models.knowledge import KnowledgeNode, UserKnowledgeMastery
from app.models.learning import LearningRoute
from app.services.knowledge_service import KnowledgeService


async def _tool_search_knowledge(user_id: str, query: str, subject: str | None = None, limit: int = 5) -> str:
    """搜索知识图谱工具 handler"""
    async with async_session_factory() as db:
        nodes, _ = await KnowledgeService.list_nodes(
            db, search=query, subject=subject, page=1, page_size=limit
        )
        if not nodes:
            return "未找到相关知识点。"

        lines = []
        for n in nodes:
            lines.append(f"🧠 {n.name}\n  学科: {n.subject}\n  描述: {(n.description or '')[:100]}")
        return "\n\n".join(lines)


async def _tool_get_mastery(user_id: str, node_name: str) -> str:
    """查询掌握度工具 handler"""
    async with async_session_factory() as db:
        # 按名称查找节点
        node_result = await db.execute(
            select(KnowledgeNode).where(KnowledgeNode.name == node_name)
        )
        node = node_result.scalar_one_or_none()
        if not node:
            return f"未找到知识节点「{node_name}」。"

        mastery_result = await db.execute(
            select(UserKnowledgeMastery).where(
                UserKnowledgeMastery.user_id == uuid.UUID(user_id),
                UserKnowledgeMastery.node_id == node.id,
            )
        )
        mastery = mastery_result.scalar_one_or_none()
        if not mastery:
            return f"未找到关于「{node_name}」的学习记录。"

        score = mastery.mastery_score
        if score < 0.1:
            level = "未开始"
        elif score < 0.4:
            level = "学习中"
        elif score < 0.7:
            level = "熟悉"
        else:
            level = "掌握"

        return (
            f"知识点：{mastery.node.name if hasattr(mastery, 'node') and mastery.node else node_name}\n"
            f"掌握度：{score:.0%}（{level}）\n"
            f"复习次数：{mastery.review_count}"
        )


async def _tool_get_route_progress(user_id: str, topic: str | None = None) -> str:
    """查看学习路线进度工具 handler"""
    async with async_session_factory() as db:
        query = select(LearningRoute).where(
            LearningRoute.user_id == uuid.UUID(user_id),
            LearningRoute.status.in_(["active", "generating"]),
        )
        if topic:
            query = query.where(LearningRoute.topic == topic)

        query = query.options(selectinload(LearningRoute.steps))
        result = await db.execute(query)
        routes = result.scalars().all()

        if not routes:
            return "当前没有进行中的学习路线。"

        lines = []
        for r in routes:
            total = r.total_steps or 0
            completed = sum(1 for s in r.steps if s.status == "completed")
            progress = f"{completed}/{total}" if total else "未知"
            lines.append(f"🗺 {r.topic}\n  进度: {progress}\n  状态: {r.status}")
        return "\n\n".join(lines)
