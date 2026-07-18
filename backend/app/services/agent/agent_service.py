import uuid
from datetime import datetime

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.config import settings
from app.core.cancel_token import clear_cancel_token, set_cancel_token
from app.models.agent_message import AgentMessage
from app.models.agent_session import AgentSession

logger = structlog.get_logger()


class AgentService:
    """
    Agent 服务层：管理会话 CRUD、消息收发、取消生成。
    编排层（AgentLoop）负责推理和工具调用，服务层负责数据持久化和业务逻辑。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- 会话管理 ----

    async def create_session(
        self,
        user_id: str,
        context_type: str = "general",
        context_id: str | None = None,
        initial_message: str | None = None,
        visibility: str = "visible",
    ) -> AgentSession:
        """创建 Agent 会话"""
        context_uuid = uuid.UUID(context_id) if context_id else None
        session = AgentSession(
            user_id=uuid.UUID(user_id),
            context_type=context_type,
            context_id=context_uuid,
            visibility=visibility,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        # 如果有初始消息，保存为用户消息
        if initial_message:
            user_msg = AgentMessage(
                session_id=session.id,
                role="user",
                content=initial_message,
            )
            self.db.add(user_msg)
            session.title = initial_message[:20] + ("..." if len(initial_message) > 20 else "")
            await self.db.commit()
            await self.db.refresh(session)

        return session

    async def create_hidden_session(
        self,
        user_id: str,
        context_type: str = "general",
        context_id: str | None = None,
        title: str | None = None,
    ) -> AgentSession:
        """创建隐藏 Agent 会话（visibility='hidden'）"""
        context_uuid = uuid.UUID(context_id) if context_id else None
        session = AgentSession(
            user_id=uuid.UUID(user_id),
            context_type=context_type,
            context_id=context_uuid,
            visibility="hidden",
            title=title,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def list_sessions(
        self,
        user_id: str,
        status: str | None = None,
        visibility: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AgentSession], int]:
        """获取会话列表（分页）

        Args:
            visibility: 可选过滤。'visible' 只返回普通会话，'hidden' 只返回隐藏会话，
                        None 返回所有会话（默认行为，向后兼容）。
        """
        query = select(AgentSession).where(AgentSession.user_id == uuid.UUID(user_id))
        count_query = select(func.count()).select_from(AgentSession).where(
            AgentSession.user_id == uuid.UUID(user_id)
        )

        if status:
            query = query.where(AgentSession.status == status)
            count_query = count_query.where(AgentSession.status == status)

        if visibility:
            query = query.where(AgentSession.visibility == visibility)
            count_query = count_query.where(AgentSession.visibility == visibility)

        query = query.order_by(desc(AgentSession.updated_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        total_result = await self.db.execute(count_query)

        sessions = list(result.scalars().all())
        total = total_result.scalar() or 0

        return sessions, total

    async def get_session(self, session_id: str, user_id: str) -> AgentSession | None:
        """获取会话详情（校验用户归属）"""
        result = await self.db.execute(
            select(AgentSession).where(
                AgentSession.id == uuid.UUID(session_id),
                AgentSession.user_id == uuid.UUID(user_id),
            )
        )
        return result.scalar_one_or_none()

    async def close_session(self, session_id: str, user_id: str) -> AgentSession | None:
        """关闭会话"""
        session = await self.get_session(session_id, user_id)
        if not session:
            return None
        session.status = "closed"
        session.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def delete_session(self, session_id: str, user_id: str) -> bool:
        """
        删除单个会话（级联删除消息）。
        返回 True 表示删除成功，False 表示会话不存在或不属于该用户。
        """
        session = await self.get_session(session_id, user_id)
        if not session:
            return False

        # 先清除取消令牌（如果存在）
        await clear_cancel_token(session_id)

        # 级联删除：ORM relationship 配置了 cascade="all, delete-orphan"
        await self.db.delete(session)
        await self.db.commit()
        return True

    async def batch_delete_sessions(self, session_ids: list[str], user_id: str) -> tuple[int, list[str]]:
        """
        批量删除会话（级联删除消息）。
        返回 (deleted_count, failed_ids)。
        支持部分成功：逐个删除，失败的记录到 failed_ids。
        """
        deleted_count = 0
        failed_ids = []

        for sid in session_ids:
            try:
                success = await self.delete_session(sid, user_id)
                if success:
                    deleted_count += 1
                else:
                    failed_ids.append(sid)
            except Exception as e:
                logger.warning("batch_delete_session_error", session_id=sid, error=str(e))
                failed_ids.append(sid)

        return deleted_count, failed_ids

    # ---- 消息管理 ----

    async def get_messages(
        self,
        session_id: str,
        user_id: str,
        before: str | None = None,
        limit: int = 50,
    ) -> list[AgentMessage]:
        """
        获取会话历史消息（游标分页）。
        before: 游标，返回此 ID 之前的消息（按 created_at 降序）。
        """
        # 先校验会话归属
        session = await self.get_session(session_id, user_id)
        if not session:
            return []

        query = (
            select(AgentMessage)
            .where(AgentMessage.session_id == uuid.UUID(session_id))
            .order_by(desc(AgentMessage.created_at))
            .limit(limit)
        )

        if before:
            cursor_result = await self.db.execute(
                select(AgentMessage.created_at).where(AgentMessage.id == uuid.UUID(before))
            )
            cursor_time = cursor_result.scalar_one_or_none()
            if cursor_time:
                query = query.where(AgentMessage.created_at < cursor_time)

        result = await self.db.execute(query)
        messages = list(result.scalars().all())
        return list(reversed(messages))  # 返回时按时间正序

    async def save_user_message(self, session_id: str, content: str) -> AgentMessage:
        """保存用户消息"""
        msg = AgentMessage(
            session_id=uuid.UUID(session_id),
            role="user",
            content=content,
        )
        self.db.add(msg)

        # 更新 session 的 updated_at
        session_result = await self.db.execute(
            select(AgentSession).where(AgentSession.id == uuid.UUID(session_id))
        )
        session = session_result.scalar_one()
        session.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    # ---- 取消生成 ----

    async def cancel_generation(self, session_id: str, user_id: str) -> bool:
        """
        取消正在进行的 Agent 生成。
        通过 Redis 设置取消令牌，AgentLoop 在每步检查此令牌。
        """
        session = await self.get_session(session_id, user_id)
        if not session:
            return False
        await set_cancel_token(session_id)
        return True

    # ---- 对话历史构建 ----

    async def build_conversation_history(self, session_id: str, max_turns: int | None = None) -> list[dict]:
        """
        从数据库加载最近的对话历史，构建为 LLM messages 格式。
        最多取最近 max_turns 轮对话（1 轮 = 1 条 user + 1 条 assistant）。
        """
        max_turns = max_turns or settings.AGENT_MAX_CONVERSATION_TURNS
        result = await self.db.execute(
            select(AgentMessage)
            .where(
                AgentMessage.session_id == uuid.UUID(session_id),
                AgentMessage.role.in_(["user", "assistant"]),
            )
            .order_by(desc(AgentMessage.created_at))
            .limit(max_turns * 2)
        )
        messages = list(reversed(result.scalars().all()))

        history = []
        for msg in messages:
            history.append({
                "role": msg.role,
                "content": msg.content,
            })
        return history
