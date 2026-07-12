# Phase 4：笔记 AI 增强 — Sprint 9 - 青云智学后端开发文档

> 版本: 0.4.0 | 创建日期: 2026-07-11  
> 基于: Phase 1-3 后端开发进度文档（v1.2）  
> 前置依赖: Phase 1（基础搭建）✅ / Phase 2（核心功能）✅ / Phase 3（Agent 智能体）✅

---

## 1. 本阶段总览

### 1.1 目标概述

本阶段为笔记系统增加两项 AI 增强能力：

1. **AI 整理笔记**：用户在笔记列表多选笔记后，输入额外提示词，由 AI 将多篇笔记整合为一篇新的成果笔记。整理方式由提示词驱动（合并/摘要/对比/扩展/重组等），走独立 API（不经过 Agent 对话），Celery 异步处理 + WebSocket 推送进度。
2. **AI 修改笔记**：为 Agent 新增 `edit_note` 工具，支持对笔记进行行号级别的局部编辑（insert / replace / delete）。Agent 调用工具后，通过 WebSocket 实时推送编辑指令到前端，前端直接应用到 Tiptap 编辑器，用户可 Ctrl+Z 撤销。

### 1.2 Sprint 列表

| Sprint | 标题 | 核心交付 |
|--------|------|----------|
| 9.1 | AI 整理笔记 | Prompt 模板、Service 扩展、Celery 任务、API 路由、WS 进度推送 |
| 9.2 | AI 修改笔记（Agent 工具） | edit_note 工具 Schema + Handler、WS 实时推送、工具注册 |

### 1.3 技术栈

沿用 Phase 1-3 全部技术栈，无新增依赖：

| 组件 | 技术选型 | 版本 |
|------|---------|------|
| Web 框架 | FastAPI | ≥0.115 |
| ORM | SQLAlchemy | ≥2.0 (async) |
| 数据库 | PostgreSQL | 16 |
| 缓存/消息队列 | Redis | 7 |
| 异步任务 | Celery | ≥5.4 |
| 搜索引擎 | Meilisearch | v1.8 |
| LLM 服务 | DeepSeek API | OpenAI 兼容接口 |
| 嵌入模型 | sentence-transformers | bge-m3 |
| 认证 | JWT | python-jose |
| 日志 | structlog | ≥24.1 |

### 1.4 设计决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| AI 整理链路 | 独立 API（不走 AgentLoop） | 整理是明确的一次性任务，不需要 ReAct 多轮推理 |
| 整理异步模式 | Celery + WS 推送 | 多篇笔记拼接后 token 量大，LLM 调用可能 10-30 秒 |
| edit_note 定位方式 | 行号（1-based） | 实现简单，LLM 可理解 |
| edit_note 前端交互 | WS 实时推送 + 可撤销 | 不打断用户体验，Tiptap 原生支持 undo |
| edit_note 推送通道 | 复用 `/ws/notifications` | 避免新增 WS 端点，消息类型区分即可 |
| 整理成果笔记 | 新建 Note 记录 | 不覆盖原始笔记，保留原始数据 |

---

## 2. 项目目录结构（增量）

以下仅列出本 Phase 新增或修改的文件：

```
backend/
├── app/
│   ├── ai/
│   │   └── prompts/
│   │       └── note_organize.py       # [新增] AI 整理笔记 Prompt 模板
│   ├── api/
│   │   └── v1/
│   │       ├── notes.py               # [修改] 新增 POST /notes/organize 端点
│   │       ├── websocket.py           # [修改] 新增 organize-progress WS 端点
│   │       └── router.py              # [修改] 注册 agent 路由（Phase 3 补建）
│   ├── schemas/
│   │   └── note.py                    # [修改] 新增 OrganizeNotesRequest/Response Schema
│   ├── services/
│   │   ├── note_service.py            # [修改] 新增 organize_notes 方法
│   │   └── agent/                     # [新增] Agent 工具系统（Phase 3 补建 + Sprint 9 扩展）
│   │       ├── __init__.py
│   │       ├── tool_schemas.py        # [新增] 工具 Schema 定义
│   │       ├── tool_registry.py       # [新增] 工具注册表
│   │       ├── agent_loop.py          # [新增] ReAct 推理循环（Phase 3 补建）
│   │       ├── context_builder.py     # [新增] 上下文注入器（Phase 3 补建）
│   │       └── handlers/              # [新增] 工具处理器
│   │           ├── __init__.py
│   │           ├── note_handler.py    # [新增] 笔记工具（含 edit_note）
│   │           ├── learning_handler.py # [新增] 学习工具
│   │           ├── review_handler.py  # [新增] 复习工具
│   │           ├── search_handler.py  # [新增] 搜索工具
│   │           └── memory_handler.py  # [新增] 记忆工具
│   └── tasks/
│       └── note_tasks.py              # [新增] 笔记整理 Celery 任务
└── alembic/
    └── versions/
        └── 20260711_add_note_organize_fields.py  # [新增] 笔记 AI 整理字段迁移
```

---

## 3. 数据库变更

### 3.1 Note 模型扩展字段

为支持 AI 整理笔记的溯源需求，在 `notes` 表新增两个字段：

```python
# app/models/note.py — 扩展 Note 模型
# 在现有 Note 类中新增以下字段：

    # AI 整理溯源字段（Sprint 9）
    origin_type = Column(
        String(20),
        default="user",
        nullable=False,
        comment="来源类型: user(用户创建) / ai_organized(AI整理生成)",
    )
    source_note_ids = Column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
        comment="AI 整理时的源笔记 ID 列表（仅 origin_type=ai_organized 时有值）",
    )
```

### 3.2 Alembic 迁移脚本

```python
# alembic/versions/20260711_add_note_organize_fields.py

"""add note organize fields

Revision ID: 20260711_organize
Revises: 20260711_change_embedding_dim
Create Date: 2026-07-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "20260711_organize"
down_revision = "20260711_change_embedding_dim"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notes",
        sa.Column(
            "origin_type",
            sa.String(20),
            server_default="user",
            nullable=False,
            comment="来源类型: user / ai_organized",
        ),
    )
    op.add_column(
        "notes",
        sa.Column(
            "source_note_ids",
            ARRAY(UUID(as_uuid=True)),
            nullable=True,
            comment="AI 整理时的源笔记 ID 列表",
        ),
    )


def downgrade() -> None:
    op.drop_column("notes", "source_note_ids")
    op.drop_column("notes", "origin_type")
```

### 3.3 ORM 模型完整更新

```python
# app/models/note.py — 完整 Note 模型（Sprint 9 更新版）
# 仅展示完整字段列表，新增字段标注 [Sprint 9]

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.tag import NoteTag


class Note(Base):
    __tablename__ = "notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(500), nullable=False, default="无标题笔记")
    content = Column(Text, nullable=True, default="")
    content_json = Column(JSONB, nullable=True)
    subject = Column(String(100), nullable=True)
    route_id = Column(
        UUID(as_uuid=True),
        ForeignKey("learning_routes.id", ondelete="SET NULL"),
        nullable=True,
    )
    node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=True,
    )
    is_template = Column(Boolean, default=False, nullable=False)
    word_count = Column(Integer, default=0, nullable=False)

    # [Sprint 9] AI 整理溯源字段
    origin_type = Column(
        String(20),
        default="user",
        nullable=False,
        comment="来源类型: user / ai_organized",
    )
    source_note_ids = Column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
        comment="AI 整理时的源笔记 ID 列表",
    )

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    tags: Mapped[list["NoteTag"]] = relationship(
        "NoteTag", back_populates="note", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Note(id={self.id}, title='{self.title[:30]}')>"
```

---

## 4. Pydantic Schema

### 4.1 新增 Schema

