# 青云智学 — Phase 1：基础搭建（P0）开发文档

> 版本：1.0
> 日期：2026-07-08
> 依赖：青云智学-后端开发文档.md v1.0
> 用途：AI编程助手可直接依照本文档逐步开发，完成Phase 1全部4个Sprint。每个Sprint包含完整的代码实现、配置说明和验收标准。

---

## 总览

Phase 1 覆盖 Sprint 1 ~ Sprint 4，目标是搭建完整的项目基础设施，跑通"用户注册→笔记管理→AI生成讲义→用户画像"核心链路。

| Sprint | 主题 | 核心交付 |
|--------|------|----------|
| Sprint 1 | 项目初始化 | 目录结构、Docker环境、FastAPI骨架、全部ORM模型、Alembic迁移、代码规范 |
| Sprint 2 | 认证与笔记基础 | JWT认证全流程、笔记CRUD、Meilisearch全文搜索、标签系统 |
| Sprint 3 | AI核心链路 | LLM适配层、RAG基础版、讲义生成异步任务、网络检索、WebSocket流式输出 |
| Sprint 4 | 用户记忆与画像 | 双层记忆存储、个人习惯画像(Push)、知识画像(Pull)、UserMemory封装、个性化知识梳理 |

---

## Sprint 1：项目初始化

### 1.1 初始化项目结构

创建以下完整目录和文件结构：

```
backend/
├── pyproject.toml
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── note.py
│   │   ├── learning.py
│   │   ├── knowledge.py
│   │   ├── review.py
│   │   └── tag.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── note.py
│   │   ├── learning.py
│   │   ├── knowledge.py
│   │   ├── review.py
│   │   └── common.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── router.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── memory/
│   │       ├── __init__.py
│   ├── agent/
│   │   ├── __init__.py
│   │   └── prompts/
│   │       └── __init__.py
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── prompts/
│   │   │   └── __init__.py
│   │   ├── rag/
│   │   │   └── __init__.py
│   │   └── web_search/
│   │       └── __init__.py
│   ├── tasks/
│   │   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py
│   │   ├── exceptions.py
│   │   ├── middleware.py
│   │   └── utils.py
├── tests/
│   ├── conftest.py
├── .env.example
├── .env
├── .gitignore
├── Dockerfile
└── docker-compose.yml
```

### 1.2 pyproject.toml

```toml
[project]
name = "qingyun-zhixue"
version = "0.1.0"
description = "青云智学 - AI驱动的全流程学习辅助软件后端"
requires-python = ">=3.11"

dependencies = [
    # Web框架
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "python-multipart>=0.0.9",

    # 数据库
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",

    # Redis & 任务队列
    "redis>=5.0",
    "celery[redis]>=5.4",

    # AI/LLM
    "openai>=1.30",
    "anthropic>=0.25",
    "dashscope>=1.17",
    "llama-index>=0.12",
    "llama-index-embeddings-huggingface>=0.3",
    "sentence-transformers>=3.0",
    "FlagEmbedding>=1.2",

    # 搜索
    "meilisearch>=0.31",

    # 网络检索
    "trafilatura>=1.9",
    "httpx>=0.27",

    # 工具
    "pydantic>=2.7",
    "pydantic-settings>=2.2",
    "python-jose[cryptography]>=3.3",
    "passlib[bcrypt]>=1.7",
    "structlog>=24.1",
    "websockets>=12.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "ruff>=0.4",
    "mypy>=1.10",
]

[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "A", "SIM"]
ignore = ["B008"]  # Depends() 在函数默认参数中使用

[tool.ruff.lint.isort]
known-first-party = ["app"]

[tool.mypy]
python_version = "3.11"
plugins = ["pydantic.mypy"]
check_untyped_defs = true
warn_return_any = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 1.3 docker-compose.yml

```yaml
version: "3.9"

services:
  postgres:
    image: apache/age:v1.5.0-pg16  # PostgreSQL 16 + Apache AGE
    container_name: qingyun-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: qingyun
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: qingyun-redis
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  meilisearch:
    image: getmeili/meilisearch:v1.8
    container_name: qingyun-meilisearch
    environment:
      MEILI_MASTER_KEY: ${MEILISEARCH_MASTER_KEY:-masterKey_dev}
      MEILI_ENVIRONMENT: development
    ports:
      - "7700:7700"
    volumes:
      - meilidata:/meili_data

volumes:
  pgdata:
  redisdata:
  meilidata:
```

### 1.4 scripts/init-db.sql

数据库初始化脚本，在PostgreSQL首次启动时自动执行：

```sql
-- 启用扩展
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS age;

-- 加载AGE到当前会话
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- 创建知识图谱
SELECT create_graph('knowledge_graph');
```

### 1.5 .env.example

```bash
# 应用
APP_NAME=qingyun-zhixue
APP_ENV=development
APP_DEBUG=true
SECRET_KEY=change-me-to-random-64-chars

# 数据库
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/qingyun
DATABASE_POOL_SIZE=20

# Redis
REDIS_URL=redis://localhost:6379/0

# Meilisearch
MEILISEARCH_URL=http://localhost:7700
MEILISEARCH_MASTER_KEY=masterKey_dev

# JWT
JWT_SECRET_KEY=change-me-to-random-64-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# LLM
DEEPSEEK_API_KEY=
QWEN_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# 嵌入模型
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIM=1024

# 搜索API
BING_SEARCH_API_KEY=

# 对象存储
OSS_ACCESS_KEY=
OSS_SECRET_KEY=
OSS_BUCKET=qingyun-zhixue
OSS_ENDPOINT=

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Agent编排
AGENT_MAX_STEPS=6
AGENT_TOKEN_BUDGET=4000

# 用户记忆
MEMORY_HABIT_SUMMARY_MAX_TOKENS=300
MEMORY_RECALL_MAX_TOKENS=800
MEMORY_INDEX_CACHE_TTL=3600
```

### 1.6 .gitignore

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/
*.egg
.env
.venv/
venv/
env/
*.db
*.sqlite3
.mypy_cache/
.ruff_cache/
.pytest_cache/
htmlcov/
.coverage
```

### 1.7 app/config.py — 配置管理

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 应用
    APP_NAME: str = "qingyun-zhixue"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    SECRET_KEY: str = "change-me"

    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/qingyun"
    DATABASE_POOL_SIZE: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Meilisearch
    MEILISEARCH_URL: str = "http://localhost:7700"
    MEILISEARCH_MASTER_KEY: str = "masterKey_dev"

    # JWT
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM API Keys
    DEEPSEEK_API_KEY: Optional[str] = None
    QWEN_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # 嵌入模型
    EMBEDDING_MODEL: str = "bge-m3"
    EMBEDDING_DIM: int = 1024

    # 搜索API
    BING_SEARCH_API_KEY: Optional[str] = None

    # 对象存储
    OSS_ACCESS_KEY: Optional[str] = None
    OSS_SECRET_KEY: Optional[str] = None
    OSS_BUCKET: str = "qingyun-zhixue"
    OSS_ENDPOINT: Optional[str] = None

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Agent
    AGENT_MAX_STEPS: int = 6
    AGENT_TOKEN_BUDGET: int = 4000

    # 用户记忆
    MEMORY_HABIT_SUMMARY_MAX_TOKENS: int = 300
    MEMORY_RECALL_MAX_TOKENS: int = 800
    MEMORY_INDEX_CACHE_TTL: int = 3600


settings = Settings()
```

### 1.8 app/database.py — 数据库连接

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=10,
    pool_pre_ping=True,
    echo=settings.APP_DEBUG,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """所有ORM模型的基类"""
    pass


async def get_db() -> AsyncSession:
    """FastAPI依赖注入：获取数据库会话"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """应用启动时初始化数据库连接（测试用）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """应用关闭时关闭数据库连接"""
    await engine.dispose()
```

### 1.9 ORM模型 — 全部表

以下为完整的SQLAlchemy 2.0 async ORM模型定义，严格按照后端开发文档第3章的Schema实现。

#### app/models/__init__.py

```python
from app.models.user import User, UserProfile, PersonalHabitProfile
from app.models.note import Note
from app.models.tag import Tag, NoteTag
from app.models.knowledge import KnowledgeNode, KnowledgeEdge, UserKnowledgeMastery
from app.models.learning import LearningRoute, LearningRouteStep, Lecture
from app.models.review import ReviewPlan
from app.models.memory import MemoryIndex, MemoryFull
from app.models.auth import RefreshToken
from app.models.learning import LearningRecord, QASession, QAMessage
from app.models.rag import DocumentChunk

__all__ = [
    "User", "UserProfile", "PersonalHabitProfile",
    "Note", "Tag", "NoteTag",
    "KnowledgeNode", "KnowledgeEdge", "UserKnowledgeMastery",
    "LearningRoute", "LearningRouteStep", "Lecture",
    "ReviewPlan",
    "MemoryIndex", "MemoryFull",
    "RefreshToken",
    "LearningRecord", "QASession", "QAMessage",
    "DocumentChunk",
]
```

