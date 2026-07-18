"""笔记相关 Celery 异步任务（Sprint 9: AI 整理笔记, Sprint 10: 整理到笔记）"""

import json
import uuid

import redis as sync_redis
from app.tasks.celery_app import celery_app, run_async
from app.config import settings

import structlog

logger = structlog.get_logger()


def _publish_organize_progress(task_id: str, data: dict) -> None:
    """发布整理进度到 Redis Pub/Sub（同步客户端）

    频道格式: organize_progress:{task_id}
    消息格式: JSON {stage, percent, message, note_id?, error?}
    """
    try:
        r = sync_redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.publish(f"organize_progress:{task_id}", json.dumps(data, ensure_ascii=False))
    except Exception as e:
        logger.warning("publish_organize_progress_failed", error=str(e))


def _publish_organize_from_chat_progress(task_id: str, data: dict) -> None:
    """发布整理到笔记进度到 Redis Pub/Sub（同步客户端）

    频道格式: organize_from_chat_progress:{task_id}
    """
    try:
        r = sync_redis.Redis.from_url(
            settings.REDIS_URL.replace("/0", "/3"), decode_responses=True
        )
        r.publish(
            f"organize_from_chat_progress:{task_id}",
            json.dumps(data, ensure_ascii=False),
        )
    except Exception as e:
        logger.warning("publish_organize_from_chat_progress_failed", error=str(e))