```python
# app/schemas/note.py — Sprint 9 新增 Schema
# 在现有文件末尾追加

from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional
from enum import Enum


class OrganizeNotesRequest(BaseModel):
    """AI 整理笔记请求"""
    note_ids: list[UUID] = Field(
        ..., min_length=1, max_length=20,
        description="选中的笔记 ID 列表（1-20 篇）",
    )
    prompt: str = Field(
        default="",
        max_length=2000,
        description="额外提示词（整理方式/要求）",
    )


class OrganizeTaskStatus(str, Enum):
    """整理任务状态"""
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class OrganizeNotesResponse(BaseModel):
    """AI 整理笔记响应"""
    task_id: str = Field(..., description="Celery 任务 ID，用于 WS 进度监听")
    message: str = Field(default="笔记整理任务已提交")


class NoteSchema_Sprint9(BaseModel):
    """扩展的笔记输出 Schema — 新增 origin_type 和 source_note_ids 字段
    
    注意：实际使用时应直接修改现有 NoteSchema，
    在 NoteSchema 中新增 origin_type 和 source_note_ids 两个字段。
    此处单独列出仅为标注增量。
    """
    # ... 现有字段保持不变 ...
    origin_type: str = Field(default="user", description="来源类型: user / ai_organized")
    source_note_ids: Optional[list[UUID]] = Field(
        default=None, description="AI 整理时的源笔记 ID 列表"
    )
```

### 4.2 现有 Schema 修改指引

在现有 `app/schemas/note.py` 的 `NoteSchema` 类中新增两个字段：

```python
# 在 NoteSchema 中追加：
    origin_type: str = "user"
    source_note_ids: list[UUID] | None = None
```

---

## 5. 核心服务实现

### 5.1 AI 整理笔记 Prompt 模板

```python
# app/ai/prompts/note_organize.py

NOTE_ORGANIZE_SYSTEM_PROMPT = """你是一个专业的学习笔记整理专家。你的任务是根据用户的要求，将多篇笔记内容整合为一篇新的、结构清晰的 Markdown 笔记。

## 你的能力

你可以按用户要求进行多种方式的整理：
- **合并重组**：将多篇笔记的内容按主题/逻辑重新组织为一篇结构化笔记
- **摘要提炼**：提取各笔记核心要点，生成精简的摘要或大纲
- **对比分析**：对比多篇笔记的异同，生成对比表格或分析
- **知识扩展**：基于现有笔记内容进行知识补充和扩展
- **纠错优化**：修正笔记中的错误，优化表述和结构
- **自定义**：按照用户的具体指令灵活处理

## 输出要求

1. 输出格式必须为 Markdown
2. 首先输出新笔记的标题（以 `# ` 开头的单行）
3. 然后输出新笔记的完整正文内容
4. 标题和正文之间用空行分隔
5. 保持知识准确性，不要编造事实
6. 如果涉及公式，使用 LaTeX 语法（$...$ 行内，$$...$$ 块级）
7. 如果涉及代码，使用 Markdown 代码块并标注语言

## 注意事项

- 严格围绕用户指定的整理方式进行处理
- 如果用户没有指定具体方式，默认进行「合并重组 + 结构化整理」
- 保留原始笔记中的重要知识点和关键细节
- 消除重复内容，建立知识之间的逻辑关联
- 使用清晰的标题层级（## 二级标题起步，因为 # 用于笔记标题）"""

NOTE_ORGANIZE_USER_PROMPT = """请整理以下 {note_count} 篇笔记。

## 用户整理要求

{user_prompt}

## 选中的笔记内容

{notes_content}

---

请按照上述要求，输出整理后的新笔记。首先输出标题行（`# 标题`），然后输出正文。"""
```

### 5.2 AI 整理笔记 Service 扩展

```python
# app/services/note_service.py — Sprint 9 新增方法
# 在现有 NoteService 类中追加以下方法

import json
import redis
import structlog
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.note import Note
from app.models.tag import Tag, NoteTag
from app.core.utils import calculate_word_count, estimate_tokens, truncate_text
from app.ai.llm_client import get_llm_client
from app.ai.prompts.note_organize import (
    NOTE_ORGANIZE_SYSTEM_PROMPT,
    NOTE_ORGANIZE_USER_PROMPT,
)
from app.config import settings

logger = structlog.get_logger()

# 同步 Redis 客户端（用于 Celery 任务中发布进度）
_sync_redis: redis.Redis | None = None


def _get_sync_redis() -> redis.Redis:
    """获取同步 Redis 客户端（供 Celery 任务使用）"""
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = redis.Redis.from_url(
            settings.REDIS_URL, decode_responses=True
        )
    return _sync_redis


class NoteService:
    # ... 现有方法保持不变 ...

    # ==================== Sprint 9: AI 整理笔记 ====================

    @staticmethod
    async def organize_notes(
        db: AsyncSession,
        user_id: UUID,
        note_ids: list[UUID],
        prompt: str,
    ) -> str:
        """提交笔记整理任务到 Celery
        
        Args:
            db: 数据库会话
            user_id: 当前用户 ID
            note_ids: 选中的笔记 ID 列表
            prompt: 用户额外提示词
            
        Returns:
            Celery task_id
            
        Raises:
            BadRequestException: 笔记数量超限或笔记不存在
        """
        from app.tasks.note_tasks import organize_notes_task
        from app.core.exceptions import BadRequestException

        if len(note_ids) > 20:
            raise BadRequestException("单次最多整理 20 篇笔记")

        # 验证所有笔记属于当前用户
        stmt = (
            select(Note)
            .where(Note.id.in_(note_ids), Note.user_id == user_id)
            .options(selectinload(Note.tags))
        )
        result = await db.execute(stmt)
        notes = result.scalars().all()

        if len(notes) != len(note_ids):
            found_ids = {n.id for n in notes}
            missing_ids = set(note_ids) - found_ids
            raise BadRequestException(
                f"以下笔记不存在或无权访问: {', '.join(str(id) for id in missing_ids)}"
            )

        # 构建笔记摘要列表（传入任务）
        notes_data = []
        for note in notes:
            tag_names = [t.tag.name for t in note.tags if t.tag]
            notes_data.append({
                "id": str(note.id),
                "title": note.title,
                "content": note.content or "",
                "subject": note.subject,
                "tags": tag_names,
                "word_count": note.word_count,
            })

        # 提交 Celery 异步任务
        task = organize_notes_task.delay(
            user_id_str=str(user_id),
            notes_data_json=json.dumps(notes_data, ensure_ascii=False),
            prompt=prompt,
        )

        logger.info(
            "note_organize_task_submitted",
            user_id=str(user_id),
            task_id=task.id,
            note_count=len(notes),
        )

        return task.id

    @staticmethod
    async def create_organized_note(
        db: AsyncSession,
        user_id: UUID,
        title: str,
        content: str,
        source_note_ids: list[UUID],
    ) -> Note:
        """创建 AI 整理后的成果笔记
        
        Args:
            db: 数据库会话
            user_id: 用户 ID
            title: 笔记标题（由 LLM 生成）
            content: 笔记内容（由 LLM 生成）
            source_note_ids: 源笔记 ID 列表
            
        Returns:
            新创建的 Note 实例
        """
        word_count = calculate_word_count(content)

        note = Note(
            user_id=user_id,
            title=title,
            content=content,
            word_count=word_count,
            origin_type="ai_organized",
            source_note_ids=source_note_ids,
        )
        db.add(note)
        await db.commit()
        await db.refresh(note)

        # 同步到 Meilisearch
        try:
            from app.services.search_service import SearchService
            await SearchService.index_note(db, note)
        except Exception as e:
            logger.warning("organize_note_meilisearch_sync_failed", error=str(e))

        logger.info(
            "organized_note_created",
            note_id=str(note.id),
            user_id=str(user_id),
            source_count=len(source_note_ids),
            word_count=word_count,
        )

        return note
