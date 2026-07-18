import uuid

from app.tasks.celery_app import celery_app, run_async
import structlog

logger = structlog.get_logger()


@celery_app.task(name="agent.update_memory_after_conversation")
def update_memory_after_conversation(session_id: str, user_id: str):
    """
    Agent 对话结束后，异步更新用户知识画像。
    分析对话中的工具调用记录，提取用户关注的知识点，
    更新 memory_index 中的相关知识画像条目。
    """
    async def _run():
        from app.database import async_session_factory
        from app.models.agent_message import AgentMessage
        from app.services.user_memory_service import UserMemoryService
        from sqlalchemy import select

        async with async_session_factory() as db:
            # 1. 加载对话消息和工具调用记录
            result = await db.execute(
                select(AgentMessage)
                .where(AgentMessage.session_id == uuid.UUID(session_id))
                .order_by(AgentMessage.created_at)
            )
            messages = result.scalars().all()

            # 2. 提取工具调用中涉及的知识点
            topics_seen = set()
            for msg in messages:
                if msg.role == "assistant" and msg.tool_calls:
                    for tc in msg.tool_calls if isinstance(msg.tool_calls, list) else []:
                        tool_name = tc.get("tool_name", "")
                        input_data = tc.get("input", {})

                        # 提取搜索/查询中的主题
                        query_text = input_data.get("query") or input_data.get("topic") or input_data.get("node_name")
                        if query_text:
                            topics_seen.add(query_text)

            # 3. 更新 memory_index 中对应条目
            if topics_seen:
                service = UserMemoryService(db)
                for topic in topics_seen:
                    try:
                        user_memory = await service.get_user_memory(uuid.UUID(user_id))
                        await user_memory.update("knowledge", {
                            "topic": topic,
                            "source": "agent_conversation",
                            "session_id": session_id,
                        })
                    except Exception as e:
                        logger.warning("memory_update_failed", topic=topic, error=str(e))

            logger.info("memory_updated_after_conversation", session_id=session_id, topics_count=len(topics_seen))

    try:
        run_async(_run())
    except Exception as e:
        logger.error("memory_update_task_failed", session_id=session_id, error=str(e))


@celery_app.task(name="agent.auto_generate_session_title")
def auto_generate_session_title(session_id: str, user_id: str):
    """
    如果会话标题仍为自动生成的截断文本，
    使用 LLM 生成更有意义的标题。
    """
    async def _run():
        from app.database import async_session_factory
        from app.models.agent_message import AgentMessage
        from app.models.agent_session import AgentSession
        from app.ai.llm_client import get_llm_client
        from sqlalchemy import select

        async with async_session_factory() as db:
            # 1. 加载会话
            session_result = await db.execute(
                select(AgentSession).where(AgentSession.id == uuid.UUID(session_id))
            )
            session = session_result.scalar_one_or_none()
            if not session:
                return

            # 2. 加载前 3 条消息
            msg_result = await db.execute(
                select(AgentMessage)
                .where(AgentMessage.session_id == uuid.UUID(session_id))
                .order_by(AgentMessage.created_at)
                .limit(3)
            )
            messages = msg_result.scalars().all()
            conversation = "\n".join([f"{m.role}: {m.content[:200]}" for m in messages])

            # 3. 调用 LLM 生成标题
            try:
                llm = get_llm_client()
                response = await llm.chat(
                    messages=[{
                        "role": "user",
                        "content": f"请为以下对话生成一个简短的标题（不超过15字）：\n{conversation}",
                    }],
                    temperature=0.3,
                    max_tokens=50,
                )
                new_title = response.content.strip().strip("'\"")

                if new_title and 2 < len(new_title) <= 30:
                    session.title = new_title
                    await db.commit()
                    logger.info("session_title_auto_generated", session_id=session_id, title=new_title)
            except Exception as e:
                logger.warning("title_generation_failed", session_id=session_id, error=str(e))

    try:
        run_async(_run())
    except Exception as e:
        logger.error("title_task_failed", session_id=session_id, error=str(e))