@celery_app.task(
    bind=True,
    name="app.tasks.note_tasks.organize_notes_task",
    max_retries=2,
    default_retry_delay=10,
)
def organize_notes_task(
    self,
    user_id_str: str,
    notes_data_json: str,
    prompt: str,
) -> dict:
    """AI 整理笔记异步任务

    流程:
    1. 解析笔记数据
    2. 构建 Prompt
    3. 调用 LLM 生成整理内容
    4. 解析 LLM 输出（标题 + 正文）
    5. 创建成果笔记
    6. 通过 Redis Pub/Sub 推送完成通知

    Args:
        user_id_str: 用户 ID（字符串）
        notes_data_json: 笔记数据 JSON 数组
        prompt: 用户额外提示词

    Returns:
        {"note_id": str, "title": str, "word_count": int}
    """
    task_id = self.request.id

    try:
        # ---- 阶段 1: 准备 ----
        _publish_organize_progress(task_id, {
            "stage": "preparing",
            "percent": 10,
            "message": "正在准备笔记内容...",
        })

        user_id = uuid.UUID(user_id_str)
        notes_data = json.loads(notes_data_json)
        note_count = len(notes_data)

        logger.info(
            "organize_notes_task_started",
            task_id=task_id,
            user_id=user_id_str,
            note_count=note_count,
        )

        # 构建笔记内容文本
        notes_content_parts = []
        for i, nd in enumerate(notes_data, 1):
            tags_str = f"标签: {', '.join(nd['tags'])}" if nd.get("tags") else "无标签"
            subject_str = f"学科: {nd['subject']}" if nd.get("subject") else "未分类"
            part = (
                f"### 笔记 {i}: {nd['title']}\n"
                f"({subject_str} | {tags_str} | {nd.get('word_count', 0)} 字)\n\n"
                f"{nd.get('content', '(空笔记)')}\n"
            )
            notes_content_parts.append(part)

        notes_content = "\n---\n\n".join(notes_content_parts)

        # ---- 阶段 2: 调用 LLM ----
        _publish_organize_progress(task_id, {
            "stage": "generating",
            "percent": 30,
            "message": f"AI 正在整理 {note_count} 篇笔记...",
        })

        user_prompt_text = prompt if prompt.strip() else "请将这多篇笔记合并整理为一篇结构清晰、逻辑连贯的笔记。"

        async def _call_llm_and_save():
            from app.ai.llm_client import get_llm_client
            from app.ai.prompts.note_organize import (
                NOTE_ORGANIZE_SYSTEM_PROMPT,
                NOTE_ORGANIZE_USER_PROMPT,
            )
            from app.database import async_session_factory

            user_message = NOTE_ORGANIZE_USER_PROMPT.format(
                note_count=note_count,
                user_prompt=user_prompt_text,
                notes_content=notes_content,
            )

            llm_client = get_llm_client()
            response = await llm_client.chat(
                messages=[
                    {"role": "system", "content": NOTE_ORGANIZE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=settings.ORGANIZE_LLM_TEMPERATURE,
                max_tokens=settings.ORGANIZE_LLM_MAX_TOKENS,
            )

            llm_output = response.content.strip()

            # 解析标题和正文
            title = "AI 整理笔记"
            content = llm_output

            if llm_output.startswith("# "):
                first_newline = llm_output.find("\n")
                if first_newline != -1:
                    title = llm_output[2:first_newline].strip()
                    content = llm_output[first_newline + 1:].strip()
                else:
                    title = llm_output[2:].strip()
                    content = ""

            if not content:
                content = llm_output  # fallback

            # 创建成果笔记
            from app.models.note import Note
            from app.core.utils import calculate_word_count

            source_ids = [uuid.UUID(nd["id"]) for nd in notes_data]

            async with async_session_factory() as session:
                note = Note(
                    user_id=user_id,
                    title=title,
                    content=content,
                    word_count=calculate_word_count(content),
                    origin_type="ai_organized",
                    source_note_ids=source_ids,
                )
                session.add(note)
                await session.commit()
                await session.refresh(note)

                # 同步到 Meilisearch
                try:
                    from app.services.note_service import _sync_note_to_meilisearch
                    await _sync_note_to_meilisearch(note)
                except Exception as e:
                    logger.warning("meilisearch_sync_failed_in_task", error=str(e))

                return str(note.id), note.title, note.word_count

        note_id, final_title, word_count = run_async(_call_llm_and_save())

        # ---- 阶段 3: 推送完成通知 ----
        _publish_organize_progress(task_id, {
            "stage": "complete",
            "percent": 100,
            "message": "整理完成！",
            "note_id": note_id,
            "title": final_title,
            "word_count": word_count,
            "source_count": note_count,
        })

        logger.info(
            "organize_notes_task_completed",
            task_id=task_id,
            note_id=note_id,
            title=final_title,
            word_count=word_count,
        )

        return {
            "note_id": note_id,
            "title": final_title,
            "word_count": word_count,
        }

    except Exception as exc:
        logger.error(
            "organize_notes_task_failed",
            task_id=task_id,
            error=str(exc),
            exc_info=True,
        )
        _publish_organize_progress(task_id, {
            "stage": "error",
            "percent": 0,
            "message": f"整理失败: {str(exc)}",
            "error": str(exc),
        })
        raise


# ==================== Sprint 10: 整理到笔记 ====================


class _RedisProgressWS:
    """WebSocket 代理对象：将 AgentLoop 的 WS 推送转为 Redis Pub/Sub 进度推送"""

    def __init__(self, task_id: str):
        self.task_id = task_id

    async def send_json(self, data: dict):
        """将 AgentLoop 的 WS 事件转为进度推送"""
        event_type = data.get("type", "")
        if event_type == "thinking":
            _publish_organize_from_chat_progress(self.task_id, {
                "type": "progress",
                "stage": "analyzing",
                "percent": 30,
            })
        elif event_type == "tool_call_start":
            tool_name = data.get("data", {}).get("tool_name", "")
            if tool_name == "get_note_content":
                _publish_organize_from_chat_progress(self.task_id, {
                    "type": "progress",
                    "stage": "reading_note",
                    "percent": 15,
                })
            elif tool_name == "edit_note":
                _publish_organize_from_chat_progress(self.task_id, {
                    "type": "progress",
                    "stage": "editing",
                    "percent": 60,
                })
        # token / done / tool_call_result 等事件不推送进度


@celery_app.task(
    bind=True,
    name="app.tasks.note_tasks.organize_from_chat_task",
    max_retries=0,
)
def organize_from_chat_task(
    self,
    user_id_str: str,
    note_id_str: str,
    agent_session_id_str: str,
    ai_reply_content: str,
    selected_text: str | None = None,
    user_prompt: str | None = None,
) -> dict:
    """整理到笔记 Celery 异步任务

    流程:
    1. 查询笔记内容
    2. 构建 Agent 系统 Prompt
    3. 创建 AgentLoop（max_steps=3, token_budget=8000）
    4. Agent 读取笔记 + 调用 edit_note 插入内容
    5. 通过 Redis Pub/Sub 推送进度

    Args:
        user_id_str: 用户 ID
        note_id_str: 笔记 ID
        agent_session_id_str: 隐藏 Agent 会话 ID
        ai_reply_content: AI 回复内容
        selected_text: 用户划词选中的文本（可选）
        user_prompt: 用户提示词（可选）

    Returns:
        {"agent_session_id": str, "operations_applied": int}
    """
    task_id = self.request.id

    try:
        # ---- 阶段 1: 启动 ----
        _publish_organize_from_chat_progress(task_id, {
            "type": "progress",
            "stage": "starting",
            "percent": 5,
            "agent_session_id": agent_session_id_str,
        })

        logger.info(
            "organize_from_chat_task_started",
            task_id=task_id,
            user_id=user_id_str,
            note_id=note_id_str,
            agent_session_id=agent_session_id_str,
        )

        async def _run_organize():
            from app.database import async_session_factory
            from app.models.note import Note
            from app.models.agent_session import AgentSession
            from app.models.agent_message import AgentMessage
            from app.ai.prompts.note_organize_agent import (
                NOTE_ORGANIZE_AGENT_SYSTEM_PROMPT,
                NOTE_ORGANIZE_USER_PROMPT_WITH_SELECTION,
                NOTE_ORGANIZE_USER_PROMPT_WITHOUT_SELECTION,
            )
            from app.services.agent.agent_loop import AgentLoop
            from app.services.agent.tool_registry import ToolRegistry
            from app.services.agent.handlers.note_handlers import (
                _tool_get_note_content,
                _tool_edit_note,
            )
            from app.services.note_service import NoteService
            from app.ai.llm_client import get_llm_client
            from sqlalchemy import select
            import uuid as _uuid

            async with async_session_factory() as db:
                # 查询笔记
                note = await NoteService.get_note(
                    db, _uuid.UUID(note_id_str), _uuid.UUID(user_id_str)
                )
                note_content = note.content or ""
                note_title = note.title or "无标题"

                # 构建系统 Prompt
                if selected_text:
                    content_to_organize = NOTE_ORGANIZE_USER_PROMPT_WITH_SELECTION.format(
                        selected_text=selected_text,
                        ai_reply_content=ai_reply_content,
                    )
                else:
                    content_to_organize = NOTE_ORGANIZE_USER_PROMPT_WITHOUT_SELECTION.format(
                        ai_reply_content=ai_reply_content,
                    )

                system_prompt = NOTE_ORGANIZE_AGENT_SYSTEM_PROMPT.format(
                    note_id=note_id_str,
                    note_content=note_content,
                    content_to_organize=content_to_organize,
                )

                # 构建用户消息
                if selected_text:
                    user_message = f"请将以下 AI 回复内容整理到笔记中。用户选中的原文是：{selected_text}，AI 的回复是：{ai_reply_content}"
                else:
                    user_message = f"请将以下 AI 回复内容整理到笔记中：{ai_reply_content}"

                # 创建受限工具注册表（只允许 get_note_content 和 edit_note）
                from app.services.agent.tool_schemas import ToolSchema, ToolParameter
                from app.services.note_service import NoteService as NS

                registry = ToolRegistry()
                all_tools = NS.as_tools()
                for tool_schema in all_tools:
                    if tool_schema.name == "get_note_content":
                        registry.register(tool_schema, _tool_get_note_content)
                    elif tool_schema.name == "edit_note":
                        # 包装 edit_note，限制只允许 insert 操作
                        original_handler = _tool_edit_note

                        async def _restricted_edit_note(user_id: str, **kwargs):
                            if kwargs.get("operation") != "insert":
                                from app.services.agent.tool_schemas import ToolResult
                                return ToolResult(
                                    success=False,
                                    error_message="整理到笔记模式下只允许 insert 操作",
                                )
                            return await original_handler(user_id, **kwargs)

                        registry.register(tool_schema, _restricted_edit_note)

                # 获取 Agent 会话
                session_result = await db.execute(
                    select(AgentSession).where(
                        AgentSession.id == _uuid.UUID(agent_session_id_str)
                    )
                )
                agent_session = session_result.scalar_one()

                # 创建 AgentLoop
                ws_proxy = _RedisProgressWS(task_id)
                agent = AgentLoop(
                    registry=registry,
                    llm_client=get_llm_client(),
                    session=agent_session,
                    db=db,
                    ws=ws_proxy,
                    cancel_key=None,  # 整理任务不可取消
                    max_steps=3,
                    token_budget=8000,
                )

                # 覆盖 system prompt（使用整理专用 prompt）
                original_build = agent._build_system_prompt
                def _custom_system_prompt(habit_summary, context_text):
                    return system_prompt
                agent._build_system_prompt = _custom_system_prompt

                # 执行 Agent 循环
                assistant_msg = await agent.run(user_message, [])

                # 统计操作数
                operations_applied = sum(
                    1 for tc in (assistant_msg.tool_calls or [])
                    if tc.get("status") == "success" and tc.get("tool_name") == "edit_note"
                )

                # 重新查询笔记获取更新后的内容
                # （_tool_edit_note 使用独立 DB session 已 commit，
                #   当前 session 需要 refresh 才能看到最新数据）
                await db.refresh(note, ["content", "word_count", "title"])

                return {
                    "operations_applied": operations_applied,
                    "note_content": note.content or "",
                    "word_count": note.word_count,
                    "title": note.title or "",
                }

        result = run_async(_run_organize())
        operations_applied = result["operations_applied"]

        # ---- 完成（附带更新后的笔记内容，供前端刷新编辑器） ----
        _publish_organize_from_chat_progress(task_id, {
            "type": "complete",
            "stage": "complete",
            "percent": 100,
            "agent_session_id": agent_session_id_str,
            "operations_applied": operations_applied,
            "message": "已将内容整理到笔记",
            "note_id": note_id_str,
            "note_content": result["note_content"],
            "word_count": result["word_count"],
            "title": result["title"],
        })

        logger.info(
            "organize_from_chat_task_completed",
            task_id=task_id,
            agent_session_id=agent_session_id_str,
            operations_applied=operations_applied,
        )

        return {
            "agent_session_id": agent_session_id_str,
            "operations_applied": operations_applied,
        }

    except Exception as exc:
        logger.error(
            "organize_from_chat_task_failed",
            task_id=task_id,
            error=str(exc),
            exc_info=True,
        )
        _publish_organize_from_chat_progress(task_id, {
            "type": "error",
            "stage": "error",
            "percent": 0,
            "error_message": f"整理失败: {str(exc)}",
        })
        raise