```

### 5.3 AI 整理笔记 Celery 任务

```python
# app/tasks/note_tasks.py — [新增文件]

"""笔记相关 Celery 异步任务"""

import json
import uuid
import redis
from datetime import datetime

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
        r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
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
    self: "organize_notes_task",
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
        user_id_str: 用户 ID（字符串，JSON 序列化友好）
        notes_data_json: 笔记数据 JSON 数组
        prompt: 用户额外提示词
        
    Returns:
        {"note_id": str, "title": str, "word_count": int}
    """
    import asyncio
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

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

        from app.ai.llm_client import get_llm_client
        from app.ai.prompts.note_organize import (
            NOTE_ORGANIZE_SYSTEM_PROMPT,
            NOTE_ORGANIZE_USER_PROMPT,
        )

        user_prompt_text = prompt if prompt.strip() else "请将这多篇笔记合并整理为一篇结构清晰、逻辑连贯的笔记。"

        user_message = NOTE_ORGANIZE_USER_PROMPT.format(
            note_count=note_count,
            user_prompt=user_prompt_text,
            notes_content=notes_content,
        )

        # 在 Celery worker 中使用新事件循环
        loop = asyncio.new_event_loop()
        try:
            llm_client = get_llm_client()
            response = loop.run_until_complete(
                llm_client.chat(
                    messages=[
                        {"role": "system", "content": NOTE_ORGANIZE_SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.7,
                    max_tokens=4096,
                )
            )
        finally:
            loop.close()

        llm_output = response.content.strip()

        # ---- 阶段 3: 解析输出 ----
        _publish_organize_progress(task_id, {
            "stage": "saving",
            "percent": 80,
            "message": "正在保存整理结果...",
        })

        # 解析标题和正文
        # 期望格式: # 标题\n\n正文内容
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
            content = llm_output  # fallback: 全部作为正文

        # ---- 阶段 4: 创建成果笔记 ----
        # 在 Celery worker 中初始化 DB
        from app.database import Base

        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
        )
        async_session_factory = async_sessionmaker(
            engine, expire_on_commit=False
        )

        async def _create_note():
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
                    from app.services.search_service import SearchService
                    await SearchService.index_note(session, note)
                except Exception as e:
                    logger.warning("meilisearch_sync_failed_in_task", error=str(e))

                return note.id, note.title, note.word_count

        note_id, final_title, word_count = run_async(_create_note())

        await engine.dispose()

        # ---- 阶段 5: 推送完成通知 ----
        _publish_organize_progress(task_id, {
            "stage": "complete",
            "percent": 100,
            "message": "整理完成！",
            "note_id": str(note_id),
            "title": final_title,
            "word_count": word_count,
            "source_count": note_count,
        })

        logger.info(
            "organize_notes_task_completed",
            task_id=task_id,
            note_id=str(note_id),
            title=final_title,
            word_count=word_count,
        )

        return {
            "note_id": str(note_id),
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
```

### 5.4 AI 修改笔记 Agent 工具

#### 5.4.1 工具基础设施（Phase 3 补建）

由于 Phase 3 Agent 工具系统的源码文件尚未创建，以下先补建基础设施，再实现 Sprint 9 的 `edit_note` 工具。

```python
# app/services/agent/__init__.py — [新增文件]

"""Agent 工具系统"""
```

```python
# app/services/agent/tool_schemas.py — [新增文件]

"""Agent 工具 Schema 定义

定义工具参数、返回值和元数据的基础数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolCategory(str, Enum):
    """工具类别"""
    READ = "read"
    WRITE = "write"


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str  # "string" | "integer" | "number" | "boolean" | "array" | "object"
    description: str
    required: bool = True
    enum: list[str] | None = None
    default: Any = None
    items_type: str | None = None  # array 类型时元素类型


@dataclass
class ToolSchema:
    """工具 Schema — 描述一个 Agent 可调用的工具"""
    name: str
    display_name: str
    description: str
    parameters: list[ToolParameter]
    category: ToolCategory
    module: str  # 所属模块: "note" | "learning" | "qa" | "review" | "search" | "memory"
    icon: str = "tool"  # 前端图标


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any = None
    error_message: str | None = None
    token_count: int = 0

    @classmethod
    def ok(cls, data: Any, token_count: int = 0) -> ToolResult:
        return cls(success=True, data=data, token_count=token_count)

    @classmethod
    def fail(cls, error_message: str) -> ToolResult:
        return cls(success=False, error_message=error_message)
```

```python
# app/services/agent/tool_registry.py — [新增文件]

"""Agent 工具注册表

管理所有 Agent 可调用的工具，提供注册、查询、执行能力。
"""

from __future__ import annotations

import structlog
from typing import Any, Callable, Awaitable
from uuid import UUID

from app.services.agent.tool_schemas import ToolSchema, ToolResult, ToolCategory

logger = structlog.get_logger()

# 工具处理器类型：async function(params: dict, db: AsyncSession, user_id: UUID, **kwargs) -> ToolResult
ToolHandler = Callable[..., Awaitable[ToolResult]]


