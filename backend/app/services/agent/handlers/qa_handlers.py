import uuid
from datetime import datetime

from sqlalchemy import desc, func, select

from app.database import async_session_factory
from app.models.learning import QAMessage, QASession


async def _tool_get_qa_history(user_id: str, limit: int = 3) -> str:
    """查看答疑历史工具 handler"""
    async with async_session_factory() as db:
        # 查询最近的 QA 会话
        sessions_result = await db.execute(
            select(QASession)
            .where(QASession.user_id == uuid.UUID(user_id))
            .order_by(desc(QASession.updated_at))
            .limit(limit)
        )
        sessions = sessions_result.scalars().all()

        if not sessions:
            return "暂无答疑记录。"

        lines = []
        for s in sessions:
            # 统计消息数
            msg_count_result = await db.execute(
                select(func.count()).select_from(QAMessage).where(
                    QAMessage.session_id == s.id
                )
            )
            msg_count = msg_count_result.scalar() or 0

            lines.append(
                f"💬 {s.node_id or '通用答疑'}\n"
                f"  消息数: {msg_count}\n"
                f"  最后活跃: {s.updated_at.strftime('%m-%d %H:%M')}"
            )
        return "\n\n".join(lines)