#### app/models/user.py

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Float, Integer, Text, DateTime, Interval
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="student")
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    profile: Mapped["UserProfile"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    habit_profile: Mapped["PersonalHabitProfile"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    cognitive_style: Mapped[str] = mapped_column(String(20), default="visual")
    preferred_study_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    avg_session_duration: Mapped[datetime | None] = mapped_column(Interval, nullable=True)
    total_study_hours: Mapped[float] = mapped_column(Float, default=0.0)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user: Mapped["User"] = relationship(back_populates="profile")


class PersonalHabitProfile(Base):
    __tablename__ = "personal_habit_profile"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    active_time_slot: Mapped[str | None] = mapped_column(String(20), nullable=True)
    content_preference: Mapped[str | None] = mapped_column(String(20), nullable=True)
    avg_session_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail_preference: Mapped[str] = mapped_column(String(20), default="balanced")
    weak_node_names: Mapped[list] = mapped_column(
        # 使用postgresql.ARRAY(Text)
        # 注意：需要 from sqlalchemy.dialects.postgresql import ARRAY
        # 实际写法见下方修正
        nullable=True
    )
    summary_cache: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user: Mapped["User"] = relationship(back_populates="habit_profile")
```

> **注意**：`weak_node_names` 字段正确写法：

```python
from sqlalchemy.dialects.postgresql import ARRAY

weak_node_names: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
```

#### app/models/note.py

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), default="无标题")
    content: Mapped[str] = mapped_column(Text, default="")
    content_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    subject: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    route_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_routes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_nodes.id"), nullable=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notes.id"), nullable=True, index=True
    )
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    tags: Mapped[list["NoteTag"]] = relationship(back_populates="note", cascade="all, delete-orphan")
```

#### app/models/tag.py

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Text, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class NoteTag(Base):
    __tablename__ = "note_tags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # 关系
    note: Mapped["Note"] = relationship(back_populates="tags")
    tag: Mapped["Tag"] = relationship()
```

#### app/models/knowledge.py

```python
import uuid
from datetime import datetime
from sqlalchemy import String, SmallInteger, Integer, Float, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    grade_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    difficulty: Mapped[int] = mapped_column(SmallInteger, default=1)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class KnowledgeEdge(Base):
    __tablename__ = "knowledge_edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # 关系
    source: Mapped["KnowledgeNode"] = relationship(foreign_keys=[source_id])
    target: Mapped["KnowledgeNode"] = relationship(foreign_keys=[target_id])


class UserKnowledgeMastery(Base):
    __tablename__ = "user_knowledge_mastery"
    __table_args__ = (UniqueConstraint("user_id", "node_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False
    )
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    node: Mapped["KnowledgeNode"] = relationship()
```

#### app/models/learning.py

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class LearningRoute(Base):
    __tablename__ = "learning_routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    estimated_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    steps: Mapped[list["LearningRouteStep"]] = relationship(back_populates="route", cascade="all, delete-orphan")


class LearningRouteStep(Base):
    __tablename__ = "learning_route_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_routes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_nodes.id"), nullable=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    prerequisites: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    route: Mapped["LearningRoute"] = relationship(back_populates="steps")


class Lecture(Base):
    __tablename__ = "lectures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_routes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_route_steps.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_nodes.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_urls: Mapped[list] = mapped_column(ARRAY(Text), default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="generated")
    token_usage: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class LearningRecord(Base):
    __tablename__ = "learning_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    route_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_routes.id", ondelete="SET NULL"), nullable=True
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_route_steps.id", ondelete="SET NULL"), nullable=True
    )
    node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_nodes.id", ondelete="SET NULL"), nullable=True
    )
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class QASession(Base):
    __tablename__ = "qa_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    lecture_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lectures.id", ondelete="SET NULL"), nullable=True
    )
    node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_nodes.id", ondelete="SET NULL"), nullable=True
    )
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    messages: Mapped[list["QAMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class QAMessage(Base):
    __tablename__ = "qa_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("qa_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # 关系
    session: Mapped["QASession"] = relationship(back_populates="messages")
```

#### app/models/review.py

```python
import uuid
from datetime import datetime
from sqlalchemy import String, SmallInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ReviewPlan(Base):
    __tablename__ = "review_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False
    )
    review_type: Mapped[str] = mapped_column(String(30), default="spaced")
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    priority: Mapped[int] = mapped_column(SmallInteger, default=3)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### app/models/memory.py

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Float, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

# pgvector类型需要特殊处理
# 方式1：使用sqlalchemy原生Column + 自定义类型
# 方式2：使用pgvector sqlalchemy扩展
# 推荐方式2：pip install pgvector
from pgvector.sqlalchemy import Vector


class MemoryIndex(Base):
    __tablename__ = "memory_index"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    memory_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1024), nullable=True)  # pgvector 1024维
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    full_memory_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class MemoryFull(Base):
    __tablename__ = "memory_full"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    memory_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_records: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### app/models/auth.py

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
```

#### app/models/rag.py

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from pgvector.sqlalchemy import Vector


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_nodes.id"), nullable=True, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1024), nullable=True)  # BGE-M3 1024维
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
```

### 1.10 Alembic配置

#### alembic.ini

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://postgres:postgres@localhost:5432/qingyun

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

#### alembic/env.py

```python
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.config import settings
from app.database import Base
from app.models import *  # noqa: F401,F403 — 确保所有模型被导入

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### 1.11 core/ — 核心工具

#### app/core/exceptions.py

```python
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppException(HTTPException):
    """应用基础异常"""
    def __init__(self, status_code: int, code: str, message: str, details: list | None = None):
        self.code = code
        self.details = details or []
        super().__init__(status_code=status_code, detail=message)


class NotFoundException(AppException):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(status_code=404, code="NOT_FOUND", message=message)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "未授权"):
        super().__init__(status_code=401, code="UNAUTHORIZED", message=message)


class ForbiddenException(AppException):
    def __init__(self, message: str = "无权限"):
        super().__init__(status_code=403, code="FORBIDDEN", message=message)


class BadRequestException(AppException):
    def __init__(self, message: str = "请求参数错误", details: list | None = None):
        super().__init__(status_code=400, code="BAD_REQUEST", message=message, details=details)


class ConflictException(AppException):
    def __init__(self, message: str = "资源冲突"):
        super().__init__(status_code=409, code="CONFLICT", message=message)


async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.detail,
                "details": exc.details,
            }
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = []
    for error in exc.errors():
        details.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
        })
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "请求参数验证失败",
                "details": details,
            }
        },
    )
```

#### app/core/security.py

```python
from datetime import datetime, timedelta
from typing import Any
from jose import jwt
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
```

#### app/core/middleware.py

```python
import time
import uuid
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        structlog.contextvars.bind_contextvars(request_id=request_id)

        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )

        response.headers["X-Request-ID"] = request_id
        structlog.contextvars.clear_contextvars()
        return response


def setup_middlewares(app: FastAPI):
    app.add_middleware(
        "CORSMiddleware",
        allow_origins=["*"],  # 生产环境需限制
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # 注意：CORSMiddleware应通过app.add_middleware正式添加
    # 上面是示意，实际代码：
    from starlette.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
```

> **注意**：`setup_middlewares` 中 CORS 部分应只添加一次，修正版本：

```python
from starlette.middleware.cors import CORSMiddleware

def setup_middlewares(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境需限制具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
```

#### app/core/utils.py

```python
import re


def estimate_tokens(text: str) -> int:
    """粗略估算token数（中文约1.5字/token，英文约4字符/token）"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


def truncate_text(text: str, max_length: int = 200) -> str:
    """截断文本到指定长度"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def calculate_word_count(text: str) -> int:
    """计算文本字数（中文按字计，英文按词计）"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    return chinese_chars + english_words
```

### 1.12 app/main.py — FastAPI入口

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
import structlog

from app.config import settings
from app.database import close_db
from app.core.exceptions import app_exception_handler, validation_exception_handler
from app.core.middleware import setup_middlewares
from app.api.v1.router import api_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    logger.info("application_starting", app_name=settings.APP_NAME)
    yield
    # 关闭
    await close_db()
    logger.info("application_shutdown")


app = FastAPI(
    title="青云智学 API",
    description="AI驱动的全流程学习辅助软件后端",
    version="0.1.0",
    lifespan=lifespan,
)

# 注册异常处理器
app.add_exception_handler(422, validation_exception_handler)
# 自定义异常处理器注册
from app.core.exceptions import AppException
app.add_exception_handler(AppException, app_exception_handler)

# 中间件
setup_middlewares(app)

# 路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}
```

### 1.13 app/api/v1/router.py — 路由汇总（骨架）

```python
from fastapi import APIRouter

api_router = APIRouter()

# Sprint 2 完成后取消注释：
# from app.api.v1 import auth, users, notes, tags
# api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
# api_router.include_router(users.router, prefix="/users", tags=["用户"])
# api_router.include_router(notes.router, prefix="/notes", tags=["笔记"])
# api_router.include_router(tags.router, prefix="/tags", tags=["标签"])

# Sprint 3 完成后取消注释：
# from app.api.v1 import learning
# api_router.include_router(learning.router, prefix="/learning", tags=["学习"])

# Sprint 4 完成后取消注释：
# from app.api.v1 import review
# api_router.include_router(review.router, prefix="/review", tags=["复习"])
```

### 1.14 代码规范配置验证

完成Sprint 1后，执行以下命令验证：

```bash
# 安装依赖
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 启动Docker服务
docker-compose up -d

# 验证代码规范
ruff check app/
ruff format --check app/
mypy app/

# 执行数据库迁移
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

### 1.15 Sprint 1 验收标准

- [ ] `docker-compose up -d` 成功启动PostgreSQL+AGE+pgvector、Redis、Meilisearch
- [ ] `ruff check app/` 零错误
- [ ] `mypy app/` 零错误（或仅第三方库缺少类型存根）
- [ ] `alembic upgrade head` 成功创建所有表
- [ ] `uvicorn app.main:app --reload` 启动成功，访问 `/health` 返回 `{"status": "ok"}`
- [ ] 所有ORM模型定义完整，与后端文档第3章Schema一一对应

---

## Sprint 2：认证与笔记基础

### 2.1 Pydantic Schema定义

#### app/schemas/common.py

```python
from pydantic import BaseModel
from typing import Generic, TypeVar, Optional

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class MessageResponse(BaseModel):
    message: str
```

#### app/schemas/user.py

```python
import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenRefresh(BaseModel):
    refresh_token: str


class UserSchema(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    role: str
    avatar_url: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfileSchema(BaseModel):
    cognitive_style: str = "visual"
    preferred_study_time: Optional[str] = None
    total_study_hours: float = 0.0
    streak_days: int = 0

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    avatar_url: Optional[str] = None
    cognitive_style: Optional[str] = Field(None, pattern="^(visual|auditory|kinesthetic)$")
    preferred_study_time: Optional[str] = Field(None, pattern="^(morning|afternoon|evening)$")


class AuthResponse(BaseModel):
    user: UserSchema
    access_token: str
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
```

#### app/schemas/note.py

```python
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Any


class NoteCreate(BaseModel):
    title: Optional[str] = "无标题"
    content: Optional[str] = ""
    content_json: Optional[dict[str, Any]] = None
    subject: Optional[str] = None
    route_id: Optional[uuid.UUID] = None
    node_id: Optional[uuid.UUID] = None
    parent_id: Optional[uuid.UUID] = None


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    content_json: Optional[dict[str, Any]] = None
    subject: Optional[str] = None
    route_id: Optional[uuid.UUID] = None
    node_id: Optional[uuid.UUID] = None
    parent_id: Optional[uuid.UUID] = None


class NoteSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    content: str
    content_json: Optional[dict[str, Any]] = None
    subject: Optional[str] = None
    route_id: Optional[uuid.UUID] = None
    node_id: Optional[uuid.UUID] = None
    parent_id: Optional[uuid.UUID] = None
    is_template: bool
    word_count: int
    created_at: datetime
    updated_at: datetime
    tags: list["NoteTagSchema"] = []

    model_config = {"from_attributes": True}


class NoteTagCreate(BaseModel):
    tag_id: uuid.UUID
    content_text: str
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    context: Optional[str] = None


class NoteTagSchema(BaseModel):
    id: uuid.UUID
    note_id: uuid.UUID
    tag_id: uuid.UUID
    content_text: Optional[str] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    context: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
```

#### app/schemas/__init__.py — 标签Schema

在 `app/schemas/note.py` 中追加：

```python
class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    description: Optional[str] = None


class TagSchema(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    name: str
    color: Optional[str] = None
    is_system: bool
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
```

### 2.2 依赖注入 — app/api/deps.py

```python
import uuid
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=401,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        if user_id is None or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user
```

### 2.3 认证服务 — app/services/auth_service.py

```python
import uuid
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserProfile
from app.models.auth import RefreshToken
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.exceptions import UnauthorizedException, ConflictException, BadRequestException
from app.config import settings


class AuthService:

    @staticmethod
    async def register(db: AsyncSession, email: str, username: str, password: str) -> dict:
        # 检查邮箱是否已注册
        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            raise ConflictException("邮箱已注册")

        # 检查用户名是否已存在
        result = await db.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none():
            raise ConflictException("用户名已存在")

        # 创建用户
        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
        )
        db.add(user)
        await db.flush()

        # 创建用户画像
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        await db.flush()

        # 生成token
        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})

        # 存储refresh_token hash
        token_record = RefreshToken(
            user_id=user.id,
            token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(token_record)
        await db.commit()
        await db.refresh(user)

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    @staticmethod
    async def login(db: AsyncSession, email: str, password: str) -> dict:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedException("邮箱或密码错误")

        if not user.is_active:
            raise UnauthorizedException("账号已被禁用")

        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})

        token_record = RefreshToken(
            user_id=user.id,
            token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(token_record)
        await db.commit()

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    @staticmethod
    async def refresh_token(db: AsyncSession, refresh_token_str: str) -> str:
        try:
            payload = decode_token(refresh_token_str)
            user_id = payload.get("sub")
            token_type = payload.get("type")
            if not user_id or token_type != "refresh":
                raise UnauthorizedException("无效的刷新令牌")
        except Exception:
            raise UnauthorizedException("无效的刷新令牌")

        # 验证token hash
        token_hash = hashlib.sha256(refresh_token_str.encode()).hexdigest()
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked == False,  # noqa: E712
                RefreshToken.expires_at > datetime.utcnow(),
            )
        )
        token_record = result.scalar_one_or_none()
        if not token_record:
            raise UnauthorizedException("刷新令牌已失效")

        # 生成新access_token
        new_access_token = create_access_token(data={"sub": user_id})
        return new_access_token

    @staticmethod
    async def logout(db: AsyncSession, user_id: uuid.UUID, refresh_token_str: str):
        token_hash = hashlib.sha256(refresh_token_str.encode()).hexdigest()
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.user_id == user_id,
            )
        )
        token_record = result.scalar_one_or_none()
        if token_record:
            token_record.revoked = True
            await db.commit()
```

### 2.4 认证路由 — app/api/v1/auth.py

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserRegister, UserLogin, TokenRefresh, AuthResponse, TokenResponse
from app.schemas.common import MessageResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    result = await AuthService.register(db, body.email, body.username, body.password)
    return AuthResponse(**result)


@router.post("/login", response_model=AuthResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await AuthService.login(db, body.email, body.password)
    return AuthResponse(**result)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: TokenRefresh, db: AsyncSession = Depends(get_db)):
    access_token = await AuthService.refresh_token(db, body.refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    body: TokenRefresh,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await AuthService.logout(db, user.id, body.refresh_token)
    return MessageResponse(message="logged out")
```

### 2.5 用户路由 — app/api/v1/users.py

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User, UserProfile
from app.schemas.user import UserSchema, UserProfileSchema, UserUpdate

router = APIRouter()


@router.get("/me")
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    return {
        "user": UserSchema.model_validate(user),
        "profile": UserProfileSchema.model_validate(profile) if profile else None,
    }


@router.patch("/me", response_model=UserSchema)
async def update_me(
    body: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    update_data = body.model_dump(exclude_unset=True)

    # 分离用户字段和画像字段
    profile_fields = {"cognitive_style", "preferred_study_time"}
    user_fields = {k: v for k, v in update_data.items() if k not in profile_fields}
    profile_fields_data = {k: v for k, v in update_data.items() if k in profile_fields}

    # 更新用户
    for field, value in user_fields.items():
        setattr(user, field, value)

    # 更新画像
    if profile_fields_data:
        result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
        profile = result.scalar_one_or_none()
        if profile:
            for field, value in profile_fields_data.items():
                setattr(profile, field, value)

    await db.flush()
    await db.refresh(user)
    return UserSchema.model_validate(user)


@router.get("/me/profile")
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户知识画像摘要（Sprint 4 完善）"""
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    return {
        "mastery_summary": {"total_nodes": 0, "mastered": 0, "learning": 0, "not_started": 0},
        "recent_activity": [],
        "streak_days": profile.streak_days if profile else 0,
        "total_study_hours": profile.total_study_hours if profile else 0.0,
    }
```

### 2.6 笔记服务 — app/services/note_service.py

```python
import uuid
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.note import Note
from app.models.tag import NoteTag, Tag
from app.core.utils import calculate_word_count
from app.core.exceptions import NotFoundException, ForbiddenException


class NoteService:

    @staticmethod
    async def create_note(db: AsyncSession, user_id: uuid.UUID, **kwargs) -> Note:
        content = kwargs.get("content", "") or ""
        note = Note(
            user_id=user_id,
            title=kwargs.get("title", "无标题"),
            content=content,
            content_json=kwargs.get("content_json"),
            subject=kwargs.get("subject"),
            route_id=kwargs.get("route_id"),
            node_id=kwargs.get("node_id"),
            parent_id=kwargs.get("parent_id"),
            word_count=calculate_word_count(content),
        )
        db.add(note)
        await db.flush()
        await db.refresh(note)
        return note

    @staticmethod
    async def get_note(db: AsyncSession, note_id: uuid.UUID, user_id: uuid.UUID) -> Note:
        result = await db.execute(
            select(Note)
            .options(selectinload(Note.tags))
            .where(Note.id == note_id, Note.user_id == user_id)
        )
        note = result.scalar_one_or_none()
        if not note:
            raise NotFoundException("笔记不存在")
        return note

    @staticmethod
    async def list_notes(
        db: AsyncSession,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        subject: str | None = None,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> tuple[list[Note], int]:
        query = select(Note).where(Note.user_id == user_id)

        if subject:
            query = query.where(Note.subject == subject)

        # 排序
        sort_column = getattr(Note, sort_by, Note.updated_at)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # 总数
        count_query = select(func.count()).select_from(Note).where(Note.user_id == user_id)
        if subject:
            count_query = count_query.where(Note.subject == subject)
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # 分页
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        notes = list(result.scalars().all())

        return notes, total

    @staticmethod
    async def update_note(db: AsyncSession, note_id: uuid.UUID, user_id: uuid.UUID, **kwargs) -> Note:
        note = await NoteService.get_note(db, note_id, user_id)

        update_data = {k: v for k, v in kwargs.items() if v is not None}
        for field, value in update_data.items():
            setattr(note, field, value)

        # 重新计算字数
        if "content" in update_data:
            note.word_count = calculate_word_count(note.content or "")

        await db.flush()
        await db.refresh(note)
        return note

    @staticmethod
    async def delete_note(db: AsyncSession, note_id: uuid.UUID, user_id: uuid.UUID):
        note = await NoteService.get_note(db, note_id, user_id)
        await db.delete(note)
        await db.flush()

    @staticmethod
    async def search_notes(
        db: AsyncSession,
        user_id: uuid.UUID,
        query: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Note], int]:
        """基础数据库搜索（Sprint 2先用LIKE，后续替换为Meilisearch）"""
        search_filter = or_(
            Note.title.ilike(f"%{query}%"),
            Note.content.ilike(f"%{query}%"),
        )
        q = select(Note).where(Note.user_id == user_id, search_filter)

        count_q = select(func.count()).select_from(Note).where(Note.user_id == user_id, search_filter)
        total = (await db.execute(count_q)).scalar()

        q = q.order_by(Note.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(q)
        return list(result.scalars().all()), total
```

### 2.7 笔记路由 — app/api/v1/notes.py

```python
import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.note import NoteCreate, NoteUpdate, NoteSchema
from app.schemas.common import PaginatedResponse, MessageResponse
from app.services.note_service import NoteService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[NoteSchema])
async def list_notes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    subject: str | None = None,
    search: str | None = None,
    sort_by: str = Query("updated_at", pattern="^(created_at|updated_at|word_count)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if search:
        notes, total = await NoteService.search_notes(db, user.id, search, page, page_size)
    else:
        notes, total = await NoteService.list_notes(db, user.id, page, page_size, subject, sort_by, sort_order)
    return PaginatedResponse(
        items=[NoteSchema.model_validate(n) for n in notes],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=NoteSchema, status_code=status.HTTP_201_CREATED)
async def create_note(
    body: NoteCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    note = await NoteService.create_note(db, user.id, **body.model_dump(exclude_unset=True))
    return NoteSchema.model_validate(note)


@router.get("/{note_id}", response_model=NoteSchema)
async def get_note(
    note_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    note = await NoteService.get_note(db, note_id, user.id)
    return NoteSchema.model_validate(note)


@router.put("/{note_id}", response_model=NoteSchema)
async def update_note(
    note_id: uuid.UUID,
    body: NoteUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    note = await NoteService.update_note(db, note_id, user.id, **body.model_dump(exclude_unset=True))
    return NoteSchema.model_validate(note)


@router.delete("/{note_id}", response_model=MessageResponse)
async def delete_note(
    note_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await NoteService.delete_note(db, note_id, user.id)
    return MessageResponse(message="deleted")
```

### 2.8 标签系统 — app/api/v1/tags.py

```python
import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.tag import Tag, NoteTag
from app.schemas.note import TagCreate, TagSchema, NoteTagCreate, NoteTagSchema
from app.schemas.common import MessageResponse
from app.core.exceptions import NotFoundException

router = APIRouter()


@router.get("", response_model=list[TagSchema])
async def list_tags(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取系统标签 + 用户自定义标签"""
    result = await db.execute(
        select(Tag).where(
            (Tag.is_system == True) | (Tag.user_id == user.id)  # noqa: E712
        )
    )
    tags = result.scalars().all()
    return [TagSchema.model_validate(t) for t in tags]


@router.post("", response_model=TagSchema, status_code=status.HTTP_201_CREATED)
async def create_tag(
    body: TagCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tag = Tag(
        user_id=user.id,
        name=body.name,
        color=body.color,
        description=body.description,
    )
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    return TagSchema.model_validate(tag)


# 笔记标签操作放在notes路由下
@router.post("/notes/{note_id}/tags", response_model=NoteTagSchema, status_code=status.HTTP_201_CREATED)
async def add_note_tag(
    note_id: uuid.UUID,
    body: NoteTagCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.note import Note
    from app.core.exceptions import ForbiddenException
    # 验证笔记归属
    result = await db.execute(select(Note).where(Note.id == note_id, Note.user_id == user.id))
    if not result.scalar_one_or_none():
        raise NotFoundException("笔记不存在")

    note_tag = NoteTag(
        note_id=note_id,
        tag_id=body.tag_id,
        content_text=body.content_text,
        start_offset=body.start_offset,
        end_offset=body.end_offset,
        context=body.context,
    )
    db.add(note_tag)
    await db.flush()
    await db.refresh(note_tag)
    return NoteTagSchema.model_validate(note_tag)


@router.delete("/notes/{note_id}/tags/{tag_id}", response_model=MessageResponse)
async def remove_note_tag(
    note_id: uuid.UUID,
    tag_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NoteTag).where(NoteTag.note_id == note_id, NoteTag.tag_id == tag_id)
    )
    note_tag = result.scalar_one_or_none()
    if not note_tag:
        raise NotFoundException("标签记录不存在")
    await db.delete(note_tag)
    await db.flush()
    return MessageResponse(message="removed")
```

### 2.9 Meilisearch集成（笔记全文搜索）

在 `app/services/` 下新建 `search_service.py`（基础版，Sprint 2仅用于笔记搜索）：

```python
import meilisearch
from app.config import settings

_client: meilisearch.Client | None = None


def get_meilisearch_client() -> meilisearch.Client:
    global _client
    if _client is None:
        _client = meilisearch.Client(settings.MEILISEARCH_URL, settings.MEILISEARCH_MASTER_KEY)
    return _client


async def init_meilisearch_indexes():
    """初始化Meilisearch索引（应用启动时调用）"""
    client = get_meilisearch_client()

    # 笔记索引
    client.create_index("notes", {"primary_key": "id"})
    notes_index = client.index("notes")
    notes_index.update_searchable_attributes(["title", "content"])
    notes_index.update_filterable_attributes(["user_id", "subject", "created_at", "updated_at"])
    notes_index.update_sortable_attributes(["created_at", "updated_at", "word_count"])

    # Sprint 3 后添加更多索引...


async def index_note(note_data: dict):
    """索引一条笔记"""
    client = get_meilisearch_client()
    client.index("notes").add_documents([note_data])


async def delete_note_index(note_id: str):
    """删除笔记索引"""
    client = get_meilisearch_client()
    client.index("notes").delete_document(note_id)


async def search_notes_meilisearch(
    query: str,
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    subject: str | None = None,
) -> dict:
    """Meilisearch全文搜索笔记"""
    client = get_meilisearch_client()
    filters = [f"user_id = {user_id}"]
    if subject:
        filters.append(f'subject = "{subject}"')

    results = client.index("notes").search(
        query,
        {
            "filter": filters,
            "offset": (page - 1) * page_size,
            "limit": page_size,
        },
    )
    return results
```

在 `app/main.py` 的 lifespan 中添加 Meilisearch 初始化：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application_starting", app_name=settings.APP_NAME)
    # 初始化Meilisearch索引
    try:
        from app.services.search_service import init_meilisearch_indexes
        await init_meilisearch_indexes()
    except Exception as e:
        logger.warning("meilisearch_init_failed", error=str(e))
    yield
    await close_db()
    logger.info("application_shutdown")
```

### 2.10 更新路由汇总

Sprint 2完成后，更新 `app/api/v1/router.py`：

```python
from fastapi import APIRouter
from app.api.v1 import auth, users, notes, tags

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户"])
api_router.include_router(notes.router, prefix="/notes", tags=["笔记"])
api_router.include_router(tags.router, tags=["标签"])
```

### 2.11 Sprint 2 验收标准

- [ ] `POST /api/v1/auth/register` 注册成功，返回user + tokens
- [ ] `POST /api/v1/auth/login` 登录成功
- [ ] `POST /api/v1/auth/refresh` 刷新token成功
- [ ] `POST /api/v1/auth/logout` 登出，refresh_token被吊销
- [ ] `GET /api/v1/users/me` 获取当前用户信息（需Bearer token）
- [ ] `PATCH /api/v1/users/me` 更新用户信息
- [ ] `POST /api/v1/notes` 创建笔记
- [ ] `GET /api/v1/notes` 获取笔记列表（分页）
- [ ] `GET /api/v1/notes?search=关键词` 全文搜索笔记
- [ ] `PUT /api/v1/notes/{id}` 更新笔记
- [ ] `DELETE /api/v1/notes/{id}` 删除笔记
- [ ] `GET /api/v1/tags` 获取标签列表（系统+自定义）
- [ ] `POST /api/v1/tags` 创建自定义标签
- [ ] `POST /api/v1/notes/{id}/tags` 为笔记添加标签
- [ ] Meilisearch索引创建成功，搜索返回正确结果

---

## Sprint 3：AI核心链路

### 3.1 LLM通信层

#### app/ai/llm_client.py — 统一LLM客户端

```python
from typing import AsyncIterator
from openai import AsyncOpenAI
import structlog

from app.config import settings

logger = structlog.get_logger()


class LLMResponse:
    """统一的LLM响应封装"""
    def __init__(self, content: str, tool_calls: list | None = None, usage: dict | None = None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.usage = usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


class LLMClient:
    """
    统一LLM调用客户端。
    Phase 1 使用DeepSeek（OpenAI兼容接口），后续Sprint扩展多模型适配。
    """

    def __init__(self):
        self._clients: dict[str, AsyncOpenAI] = {}
        self._init_clients()

    def _init_clients(self):
        # DeepSeek（OpenAI兼容接口）
        if settings.DEEPSEEK_API_KEY:
            self._clients["deepseek-v3"] = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com/v1",
            )
        # 后续Sprint添加其他供应商...

    def _get_client(self, model: str) -> AsyncOpenAI:
        """根据模型名称获取客户端"""
        if model.startswith("deepseek"):
            return self._clients.get("deepseek-v3")
        # 后续扩展...
        # 默认使用deepseek
        return self._clients.get("deepseek-v3")

    async def chat(
        self,
        messages: list[dict],
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
    ) -> LLMResponse:
        client = self._get_client(model)
        if not client:
            raise RuntimeError(f"LLM client for model '{model}' not configured")

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        if stream:
            return await self._stream_chat(client, kwargs)
        else:
            return await self._sync_chat(client, kwargs)

    async def _sync_chat(self, client: AsyncOpenAI, kwargs: dict) -> LLMResponse:
        try:
            response = await client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            content = choice.message.content or ""

            tool_calls = []
            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    tool_calls.append({
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    })

            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

            return LLMResponse(content=content, tool_calls=tool_calls, usage=usage)
        except Exception as e:
            logger.error("llm_chat_failed", error=str(e), model=kwargs.get("model"))
            raise

    async def _stream_chat(self, client: AsyncOpenAI, kwargs: dict) -> LLMResponse:
        """流式聊天 — 返回LLMResponse（streaming由WebSocket层处理）"""
        kwargs["stream"] = True
        stream = await client.chat.completions.create(**kwargs)

        content_parts = []
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content_parts.append(chunk.choices[0].delta.content)

        return LLMResponse(content="".join(content_parts))

    async def embed(self, texts: list[str], model: str = "bge-m3") -> list[list[float]]:
        """
        文本嵌入。Phase 1 使用本地模型（sentence-transformers），
        后续可切换API调用。
        """
        # Phase 1 使用本地模型
        from app.ai.rag.embedding import get_embedder
        embedder = get_embedder()
        embeddings = embedder.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()


# 全局单例
_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
```

#### app/ai/llm_router.py — 模型路由

```python
from app.ai.llm_client import get_llm_client

# 模型路由配置
MODEL_ROUTING = {
    "default": "deepseek-chat",
    "long_context": "deepseek-chat",        # Phase 1统一用DeepSeek
    "chinese_education": "deepseek-chat",
    "high_precision": "deepseek-chat",
    "embedding": "bge-m3",
    "agent_chat": "deepseek-chat",
}


async def route_model(task_type: str, context_length: int = 0, **kwargs) -> str:
    """根据任务类型选择模型"""
    if context_length > 32000:
        return MODEL_ROUTING["long_context"]
    return MODEL_ROUTING.get(task_type, MODEL_ROUTING["default"])
```

### 3.2 RAG管道基础版

#### app/ai/rag/embedding.py

```python
from sentence_transformers import SentenceTransformer
import structlog

logger = structlog.get_logger()

_embedder: SentenceTransformer | None = None


def get_embedder() -> SentenceTransformer:
    """获取全局嵌入模型（懒加载单例）"""
    global _embedder
    if _embedder is None:
        logger.info("loading_embedding_model", model="BAAI/bge-m3")
        _embedder = SentenceTransformer("BAAI/bge-m3")
        logger.info("embedding_model_loaded")
    return _embedder


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量嵌入文本"""
    embedder = get_embedder()
    embeddings = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


async def embed_query(text: str) -> list[float]:
    """嵌入单条查询"""
    embedder = get_embedder()
    embedding = embedder.encode([text], normalize_embeddings=True, show_progress_bar=False)
    return embedding[0].tolist()
```

#### app/ai/rag/chunking.py

```python
from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    metadata: dict | None = None


class SmartChunker:

    @staticmethod
    def chunk_by_paragraphs(
        text: str,
        target_size: int = 400,
        overlap: int = 50,
    ) -> list[Chunk]:
        """按段落边界分块，合并过短段落，拆分过长段落"""
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 粗略估算：中文1字≈1token，英文4字符≈1token
            char_limit = target_size * 3  # 保守估计

            if len(current_chunk) + len(para) > char_limit:
                if current_chunk:
                    chunks.append(Chunk(text=current_chunk.strip()))
                # 保留overlap
                if overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-(overlap * 3):]
                    current_chunk = overlap_text + "\n\n" + para
                else:
                    current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para

        if current_chunk.strip():
            chunks.append(Chunk(text=current_chunk.strip()))

        return chunks
```

#### app/ai/rag/pipeline.py — RAG主管道（基础版）

```python
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text as sql_text

from app.ai.rag.chunking import SmartChunker, Chunk
from app.ai.rag.embedding import embed_texts, embed_query
from app.models.rag import DocumentChunk

logger = structlog.get_logger()


class RAGPipeline:
    """
    基础版RAG管道。
    Phase 1：单路向量检索。
    Sprint 8 扩展为混合检索（向量+关键词+RRF+Reranker）。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def ingest(self, source_text: str, source_type: str, source_id: str | None = None, metadata: dict | None = None) -> int:
        """数据摄入：分块 → 嵌入 → 存储"""
        # 1. 分块
        chunker = SmartChunker()
        chunks = chunker.chunk_by_paragraphs(source_text)

        if not chunks:
            return 0

        # 2. 批量嵌入
        texts = [c.text for c in chunks]
        embeddings = await embed_texts(texts)

        # 3. 存储到数据库
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            doc_chunk = DocumentChunk(
                source_type=source_type,
                source_id=source_id,
                chunk_index=i,
                content=chunk.text,
                embedding=embedding,
                metadata_=metadata or {},
            )
            self.db.add(doc_chunk)

        await self.db.flush()
        logger.info("rag_ingested", source_type=source_type, chunks=len(chunks))
        return len(chunks)

    async def retrieve(self, query: str, top_k: int = 5, subject: str | None = None) -> list[dict]:
        """检索：向量相似度搜索"""
        query_embedding = await embed_query(query)

        # 使用pgvector余弦距离检索
        # embedding <=> query_embedding 返回余弦距离
        sql = """
            SELECT id, content, source_type, source_id, metadata,
                   1 - (embedding <=> :query_vec::vector) as similarity
            FROM document_chunks
            WHERE embedding IS NOT NULL
        """
        params = {"query_vec": str(query_embedding)}

        if subject:
            sql += " AND subject = :subject"
            params["subject"] = subject

        sql += " ORDER BY embedding <=> :query_vec2::vector LIMIT :top_k"
        params["query_vec2"] = str(query_embedding)
        params["top_k"] = top_k

        result = await self.db.execute(sql_text(sql), params)
        rows = result.fetchall()

        return [
            {
                "id": str(row[0]),
                "content": row[1],
                "source_type": row[2],
                "source_id": row[3],
                "metadata": row[4],
                "similarity": float(row[5]),
            }
            for row in rows
        ]
```

### 3.3 网络检索模块

#### app/ai/web_search/searcher.py

```python
import httpx
import structlog
from dataclasses import dataclass

from app.config import settings

logger = structlog.get_logger()


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class WebSearcher:

    def __init__(self):
        self.api_key = settings.BING_SEARCH_API_KEY

    async def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        if not self.api_key:
            logger.warning("bing_api_key_not_configured")
            return []

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://api.bing.microsoft.com/v7.0/search",
                    headers={"Ocp-Apim-Subscription-Key": self.api_key},
                    params={"q": query, "count": num_results, "mkt": "zh-CN"},
                    timeout=10.0,
                )
                data = response.json()
                return [
                    SearchResult(
                        title=item["name"],
                        url=item["url"],
                        snippet=item.get("snippet", ""),
                    )
                    for item in data.get("webPages", {}).get("value", [])
                ]
            except Exception as e:
                logger.error("web_search_failed", error=str(e))
                return []
```

#### app/ai/web_search/scraper.py

```python
import httpx
import trafilatura
import structlog
from dataclasses import dataclass

logger = structlog.get_logger()


@dataclass
class ScrapedContent:
    url: str
    text: str
    title: str | None = None


class WebScraper:

    async def extract(self, url: str) -> ScrapedContent | None:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=15.0, follow_redirects=True)
                text = trafilatura.extract(
                    response.text,
                    include_comments=False,
                    include_tables=True,
                    favor_precision=True,
                )
                if not text:
                    return None
                return ScrapedContent(url=url, text=text)
            except Exception as e:
                logger.error("web_scrape_failed", url=url, error=str(e))
                return None
```

### 3.4 Prompt模板

#### app/ai/prompts/lecture.py

```python
LECTURE_GENERATION_PROMPT = """你是一位经验丰富的教育专家，正在为学生准备学习材料。

## 任务
根据以下信息，生成一份结构化的学习讲义。

## 知识点信息
- 主题：{topic}
- 知识点：{node_name}
- 难度等级：{difficulty}/5
- 学生水平：{student_level}

## 参考材料
{retrieved_context}

## 输出要求
请按以下结构输出Markdown格式讲义：

### 核心概念
（用简洁的语言解释核心概念，200-300字）

### 关键公式/定理
（列出相关的公式或定理，附证明思路或推导过程）

### 典型例题
（提供2-3道由浅入深的例题，每题附详细解答过程）

### 常见误区
（列出3-5个学生容易犯的错误或理解偏差）

### 知识关联
（说明本知识点与前后知识点的联系）

### 自我检测
（提供3道检测题，覆盖不同难度层次）

## 注意事项
- 使用中文，语言要清晰易懂
- 公式使用LaTeX格式（$...$ 行内，$$...$$ 块级）
- 如果参考材料不足以支撑某个部分，请基于你的知识补充，但标注[AI补充]
- 每个部分标注预估阅读时间
"""
```

### 3.5 讲义生成异步任务

#### app/tasks/celery_app.py

```python
from celery import Celery
from app.config import settings

celery_app = Celery(
    "qingyun",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5分钟超时
    task_soft_time_limit=240,
)
```

#### app/tasks/lecture_tasks.py

```python
import asyncio
import structlog
from app.tasks.celery_app import celery_app
from app.ai.prompts.lecture import LECTURE_GENERATION_PROMPT

logger = structlog.get_logger()


def run_async(coro):
    """在Celery任务中运行异步代码"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="generate_lecture")
def generate_lecture_task(self, lecture_id: str, user_id: str, topic: str, node_name: str = "", difficulty: int = 3):
    """异步生成讲义"""
    return run_async(_generate_lecture(self, lecture_id, user_id, topic, node_name, difficulty))


async def _generate_lecture(self, lecture_id, user_id, topic, node_name, difficulty):
    from app.database import async_session_factory
    from app.ai.llm_client import get_llm_client
    from app.ai.rag.pipeline import RAGPipeline
    from app.ai.web_search.searcher import WebSearcher
    from app.models.learning import Lecture
    from sqlalchemy import select
    import uuid

    logger.info("lecture_generation_started", lecture_id=lecture_id, topic=topic)

    async with async_session_factory() as db:
        try:
            # 1. RAG检索相关内容
            rag = RAGPipeline(db)
            context_results = await rag.retrieve(query=f"{topic} {node_name}", top_k=5)
            retrieved_context = "\n\n".join([r["content"][:500] for r in context_results])

            # 2. 网络搜索补充
            searcher = WebSearcher()
            web_results = await searcher.search(f"{topic} 教程", num_results=3)
            if web_results:
                retrieved_context += "\n\n## 网络参考\n"
                for r in web_results:
                    retrieved_context += f"- {r.title}: {r.snippet}\n"

            # 3. 构建Prompt
            prompt = LECTURE_GENERATION_PROMPT.format(
                topic=topic,
                node_name=node_name or topic,
                difficulty=difficulty,
                student_level="中等",
                retrieved_context=retrieved_context or "暂无参考材料，请基于你的知识生成。",
            )

            # 4. 调用LLM
            llm = get_llm_client()
            response = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4096,
            )

            # 5. 保存讲义
            result = await db.execute(select(Lecture).where(Lecture.id == uuid.UUID(lecture_id)))
            lecture = result.scalar_one_or_none()
            if lecture:
                lecture.content = response.content
                lecture.status = "generated"
                lecture.token_usage = response.usage.get("total_tokens", 0)
                await db.commit()

            logger.info("lecture_generation_completed", lecture_id=lecture_id)
            return {"lecture_id": lecture_id, "status": "generated", "token_usage": response.usage}

        except Exception as e:
            logger.error("lecture_generation_failed", lecture_id=lecture_id, error=str(e))
            # 更新状态为失败
            result = await db.execute(select(Lecture).where(Lecture.id == uuid.UUID(lecture_id)))
            lecture = result.scalar_one_or_none()
            if lecture:
                lecture.status = "failed"
                await db.commit()
            raise
```

### 3.6 学习模块服务与路由

#### app/services/learning_service.py（Phase 1基础版）

```python
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.learning import LearningRoute, LearningRouteStep, Lecture
from app.core.exceptions import NotFoundException


class LearningService:

    @staticmethod
    async def create_route(db: AsyncSession, user_id: uuid.UUID, topic: str, **kwargs) -> LearningRoute:
        """创建学习路线（Phase 1简化版：直接创建空路线，后续Sprint接入LLM+知识图谱）"""
        route = LearningRoute(
            user_id=user_id,
            topic=topic,
            description=kwargs.get("description", ""),
            estimated_hours=kwargs.get("available_hours"),
            metadata_=kwargs.get("preferences", {}),
        )
        db.add(route)
        await db.flush()
        await db.refresh(route)
        return route

    @staticmethod
    async def get_route(db: AsyncSession, route_id: uuid.UUID, user_id: uuid.UUID) -> LearningRoute:
        result = await db.execute(
            select(LearningRoute)
            .options(selectinload(LearningRoute.steps))
            .where(LearningRoute.id == route_id, LearningRoute.user_id == user_id)
        )
        route = result.scalar_one_or_none()
        if not route:
            raise NotFoundException("学习路线不存在")
        return route

    @staticmethod
    async def create_lecture(
        db: AsyncSession,
        user_id: uuid.UUID,
        route_id: uuid.UUID | None = None,
        step_id: uuid.UUID | None = None,
        node_id: uuid.UUID | None = None,
        title: str = "",
    ) -> Lecture:
        """创建讲义记录（状态为generating），然后触发异步任务"""
        lecture = Lecture(
            user_id=user_id,
            route_id=route_id,
            step_id=step_id,
            node_id=node_id,
            title=title,
            content="",
            status="generating",
        )
        db.add(lecture)
        await db.flush()
        await db.refresh(lecture)
        return lecture

    @staticmethod
    async def get_lecture(db: AsyncSession, lecture_id: uuid.UUID, user_id: uuid.UUID) -> Lecture:
        result = await db.execute(
            select(Lecture).where(Lecture.id == lecture_id, Lecture.user_id == user_id)
        )
        lecture = result.scalar_one_or_none()
        if not lecture:
            raise NotFoundException("讲义不存在")
        return lecture
```

#### app/api/v1/learning.py

```python
import uuid
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import MessageResponse
from app.services.learning_service import LearningService

router = APIRouter()


class RouteCreateRequest(BaseModel):
    topic: str
    goal: Optional[str] = None
    available_hours: Optional[float] = None
    current_level: Optional[str] = Field(None, pattern="^(beginner|intermediate|advanced)$")
    preferences: Optional[dict] = None


class LectureGenerateRequest(BaseModel):
    route_id: Optional[uuid.UUID] = None
    step_id: Optional[uuid.UUID] = None
    node_id: Optional[uuid.UUID] = None
    topic: str = ""
    custom_instructions: Optional[str] = None


@router.post("/routes")
async def create_route(
    body: RouteCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    route = await LearningService.create_route(
        db, user.id, body.topic,
        description=body.goal,
        available_hours=body.available_hours,
        preferences=body.preferences,
    )
    return {
        "id": str(route.id),
        "topic": route.topic,
        "status": route.status,
        "total_steps": route.total_steps,
        "steps": [],
    }


@router.get("/routes/{route_id}")
async def get_route(
    route_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    route = await LearningService.get_route(db, route_id, user.id)
    return {
        "id": str(route.id),
        "topic": route.topic,
        "description": route.description,
        "status": route.status,
        "total_steps": route.total_steps,
        "current_step": route.current_step,
        "estimated_hours": route.estimated_hours,
        "steps": [
            {
                "id": str(s.id),
                "step_order": s.step_order,
                "title": s.title,
                "description": s.description,
                "status": s.status,
                "estimated_minutes": s.estimated_minutes,
            }
            for s in sorted(route.steps, key=lambda x: x.step_order)
        ],
    }


@router.post("/lectures/generate")
async def generate_lecture(
    body: LectureGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 创建讲义记录
    lecture = await LearningService.create_lecture(
        db, user.id,
        route_id=body.route_id,
        step_id=body.step_id,
        node_id=body.node_id,
        title=body.topic or "未命名讲义",
    )

    # 触发异步任务
    from app.tasks.lecture_tasks import generate_lecture_task
    generate_lecture_task.delay(
        str(lecture.id),
        str(user.id),
        body.topic or "未命名主题",
    )

    return {"lecture_id": str(lecture.id), "status": "generating"}


@router.get("/lectures/{lecture_id}")
async def get_lecture(
    lecture_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lecture = await LearningService.get_lecture(db, lecture_id, user.id)
    return {
        "id": str(lecture.id),
        "title": lecture.title,
        "content": lecture.content,
        "status": lecture.status,
        "token_usage": lecture.token_usage,
        "created_at": lecture.created_at.isoformat(),
    }
```

### 3.7 WebSocket流式输出

#### app/api/v1/websocket.py

```python
import json
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.core.security import decode_token
from app.models.user import User
from sqlalchemy import select
import structlog

logger = structlog.get_logger()

router = APIRouter()


class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)

    async def send_json(self, client_id: str, data: dict):
        ws = self.active_connections.get(client_id)
        if ws:
            await ws.send_json(data)


manager = ConnectionManager()


async def verify_ws_token(websocket: WebSocket) -> str | None:
    """从WebSocket首条消息或URL参数中验证token"""
    # 从查询参数获取token
    token = websocket.query_params.get("token")
    if not token:
        return None
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except Exception:
        return None


@router.websocket("/ws/lecture-progress/{lecture_id}")
async def ws_lecture_progress(websocket: WebSocket, lecture_id: str):
    """讲义生成进度推送"""
    await websocket.accept()
    try:
        # Phase 1：简单实现，等待任务完成通知
        # 实际生产环境需通过Redis pub/sub接收Celery任务状态
        await websocket.send_json({
            "type": "progress",
            "data": {"stage": "generating", "percent": 0},
        })
        # 保持连接，等待关闭
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        logger.info("lecture_progress_ws_disconnected", lecture_id=lecture_id)


@router.websocket("/ws/notifications")
async def ws_notifications(websocket: WebSocket):
    """系统通知推送"""
    user_id = await verify_ws_token(websocket)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        logger.info("notifications_ws_disconnected", user_id=user_id)
```

### 3.8 更新路由和main.py

更新 `app/api/v1/router.py`：

```python
from fastapi import APIRouter
from app.api.v1 import auth, users, notes, tags, learning, websocket

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户"])
api_router.include_router(notes.router, prefix="/notes", tags=["笔记"])
api_router.include_router(tags.router, tags=["标签"])
api_router.include_router(learning.router, prefix="/learning", tags=["学习"])
api_router.include_router(websocket.router, tags=["WebSocket"])
```

### 3.9 Sprint 3 验收标准

- [ ] LLMClient能成功调用DeepSeek API返回结果
- [ ] BGE-M3嵌入模型加载成功，embed_texts返回正确维度向量（1024维）
- [ ] RAGPipeline.ingest 能将文本分块、嵌入、存入document_chunks表
- [ ] RAGPipeline.retrieve 能通过向量检索返回相似内容
- [ ] `POST /api/v1/learning/routes` 创建学习路线
- [ ] `POST /api/v1/learning/lectures/generate` 触发异步讲义生成，返回lecture_id
- [ ] Celery Worker能消费任务，调用LLM生成讲义内容并保存到数据库
- [ ] `GET /api/v1/learning/lectures/{id}` 获取生成完成的讲义
- [ ] WebSocket `/ws/lecture-progress/{id}` 连接成功，能接收进度消息
- [ ] WebSocket `/ws/notifications` 连接成功（需token认证）
- [ ] WebSearcher能调用Bing API（如配置了API Key）

---

## Sprint 4：用户记忆与画像

### 4.1 记忆子模块

#### app/services/memory/models.py

```python
import uuid
from pydantic import BaseModel
from typing import Optional


class MemoryEntry(BaseModel):
    """记忆条目 — 轻量Pydantic模型"""
    id: uuid.UUID
    memory_type: str          # knowledge / habit / preference
    topic: str
    summary: str              # 索引层摘要（≤100 token）
    relevance_score: float = 0.0
    full_data: Optional[dict] = None


class HabitSummary(BaseModel):
    """个人习惯摘要（Push模式，嵌入system prompt）"""
    text: str                 # 200-300 token的摘要文本
    weak_nodes: list[str] = []
    token_count: int = 0
```

#### app/services/memory/repository.py

```python
import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import MemoryIndex, MemoryFull
from app.services.memory.models import MemoryEntry
from app.ai.rag.embedding import embed_query


class MemoryRepository:
    """记忆存储层 — 封装索引层和全量层的CRUD"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_index_by_topic(self, user_id: uuid.UUID, topic: str, top_k: int = 5) -> list[MemoryEntry]:
        """索引层精确/模糊主题匹配"""
        result = await self.db.execute(
            select(MemoryIndex)
            .where(
                MemoryIndex.user_id == user_id,
                MemoryIndex.topic.ilike(f"%{topic}%"),
            )
            .order_by(MemoryIndex.relevance_score.desc())
            .limit(top_k)
        )
        rows = result.scalars().all()
        return [
            MemoryEntry(
                id=r.id,
                memory_type=r.memory_type,
                topic=r.topic,
                summary=r.summary,
                relevance_score=r.relevance_score or 0.0,
            )
            for r in rows
        ]

    async def search_index_by_vector(self, user_id: uuid.UUID, query_embedding: list[float], top_k: int = 5) -> list[MemoryEntry]:
        """索引层向量检索"""
        sql = """
            SELECT id, memory_type, topic, summary, relevance_score, full_memory_id,
                   1 - (embedding <=> :query_vec::vector) as similarity
            FROM memory_index
            WHERE user_id = :user_id AND embedding IS NOT NULL
            ORDER BY embedding <=> :query_vec2::vector
            LIMIT :top_k
        """
        result = await self.db.execute(
            sql,
            {
                "query_vec": str(query_embedding),
                "user_id": str(user_id),
                "query_vec2": str(query_embedding),
                "top_k": top_k,
            },
        )
        rows = result.fetchall()
        return [
            MemoryEntry(
                id=row[0],
                memory_type=row[1],
                topic=row[2],
                summary=row[3],
                relevance_score=float(row[4] or 0),
            )
            for row in rows
        ]

    async def load_full(self, full_ids: list[uuid.UUID]) -> list[MemoryEntry]:
        """全量层批量加载"""
        if not full_ids:
            return []
        result = await self.db.execute(
            select(MemoryFull).where(MemoryFull.id.in_(full_ids))
        )
        rows = result.scalars().all()
        return [
            MemoryEntry(
                id=r.id,
                memory_type=r.memory_type,
                topic=r.topic,
                summary="",
                full_data=r.content,
            )
            for r in rows
        ]

    async def upsert_full(self, memory_type: str, topic: str, content: dict, source_records: list | None = None) -> uuid.UUID:
        """创建或更新全量记忆"""
        # 查找是否已存在
        result = await self.db.execute(
            select(MemoryFull).where(
                MemoryFull.memory_type == memory_type,
                MemoryFull.topic == topic,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.content = content
            if source_records:
                existing.source_records = source_records
            await self.db.flush()
            return existing.id
        else:
            new_record = MemoryFull(
                memory_type=memory_type,
                topic=topic,
                content=content,
                source_records=source_records or [],
            )
            self.db.add(new_record)
            await self.db.flush()
            return new_record.id

    async def upsert_index(self, user_id: uuid.UUID, memory_type: str, topic: str, summary: str, full_memory_id: uuid.UUID | None = None):
        """创建或更新索引条目（含embedding）"""
        # 生成embedding
        embedding = await embed_query(summary)

        # 查找是否已存在
        result = await self.db.execute(
            select(MemoryIndex).where(
                MemoryIndex.user_id == user_id,
                MemoryIndex.memory_type == memory_type,
                MemoryIndex.topic == topic,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.summary = summary
            existing.embedding = embedding
            existing.full_memory_id = full_memory_id
            await self.db.flush()
        else:
            new_entry = MemoryIndex(
                user_id=user_id,
                memory_type=memory_type,
                topic=topic,
                summary=summary,
                embedding=embedding,
                full_memory_id=full_memory_id,
            )
            self.db.add(new_entry)
            await self.db.flush()
```

#### app/services/memory/user_memory.py

```python
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserProfile, PersonalHabitProfile
from app.models.knowledge import UserKnowledgeMastery
from app.services.memory.repository import MemoryRepository
from app.services.memory.models import MemoryEntry
from app.ai.rag.embedding import embed_query
import structlog

logger = structlog.get_logger()


class UserMemory:
    """
    用户记忆对象 — AI通过AgentLoop直接调用的统一接口。
    """

    def __init__(self, user_id: uuid.UUID, db: AsyncSession):
        self.user_id = user_id
        self.db = db
        self.repo = MemoryRepository(db)
        self._index_cache: dict[str, MemoryEntry] | None = None

    # ---------- 推送部分：个人习惯摘要 ----------

    async def get_habit_summary(self) -> str:
        """返回200-300 token的个人习惯摘要，嵌入system prompt"""
        result = await self.db.execute(
            select(PersonalHabitProfile).where(PersonalHabitProfile.user_id == self.user_id)
        )
        profile = result.scalar_one_or_none()

        if profile and profile.summary_cache:
            return profile.summary_cache

        # 无缓存，实时生成
        summary = await self._build_habit_summary()
        if profile:
            profile.summary_cache = summary
        else:
            profile = PersonalHabitProfile(user_id=self.user_id, summary_cache=summary)
            self.db.add(profile)
        await self.db.flush()
        return summary

    async def _build_habit_summary(self) -> str:
        """生成个人习惯摘要文本（严格控制在300 token以内）"""
        result = await self.db.execute(
            select(PersonalHabitProfile).where(PersonalHabitProfile.user_id == self.user_id)
        )
        profile = result.scalar_one_or_none()

        result2 = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == self.user_id)
        )
        base = result2.scalar_one_or_none()

        parts = []
        if profile:
            if profile.active_time_slot:
                parts.append(f"活跃时段：{profile.active_time_slot}")
            if profile.content_preference:
                parts.append(f"内容偏好：{profile.content_preference}")
            if profile.avg_session_minutes:
                parts.append(f"单次学习时长：{profile.avg_session_minutes}分钟")
            parts.append(f"回答详略：{profile.detail_preference or 'balanced'}")
            if profile.weak_node_names:
                parts.append(f"待加强：{'、'.join(profile.weak_node_names[:5])}")
        if base:
            parts.append(f"连续学习：{base.streak_days}天")

        return "用户画像：" + "；".join(parts) if parts else "用户画像：暂无数据"

    # ---------- 拉取部分：知识画像工具 ----------

    async def recall(self, topic: str, depth: str = "summary") -> str:
        """
        AI主动回忆知识内容。
        depth="summary" → 索引层摘要
        depth="detail"  → 全量层完整数据
        """
        results = await self.repo.search_index_by_topic(self.user_id, topic, top_k=5)
        if not results:
            # 尝试向量检索
            query_emb = await embed_query(topic)
            results = await self.repo.search_index_by_vector(self.user_id, query_emb, top_k=5)

        if not results:
            return f"未找到与'{topic}'相关的学习记忆。"

        if depth == "summary":
            return "\n".join([f"- [{r.topic}] {r.summary}" for r in results])

        # depth="detail"
        full_ids = []
        # 需要获取full_memory_id
        for r in results:
            idx_result = await self.db.execute(
                select(MemoryIndex).where(MemoryIndex.id == r.id)
            )
            idx = idx_result.scalar_one_or_none()
            if idx and idx.full_memory_id:
                full_ids.append(idx.full_memory_id)

        full_records = await self.repo.load_full(full_ids)
        if not full_records:
            return "\n".join([f"- [{r.topic}] {r.summary}" for r in results])

        parts = []
        for rec in full_records:
            parts.append(f"### {rec.topic}\n")
            if rec.full_data:
                import json
                parts.append(json.dumps(rec.full_data, ensure_ascii=False, indent=2)[:1500])
        return "\n".join(parts)[:4000]  # 限制总长度

    async def search_memory(self, query: str, top_k: int = 5) -> str:
        """语义搜索记忆"""
        query_embedding = await embed_query(query)
        results = await self.repo.search_index_by_vector(self.user_id, query_embedding, top_k=top_k)
        if not results:
            return "未找到相关记忆。"
        return "\n".join([f"- [{r.topic}] {r.summary} (相关度: {r.relevance_score:.2f})" for r in results])

    # ---------- 写入部分 ----------

    async def update(self, memory_type: str, data: dict) -> bool:
        """学习事件后更新索引层+全量层"""
        topic = data.get("topic", "")
        if not topic:
            return False

        # 1. 更新全量层
        full_id = await self.repo.upsert_full(
            memory_type=memory_type,
            topic=topic,
            content=data,
        )

        # 2. 生成摘要，更新索引层
        summary = self._generate_summary(memory_type, data)
        await self.repo.upsert_index(self.user_id, memory_type, topic, summary, full_id)

        # 3. 知识更新时刷新薄弱知识点
        if memory_type == "knowledge":
            await self._refresh_weak_nodes()

        # 4. 清缓存
        self._index_cache = None
        return True

    async def load_index(self):
        """会话初始化时加载索引层到内存"""
        from app.models.memory import MemoryIndex
        result = await self.db.execute(
            select(MemoryIndex).where(MemoryIndex.user_id == self.user_id)
        )
        self._index_cache = {r.topic: MemoryEntry(
            id=r.id, memory_type=r.memory_type, topic=r.topic, summary=r.summary
        ) for r in result.scalars().all()}

    def _generate_summary(self, memory_type: str, data: dict) -> str:
        """为索引层生成简洁摘要（≤100 token）"""
        topic = data.get("topic", "未知")
        if memory_type == "knowledge":
            mastery = data.get("mastery_score", 0)
            level = "已掌握" if mastery > 0.7 else "学习中" if mastery > 0.3 else "薄弱"
            return f"{topic}: {level}, mastery={mastery:.2f}"
        elif memory_type == "habit":
            return f"{topic}: {data.get('description', '')}"
        return f"{topic}: {str(data)[:100]}"

    async def _refresh_weak_nodes(self):
        """重新计算薄弱知识点名称列表"""
        result = await self.db.execute(
            select(UserKnowledgeMastery)
            .where(
                UserKnowledgeMastery.user_id == self.user_id,
                UserKnowledgeMastery.mastery_score < 0.4,
            )
            .order_by(UserKnowledgeMastery.mastery_score.asc())
            .limit(10)
        )
        weak_mastery = result.scalars().all()

        # 获取知识点名称
        from app.models.knowledge import KnowledgeNode
        weak_names = []
        for m in weak_mastery:
            node_result = await self.db.execute(
                select(KnowledgeNode.name).where(KnowledgeNode.id == m.node_id)
            )
            name = node_result.scalar_one_or_none()
            if name:
                weak_names.append(name)

        # 更新到personal_habit_profile
        profile_result = await self.db.execute(
            select(PersonalHabitProfile).where(PersonalHabitProfile.user_id == self.user_id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile:
            profile.weak_node_names = weak_names
            profile.summary_cache = None  # 清除缓存，下次重新生成
            await self.db.flush()
```

### 4.2 用户记忆服务 — app/services/user_memory_service.py

```python
import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserProfile, PersonalHabitProfile
from app.models.knowledge import UserKnowledgeMastery
from app.models.memory import MemoryIndex, MemoryFull
from app.services.memory.user_memory import UserMemory
from app.services.memory.repository import MemoryRepository


class UserMemoryService:
    """用户记忆服务 — 业务逻辑层"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_memory(self, user_id: uuid.UUID) -> UserMemory:
        """获取用户的UserMemory对象（供Agent调用）"""
        memory = UserMemory(user_id, self.db)
        await memory.load_index()
        return memory

    async def update_knowledge_mastery(
        self,
        user_id: uuid.UUID,
        node_id: uuid.UUID,
        mastery_score: float,
        correct: bool = False,
    ):
        """更新知识掌握度，同步更新记忆系统"""
        # 1. 更新user_knowledge_mastery
        result = await self.db.execute(
            select(UserKnowledgeMastery).where(
                UserKnowledgeMastery.user_id == user_id,
                UserKnowledgeMastery.node_id == node_id,
            )
        )
        mastery = result.scalar_one_or_none()

        if mastery:
            mastery.mastery_score = mastery_score
            mastery.total_count += 1
            if correct:
                mastery.correct_count += 1
        else:
            mastery = UserKnowledgeMastery(
                user_id=user_id,
                node_id=node_id,
                mastery_score=mastery_score,
                total_count=1,
                correct_count=1 if correct else 0,
            )
            self.db.add(mastery)

        await self.db.flush()

        # 2. 获取知识点名称
        from app.models.knowledge import KnowledgeNode
        node_result = await self.db.execute(select(KnowledgeNode).where(KnowledgeNode.id == node_id))
        node = node_result.scalar_one_or_none()
        node_name = node.name if node else str(node_id)

        # 3. 同步更新记忆系统
        memory = UserMemory(user_id, self.db)
        await memory.update("knowledge", {
            "topic": node_name,
            "node_id": str(node_id),
            "mastery_score": mastery_score,
            "total_count": mastery.total_count,
            "correct_count": mastery.correct_count,
        })

    async def update_learning_behavior(self, user_id: uuid.UUID, duration_seconds: int, activity_type: str):
        """更新学习行为统计"""
        result = await self.db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        profile = result.scalar_one_or_none()
        if profile:
            profile.total_study_hours += duration_seconds / 3600.0
            from datetime import datetime
            profile.last_active_at = datetime.utcnow()
            await self.db.flush()

        # 更新个人习惯画像
        habit_result = await self.db.execute(
            select(PersonalHabitProfile).where(PersonalHabitProfile.user_id == user_id)
        )
        habit = habit_result.scalar_one_or_none()
        if habit:
            # 简单更新平均时长
            if habit.avg_session_minutes:
                habit.avg_session_minutes = (habit.avg_session_minutes + duration_seconds // 60) // 2
            else:
                habit.avg_session_minutes = duration_seconds // 60
            # 清除摘要缓存
            habit.summary_cache = None
            await self.db.flush()

    async def get_mastery_summary(self, user_id: uuid.UUID) -> dict:
        """获取知识掌握度统计"""
        result = await self.db.execute(
            select(UserKnowledgeMastery).where(UserKnowledgeMastery.user_id == user_id)
        )
        all_mastery = result.scalars().all()

        total = len(all_mastery)
        mastered = sum(1 for m in all_mastery if m.mastery_score > 0.7)
        learning = sum(1 for m in all_mastery if 0.3 < m.mastery_score <= 0.7)
        not_started = total - mastered - learning

        return {
            "total_nodes": total,
            "mastered": mastered,
            "learning": learning,
            "not_started": not_started,
        }
```

### 4.3 完善用户画像API

更新 `app/api/v1/users.py` 的 `get_profile` 端点：

```python
@router.get("/me/profile")
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.user_memory_service import UserMemoryService
    service = UserMemoryService(db)
    mastery_summary = await service.get_mastery_summary(user.id)

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()

    return {
        "mastery_summary": mastery_summary,
        "recent_activity": [],  # Sprint 4 暂不返回，后续补充
        "streak_days": profile.streak_days if profile else 0,
        "total_study_hours": profile.total_study_hours if profile else 0.0,
    }
```

### 4.4 个性化知识梳理

在 `app/api/v1/learning.py` 中添加个性化知识梳理端点：

```python
from app.ai.prompts.summary import PERSONALIZED_SUMMARY_PROMPT


class PersonalizedSummaryRequest(BaseModel):
    lecture_id: uuid.UUID
    node_id: Optional[uuid.UUID] = None


@router.post("/personalized-summary")
async def generate_personalized_summary(
    body: PersonalizedSummaryRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """基于用户知识画像裁剪和增强讲义"""
    from app.services.learning_service import LearningService
    from app.services.user_memory_service import UserMemoryService

    # 获取原始讲义
    lecture = await LearningService.get_lecture(db, body.lecture_id, user.id)

    # 获取用户记忆
    memory_service = UserMemoryService(db)
    memory = await memory_service.get_user_memory(user.id)
    habit_summary = await memory.get_habit_summary()

    # 获取知识掌握情况
    mastery_info = ""
    if body.node_id:
        recall_result = await memory.recall(lecture.title, depth="summary")
        mastery_info = recall_result

    # 构建个性化Prompt
    from app.ai.llm_client import get_llm_client
    llm = get_llm_client()

    prompt = PERSONALIZED_SUMMARY_PROMPT.format(
        original_content=lecture.content[:3000],
        user_profile=habit_summary,
        mastery_info=mastery_info or "暂无掌握度数据",
    )

    # 创建新的个性化讲义
    personal_lecture = await LearningService.create_lecture(
        db, user.id,
        title=f"[个性化] {lecture.title}",
    )

    # 异步生成
    from app.tasks.lecture_tasks import generate_personalized_summary_task
    generate_personalized_summary_task.delay(
        str(personal_lecture.id),
        prompt,
    )

    return {"lecture_id": str(personal_lecture.id), "status": "generating"}
```

#### app/ai/prompts/summary.py

```python
PERSONALIZED_SUMMARY_PROMPT = """你是一位个性化学习助手。请根据学生的知识掌握情况，对以下讲义进行个性化裁剪和增强。

## 原始讲义内容
{original_content}

## 学生学习画像
{user_profile}

## 学生知识掌握情况
{mastery_info}

## 要求
1. 对于学生已掌握的知识点，简要回顾即可
2. 对于学生薄弱的知识点，增加详细解释和更多例题
3. 补充学生可能遗漏的前置知识
4. 使用学生偏好的内容形式（如图文/交互）
5. 保持Markdown格式，公式用LaTeX
"""
```

在 `app/tasks/lecture_tasks.py` 中添加：

```python
@celery_app.task(bind=True, name="generate_personalized_summary")
def generate_personalized_summary_task(self, lecture_id: str, prompt: str):
    """异步生成个性化知识梳理"""
    return run_async(_generate_summary(self, lecture_id, prompt))


async def _generate_summary(self, lecture_id, prompt):
    from app.database import async_session_factory
    from app.ai.llm_client import get_llm_client
    from app.models.learning import Lecture
    from sqlalchemy import select
    import uuid

    async with async_session_factory() as db:
        try:
            llm = get_llm_client()
            response = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=4096,
            )

            result = await db.execute(select(Lecture).where(Lecture.id == uuid.UUID(lecture_id)))
            lecture = result.scalar_one_or_none()
            if lecture:
                lecture.content = response.content
                lecture.status = "personalized"
                lecture.token_usage = response.usage.get("total_tokens", 0)
                await db.commit()

            return {"lecture_id": lecture_id, "status": "personalized"}
        except Exception as e:
            logger.error("personalized_summary_failed", lecture_id=lecture_id, error=str(e))
            raise
```

### 4.5 Sprint 4 验收标准

- [ ] `UserMemory.get_habit_summary()` 返回200-300 token的习惯摘要
- [ ] `UserMemory.recall("某知识点")` 返回索引层摘要
- [ ] `UserMemory.recall("某知识点", depth="detail")` 返回全量层详情
- [ ] `UserMemory.search_memory("语义查询")` 返回向量匹配结果
- [ ] `UserMemory.update("knowledge", {...})` 同步更新索引层+全量层
- [ ] `UserMemoryService.update_knowledge_mastery()` 更新掌握度并同步记忆
- [ ] `GET /api/v1/users/me/profile` 返回正确的掌握度统计
- [ ] `POST /api/v1/learning/personalized-summary` 触发个性化梳理异步任务
- [ ] 端到端测试：注册→创建笔记→生成讲义→查看个性化梳理结果

---

## Phase 1 整体验收

完成全部4个Sprint后，以下端到端流程应全部跑通：

1. **用户注册登录**：注册→登录→获取token→访问受保护接口
2. **笔记管理**：创建笔记→搜索→添加标签→更新→删除
3. **AI生成讲义**：创建学习路线→触发讲义生成→Celery异步处理→获取生成结果
4. **用户画像**：查看掌握度统计→习惯摘要生成→知识记忆检索
5. **个性化梳理**：基于讲义+用户画像→生成个性化学习材料
6. **基础设施**：Docker环境正常→数据库迁移成功→Meilisearch索引正常→WebSocket连接正常

### 技术债记录（Phase 2解决）

- Meilisearch笔记搜索在Sprint 2用LIKE，Sprint 3后替换为Meilisearch
- 学习路线生成在Phase 1为简化版（空路线），Sprint 5接入LLM+知识图谱
- RAG管道Phase 1为单路向量检索，Sprint 8扩展混合检索+Reranker
- 多模型适配Phase 1仅DeepSeek，Sprint 9接入通义千问、Claude
- Agent编排模块Phase 1不实现，Sprint 10完成
- 复习系统Phase 1不实现，Sprint 7完成