class ToolRegistry:
    """工具注册表 — 单例模式"""

    _instance: ToolRegistry | None = None
    _tools: dict[str, tuple[ToolSchema, ToolHandler]] = {}

    def __new__(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    def register(self, schema: ToolSchema, handler: ToolHandler) -> None:
        """注册工具"""
        self._tools[schema.name] = (schema, handler)
        logger.info("tool_registered", tool_name=schema.name, module=schema.module)

    def get_schema(self, name: str) -> ToolSchema | None:
        """获取工具 Schema"""
        entry = self._tools.get(name)
        return entry[0] if entry else None

    def get_all_schemas(self) -> list[ToolSchema]:
        """获取所有工具 Schema"""
        return [schema for schema, _ in self._tools.values()]

    def get_schemas_by_category(self, category: ToolCategory) -> list[ToolSchema]:
        """按类别获取工具 Schema"""
        return [
            schema
            for schema, _ in self._tools.values()
            if schema.category == category
        ]

    async def execute(
        self,
        tool_name: str,
        params: dict[str, Any],
        db: Any,
        user_id: UUID,
        **kwargs: Any,
    ) -> ToolResult:
        """执行工具
        
        Args:
            tool_name: 工具名称
            params: 工具参数
            db: 数据库会话
            user_id: 当前用户 ID
            **kwargs: 额外参数（如 ws_manager 用于 WebSocket 推送）
            
        Returns:
            ToolResult
        """
        entry = self._tools.get(tool_name)
        if entry is None:
            return ToolResult.fail(f"未知工具: {tool_name}")

        schema, handler = entry

        try:
            result = await handler(params=params, db=db, user_id=user_id, **kwargs)
            logger.info(
                "tool_executed",
                tool_name=tool_name,
                success=result.success,
            )
            return result
        except Exception as e:
            logger.error(
                "tool_execution_failed",
                tool_name=tool_name,
                error=str(e),
                exc_info=True,
            )
            return ToolResult.fail(f"工具执行失败: {str(e)}")


def get_tool_registry() -> ToolRegistry:
    """获取工具注册表单例"""
    return ToolRegistry()
```

#### 5.4.2 edit_note 工具 Handler

```python
# app/services/agent/handlers/__init__.py — [新增文件]

"""Agent 工具处理器"""
```

```python
# app/services/agent/handlers/note_handler.py — [新增文件]

"""笔记相关 Agent 工具处理器

包含:
- search_notes: 搜索笔记
- get_note_content: 获取笔记内容
- edit_note: 编辑笔记（Sprint 9 新增）
"""

from __future__ import annotations

import structlog
from typing import Any
from uuid import UUID

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.note import Note
from app.models.tag import NoteTag
from app.services.agent.tool_schemas import ToolResult
from app.core.utils import calculate_word_count, truncate_text

logger = structlog.get_logger()


async def search_notes_handler(
    params: dict[str, Any],
    db: AsyncSession,
    user_id: UUID,
    **kwargs: Any,
) -> ToolResult:
    """搜索笔记"""
    query = params.get("query", "")
    limit = min(params.get("limit", 10), 20)

    stmt = (
        select(Note)
        .where(Note.user_id == user_id)
        .options(selectinload(Note.tags))
    )

    if query:
        search_filter = or_(
            Note.title.ilike(f"%{query}%"),
            Note.content.ilike(f"%{query}%"),
        )
        stmt = stmt.where(search_filter)

    stmt = stmt.order_by(Note.updated_at.desc()).limit(limit)
    result = await db.execute(stmt)
    notes = result.scalars().all()

    if not notes:
        return ToolResult.ok(data={"message": "未找到匹配的笔记", "notes": []})

    notes_list = []
    for note in notes:
        tags = [t.tag.name for t in note.tags if t.tag]
        notes_list.append({
            "id": str(note.id),
            "title": note.title,
            "subject": note.subject,
            "tags": tags,
            "summary": truncate_text(note.content or "", 200),
            "word_count": note.word_count,
            "updated_at": note.updated_at.isoformat() if note.updated_at else None,
        })

    return ToolResult.ok(data={
        "message": f"找到 {len(notes_list)} 篇笔记",
        "notes": notes_list,
    })


async def get_note_content_handler(
    params: dict[str, Any],
    db: AsyncSession,
    user_id: UUID,
    **kwargs: Any,
) -> ToolResult:
    """获取笔记完整内容"""
    note_id = params.get("note_id")
    if not note_id:
        return ToolResult.fail("缺少参数: note_id")

    try:
        note_uuid = UUID(note_id) if isinstance(note_id, str) else note_id
    except ValueError:
        return ToolResult.fail(f"无效的笔记 ID: {note_id}")

    stmt = (
        select(Note)
        .where(Note.id == note_uuid, Note.user_id == user_id)
        .options(selectinload(Note.tags))
    )
    result = await db.execute(stmt)
    note = result.scalar_one_or_none()

    if not note:
        return ToolResult.fail(f"笔记不存在或无权访问: {note_id}")

    tags = [t.tag.name for t in note.tags if t.tag]
    total_lines = len((note.content or "").split("\n"))

    return ToolResult.ok(data={
        "id": str(note.id),
        "title": note.title,
        "content": note.content or "",
        "subject": note.subject,
        "tags": tags,
        "word_count": note.word_count,
        "total_lines": total_lines,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    })


async def edit_note_handler(
    params: dict[str, Any],
    db: AsyncSession,
    user_id: UUID,
    **kwargs: Any,
) -> ToolResult:
    """编辑笔记 — 支持行号级别的局部编辑

    操作类型:
    - insert: 在 start_line 行之前插入 content
    - replace: 替换 start_line 到 end_line（含）的内容为 content
    - delete: 删除 start_line 到 end_line（含）的内容

    行号规则:
    - 1-based（第一行 = 1）
    - insert 时 end_line 忽略
    - start_line 超出范围时: insert 追加到末尾，replace/delete 返回错误
    """
    from app.services.search_service import SearchService

    # ---- 参数解析 ----
    note_id = params.get("note_id")
    operation = params.get("operation")
    start_line = params.get("start_line")
    end_line = params.get("end_line")
    content = params.get("content", "")

    if not note_id or not operation or start_line is None:
        return ToolResult.fail("缺少必填参数: note_id, operation, start_line")

    if operation not in ("insert", "replace", "delete"):
        return ToolResult.fail(f"无效操作: {operation}，可选: insert, replace, delete")

    if operation in ("replace", "delete") and end_line is None:
        return ToolResult.fail(f"操作 {operation} 需要提供 end_line 参数")

    try:
        note_uuid = UUID(note_id) if isinstance(note_id, str) else note_id
    except ValueError:
        return ToolResult.fail(f"无效的笔记 ID: {note_id}")

    # ---- 查询笔记 ----
    stmt = select(Note).where(Note.id == note_uuid, Note.user_id == user_id)
    result = await db.execute(stmt)
    note = result.scalar_one_or_none()

    if not note:
        return ToolResult.fail(f"笔记不存在或无权访问: {note_id}")

    # ---- 执行编辑 ----
    original_content = note.content or ""
    lines = original_content.split("\n") if original_content else [""]
    total_lines = len(lines)

    # 校验行号范围
    if start_line < 1:
        return ToolResult.fail(f"start_line 必须 >= 1，当前值: {start_line}")

    if operation == "insert":
        # insert: 在 start_line 之前插入
        # start_line 可以 = total_lines + 1（追加到末尾）
        insert_idx = min(start_line - 1, total_lines)
        new_lines = content.split("\n") if content else []
        lines = lines[:insert_idx] + new_lines + lines[insert_idx:]

    elif operation == "replace":
        if end_line is None or end_line < start_line:
            return ToolResult.fail(
                f"end_line 必须 >= start_line，当前: start={start_line}, end={end_line}"
            )
        if start_line > total_lines:
            return ToolResult.fail(
                f"start_line ({start_line}) 超出范围（共 {total_lines} 行）"
            )
        start_idx = start_line - 1
        end_idx = min(end_line, total_lines)  # end_line 是 inclusive，切片需要 exclusive
        new_lines = content.split("\n") if content else []
        lines = lines[:start_idx] + new_lines + lines[end_idx:]

    elif operation == "delete":
        if end_line is None or end_line < start_line:
            return ToolResult.fail(
                f"end_line 必须 >= start_line，当前: start={start_line}, end={end_line}"
            )
        if start_line > total_lines:
            return ToolResult.fail(
                f"start_line ({start_line}) 超出范围（共 {total_lines} 行）"
            )
        start_idx = start_line - 1
        end_idx = min(end_line, total_lines)
        lines = lines[:start_idx] + lines[end_idx:]

    # ---- 保存 ----
    new_content = "\n".join(lines)
    note.content = new_content
    note.word_count = calculate_word_count(new_content)
    await db.commit()
    await db.refresh(note)

    # 同步到 Meilisearch
    try:
        await SearchService.index_note(db, note)
    except Exception as e:
        logger.warning("edit_note_meilisearch_sync_failed", note_id=str(note.id), error=str(e))

    # ---- WebSocket 推送编辑通知 ----
    ws_manager = kwargs.get("ws_manager")
    if ws_manager:
        client_id = f"user_{user_id}"
        await ws_manager.send_json(client_id, {
            "type": "note_edit",
            "data": {
                "note_id": str(note.id),
                "operation": operation,
                "start_line": start_line,
                "end_line": end_line,
                "content": content,
                "new_content": new_content,  # 完整新内容，前端可直接替换
                "title": note.title,
                "word_count": note.word_count,
            },
        })

    # 构造操作描述（返回给 LLM）
    operation_desc = {
        "insert": f"在第 {start_line} 行前插入了 {len(content.split(chr(10)))} 行",
        "replace": f"替换了第 {start_line}-{end_line} 行为 {len(content.split(chr(10)))} 行新内容",
        "delete": f"删除了第 {start_line}-{end_line} 行",
    }

    logger.info(
        "note_edited_by_agent",
        note_id=str(note.id),
        user_id=str(user_id),
        operation=operation,
        start_line=start_line,
        end_line=end_line,
    )

    return ToolResult.ok(data={
        "message": f"笔记「{note.title}」修改成功: {operation_desc[operation]}",
        "note_id": str(note.id),
        "operation": operation,
        "new_total_lines": len(lines),
        "new_word_count": note.word_count,
    })
```

#### 5.4.3 其他工具 Handler（Phase 3 补建，摘要列出）

以下 Handler 文件需补建，实现逻辑参考 Phase 3 进度文档描述。此处列出文件骨架和注册入口：

```python
# app/services/agent/handlers/learning_handler.py — [新增文件]

"""学习模块 Agent 工具处理器

包含:
- search_knowledge: 搜索知识图谱
- get_mastery: 获取知识掌握度
- get_route_progress: 获取路线进度
"""

from __future__ import annotations
from typing import Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.agent.tool_schemas import ToolResult


async def search_knowledge_handler(
    params: dict[str, Any], db: AsyncSession, user_id: UUID, **kwargs: Any,
) -> ToolResult:
    """搜索知识图谱节点"""
    # 实现参考 Phase 3 进度文档 §3.1 工具清单
    # 查询 knowledge_nodes 表，按 name/description 模糊搜索
    ...


async def get_mastery_handler(
    params: dict[str, Any], db: AsyncSession, user_id: UUID, **kwargs: Any,
) -> ToolResult:
    """获取知识掌握度"""
    ...


async def get_route_progress_handler(
    params: dict[str, Any], db: AsyncSession, user_id: UUID, **kwargs: Any,
) -> ToolResult:
    """获取路线进度"""
    ...
```

```python
# app/services/agent/handlers/review_handler.py — [新增文件]

"""复习模块 Agent 工具处理器

包含:
- get_review_status: 获取复习状态
- schedule_review: 安排复习计划
"""

from __future__ import annotations
from typing import Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.agent.tool_schemas import ToolResult


async def get_review_status_handler(
    params: dict[str, Any], db: AsyncSession, user_id: UUID, **kwargs: Any,
) -> ToolResult:
    """获取复习状态"""
    ...


async def schedule_review_handler(
    params: dict[str, Any], db: AsyncSession, user_id: UUID, **kwargs: Any,
) -> ToolResult:
    """安排复习计划"""
    ...
```

```python
# app/services/agent/handlers/search_handler.py — [新增文件]

"""搜索模块 Agent 工具处理器

包含:
- global_search: 全局搜索
- semantic_search: 语义搜索
"""

from __future__ import annotations
from typing import Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.agent.tool_schemas import ToolResult


async def global_search_handler(
    params: dict[str, Any], db: AsyncSession, user_id: UUID, **kwargs: Any,
) -> ToolResult:
    """全局搜索（笔记/讲义/知识点/路线）"""
    ...


async def semantic_search_handler(
    params: dict[str, Any], db: AsyncSession, user_id: UUID, **kwargs: Any,
) -> ToolResult:
    """语义相似度搜索"""
    ...
```

```python
# app/services/agent/handlers/memory_handler.py — [新增文件]

"""记忆模块 Agent 工具处理器

包含:
- recall_knowledge: 回忆知识点
- search_memory: 搜索记忆
"""

from __future__ import annotations
from typing import Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.agent.tool_schemas import ToolResult


async def recall_knowledge_handler(
    params: dict[str, Any], db: AsyncSession, user_id: UUID, **kwargs: Any,
) -> ToolResult:
    """回忆知识点"""
    ...


async def search_memory_handler(
    params: dict[str, Any], db: AsyncSession, user_id: UUID, **kwargs: Any,
) -> ToolResult:
    """搜索记忆"""
    ...
```

#### 5.4.4 工具注册入口

```python
# app/services/agent/register_tools.py — [新增文件]

"""注册所有 Agent 工具到 ToolRegistry

应用启动时调用 init_tool_registry() 完成注册。
"""

import structlog
from app.services.agent.tool_schemas import ToolSchema, ToolParameter, ToolCategory
from app.services.agent.tool_registry import get_tool_registry

from app.services.agent.handlers.note_handler import (
    search_notes_handler,
    get_note_content_handler,
    edit_note_handler,
)
from app.services.agent.handlers.learning_handler import (
    search_knowledge_handler,
    get_mastery_handler,
    get_route_progress_handler,
)
from app.services.agent.handlers.review_handler import (
    get_review_status_handler,
    schedule_review_handler,
)
from app.services.agent.handlers.search_handler import (
    global_search_handler,
    semantic_search_handler,
)
from app.services.agent.handlers.memory_handler import (
    recall_knowledge_handler,
    search_memory_handler,
)

logger = structlog.get_logger()


def init_tool_registry() -> None:
    """初始化并注册所有 Agent 工具"""
    registry = get_tool_registry()

    # ========== 笔记模块 (note) ==========

    registry.register(
        schema=ToolSchema(
            name="search_notes",
            display_name="搜索笔记",
            description="根据关键词搜索用户的笔记，返回匹配笔记的标题、摘要和标签",
            parameters=[
                ToolParameter(
                    name="query", type="string",
                    description="搜索关键词", required=True,
                ),
                ToolParameter(
                    name="limit", type="integer",
                    description="返回数量上限（默认 10，最大 20）",
                    required=False, default=10,
                ),
            ],
            category=ToolCategory.READ,
            module="note",
            icon="FileSearch",
        ),
        handler=search_notes_handler,
    )

    registry.register(
        schema=ToolSchema(
            name="get_note_content",
            display_name="获取笔记内容",
            description="获取指定笔记的完整内容，返回 Markdown 格式文本和总行数",
            parameters=[
                ToolParameter(
                    name="note_id", type="string",
                    description="笔记 ID", required=True,
                ),
            ],
            category=ToolCategory.READ,
            module="note",
            icon="FileText",
        ),
        handler=get_note_content_handler,
    )

    # [Sprint 9] edit_note 工具
    registry.register(
        schema=ToolSchema(
            name="edit_note",
            display_name="编辑笔记",
            description=(
                "对指定笔记进行局部编辑。支持三种操作：\n"
                "- insert: 在指定行号前插入新内容\n"
                "- replace: 替换指定行号范围的内容\n"
                "- delete: 删除指定行号范围的内容\n"
                "行号为 1-based（第一行 = 1）。修改会实时推送到用户前端编辑器。"
            ),
            parameters=[
                ToolParameter(
                    name="note_id", type="string",
                    description="要修改的笔记 ID", required=True,
                ),
                ToolParameter(
                    name="operation", type="string",
                    description="操作类型: insert(插入), replace(替换), delete(删除)",
                    required=True, enum=["insert", "replace", "delete"],
                ),
                ToolParameter(
                    name="start_line", type="integer",
                    description="起始行号（1-based，第一行=1）", required=True,
                ),
                ToolParameter(
                    name="end_line", type="integer",
                    description="结束行号（1-based，含。replace/delete 时必填，insert 时忽略）",
                    required=False,
                ),
                ToolParameter(
                    name="content", type="string",
                    description="新内容（insert/replace 时必填，delete 时忽略）",
                    required=False,
                ),
            ],
            category=ToolCategory.WRITE,
            module="note",
            icon="FileEdit",
        ),
        handler=edit_note_handler,
    )

    # ========== 学习模块 (learning) ==========

    registry.register(
        schema=ToolSchema(
            name="search_knowledge",
            display_name="搜索知识图谱",
            description="搜索知识图谱中的知识点，返回匹配的知识节点列表",
            parameters=[
                ToolParameter(
                    name="query", type="string",
                    description="搜索关键词", required=True,
                ),
                ToolParameter(
                    name="subject", type="string",
                    description="按学科筛选", required=False,
                ),
            ],
            category=ToolCategory.READ,
            module="learning",
            icon="Network",
        ),
        handler=search_knowledge_handler,
    )

    registry.register(
        schema=ToolSchema(
            name="get_mastery",
            display_name="获取知识掌握度",
            description="获取用户对指定知识点的掌握度分数（0-1）",
            parameters=[
                ToolParameter(
                    name="node_id", type="string",
                    description="知识节点 ID", required=True,
                ),
            ],
            category=ToolCategory.READ,
            module="learning",
            icon="Gauge",
        ),
        handler=get_mastery_handler,
    )

    registry.register(
        schema=ToolSchema(
            name="get_route_progress",
            display_name="获取路线进度",
            description="获取指定学习路线的步骤列表和完成进度",
            parameters=[
                ToolParameter(
                    name="route_id", type="string",
                    description="学习路线 ID", required=True,
                ),
            ],
            category=ToolCategory.READ,
            module="learning",
            icon="Map",
        ),
        handler=get_route_progress_handler,
    )

    # ========== 复习模块 (review) ==========

    registry.register(
        schema=ToolSchema(
            name="get_review_status",
            display_name="获取复习状态",
            description="获取用户的复习计划状态，包括待复习数量、逾期数量等",
            parameters=[],
            category=ToolCategory.READ,
            module="review",
            icon="CalendarClock",
        ),
        handler=get_review_status_handler,
    )

    registry.register(
        schema=ToolSchema(
            name="schedule_review",
            display_name="安排复习计划",
            description="为指定知识点创建或更新复习计划",
            parameters=[
                ToolParameter(
                    name="node_id", type="string",
                    description="知识节点 ID", required=True,
                ),
                ToolParameter(
                    name="review_date", type="string",
                    description="计划复习日期（ISO 格式，如 2026-07-15）",
                    required=False,
                ),
            ],
            category=ToolCategory.WRITE,
            module="review",
            icon="CalendarPlus",
        ),
        handler=schedule_review_handler,
    )

    # ========== 搜索模块 (search) ==========

    registry.register(
        schema=ToolSchema(
            name="global_search",
            display_name="全局搜索",
            description="跨类型搜索（笔记/讲义/知识点/路线），返回匹配结果",
            parameters=[
                ToolParameter(
                    name="query", type="string",
                    description="搜索关键词", required=True,
                ),
                ToolParameter(
                    name="type", type="string",
                    description="搜索类型: all/notes/lectures/knowledge/routes",
                    required=False, default="all",
                    enum=["all", "notes", "lectures", "knowledge", "routes"],
                ),
            ],
            category=ToolCategory.READ,
            module="search",
            icon="Search",
        ),
        handler=global_search_handler,
    )

    registry.register(
        schema=ToolSchema(
            name="semantic_search",
            display_name="语义搜索",
            description="基于语义相似度的智能搜索，适合模糊概念查找",
            parameters=[
                ToolParameter(
                    name="query", type="string",
                    description="搜索查询（自然语言描述）", required=True,
                ),
            ],
            category=ToolCategory.READ,
            module="search",
            icon="Sparkles",
        ),
        handler=semantic_search_handler,
    )

    # ========== 记忆模块 (memory) ==========

    registry.register(
        schema=ToolSchema(
            name="recall_knowledge",
            display_name="回忆知识点",
            description="回忆指定知识点的详细信息，包括描述、关联和掌握度",
            parameters=[
                ToolParameter(
                    name="node_id", type="string",
                    description="知识节点 ID", required=True,
                ),
            ],
            category=ToolCategory.READ,
            module="memory",
            icon="Brain",
        ),
        handler=recall_knowledge_handler,
    )

    registry.register(
        schema=ToolSchema(
            name="search_memory",
            display_name="搜索记忆",
            description="搜索用户的学习记忆和历史记录",
            parameters=[
                ToolParameter(
                    name="query", type="string",
                    description="搜索关键词", required=True,
                ),
            ],
            category=ToolCategory.READ,
            module="memory",
            icon="Database",
        ),
        handler=search_memory_handler,
    )

    total = len(registry.get_all_schemas())
    logger.info("tool_registry_initialized", total_tools=total)
```

### 5.5 AgentLoop 中 edit_note 的集成要点

AgentLoop 在执行工具调用时，需将 `ConnectionManager` 传入工具的 `**kwargs`，以便 `edit_note_handler` 推送 WebSocket 消息。

```python
# app/services/agent/agent_loop.py — 工具执行片段（关键代码）

# 在 AgentLoop.run() 方法中，工具执行调用：
result = await registry.execute(
    tool_name=tool_name,
    params=tool_params,
    db=db_session,
    user_id=user_id,
    ws_manager=connection_manager,  # 传入 ConnectionManager
)

# 对于 category="write" 的工具，每轮限调 1 次
# 已有逻辑: write_tools_this_round.add(tool_name)
```

---

## 6. API 路由

### 6.1 AI 整理笔记端点

```python
# app/api/v1/notes.py — Sprint 9 新增端点
# 在现有文件末尾（batch-delete 之后）追加

from app.schemas.note import OrganizeNotesRequest, OrganizeNotesResponse


@router.post("/organize", response_model=OrganizeNotesResponse)
async def organize_notes(
    request: OrganizeNotesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 整理笔记

    将选中的多篇笔记提交给 AI 进行整理，生成一篇新的成果笔记。
    整理方式由 prompt 参数驱动（合并/摘要/对比/扩展等）。
    异步处理，通过 WebSocket 监听进度。
    """
    task_id = await NoteService.organize_notes(
        db=db,
        user_id=current_user.id,
        note_ids=request.note_ids,
        prompt=request.prompt,
    )
    return OrganizeNotesResponse(
        task_id=task_id,
        message=f"笔记整理任务已提交，共 {len(request.note_ids)} 篇笔记",
    )
```

**注意**：`/organize` 端点必须在 `/{note_id}` 端点之前注册，否则 FastAPI 会将 "organize" 解析为 note_id 路径参数。如果现有路由中 `/{note_id}` 在前，需要调整顺序。

```python
# 路由注册顺序检查：
# 现有顺序（可能的问题）：
#   GET    /{note_id}   ← 会先匹配 "organize"
#   PUT    /{note_id}
#   DELETE /{note_id}
#   POST   /batch-delete
#
# 修改后顺序：
#   POST   /batch-delete
#   POST   /organize        ← 新增，放在 /{note_id} 之前
#   GET    /{note_id}
#   PUT    /{note_id}
#   DELETE /{note_id}
```

### 6.2 Agent 工具列表端点（Phase 3 补建）

```python
# app/api/v1/agent.py — [新增文件]
# Phase 3 补建，包含 Sprint 9 的 edit_note 工具

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.agent.tool_registry import get_tool_registry

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.get("/tools")
async def list_tools(
    current_user: User = Depends(get_current_user),
):
    """获取 Agent 可用工具列表"""
    registry = get_tool_registry()
    tools = registry.get_all_schemas()
    return {
        "tools": [
            {
                "name": t.name,
                "display_name": t.display_name,
                "description": t.description,
                "category": t.category.value,
                "module": t.module,
                "icon": t.icon,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "required": p.required,
                        "enum": p.enum,
                        "default": p.default,
                    }
                    for p in t.parameters
                ],
            }
            for t in tools
        ]
    }
```

---

## 7. WebSocket 端点

### 7.1 AI 整理笔记进度推送

```python
# app/api/v1/websocket.py — Sprint 9 新增端点
# 在现有文件中追加

import json
import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.config import settings
from app.core.security import decode_token

import structlog

logger = structlog.get_logger()

router = APIRouter()


@router.websocket("/ws/organize-progress/{task_id}")
async def organize_progress_ws(
    websocket: WebSocket,
    task_id: str,
    token: str = Query(...),
):
    """AI 整理笔记进度 WebSocket

    客户端连接后订阅 Redis Pub/Sub 频道 organize_progress:{task_id}，
    实时接收 Celery 任务推送的进度消息。

    消息格式:
    {
        "stage": "preparing" | "generating" | "saving" | "complete" | "error",
        "percent": 0-100,
        "message": "进度描述",
        "note_id": "成果笔记 ID（仅 complete 时）",
        "title": "笔记标题（仅 complete 时）",
        "word_count": 字数（仅 complete 时）,
        "source_count": 源笔记数（仅 complete 时）,
        "error": "错误信息（仅 error 时）"
    }

    进度阶段:
    | 阶段       | 百分比 | 说明                          |
    |------------|--------|-------------------------------|
    | preparing  | 10%    | 准备笔记内容                   |
    | generating | 30%    | AI 正在整理                    |
    | saving     | 80%    | 保存整理结果                   |
    | complete   | 100%   | 完成，携带成果笔记信息          |
    | error      | -      | 失败，携带错误信息              |
    """
    # Token 验证
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=4001, reason="Token verification failed")
        return

    await websocket.accept()

    # 订阅 Redis Pub/Sub
    redis_client = aioredis.Redis.from_url(
        settings.REDIS_URL, decode_responses=True
    )
    pubsub = redis_client.pubsub()
    channel = f"organize_progress:{task_id}"

    try:
        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)

                # 完成或失败时关闭连接
                if data.get("stage") in ("complete", "error"):
                    break

    except WebSocketDisconnect:
        logger.info("organize_progress_ws_disconnected", task_id=task_id)
    except Exception as e:
        logger.error("organize_progress_ws_error", task_id=task_id, error=str(e))
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await redis_client.close()
        except Exception:
            pass
```

### 7.2 AI 修改笔记通知推送（复用现有通知 WS）

`edit_note` 工具执行后，通过现有的 `/ws/notifications` 端点推送 `note_edit` 类型消息。无需新增 WebSocket 端点。

**消息格式**（通过 `/ws/notifications` 推送）：

```json
{
    "type": "note_edit",
    "data": {
        "note_id": "uuid-string",
        "operation": "insert | replace | delete",
        "start_line": 5,
        "end_line": 8,
        "content": "新插入/替换的内容",
        "new_content": "编辑后的完整笔记内容",
        "title": "笔记标题",
        "word_count": 1234
    }
}
```

**前端处理逻辑**：

1. 监听 `/ws/notifications` 的 `note_edit` 消息
2. 检查 `note_id` 是否匹配当前打开的笔记
3. 如果匹配，用 `new_content` 替换编辑器内容（Tiptap `editor.commands.setContent()`）
4. 更新同步状态为 "AI 已修改"
5. 用户可通过 Ctrl+Z 撤销（Tiptap 历史记录）

---

## 8. 路由注册更新

### 8.1 router.py 更新

```python
# app/api/v1/router.py — 更新版

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.notes import router as notes_router
from app.api.v1.tags import router as tags_router
from app.api.v1.learning import router as learning_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.websocket import router as websocket_router
from app.api.v1.qa import router as qa_router
from app.api.v1.review import router as review_router
from app.api.v1.search import router as search_router      # Phase 3
from app.api.v1.agent import router as agent_router         # Phase 3 + Sprint 9

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(notes_router, prefix="/notes", tags=["笔记"])
api_router.include_router(tags_router, prefix="/tags", tags=["标签"])
api_router.include_router(learning_router, prefix="/learning", tags=["学习"])
api_router.include_router(knowledge_router, prefix="/knowledge", tags=["知识图谱"])
api_router.include_router(qa_router, tags=["答疑"])
api_router.include_router(review_router, prefix="/review", tags=["复习"])
api_router.include_router(search_router, prefix="/search", tags=["搜索"])
api_router.include_router(agent_router, tags=["Agent"])     # Phase 3 + Sprint 9
api_router.include_router(websocket_router)                 # WebSocket 端点
```

### 8.2 main.py 工具注册初始化

```python
# app/main.py — lifespan 中新增工具注册

from app.services.agent.register_tools import init_tool_registry

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... 现有初始化逻辑 ...

    # [Sprint 9] 初始化 Agent 工具注册表
    init_tool_registry()

    # ... 现有 Meilisearch 初始化等 ...

    yield
```

### 8.3 Celery include 更新

```python
# app/tasks/celery_app.py — 更新 include 列表

celery_app = Celery(
    "qingyun",
    include=[
        "app.tasks.learning_tasks",
        "app.tasks.review_tasks",
        "app.tasks.note_tasks",       # [Sprint 9] 新增
    ],
)
```

---

## 9. 配置更新

```python
# app/config.py — Sprint 9 新增配置项

class Settings(BaseSettings):
    # ... 现有配置 ...

    # [Sprint 9] AI 整理笔记配置
    ORGANIZE_MAX_NOTES: int = 20           # 单次整理最大笔记数
    ORGANIZE_MAX_PROMPT_LENGTH: int = 2000 # 提示词最大长度
    ORGANIZE_LLM_TEMPERATURE: float = 0.7  # LLM 温度参数
    ORGANIZE_LLM_MAX_TOKENS: int = 4096    # LLM 最大 token 输出
```

---

## 10. 前端开发规格

### 10.1 AI 整理笔记 — 前端

#### 10.1.1 笔记列表页多选模式扩展

在现有 `NotesListPage` 的多选管理模式中，新增「AI 整理」按钮（与「批量删除」并列）。

**UI 交互流程**：

```
笔记列表页 → 进入多选模式 → 选中 2-20 篇笔记
  → 点击「AI 整理」按钮
  → 弹出 Modal 对话框
    → TextArea 输入额外提示词（placeholder: "请描述整理方式，如：合并为一篇结构化笔记 / 提取核心要点生成摘要 / 对比分析异同..."）
    → 点击「开始整理」
  → Modal 显示进度条（监听 WebSocket）
    → preparing (10%) → generating (30%) → saving (80%) → complete (100%)
  → 完成 → 自动跳转到新笔记编辑页
```

**新增 API 调用**：

```typescript
// api/notes.ts — 新增

/** AI 整理笔记 */
organizeNotes: (data: { note_ids: string[]; prompt: string }) =>
  api.post<{ task_id: string; message: string }>("/notes/organize", data),
```

**新增类型**：

```typescript
// types/note.ts — 新增

interface OrganizeNotesRequest {
  note_ids: string[];   // 1-20 篇
  prompt: string;       // 额外提示词
}

interface OrganizeNotesResponse {
  task_id: string;
  message: string;
}

interface OrganizeProgress {
  stage: "preparing" | "generating" | "saving" | "complete" | "error";
  percent: number;
  message: string;
  note_id?: string;
  title?: string;
  word_count?: number;
  source_count?: number;
  error?: string;
}
```

**Note 类型扩展**：

```typescript
// types/note.ts — Note 接口新增字段

interface Note {
  // ... 现有字段 ...
  origin_type: "user" | "ai_organized";
  source_note_ids: string[] | null;
}
```

**WebSocket 进度监听**：

```typescript
// hooks/useOrganizeProgress.ts — [新增文件]

/**
 * AI 整理笔记进度 Hook
 * 连接 /ws/organize-progress/{task_id}，接收进度推送
 */
function useOrganizeProgress(taskId: string | null) {
  // 使用原生 WebSocket（参考 useWebSocket 模式）
  // WS URL: ws://127.0.0.1:8000/ws/organize-progress/{task_id}?token={access_token}
  // 返回: { progress: OrganizeProgress | null, isConnected: boolean }
}
```

#### 10.1.2 整理进度 Modal 组件

```typescript
// components/notes/OrganizeProgressModal.tsx — [新增文件]

/**
 * AI 整理笔记进度弹窗
 * 
 * Props:
 * - open: boolean
 * - taskId: string | null
 * - onComplete: (noteId: string) => void  // 完成后跳转
 * - onError: (error: string) => void
 * - onClose: () => void
 * 
 * 内部逻辑:
 * 1. taskId 变化时建立 WebSocket 连接
 * 2. 显示进度条 + 阶段文字
 * 3. complete 时显示「查看成果笔记」按钮
 * 4. error 时显示错误信息和「重试」按钮
 */
```

### 10.2 AI 修改笔记 — 前端

#### 10.2.1 通知 WebSocket 扩展

在现有 `useNotificationWS` Hook 中新增 `note_edit` 消息类型处理：

```typescript
// hooks/useNotificationWS.ts — 扩展

// 在消息处理 switch 中新增:
case "note_edit":
  // 1. 检查 note_id 是否匹配当前打开的笔记
  // 2. 如果匹配，调用 noteStore.applyAiEdit(data)
  // 3. 显示通知: "AI 已修改此笔记"
  break;
```

#### 10.2.2 笔记编辑器集成

```typescript
// pages/notes/NoteEditorPage.tsx — 扩展

// 1. 监听 noteStore 的 AI 编辑事件
// 2. 当收到与当前 noteId 匹配的编辑通知时:
//    - 使用 editor.commands.setContent(data.new_content) 替换编辑器内容
//    - 同步更新 content state
//    - 显示 toast: "AI 已修改此笔记（Ctrl+Z 可撤销）"
//    - 标记同步状态为 "ai_modified"

// 3. 在 ToolCallDisplay 中展示 edit_note 工具调用详情:
//    - 显示操作类型（插入/替换/删除）
//    - 显示行号范围
//    - 显示内容预览（截断到 100 字符）
```

#### 10.2.3 noteStore 扩展

```typescript
// stores/noteStore.ts — 新增 action

/**
 * 应用 AI 编辑到当前笔记
 * 由 useNotificationWS 在收到 note_edit 消息时调用
 */
applyAiEdit: (editData: {
  note_id: string;
  operation: "insert" | "replace" | "delete";
  new_content: string;
  word_count: number;
}) => void;
```

#### 10.2.4 Agent 工具调用展示

```typescript
// components/agent/ToolCallDisplay.tsx — 扩展

// 新增 edit_note 工具的展示卡片:
// - 图标: FileEdit
// - 标题: "编辑笔记「{title}」"
// - 详情:
//   - insert: "在第 {start_line} 行前插入 {lines} 行"
//   - replace: "替换第 {start_line}-{end_line} 行"
//   - delete: "删除第 {start_line}-{end_line} 行"
// - 状态: 成功(绿色) / 失败(红色)
```

---

## 11. 验收标准

### 11.1 Sprint 9.1: AI 整理笔记

| # | 验收条件 | 验证方法 |
|---|---------|----------|
| 1 | `POST /notes/organize` 接受 note_ids + prompt，返回 task_id | curl / Swagger UI 测试 |
| 2 | 笔记数量限制 1-20 篇，超限返回 400 | 发送 21 个 note_ids 验证 |
| 3 | 只能整理自己的笔记，跨用户返回 400 | 使用 A 的 token 整理 B 的笔记 |
| 4 | Celery 任务正确执行：准备 → LLM 调用 → 保存 | 查看 Celery worker 日志 |
| 5 | WebSocket 进度推送正确：preparing → generating → saving → complete | 前端连接 WS 验证 |
| 6 | 成果笔记正确创建，origin_type="ai_organized"，source_note_ids 正确 | 数据库查询验证 |
| 7 | 成果笔记同步到 Meilisearch | 搜索新笔记可找到 |
| 8 | LLM 输出正确解析标题和正文 | 检查笔记标题非默认值 |
| 9 | 任务失败时推送 error 消息 | 模拟 LLM 超时/错误 |
| 10 | 前端多选 → 弹窗 → 进度 → 跳转全流程 | 手动 E2E 测试 |

### 11.2 Sprint 9.2: AI 修改笔记

| # | 验收条件 | 验证方法 |
|---|---------|----------|
| 1 | `edit_note` 工具正确注册到 ToolRegistry | `GET /agent/tools` 返回 13 个工具 |
| 2 | insert 操作：在指定行前插入内容 | 通过 Agent 对话触发 insert |
| 3 | replace 操作：替换指定行范围 | 通过 Agent 对话触发 replace |
| 4 | delete 操作：删除指定行范围 | 通过 Agent 对话触发 delete |
| 5 | 行号越界时返回有意义的错误信息 | 传入 start_line=99999 |
| 6 | 修改后笔记正确保存到数据库 | 数据库查询验证 |
| 7 | 修改后同步到 Meilisearch | 搜索可找到新内容 |
| 8 | WebSocket 推送 note_edit 消息到正确用户 | 监听 /ws/notifications |
| 9 | 前端编辑器实时更新内容 | 打开笔记 + Agent 对话测试 |
| 10 | 用户可 Ctrl+Z 撤销 AI 修改 | 手动测试 |
| 11 | 只能修改自己的笔记 | 跨用户测试 |
| 12 | Agent 能正确获取笔记行数并据此决定编辑位置 | 观察 Agent 工具调用参数 |

### 11.3 Phase 4 整体验收

| # | 验收条件 |
|---|---------|
| 1 | 笔记列表页多选模式下「AI 整理」按钮可见且功能完整 |
| 2 | 整理完成后可在笔记列表中看到成果笔记（origin_type=ai_organized） |
| 3 | Agent 对话中可以请求 AI 修改当前笔记，修改实时生效 |
| 4 | 所有新 API 端点在 Swagger UI 中正确展示 |
| 5 | 所有 WebSocket 端点正确推送消息 |
| 6 | 无回归：现有笔记 CRUD、Agent 12 工具、搜索等功能不受影响 |

---

## 12. 技术债记录

| # | 项目 | 描述 | 优先级 |
|---|------|------|--------|
| 1 | 整理成果溯源 UI | 成果笔记中展示源笔记列表和整理提示词，支持点击跳转 | P2 |
| 2 | edit_note 冲突处理 | 用户手动编辑和 AI 编辑同时发生时的冲突解决策略 | P1 |
| 3 | edit_note 权限细化 | 支持笔记所有者设置「是否允许 AI 修改」开关 | P3 |
| 4 | 整理任务取消 | 支持中途取消正在执行的整理任务（复用 cancel_token） | P2 |
| 5 | edit_note 增量推送 | 当前推送完整 new_content，大笔记时 token 浪费；可改为只推送 diff | P2 |
| 6 | 整理历史记录 | 记录每次整理的输入/输出，支持对比查看 | P3 |
| 7 | Phase 3 Agent 源码补建 | tool_schemas.py / tool_registry.py / handlers/ 等文件需从进度文档落地为实际代码 | P0 |

---

## 附录 A: 完整 API 端点清单（本 Phase 新增）

| 方法 | 路径 | 描述 | Sprint |
|------|------|------|--------|
| POST | /api/v1/notes/organize | AI 整理笔记（异步） | 9.1 |
| GET | /api/v1/agent/tools | 获取 Agent 工具列表（含 edit_note） | 9.2 |

## 附录 B: WebSocket 端点清单（本 Phase 新增/扩展）

| 路径 | 描述 | Sprint |
|------|------|--------|
| WS /ws/organize-progress/{task_id} | 笔记整理进度推送 | 9.1 |
| WS /ws/notifications（扩展消息类型） | 新增 note_edit 消息类型 | 9.2 |

## 附录 C: Agent 工具清单（本 Phase 新增）

| 工具名 | 模块 | 描述 | 类别 | Sprint |
|--------|------|------|------|--------|
| edit_note | note | 行号级别局部编辑笔记 | write | 9.2 |

**Phase 4 完成后 Agent 工具总数**: 13 个（原 12 个 + edit_note）

## 附录 D: 数据库模型变更

| 表名 | 变更类型 | 字段 | 说明 |
|------|----------|------|------|
| notes | 新增列 | origin_type VARCHAR(20) DEFAULT 'user' | 来源类型 |
| notes | 新增列 | source_note_ids UUID[] | 源笔记 ID 列表 |
