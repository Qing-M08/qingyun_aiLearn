import uuid
from datetime import datetime

import structlog
from sqlalchemy import desc, func, select

from app.database import async_session_factory
from app.models.learning import QAMessage, QASession

logger = structlog.get_logger()


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


async def _tool_socratic_qa(user_id: str, question: str, topic: str = "", context: str = "") -> str:
    """苏格拉底答疑工具 handler。

    Agent 在判定用户问题为概念理解类问题后调用此工具。
    工具使用苏格拉底导师模式生成引导式回答，不直接给出答案。
    """
    from app.ai.llm_client import get_llm_client
    from app.ai.prompts.qa import SOCRATIC_QA_TOOL_PROMPT

    # 拼接上下文
    context_parts = []
    if topic:
        context_parts.append(f"知识点：{topic}")
    if context:
        context_parts.append(context)
    context_text = "\n".join(context_parts) if context_parts else "无额外上下文"

    # 构建 system prompt
    system_prompt = SOCRATIC_QA_TOOL_PROMPT.format(
        question=question,
        context=context_text,
    )

    try:
        llm = get_llm_client()
        response = await llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.7,
            max_tokens=1000,
        )
        return response.content
    except Exception as e:
        logger.error("socratic_qa_failed", error=str(e))
        return f"抱歉，答疑服务暂时不可用。请稍后重试。"
