"""笔记相关 Celery 异步任务（Sprint 9: AI 整理笔记）"""

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
