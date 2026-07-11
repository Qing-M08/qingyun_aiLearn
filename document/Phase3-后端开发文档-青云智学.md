# 青云智学 — Phase 3 后端开发文档

> 版本：1.0
> 日期：2026-07-10
> 前置依赖：Phase 1-2 后端已完成（Sprint 1-7），Sprint 8（讲义→笔记打通）已完成
> 配套文档：`青云智学-后端开发文档.md`（Phase 1-2 全量基线）、`Phase3-前端开发文档-青云智学.md`
> 用途：本文档供 AI 编程助手作为 Phase 3 后端开发参考。AI 应严格按照本文档的规范进行代码生成。

---

## 1. Phase 3 概述

### 1.1 背景

Phase 1-2 已完成全部基础搭建和核心功能：认证、笔记 CRUD、学习路线生成、讲义生成、苏格拉底答疑、复习系统、用户记忆与画像。Sprint 8（讲义→笔记打通）已完成，讲义生成后自动创建笔记并跳转编辑页。

Phase 3 后端的核心目标：

1. **Agent 编排模块完整实现**：在已有 ToolSchema/ToolRegistry/AgentLoop 骨架基础上，升级为会话制（Session-based）架构，支持上下文注入、消息持久化、取消生成、工具调用分步推送等，与前端 Agent 页面和笔记页面 Agent 集成完全对接。
2. **搜索增强**：全局搜索 API（带高亮片段和分面统计）、语义搜索 API、知识节点关联内容 API。
3. **各业务服务 Tool 化**：为笔记、学习、答疑、复习、搜索、用户记忆六个服务实现 `as_tools()` 工具接口和 handler，供 Agent 调用。

### 1.2 与前端文档的对齐说明

本文档的 API 设计已与 `Phase3-前端开发文档-青云智学.md` 完全对齐，包括：

- Agent REST API：会话 CRUD + 消息收发 + 取消 + 工具列表
- Agent WebSocket：`/ws/agent/{session_id}` 路径携带 session_id，7 种消息类型（thinking / tool_call_start / tool_call_result / token / done / error / session_created）
- 搜索 API：`GET /search/global`（高亮 + 分面）、`GET /search/semantic`、`GET /knowledge/nodes/{id}/relation`

### 1.3 开发顺序

| Sprint | 主题 | 预计周期 | 优先级 |
|--------|------|----------|--------|
| Sprint 8 | 搜索增强（全局搜索 + 知识关联 API） | 第 1 周 | P2 |
| Sprint 9 | 各服务 Tool 化 + Agent 服务层 | 第 2 周 | P1 |
| Sprint 10 | Agent 编排层升级 + WebSocket 协议 | 第 3 周 | P1 |
| Sprint 11 | 端到端联调 + 部署准备 | 第 4 周 | P1 |

> 说明：Sprint 8 搜索增强无前端依赖，可先行。Sprint 9-10 的 Agent 模块需与前端 Sprint 11 同步联调。

### 1.4 Phase 3 新增/修改文件清单

```
app/
├── models/
│   ├── agent_session.py              # 【新增】Agent 会话 ORM 模型
│   └── agent_message.py              # 【新增】Agent 消息 ORM 模型
├── schemas/
│   └── agent.py                      # 【新增】Agent Pydantic Schema
├── services/
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── agent_service.py          # 【新增】Agent 服务层（会话管理、消息处理）
│   │   ├── agent_loop.py             # 【修改】Agent 循环核心（升级：会话绑定、取消、分步工具推送）
│   │   ├── tool_schemas.py           # 【已有】工具 Schema 定义（Phase 1-2 已定义）
│   │   ├── tool_registry.py          # 【已有】工具注册表（Phase 1-2 已定义）
│   │   └── context_builder.py        # 【新增】上下文构建器（根据 context_type 注入上下文）
│   ├── note.py                       # 【修改】新增 as_tools() + handler
│   ├── learning.py                   # 【修改】新增 as_tools() + handler
│   ├── qa.py                         # 【修改】新增 as_tools() + handler
│   ├── review.py                     # 【修改】新增 as_tools() + handler
│   ├── search.py                     # 【修改】新增 as_tools() + handler + 全局搜索增强
│   └── user_memory.py                # 【修改】新增 as_tools() + handler
├── api/v1/
│   ├── agent.py                      # 【新增】Agent REST + WebSocket 路由
│   └── search.py                     # 【修改】新增全局搜索、语义搜索、知识关联路由
├── ai/prompts/
│   └── agent.py                      # 【修改】升级 Agent system prompt（上下文感知）
├── core/
│   └── cancel_token.py               # 【新增】取消令牌管理（Redis-based）
└── alembic/versions/
    └── xxx_add_agent_tables.py       # 【新增】Agent 表迁移脚本
```

---

## 2. 新增数据库 Schema

### 2.1 agent_sessions 表

```sql
CREATE TABLE agent_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           VARCHAR(200),                    -- 会话标题（自动生成或用户自定义）
    context_type    VARCHAR(20) NOT NULL DEFAULT 'general'
                    CHECK (context_type IN ('general', 'note', 'lecture', 'route')),
    context_id      UUID,                            -- 关联的笔记/讲义/路线 ID（通用字段，不建外键）
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'closed')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_agent_sessions_user_status ON agent_sessions(user_id, status);
CREATE INDEX idx_agent_sessions_user_updated ON agent_sessions(user_id, updated_at DESC);
CREATE INDEX idx_agent_sessions_context ON agent_sessions(context_type, context_id)
    WHERE context_id IS NOT NULL;
```

### 2.2 agent_messages 表

```sql
CREATE TABLE agent_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL
                    CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL DEFAULT '',
    tool_calls      JSONB NOT NULL DEFAULT '[]',     -- 工具调用记录（仅 assistant 消息有）
    metadata        JSONB NOT NULL DEFAULT '{}',     -- 扩展元数据（token 消耗、步数等）
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_agent_messages_session_created ON agent_messages(session_id, created_at);
CREATE INDEX idx_agent_messages_session_role ON agent_messages(session_id, role);
```

**tool_calls JSONB 结构：**

```json
[
  {
    "id": "tc_abc123",
    "tool_name": "search_knowledge",
    "tool_display_name": "搜索知识图谱",
    "input": {"query": "二次函数"},
    "output": "找到 3 个相关知识点...",
    "status": "success",
    "error_message": null,
    "started_at": "2026-07-10T10:00:00Z",
    "completed_at": "2026-07-10T10:00:02Z"
  }
]
```

**metadata JSONB 结构（assistant 消息）：**

```json
{
  "total_steps": 3,
  "tokens_used": 1850,
  "model": "deepseek-v3",
  "finish_reason": "stop"
}
```

### 2.3 Alembic 迁移脚本

```python
# alembic/versions/20260710_add_agent_tables.py

def upgrade():
    op.create_table(
        'agent_sessions',
        sa.Column('id', sa.dialects.postgresql.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.dialects.postgresql.UUID(), nullable=False),
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('context_type', sa.String(20), nullable=False, server_default='general'),
        sa.Column('context_id', sa.dialects.postgresql.UUID(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("context_type IN ('general', 'note', 'lecture', 'route')"),
        sa.CheckConstraint("status IN ('active', 'closed')"),
    )
    op.create_index('idx_agent_sessions_user_status', 'agent_sessions', ['user_id', 'status'])
    op.create_index('idx_agent_sessions_user_updated', 'agent_sessions', ['user_id', sa.text('updated_at DESC')])
    op.create_index('idx_agent_sessions_context', 'agent_sessions', ['context_type', 'context_id'],
                     postgresql_where=sa.text("context_id IS NOT NULL"))

    op.create_table(
        'agent_messages',
        sa.Column('id', sa.dialects.postgresql.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('session_id', sa.dialects.postgresql.UUID(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False, server_default=''),
        sa.Column('tool_calls', sa.dialects.postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('metadata', sa.dialects.postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['agent_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')"),
    )
    op.create_index('idx_agent_messages_session_created', 'agent_messages', ['session_id', 'created_at'])
    op.create_index('idx_agent_messages_session_role', 'agent_messages', ['session_id', 'role'])


def downgrade():
    op.drop_table('agent_messages')
    op.drop_table('agent_sessions')
```

---

## 3. 新增 ORM 模型

### 3.1 AgentSession 模型

```python
# app/models/agent_session.py

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Index, CheckConstraint, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=True)
    context_type = Column(String(20), nullable=False, default="general")
    context_id = Column(UUID(as_uuid=True), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    messages = relationship("AgentMessage", back_populates="session", cascade="all, delete-orphan",
                            order_by="AgentMessage.created_at")

    __table_args__ = (
        CheckConstraint("context_type IN ('general', 'note', 'lecture', 'route')"),
        CheckConstraint("status IN ('active', 'closed')"),
        Index("idx_agent_sessions_user_status", "user_id", "status"),
        Index("idx_agent_sessions_user_updated", "user_id", text("updated_at DESC")),
        Index("idx_agent_sessions_context", "context_type", "context_id",
              postgresql_where=text("context_id IS NOT NULL")),
    )
```

### 3.2 AgentMessage 模型

```python
# app/models/agent_message.py

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False, default="")
    tool_calls = Column(JSONB, nullable=False, default=list)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # 关系
    session = relationship("AgentSession", back_populates="messages")

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')"),
        Index("idx_agent_messages_session_created", "session_id", "created_at"),
        Index("idx_agent_messages_session_role", "session_id", "role"),
    )
```

---

## 4. Agent 编排层实现

> 本章在 Phase 1-2 已有的 `tool_schemas.py`、`tool_registry.py`、`agent_loop.py` 基础上进行升级。已有部分保持不变的不再重复，仅列出变更和新增。

### 4.1 工具 Schema 定义 (agent/tool_schemas.py) — 保持不变

Phase 1-2 已定义的 `ToolParameter`、`ToolSchema`、`ToolResult` 三个类保持不变。此处补充工具显示名称字段，供前端展示：

```python
# app/services/agent/tool_schemas.py — 新增字段

class ToolSchema(BaseModel):
    name: str                          # 工具唯一标识，如 "search_knowledge"
    display_name: str = ""             # 【新增】工具显示名称，如 "搜索知识图谱"
    description: str                   # AI 可读的功能描述
    parameters: dict[str, ToolParameter]
    category: str = "read"             # "read" | "write" — 控制权限和限流
    module: str = ""                   # 来源服务模块名
    icon: str = "search"               # 【新增】图标名称（对应 Ant Design icon）
```

### 4.2 工具注册表 (agent/tool_registry.py) — 保持不变

Phase 1-2 已定义的 `ToolRegistry` 和 `init_tool_registry()` 保持不变。各服务的 `as_tools()` 注册逻辑不变。

### 4.3 Agent 循环核心 (agent/agent_loop.py) — 升级

升级要点：

1. 绑定 session_id，消息持久化到 agent_messages 表
2. 工具调用拆分为 `tool_call_start` + `tool_call_result` 两条 WS 消息
3. 支持取消令牌（cancel_token），前端可通过 API 中断生成
4. 上下文注入（根据 session 的 context_type/context_id 自动注入相关上下文）
5. 流式 token 推送（复用现有 LLM stream 能力）

```python
# app/services/agent/agent_loop.py

import uuid
from datetime import datetime
from typing import AsyncGenerator

class AgentLoop:
    """
    ReAct 模式 Agent 循环（Phase 3 升级版）。

    升级内容：
      - 绑定 AgentSession，消息持久化
      - 工具调用拆分为 start + result 两条 WS 消息
      - 支持取消令牌（Redis-based cancel token）
      - 上下文注入（根据 context_type 自动注入笔记/讲义/路线摘要）
      - 流式 token 推送

    安全控制（同 Phase 1-2）：
      - max_steps: 最大推理轮数（默认 6）
      - token_budget: 单次对话最大 token 消耗（默认 4000）
      - 写操作限流：category="write" 的工具每轮最多调用 1 次
    """

    def __init__(
        self,
        registry: ToolRegistry,
        llm_client: LLMClient,
        session: AgentSession,
        db: AsyncSession,
        ws: WebSocket | None = None,
        cancel_key: str | None = None,
        max_steps: int = 6,
        token_budget: int = 4000,
    ):
        self.registry = registry
        self.llm = llm_client
        self.session = session
        self.db = db
        self.ws = ws
        self.cancel_key = cancel_key       # Redis key，用于取消检测
        self.max_steps = max_steps
        self.token_budget = token_budget
        self.total_tokens_used = 0

    async def run(self, user_message: str, conversation_history: list[dict]) -> AgentMessage:
        """
        执行一次完整的 Agent 循环。
        返回持久化后的 assistant AgentMessage。
        """
        user_id = str(self.session.user_id)

        # 1. 加载用户记忆（Push 模式：习惯摘要注入 system prompt）
        memory_service = UserMemoryService(self.db)
        habit_summary = await memory_service.get_habit_summary(user_id)

        # 2. 构建上下文（根据 context_type 注入相关内容）
        context_text = await self._build_context()

        # 3. 构建 system prompt
        system_prompt = self._build_system_prompt(habit_summary, context_text)

        # 4. 初始化消息上下文
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        # 5. 推送 thinking 事件
        await self._push_ws("thinking", {"content": "正在分析您的问题..."})

        # 6. ReAct 循环
        all_tool_calls = []
        final_answer = ""
        step = 0

        for step in range(self.max_steps):
            # 检查取消
            if await self._is_cancelled():
                await self._push_ws("done", {
                    "message": self._build_message_dict(
                        content="已取消生成。",
                        tool_calls=all_tool_calls,
                        step=step + 1,
                    )
                })
                return await self._save_assistant_message("已取消生成。", all_tool_calls, step + 1)

            # 检查 token 预算
            if self.total_tokens_used >= self.token_budget:
                final_answer = "已达到本次对话的 token 上限，以下是我目前的回答。"
                break

            # 调用 LLM
            response = await self.llm.chat(
                messages=messages,
                tools=self._format_tools_for_llm(),
                tool_choice="auto",
                stream=False,  # 先非流式判断是否需要工具调用
            )
            self.total_tokens_used += response.usage.total_tokens

            # 情况 A：LLM 决定调用工具
            if response.tool_calls:
                # 推送 thinking（工具调用前的思考）
                thinking_text = response.content or "让我使用工具来查找相关信息..."
                await self._push_ws("thinking", {"content": thinking_text})

                for tool_call in response.tool_calls:
                    tc_id = str(uuid.uuid4())
                    tc_start_time = datetime.utcnow()

                    # 推送 tool_call_start
                    tool_schema = self.registry.get_tool(tool_call.name)
                    await self._push_ws("tool_call_start", {
                        "tool_call_id": tc_id,
                        "tool_name": tool_call.name,
                        "tool_display_name": tool_schema.display_name if tool_schema else tool_call.name,
                        "input": tool_call.arguments,
                    })

                    # 执行工具
                    result = await self.registry.execute(tool_call.name, **tool_call.arguments)
                    self.total_tokens_used += result.token_count

                    tc_end_time = datetime.utcnow()

                    # 记录工具调用
                    tc_record = {
                        "id": tc_id,
                        "tool_name": tool_call.name,
                        "tool_display_name": tool_schema.display_name if tool_schema else tool_call.name,
                        "input": tool_call.arguments,
                        "output": result.data if result.success else None,
                        "status": "success" if result.success else "error",
                        "error_message": result.error_message,
                        "started_at": tc_start_time.isoformat() + "Z",
                        "completed_at": tc_end_time.isoformat() + "Z",
                    }
                    all_tool_calls.append(tc_record)

                    # 推送 tool_call_result
                    await self._push_ws("tool_call_result", {
                        "tool_call_id": tc_id,
                        "status": "success" if result.success else "error",
                        "output": result.data if result.success else None,
                        "error_message": result.error_message,
                    })

                    # 将工具结果注入上下文
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result.data if result.success else f"工具调用失败: {result.error_message}",
                    })

                continue  # 继续下一轮推理

            # 情况 B：LLM 给出最终回答
            else:
                final_answer = response.content
                break

        # 7. 循环结束
        if not final_answer:
            final_answer = "抱歉，我暂时无法完成这个请求，请尝试换一种方式提问。"

        # 8. 流式推送最终回答的 token（逐段推送）
        # 注意：如果 LLM 支持 stream 模式，上面的情况 B 可以直接用 stream
        # 这里为了简化，将最终回答一次性推送（前端拼接显示）
        await self._push_ws("token", {"content": final_answer})

        # 9. 持久化 assistant 消息
        assistant_msg = await self._save_assistant_message(final_answer, all_tool_calls, step + 1)

        # 10. 推送 done 事件
        await self._push_ws("done", {
            "message": self._message_to_dict(assistant_msg),
        })

        return assistant_msg

    async def _build_context(self) -> str:
        """根据 session 的 context_type 构建上下文文本"""
        if self.session.context_type == "general" or not self.session.context_id:
            return ""

        builder = ContextBuilder(self.db)
        return await builder.build_context(
            context_type=self.session.context_type,
            context_id=str(self.session.context_id),
            user_id=str(self.session.user_id),
        )

    async def _is_cancelled(self) -> bool:
        """检查取消令牌（Redis）"""
        if not self.cancel_key:
            return False
        redis = await get_redis()
        return await redis.get(self.cancel_key) is not None

    async def _save_assistant_message(
        self, content: str, tool_calls: list[dict], steps: int
    ) -> AgentMessage:
        """持久化 assistant 消息到数据库"""
        msg = AgentMessage(
            session_id=self.session.id,
            role="assistant",
            content=content,
            tool_calls=tool_calls,
            metadata_={
                "total_steps": steps,
                "tokens_used": self.total_tokens_used,
                "model": self.llm.model_name,
                "finish_reason": "stop",
            },
        )
        self.db.add(msg)

        # 更新 session 的 updated_at
        self.session.updated_at = datetime.utcnow()

        # 自动生成标题（取第一条用户消息的前 20 个字符）
        if not self.session.title:
            first_user_msg = await self.db.execute(
                select(AgentMessage).where(
                    AgentMessage.session_id == self.session.id,
                    AgentMessage.role == "user"
                ).order_by(AgentMessage.created_at).limit(1)
            )
            first_msg = first_user_msg.scalar_one_or_none()
            if first_msg:
                self.session.title = first_msg.content[:20] + ("..." if len(first_msg.content) > 20 else "")

        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    def _message_to_dict(self, msg: AgentMessage) -> dict:
        """将 AgentMessage ORM 对象转为前端期望的 dict"""
        return {
            "id": str(msg.id),
            "session_id": str(msg.session_id),
            "role": msg.role,
            "content": msg.content,
            "tool_calls": msg.tool_calls,
            "metadata": msg.metadata_,
            "created_at": msg.created_at.isoformat() + "Z",
        }

    def _build_system_prompt(self, habit_summary: str | None, context_text: str) -> str:
        """构建包含用户习惯和上下文的 system prompt"""
        return render_prompt("agent/system", {
            "habit_summary": habit_summary or "暂无用户习惯数据",
            "context_text": context_text or "无额外上下文",
            "tools": self.registry.get_all_schemas(),
            "current_time": datetime.utcnow().isoformat(),
        })

    def _format_tools_for_llm(self) -> list[dict]:
        """将 ToolSchema 转换为 LLM API 需要的 tools 格式"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            k: {"type": v.type, "description": v.description}
                            for k, v in t.parameters.items()
                        },
                        "required": [k for k, v in t.parameters.items() if v.required],
                    },
                },
            }
            for t in self.registry.get_all_schemas()
        ]

    async def _push_ws(self, event_type: str, data: dict):
        """通过 WebSocket 推送事件到前端"""
        if self.ws:
            await self.ws.send_json({"type": event_type, "data": data})
```

### 4.4 上下文构建器 (agent/context_builder.py)

```python
# app/services/agent/context_builder.py

class ContextBuilder:
    """
    根据 AgentSession 的 context_type 和 context_id，
    构建注入 system prompt 的上下文文本。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_context(self, context_type: str, context_id: str, user_id: str) -> str:
        if context_type == "note":
            return await self._build_note_context(context_id, user_id)
        elif context_type == "lecture":
            return await self._build_lecture_context(context_id)
        elif context_type == "route":
            return await self._build_route_context(context_id)
        return ""

    async def _build_note_context(self, note_id: str, user_id: str) -> str:
        """注入当前笔记的标题、内容摘要、标签、关联知识点"""
        result = await self.db.execute(
            select(Note).where(Note.id == note_id, Note.user_id == user_id)
        )
        note = result.scalar_one_or_none()
        if not note:
            return ""

        # 获取笔记标签
        tag_result = await self.db.execute(
            select(Tag.name).join(NoteTag).where(NoteTag.note_id == note.id)
        )
        tags = [row[0] for row in tag_result.fetchall()]

        # 截取笔记内容前 500 字作为上下文
        content_preview = note.content[:500] if note.content else ""

        return (
            f"## 当前上下文：笔记\n"
            f"- 标题：{note.title}\n"
            f"- 学科：{note.subject or '未分类'}\n"
            f"- 标签：{', '.join(tags) if tags else '无'}\n"
            f"- 内容摘要：\n{content_preview}\n"
        )

    async def _build_lecture_context(self, lecture_id: str) -> str:
        """注入讲义的标题、关联知识点、内容摘要"""
        result = await self.db.execute(
            select(Lecture).where(Lecture.id == lecture_id)
        )
        lecture = result.scalar_one_or_none()
        if not lecture:
            return ""

        return (
            f"## 当前上下文：讲义\n"
            f"- 标题：{lecture.title}\n"
            f"- 关联知识点：{lecture.node_name or '无'}\n"
            f"- 内容摘要：\n{(lecture.content or '')[:500]}\n"
        )

    async def _build_route_context(self, route_id: str) -> str:
        """注入学习路线的主题、进度、步骤列表"""
        result = await self.db.execute(
            select(LearningRoute).where(LearningRoute.id == route_id)
        )
        route = result.scalar_one_or_none()
        if not route:
            return ""

        # 获取步骤列表
        steps_result = await self.db.execute(
            select(LearningRouteStep)
            .where(LearningRouteStep.route_id == route_id)
            .order_by(LearningRouteStep.order)
        )
        steps = steps_result.scalars().all()

        steps_text = "\n".join([
            f"  {s.order}. {s.title} ({'已完成' if s.status == 'completed' else '未完成'})"
            for s in steps
        ])

        return (
            f"## 当前上下文：学习路线\n"
            f"- 主题：{route.topic}\n"
            f"- 状态：{route.status}\n"
            f"- 步骤：\n{steps_text}\n"
        )
```

### 4.5 取消令牌管理 (core/cancel_token.py)

```python
# app/core/cancel_token.py

import redis.asyncio as redis

CANCEL_TTL = 300  # 取消令牌有效期 5 分钟（防止残留 key）

async def set_cancel_token(session_id: str):
    """设置取消令牌，Agent 循环每步检查此 key"""
    r = await get_redis()
    await r.set(f"agent_cancel:{session_id}", "1", ex=CANCEL_TTL)

async def clear_cancel_token(session_id: str):
    """清除取消令牌（新一轮对话开始时）"""
    r = await get_redis()
    await r.delete(f"agent_cancel:{session_id}")

async def is_cancelled(session_id: str) -> bool:
    """检查是否已取消"""
    r = await get_redis()
    return await r.get(f"agent_cancel:{session_id}") is not None
```

---

## 5. Agent 服务层

### 5.1 AgentService (agent/agent_service.py)

```python
# app/services/agent/agent_service.py

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

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
    ) -> AgentSession:
        """创建 Agent 会话"""
        session = AgentSession(
            user_id=user_id,
            context_type=context_type,
            context_id=context_id,
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

        return session

    async def list_sessions(
        self,
        user_id: str,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AgentSession], int]:
        """获取会话列表（分页）"""
        query = select(AgentSession).where(AgentSession.user_id == user_id)
        count_query = select(func.count()).select_from(AgentSession).where(AgentSession.user_id == user_id)

        if status:
            query = query.where(AgentSession.status == status)
            count_query = count_query.where(AgentSession.status == status)

        query = query.order_by(desc(AgentSession.updated_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        total_result = await self.db.execute(count_query)

        sessions = result.scalars().all()
        total = total_result.scalar()

        return sessions, total

    async def get_session(self, session_id: str, user_id: str) -> AgentSession | None:
        """获取会话详情（校验用户归属）"""
        result = await self.db.execute(
            select(AgentSession).where(
                AgentSession.id == session_id,
                AgentSession.user_id == user_id,
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
            .where(AgentMessage.session_id == session_id)
            .order_by(desc(AgentMessage.created_at))
            .limit(limit)
        )

        if before:
            # 获取游标消息的 created_at
            cursor_result = await self.db.execute(
                select(AgentMessage.created_at).where(AgentMessage.id == before)
            )
            cursor_time = cursor_result.scalar_one_or_none()
            if cursor_time:
                query = query.where(AgentMessage.created_at < cursor_time)

        result = await self.db.execute(query)
        messages = result.scalars().all()
        return list(reversed(messages))  # 返回时按时间正序

    async def save_user_message(self, session_id: str, content: str) -> AgentMessage:
        """保存用户消息"""
        msg = AgentMessage(
            session_id=session_id,
            role="user",
            content=content,
        )
        self.db.add(msg)

        # 更新 session 的 updated_at
        await self.db.execute(
            select(AgentSession).where(AgentSession.id == session_id).with_for_update()
        )
        session_result = await self.db.execute(
            select(AgentSession).where(AgentSession.id == session_id)
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

    async def build_conversation_history(self, session_id: str, max_turns: int = 10) -> list[dict]:
        """
        从数据库加载最近的对话历史，构建为 LLM messages 格式。
        最多取最近 max_turns 轮对话（1 轮 = 1 条 user + 1 条 assistant）。
        """
        result = await self.db.execute(
            select(AgentMessage)
            .where(
                AgentMessage.session_id == session_id,
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
```

---

## 6. 各服务 Tool 化改造

> 每个业务服务通过 `as_tools()` 类方法暴露工具 Schema，通过 `_tool_{name}` 函数实现 handler。
> 工具接口返回 AI 友好的简洁文本（不是分页 JSON）。

### 6.1 笔记服务 (services/note.py) — 新增 as_tools + handler

```python
# app/services/note.py — 新增部分

class NoteService:
    # ... 现有 CRUD 方法保持不变 ...

    @classmethod
    def as_tools(cls) -> list[ToolSchema]:
        """暴露笔记相关工具供 Agent 调用"""
        return [
            ToolSchema(
                name="search_notes",
                display_name="搜索笔记",
                description="按关键词搜索用户的笔记，返回标题和内容摘要",
                parameters={
                    "query": ToolParameter(type="string", description="搜索关键词"),
                    "tag": ToolParameter(type="string", description="按标签筛选", required=False),
                    "limit": ToolParameter(type="integer", description="返回数量", required=False, default=5),
                },
                category="read",
                module="note",
                icon="file-text",
            ),
            ToolSchema(
                name="get_note_content",
                display_name="获取笔记内容",
                description="获取指定笔记的完整内容",
                parameters={
                    "note_id": ToolParameter(type="string", description="笔记 ID"),
                },
                category="read",
                module="note",
                icon="file-text",
            ),
        ]


# ---- Handler ----
# app/services/note_handlers.py

async def _tool_search_notes(user_id: str, query: str, tag: str | None = None, limit: int = 5) -> str:
    """搜索笔记工具 handler"""
    db = await get_db_session()
    service = NoteService(db)
    notes = await service.search(user_id, query, tag=tag, limit=limit)
    if not notes:
        return "未找到相关笔记。"
    lines = []
    for n in notes:
        tags_str = ", ".join([t.name for t in n.tags]) if n.tags else "无标签"
        preview = (n.content or "")[:150].replace("\n", " ")
        lines.append(f"📝 {n.title}\n  标签: {tags_str}\n  摘要: {preview}...")
    return "\n\n".join(lines)


async def _tool_get_note_content(user_id: str, note_id: str) -> str:
    """获取笔记内容工具 handler"""
    db = await get_db_session()
    service = NoteService(db)
    note = await service.get_note(note_id, user_id)
    if not note:
        return "笔记不存在或无权访问。"
    return f"标题：{note.title}\n学科：{note.subject or '未分类'}\n\n{note.content}"
```

### 6.2 学习服务 (services/learning.py) — 新增 as_tools + handler

```python
# app/services/learning.py — 新增部分

class LearningService:
    # ... 现有方法保持不变 ...

    @classmethod
    def as_tools(cls) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="search_knowledge",
                display_name="搜索知识图谱",
                description="按关键词搜索知识图谱中的知识点，返回名称、学科和描述",
                parameters={
                    "query": ToolParameter(type="string", description="搜索关键词"),
                    "subject": ToolParameter(type="string", description="学科筛选", required=False),
                    "limit": ToolParameter(type="integer", description="返回数量", required=False, default=5),
                },
                category="read",
                module="learning",
                icon="apartment",
            ),
            ToolSchema(
                name="get_mastery",
                display_name="查询掌握度",
                description="查询用户对指定知识点的掌握度分数",
                parameters={
                    "node_name": ToolParameter(type="string", description="知识点名称"),
                },
                category="read",
                module="learning",
                icon="dashboard",
            ),
            ToolSchema(
                name="get_route_progress",
                display_name="查看学习路线进度",
                description="获取用户当前学习路线的进度概况",
                parameters={
                    "topic": ToolParameter(type="string", description="路线主题（可选，不传则返回所有进行中路线）", required=False),
                },
                category="read",
                module="learning",
                icon="flag",
            ),
        ]


# ---- Handler ----
# app/services/learning_handlers.py

async def _tool_search_knowledge(user_id: str, query: str, subject: str | None = None, limit: int = 5) -> str:
    """搜索知识图谱工具 handler"""
    db = await get_db_session()
    service = LearningService(db)
    nodes = await service.search_nodes(query, subject=subject, limit=limit)
    if not nodes:
        return "未找到相关知识点。"
    lines = []
    for n in nodes:
        lines.append(f"🧠 {n.name}\n  学科: {n.subject}\n  描述: {(n.description or '')[:100]}")
    return "\n\n".join(lines)


async def _tool_get_mastery(user_id: str, node_name: str) -> str:
    """查询掌握度工具 handler"""
    db = await get_db_session()
    service = LearningService(db)
    mastery = await service.get_user_mastery(user_id, node_name)
    if not mastery:
        return f"未找到关于「{node_name}」的学习记录。"
    score = mastery.mastery_score
    level = "未开始" if score < 0.1 else "学习中" if score < 0.4 else "熟悉" if score < 0.7 else "掌握"
    return f"知识点：{mastery.node_name}\n掌握度：{score:.0%}（{level}）\n复习次数：{mastery.review_count}"


async def _tool_get_route_progress(user_id: str, topic: str | None = None) -> str:
    """查看学习路线进度工具 handler"""
    db = await get_db_session()
    service = LearningService(db)
    routes = await service.get_active_routes(user_id, topic=topic)
    if not routes:
        return "当前没有进行中的学习路线。"
    lines = []
    for r in routes:
        total = r.total_steps or 0
        completed = r.completed_steps or 0
        progress = f"{completed}/{total}" if total else "未知"
        lines.append(f"🗺 {r.topic}\n  进度: {progress}\n  状态: {r.status}")
    return "\n\n".join(lines)
```

### 6.3 答疑服务 (services/qa.py) — 新增 as_tools + handler

```python
# app/services/qa.py — 新增部分

class QAService:
    # ... 现有方法保持不变 ...

    @classmethod
    def as_tools(cls) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="get_qa_history",
                display_name="查看答疑历史",
                description="获取用户最近答疑会话的摘要",
                parameters={
                    "limit": ToolParameter(type="integer", description="返回数量", required=False, default=3),
                },
                category="read",
                module="qa",
                icon="message",
            ),
        ]


# ---- Handler ----
# app/services/qa_handlers.py

async def _tool_get_qa_history(user_id: str, limit: int = 3) -> str:
    """查看答疑历史工具 handler"""
    db = await get_db_session()
    service = QAService(db)
    sessions = await service.get_recent_sessions(user_id, limit=limit)
    if not sessions:
        return "暂无答疑记录。"
    lines = []
    for s in sessions:
        lines.append(f"💬 {s.node_name or '通用答疑'}\n  消息数: {s.message_count}\n  最后活跃: {s.updated_at.strftime('%m-%d %H:%M')}")
    return "\n\n".join(lines)
```

### 6.4 复习服务 (services/review.py) — 新增 as_tools + handler

```python
# app/services/review.py — 新增部分

class ReviewService:
    # ... 现有方法保持不变 ...

    @classmethod
    def as_tools(cls) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="get_review_status",
                display_name="查看复习状态",
                description="获取用户当前待复习的知识点列表和复习统计",
                parameters={
                    "limit": ToolParameter(type="integer", description="返回数量", required=False, default=5),
                },
                category="read",
                module="review",
                icon="redo",
            ),
            ToolSchema(
                name="schedule_review",
                display_name="创建复习计划",
                description="为指定知识点创建复习计划",
                parameters={
                    "node_name": ToolParameter(type="string", description="知识点名称"),
                    "review_type": ToolParameter(
                        type="string",
                        description="复习类型",
                        enum=["flashcard", "quiz", "explanation"],
                        default="flashcard",
                    ),
                },
                category="write",   # 写操作，限流
                module="review",
                icon="schedule",
            ),
        ]


# ---- Handler ----
# app/services/review_handlers.py

async def _tool_get_review_status(user_id: str, limit: int = 5) -> str:
    """查看复习状态工具 handler"""
    db = await get_db_session()
    service = ReviewService(db)
    stats = await service.get_review_stats(user_id)
    pending = await service.get_pending_reviews(user_id, limit=limit)

    lines = [f"📊 复习统计：连续复习 {stats.streak_days} 天，累计复习 {stats.total_reviews} 次"]
    if pending:
        lines.append("\n📋 待复习：")
        for p in pending:
            lines.append(f"  - {p.node_name}（掌握度 {p.mastery_score:.0%}，到期 {p.next_review_date.strftime('%m-%d')}）")
    else:
        lines.append("\n暂无待复习内容。")
    return "\n".join(lines)


async def _tool_schedule_review(user_id: str, node_name: str, review_type: str = "flashcard") -> str:
    """创建复习计划工具 handler"""
    db = await get_db_session()
    service = ReviewService(db)
    plan = await service.create_review_plan(user_id, node_name, review_type)
    if not plan:
        return f"无法为「{node_name}」创建复习计划，请确认该知识点存在。"
    return f"已创建复习计划：{node_name}\n类型: {review_type}\n下次复习: {plan.next_review_date.strftime('%Y-%m-%d')}"
```

### 6.5 搜索服务 (services/search.py) — 新增 as_tools + handler

```python
# app/services/search.py — 新增部分

class SearchService:
    # ... 现有 hybrid_search / meilisearch_search / pgvector_search / rrf 保持不变 ...

    @classmethod
    def as_tools(cls) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="global_search",
                display_name="全局搜索",
                description="全局搜索用户的笔记、讲义、知识点，返回匹配摘要",
                parameters={
                    "query": ToolParameter(type="string", description="搜索关键词"),
                    "search_type": ToolParameter(
                        type="string",
                        description="搜索范围",
                        enum=["notes", "lectures", "knowledge", "all"],
                        default="all",
                    ),
                    "top_k": ToolParameter(type="integer", description="返回数量", required=False, default=5),
                },
                category="read",
                module="search",
                icon="search",
            ),
            ToolSchema(
                name="semantic_search",
                display_name="语义搜索",
                description="语义相似度搜索，适合模糊概念查找",
                parameters={
                    "query": ToolParameter(type="string", description="自然语言描述"),
                    "top_k": ToolParameter(type="integer", description="返回数量", required=False, default=5),
                },
                category="read",
                module="search",
                icon="bulb",
            ),
        ]


# ---- Handler ----
# app/services/search_handlers.py

async def _tool_global_search(user_id: str, query: str, search_type: str = "all", top_k: int = 5) -> str:
    """全局搜索工具 handler"""
    results = await hybrid_search(query, user_id, search_type, top_k)
    if not results:
        return "未找到相关内容。"
    lines = []
    for r in results:
        type_icon = {"note": "📝", "lecture": "📖", "knowledge": "🧠"}.get(r["source_type"], "📄")
        lines.append(f"{type_icon} [{r['source_type']}] {r['title']}\n  摘要: {r.get('snippet', r['content'][:120])}")
    return "\n\n".join(lines)


async def _tool_semantic_search(user_id: str, query: str, top_k: int = 5) -> str:
    """语义搜索工具 handler"""
    embedding = await get_embedding(query)
    results = await pgvector_search(embedding, user_id, top_k)
    if not results:
        return "未找到语义相关内容。"
    lines = []
    for r in results:
        sim = r.get("similarity", 0)
        lines.append(f"[相似度:{sim:.2f}] {r['title']}\n  {r['content'][:150]}")
    return "\n\n".join(lines)
```

### 6.6 用户记忆服务 (services/user_memory.py) — 新增 as_tools + handler

```python
# app/services/user_memory.py — 新增部分

class UserMemoryService:
    # ... 现有 get_habit_summary / recall / search_memory 保持不变 ...

    @classmethod
    def as_tools(cls) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="recall_knowledge",
                display_name="回忆知识画像",
                description="按需检索用户的知识画像，获取某主题的详细信息",
                parameters={
                    "topic": ToolParameter(type="string", description="主题关键词"),
                    "depth": ToolParameter(
                        type="string",
                        description="检索深度",
                        enum=["brief", "detailed"],
                        default="brief",
                    ),
                },
                category="read",
                module="user_memory",
                icon="database",
            ),
            ToolSchema(
                name="search_memory",
                display_name="搜索记忆",
                description="语义搜索用户的历史记忆和学习记录",
                parameters={
                    "query": ToolParameter(type="string", description="搜索描述"),
                    "top_k": ToolParameter(type="integer", description="返回数量", required=False, default=3),
                },
                category="read",
                module="user_memory",
                icon="history",
            ),
        ]


# ---- Handler ----
# app/services/memory_handlers.py

async def _tool_recall_knowledge(user_id: str, topic: str, depth: str = "brief") -> str:
    """回忆知识画像工具 handler"""
    db = await get_db_session()
    service = UserMemoryService(db)
    result = await service.recall(user_id, topic, depth=depth)
    if not result:
        return f"未找到关于「{topic}」的知识画像。"
    return result.to_text()


async def _tool_search_memory(user_id: str, query: str, top_k: int = 3) -> str:
    """搜索记忆工具 handler"""
    db = await get_db_session()
    service = UserMemoryService(db)
    results = await service.search_memory(user_id, query, top_k=top_k)
    if not results:
        return "未找到相关记忆。"
    lines = []
    for r in results:
        lines.append(f"[{r.source_type}] {r.title}\n  {r.content[:150]}")
    return "\n\n".join(lines)
```

### 6.7 工具注册汇总

```python
# app/services/agent/tool_registry.py — init_tool_registry 更新

async def init_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()

    from services.note import NoteService
    from services.note_handlers import _tool_search_notes, _tool_get_note_content
    from services.learning import LearningService
    from services.learning_handlers import _tool_search_knowledge, _tool_get_mastery, _tool_get_route_progress
    from services.qa import QAService
    from services.qa_handlers import _tool_get_qa_history
    from services.review import ReviewService
    from services.review_handlers import _tool_get_review_status, _tool_schedule_review
    from services.search import SearchService
    from services.search_handlers import _tool_global_search, _tool_semantic_search
    from services.user_memory import UserMemoryService
    from services.memory_handlers import _tool_recall_knowledge, _tool_search_memory

    registry.register_from_service(NoteService, {
        "search_notes": _tool_search_notes,
        "get_note_content": _tool_get_note_content,
    })
    registry.register_from_service(LearningService, {
        "search_knowledge": _tool_search_knowledge,
        "get_mastery": _tool_get_mastery,
        "get_route_progress": _tool_get_route_progress,
    })
    registry.register_from_service(QAService, {
        "get_qa_history": _tool_get_qa_history,
    })
    registry.register_from_service(ReviewService, {
        "get_review_status": _tool_get_review_status,
        "schedule_review": _tool_schedule_review,
    })
    registry.register_from_service(SearchService, {
        "global_search": _tool_global_search,
        "semantic_search": _tool_semantic_search,
    })
    registry.register_from_service(UserMemoryService, {
        "recall_knowledge": _tool_recall_knowledge,
        "search_memory": _tool_search_memory,
    })

    return registry
```

> 说明：`register_from_service` 的第二个参数由原来的 `handler_module` 改为 `dict[str, handler]`，显式映射工具名到 handler。这样更清晰，避免依赖 handler 函数命名约定。

---

## 7. Pydantic Schema

### 7.1 Agent 请求/响应 Schema

```python
# app/schemas/agent.py

from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime


# ---- 请求 Schema ----

class CreateAgentSessionRequest(BaseModel):
    context_type: str = Field(default="general", pattern="^(general|note|lecture|route)$")
    context_id: str | None = None
    initial_message: str | None = None


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)


class ListSessionsRequest(BaseModel):
    status: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ListMessagesRequest(BaseModel):
    before: str | None = None
    limit: int = Field(default=50, ge=1, le=200)


# ---- 响应 Schema ----

class ToolCallResponse(BaseModel):
    id: str
    tool_name: str
    tool_display_name: str
    input: dict[str, Any]
    output: Any | None = None
    status: str                       # "calling" | "success" | "error"
    error_message: str | None = None
    started_at: str
    completed_at: str | None = None


class AgentMessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    tool_calls: list[ToolCallResponse] = []
    metadata: dict[str, Any] = {}
    created_at: str


class AgentSessionResponse(BaseModel):
    id: str
    user_id: str
    title: str | None = None
    context_type: str
    context_id: str | None = None
    status: str
    created_at: str
    updated_at: str


class SendMessageResponse(BaseModel):
    user_message: AgentMessageResponse
    assistant_message: AgentMessageResponse


class ToolDefinitionResponse(BaseModel):
    name: str
    display_name: str
    description: str
    icon: str


# ---- WebSocket 消息 Schema ----

class WSMessageThinking(BaseModel):
    type: str = "thinking"
    data: dict[str, str]              # {"content": "..."}


class WSMessageToolCallStart(BaseModel):
    type: str = "tool_call_start"
    data: dict[str, Any]              # {"tool_call_id", "tool_name", "tool_display_name", "input"}


class WSMessageToolCallResult(BaseModel):
    type: str = "tool_call_result"
    data: dict[str, Any]              # {"tool_call_id", "status", "output", "error_message"}


class WSMessageToken(BaseModel):
    type: str = "token"
    data: dict[str, str]              # {"content": "..."}


class WSMessageDone(BaseModel):
    type: str = "done"
    data: dict[str, Any]              # {"message": AgentMessageResponse}


class WSMessageError(BaseModel):
    type: str = "error"
    data: dict[str, str]              # {"message": "..."}


class WSMessageSessionCreated(BaseModel):
    type: str = "session_created"
    data: dict[str, Any]              # {"session": AgentSessionResponse}
```

---

## 8. 路由层

### 8.1 Agent REST API

```yaml
# app/api/v1/agent.py

# ---- 会话管理 ----

POST /api/v1/agent/sessions
  summary: 创建 Agent 会话
  tags: [Agent]
  security: [BearerAuth]
  requestBody:
    application/json:
      schema:
        context_type: string (enum: general|note|lecture|route, default: general)
        context_id: string (optional)
        initial_message: string (optional)
  responses:
    201:
      description: 会话创建成功
      body:
        data: AgentSessionResponse

GET /api/v1/agent/sessions
  summary: 获取会话列表
  tags: [Agent]
  security: [BearerAuth]
  parameters:
    - name: status
      in: query
      schema: string (optional)
    - name: page
      in: query
      schema: integer (default: 1)
    - name: page_size
      in: query
      schema: integer (default: 20)
  responses:
    200:
      description: 会话列表
      body:
        data:
          items: AgentSessionResponse[]
          total: integer

GET /api/v1/agent/sessions/{session_id}
  summary: 获取会话详情
  tags: [Agent]
  security: [BearerAuth]
  parameters:
    - name: session_id
      in: path
      required: true
      schema: string (uuid)
  responses:
    200:
      description: 会话详情
      body:
        data: AgentSessionResponse
    404:
      description: 会话不存在

POST /api/v1/agent/sessions/{session_id}/close
  summary: 关闭会话
  tags: [Agent]
  security: [BearerAuth]
  parameters:
    - name: session_id
      in: path
      required: true
      schema: string (uuid)
  responses:
    200:
      description: 会话已关闭
      body:
        data: AgentSessionResponse

# ---- 消息管理 ----

POST /api/v1/agent/sessions/{session_id}/messages
  summary: 发送消息（HTTP 非流式）
  description: |
    发送用户消息并等待 Agent 完整回复后返回。
    适用于不需要流式体验的场景（如笔记页面嵌入的简短对话）。
    如需流式体验，请使用 WebSocket 端点。
  tags: [Agent]
  security: [BearerAuth]
  parameters:
    - name: session_id
      in: path
      required: true
      schema: string (uuid)
  requestBody:
    application/json:
      schema:
        content: string (required, 1-10000 chars)
  responses:
    200:
      description: 消息发送成功，Agent 已回复
      body:
        data:
          user_message: AgentMessageResponse
          assistant_message: AgentMessageResponse

GET /api/v1/agent/sessions/{session_id}/messages
  summary: 获取历史消息
  tags: [Agent]
  security: [BearerAuth]
  parameters:
    - name: session_id
      in: path
      required: true
      schema: string (uuid)
    - name: before
      in: query
      schema: string (uuid, optional) — 游标，返回此 ID 之前的的消息
    - name: limit
      in: query
      schema: integer (default: 50)
  responses:
    200:
      description: 消息列表（按时间正序）
      body:
        data: AgentMessageResponse[]

# ---- 取消生成 ----

POST /api/v1/agent/sessions/{session_id}/cancel
  summary: 取消当前生成
  description: 通过 Redis 设置取消令牌，AgentLoop 在每步检查并中断
  tags: [Agent]
  security: [BearerAuth]
  parameters:
    - name: session_id
      in: path
      required: true
      schema: string (uuid)
  responses:
    200:
      description: 取消请求已发送
      body:
        data: { "cancelled": true }

# ---- 工具列表 ----

GET /api/v1/agent/tools
  summary: 获取可用工具列表
  description: 返回 Agent 可调用的所有工具定义，供前端展示
  tags: [Agent]
  security: [BearerAuth]
  responses:
    200:
      description: 工具列表
      body:
        data: ToolDefinitionResponse[]
```

### 8.2 Agent REST 路由实现

```python
# app/api/v1/agent.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post("/sessions", status_code=201)
async def create_session(
    request: CreateAgentSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建 Agent 会话"""
    service = AgentService(db)
    session = await service.create_session(
        user_id=str(user.id),
        context_type=request.context_type,
        context_id=request.context_id,
        initial_message=request.initial_message,
    )
    return {"data": AgentSessionResponse.model_validate(session)}


@router.get("/sessions")
async def list_sessions(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取会话列表"""
    service = AgentService(db)
    sessions, total = await service.list_sessions(
        user_id=str(user.id),
        status=status,
        page=page,
        page_size=page_size,
    )
    return {
        "data": {
            "items": [AgentSessionResponse.model_validate(s) for s in sessions],
            "total": total,
        }
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取会话详情"""
    service = AgentService(db)
    session = await service.get_session(session_id, str(user.id))
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"data": AgentSessionResponse.model_validate(session)}


@router.post("/sessions/{session_id}/close")
async def close_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """关闭会话"""
    service = AgentService(db)
    session = await service.close_session(session_id, str(user.id))
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"data": AgentSessionResponse.model_validate(session)}


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    registry: ToolRegistry = Depends(get_tool_registry),
):
    """发送消息（HTTP 非流式）"""
    service = AgentService(db)

    # 校验会话
    session = await service.get_session(session_id, str(user.id))
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.status == "closed":
        raise HTTPException(status_code=400, detail="会话已关闭")

    # 清除取消令牌
    await clear_cancel_token(session_id)

    # 保存用户消息
    user_msg = await service.save_user_message(session_id, request.content)

    # 构建对话历史
    history = await service.build_conversation_history(session_id)

    # 运行 Agent 循环（非流式，等待完整回复）
    agent = AgentLoop(
        registry=registry,
        llm_client=get_llm_client("agent_chat"),
        session=session,
        db=db,
        cancel_key=f"agent_cancel:{session_id}",
        max_steps=settings.AGENT_MAX_STEPS,
        token_budget=settings.AGENT_TOKEN_BUDGET,
    )
    assistant_msg = await agent.run(request.content, history[:-1])  # 排除刚保存的用户消息

    return {
        "data": {
            "user_message": AgentMessageResponse.model_validate(user_msg),
            "assistant_message": AgentMessageResponse.model_validate(assistant_msg),
        }
    }


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    before: str | None = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取历史消息"""
    service = AgentService(db)
    messages = await service.get_messages(session_id, str(user.id), before=before, limit=limit)
    return {
        "data": [AgentMessageResponse.model_validate(m) for m in messages],
    }


@router.post("/sessions/{session_id}/cancel")
async def cancel_generation(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消当前生成"""
    service = AgentService(db)
    success = await service.cancel_generation(session_id, str(user.id))
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"data": {"cancelled": True}}


@router.get("/tools")
async def get_available_tools(
    registry: ToolRegistry = Depends(get_tool_registry),
    user: User = Depends(get_current_user),
):
    """获取可用工具列表"""
    tools = registry.get_all_schemas()
    return {
        "data": [
            ToolDefinitionResponse(
                name=t.name,
                display_name=t.display_name,
                description=t.description,
                icon=t.icon,
            )
            for t in tools
        ]
    }
```

### 8.3 Agent WebSocket 路由

```python
# app/api/v1/agent.py — WebSocket 部分

@router.websocket("/ws/agent/{session_id}")
async def ws_agent_chat(
    ws: WebSocket,
    session_id: str,
    token: str = Query(...),
):
    """
    Agent WebSocket 对话端点。

    连接地址：ws(s)://{host}/api/v1/ws/agent/{session_id}?token={access_token}

    客户端 → 服务端：
      - { "type": "message", "content": "用户消息" }
      - { "type": "cancel" }

    服务端 → 客户端：
      - thinking / tool_call_start / tool_call_result / token / done / error / session_created
    """
    # 1. 认证
    user = await authenticate_ws_token(token)
    if not user:
        await ws.close(code=4001, reason="认证失败")
        return

    await ws.accept()

    # 2. 获取数据库会话和 Agent 会话
    db = await get_db_session()
    agent_service = AgentService(db)
    session = await agent_service.get_session(session_id, str(user.id))

    if not session:
        await ws.send_json({"type": "error", "data": {"message": "会话不存在"}})
        await ws.close(code=4004, reason="会话不存在")
        return

    if session.status == "closed":
        await ws.send_json({"type": "error", "data": {"message": "会话已关闭"}})
        await ws.close(code=4003, reason="会话已关闭")
        return

    # 3. 推送 session_created 确认
    await ws.send_json({
        "type": "session_created",
        "data": {
            "session": AgentSessionResponse.model_validate(session).model_dump(),
        },
    })

    # 4. 初始化工具注册表
    registry = await init_tool_registry()

    # 5. 消息循环
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "message":
                content = data.get("content", "").strip()
                if not content:
                    await ws.send_json({"type": "error", "data": {"message": "消息内容不能为空"}})
                    continue

                # 清除取消令牌
                await clear_cancel_token(session_id)

                # 保存用户消息
                user_msg = await agent_service.save_user_message(session_id, content)

                # 构建对话历史
                history = await agent_service.build_conversation_history(session_id)

                # 运行 Agent 循环
                agent = AgentLoop(
                    registry=registry,
                    llm_client=get_llm_client("agent_chat"),
                    session=session,
                    db=db,
                    ws=ws,
                    cancel_key=f"agent_cancel:{session_id}",
                    max_steps=settings.AGENT_MAX_STEPS,
                    token_budget=settings.AGENT_TOKEN_BUDGET,
                )

                try:
                    await agent.run(content, history[:-1])
                except Exception as e:
                    logger.error(f"Agent loop error: {e}", exc_info=True)
                    await ws.send_json({
                        "type": "error",
                        "data": {"message": "处理消息时发生错误，请重试。"},
                    })

            elif msg_type == "cancel":
                await set_cancel_token(session_id)
                await ws.send_json({
                    "type": "done",
                    "data": {
                        "message": {
                            "id": "",
                            "session_id": session_id,
                            "role": "assistant",
                            "content": "已取消生成。",
                            "tool_calls": [],
                            "metadata": {},
                            "created_at": datetime.utcnow().isoformat() + "Z",
                        }
                    },
                })

    except WebSocketDisconnect:
        logger.info(f"Agent WS disconnected: session={session_id}")
    except Exception as e:
        logger.error(f"Agent WS error: {e}", exc_info=True)
    finally:
        await db.close()
```

---

## 9. 搜索增强

### 9.1 全局搜索 API

```yaml
# app/api/v1/search.py — 新增端点

GET /api/v1/search/global
  summary: 全局搜索（带高亮和分面统计）
  tags: [Search]
  security: [BearerAuth]
  parameters:
    - name: q
      in: query
      required: true
      schema: string — 搜索关键词
    - name: type
      in: query
      schema: string (enum: all|notes|lectures|knowledge|routes, default: all)
    - name: subject
      in: query
      schema: string (optional) — 学科筛选
    - name: page
      in: query
      schema: integer (default: 1)
    - name: page_size
      in: query
      schema: integer (default: 20)
    - name: highlight
      in: query
      schema: boolean (default: true) — 是否返回高亮片段
  responses:
    200:
      description: 搜索结果
      body:
        data:
          results: SearchResultWithHighlight[]
          total: integer
          facets: { type: string, count: integer }[]

GET /api/v1/search/semantic
  summary: 语义搜索
  tags: [Search]
  security: [BearerAuth]
  parameters:
    - name: q
      in: query
      required: true
      schema: string — 自然语言描述
    - name: type
      in: query
      schema: string (optional) — 类型筛选
    - name: top_k
      in: query
      schema: integer (default: 10)
  responses:
    200:
      description: 语义搜索结果
      body:
        data: SearchResultWithHighlight[]

GET /api/v1/knowledge/nodes/{node_id}/relation
  summary: 获取知识节点关联内容
  tags: [Knowledge]
  security: [BearerAuth]
  parameters:
    - name: node_id
      in: path
      required: true
      schema: string (uuid)
  responses:
    200:
      description: 知识节点关联内容
      body:
        data: KnowledgeRelationResponse
```

### 9.2 全局搜索实现

```python
# app/services/search.py — 新增全局搜索方法

class SearchService:
    # ... 现有方法保持不变 ...

    async def global_search(
        self,
        user_id: str,
        query: str,
        search_type: str = "all",
        subject: str | None = None,
        page: int = 1,
        page_size: int = 20,
        highlight: bool = True,
    ) -> dict:
        """
        全局搜索：跨所有索引搜索，返回带高亮和分面统计的结果。

        实现策略：
        1. 根据 search_type 选择 Meilisearch 索引
        2. 执行关键词搜索，获取高亮片段
        3. 并行执行语义搜索（如果 query 长度 > 2）
        4. RRF 融合两路结果
        5. 计算分面统计（按 type 分组计数）
        6. 分页返回
        """
        # 1. 确定搜索索引
        index_map = {
            "notes": "notes",
            "lectures": "lectures",
            "knowledge": "knowledge_nodes",
            "routes": "learning_routes",
            "all": ["notes", "lectures", "knowledge_nodes", "learning_routes"],
        }
        indexes = index_map.get(search_type, index_map["all"])

        # 2. Meilisearch 关键词搜索
        ms_client = get_meilisearch_client()
        filters = []
        if subject:
            filters.append(f'subject = "{subject}"')
        # 笔记需要过滤用户
        user_filter = f'user_id = "{user_id}"'

        keyword_results = []
        if isinstance(indexes, list):
            for idx in indexes:
                idx_filters = [user_filter] if idx in ("notes", "lectures") else []
                if subject:
                    idx_filters.append(f'subject = "{subject}"')

                search_params = {
                    "q": query,
                    "limit": page_size * 2,
                    "offset": 0,
                }
                if idx_filters:
                    search_params["filter"] = idx_filters
                if highlight:
                    search_params["attributesToHighlight"] = ["title", "content", "description"]
                    search_params["highlightPreTag"] = "<em>"
                    search_params["highlightPostTag"] = "</em>"

                result = ms_client.index(idx).search(query, search_params)
                for hit in result.get("hits", []):
                    keyword_results.append(self._format_search_hit(hit, idx, user_id))
        else:
            search_params = {
                "q": query,
                "limit": page_size * 2,
            }
            if filters:
                search_params["filter"] = filters
            if highlight:
                search_params["attributesToHighlight"] = ["title", "content", "description"]
                search_params["highlightPreTag"] = "<em>"
                search_params["highlightPostTag"] = "</em>"

            result = ms_client.index(indexes).search(query, search_params)
            for hit in result.get("hits", []):
                keyword_results.append(self._format_search_hit(hit, indexes, user_id))

        # 3. 语义搜索（并行）
        query_embedding = await get_embedding(query)
        vector_results = await pgvector_search(query_embedding, user_id, top_k=page_size * 2)
        vector_formatted = [
            {
                "id": r["id"],
                "type": self._source_type_to_result_type(r.get("source_type", "")),
                "title": r.get("title", ""),
                "content_preview": r.get("content", "")[:200],
                "subject": r.get("subject"),
                "score": r.get("similarity", 0),
                "highlights": [],
                "created_at": r.get("created_at", ""),
            }
            for r in vector_results
        ]

        # 4. RRF 融合
        fused = reciprocal_rank_fusion(
            [keyword_results, vector_formatted],
            k=60,
        )

        # 5. 分面统计
        facets = {}
        for item in fused:
            t = item["type"]
            facets[t] = facets.get(t, 0) + 1
        facet_list = [{"type": k, "count": v} for k, v in facets.items()]

        # 6. 分页
        total = len(fused)
        start = (page - 1) * page_size
        paged = fused[start:start + page_size]

        return {
            "results": paged,
            "total": total,
            "facets": facet_list,
        }

    def _format_search_hit(self, hit: dict, index_name: str, user_id: str) -> dict:
        """将 Meilisearch 命中结果格式化为统一结构"""
        type_map = {
            "notes": "note",
            "lectures": "lecture",
            "knowledge_nodes": "knowledge",
            "learning_routes": "route",
        }
        result_type = type_map.get(index_name, "note")

        # 提取高亮片段
        highlights = []
        formatted = hit.get("_formatted", {})
        for field in ["title", "content", "description"]:
            if field in formatted:
                fragment = formatted[field]
                if "<em>" in fragment:
                    highlights.append({
                        "field": field,
                        "fragments": [fragment],
                    })

        return {
            "id": hit.get("id", ""),
            "type": result_type,
            "title": hit.get("title", ""),
            "content_preview": (hit.get("content", "") or "")[:200],
            "subject": hit.get("subject"),
            "score": 1.0,  # Meilisearch 不直接返回分数，用排名代替
            "highlights": highlights,
            "tag_names": hit.get("tag_names", []),
            "related_node_ids": hit.get("related_node_ids", []),
            "created_at": hit.get("created_at", ""),
        }

    def _source_type_to_result_type(self, source_type: str) -> str:
        mapping = {
            "user_note": "note",
            "note": "note",
            "lecture": "lecture",
            "knowledge_node": "knowledge",
            "learning_route": "route",
        }
        return mapping.get(source_type, source_type)
```

### 9.3 知识节点关联 API 实现

```python
# app/api/v1/search.py — 新增路由

@router.get("/knowledge/nodes/{node_id}/relation")
async def get_knowledge_relation(
    node_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取知识节点的关联内容（前置/后续知识、关联笔记、关联路线）"""
    service = KnowledgeService(db)
    relation = await service.get_node_relation(node_id, str(user.id))
    return {"data": relation}


# app/services/knowledge.py — 新增方法

class KnowledgeService:
    # ... 现有方法保持不变 ...

    async def get_node_relation(self, node_id: str, user_id: str) -> dict:
        """
        获取知识节点的关联内容视图。
        返回：中心节点信息 + 前置知识 + 后续知识 + 关联笔记 + 关联路线。
        """
        # 1. 获取中心节点
        node_result = await self.db.execute(
            select(KnowledgeNode).where(KnowledgeNode.id == node_id)
        )
        center_node = node_result.scalar_one_or_none()
        if not center_node:
            raise HTTPException(status_code=404, detail="知识节点不存在")

        # 2. 获取前置知识（通过 knowledge_edges 的 relation_type = 'prerequisite'）
        prereq_result = await self.db.execute(
            select(KnowledgeNode, KnowledgeEdge.weight)
            .join(KnowledgeEdge, KnowledgeEdge.from_node_id == KnowledgeNode.id)
            .where(
                KnowledgeEdge.to_node_id == node_id,
                KnowledgeEdge.relation_type == "prerequisite",
            )
        )
        prerequisite_nodes = []
        for node, weight in prereq_result.fetchall():
            # 获取用户对该节点的掌握度
            mastery_result = await self.db.execute(
                select(UserKnowledgeMastery).where(
                    UserKnowledgeMastery.user_id == user_id,
                    UserKnowledgeMastery.node_id == node.id,
                )
            )
            mastery = mastery_result.scalar_one_or_none()
            prerequisite_nodes.append({
                "id": str(node.id),
                "name": node.name,
                "mastery_score": mastery.mastery_score if mastery else None,
            })

        # 3. 获取后续知识
        dep_result = await self.db.execute(
            select(KnowledgeNode, KnowledgeEdge.weight)
            .join(KnowledgeEdge, KnowledgeEdge.to_node_id == KnowledgeNode.id)
            .where(
                KnowledgeEdge.from_node_id == node_id,
                KnowledgeEdge.relation_type == "prerequisite",
            )
        )
        dependent_nodes = []
        for node, weight in dep_result.fetchall():
            mastery_result = await self.db.execute(
                select(UserKnowledgeMastery).where(
                    UserKnowledgeMastery.user_id == user_id,
                    UserKnowledgeMastery.node_id == node.id,
                )
            )
            mastery = mastery_result.scalar_one_or_none()
            dependent_nodes.append({
                "id": str(node.id),
                "name": node.name,
                "mastery_score": mastery.mastery_score if mastery else None,
            })

        # 4. 获取关联笔记（通过笔记内容中引用了该知识点，或通过 tag 关联）
        # 简化策略：搜索标题或标签中包含知识点名称的笔记
        note_result = await self.db.execute(
            select(Note.id, Note.title, Note.updated_at)
            .where(
                Note.user_id == user_id,
                Note.title.ilike(f"%{center_node.name}%"),
            )
            .order_by(desc(Note.updated_at))
            .limit(10)
        )
        related_notes = [
            {"id": str(r.id), "title": r.title, "updated_at": r.updated_at.isoformat() + "Z"}
            for r in note_result.fetchall()
        ]

        # 5. 获取关联学习路线（路线步骤中包含该知识点）
        route_result = await self.db.execute(
            select(LearningRoute.id, LearningRoute.topic, LearningRoute.status)
            .join(LearningRouteStep, LearningRouteStep.route_id == LearningRoute.id)
            .where(LearningRouteStep.node_id == node_id)
            .distinct()
            .limit(10)
        )
        related_routes = [
            {"id": str(r.id), "topic": r.topic, "status": r.status}
            for r in route_result.fetchall()
        ]

        return {
            "center_node": {
                "id": str(center_node.id),
                "name": center_node.name,
                "subject": center_node.subject,
            },
            "related_notes": related_notes,
            "related_routes": related_routes,
            "prerequisite_nodes": prerequisite_nodes,
            "dependent_nodes": dependent_nodes,
        }
```

### 9.4 搜索路由注册

```python
# app/api/v1/search.py — 新增/修改

from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/search", tags=["Search"])

@router.get("/global")
async def global_search(
    q: str = Query(..., min_length=1),
    type: str = Query(default="all", pattern="^(all|notes|lectures|knowledge|routes)$"),
    subject: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    highlight: bool = Query(default=True),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """全局搜索（带高亮和分面统计）"""
    service = SearchService(db)
    result = await service.global_search(
        user_id=str(user.id),
        query=q,
        search_type=type,
        subject=subject,
        page=page,
        page_size=page_size,
        highlight=highlight,
    )
    return {"data": result}


@router.get("/semantic")
async def semantic_search(
    q: str = Query(..., min_length=1),
    type: str | None = None,
    top_k: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """语义搜索"""
    embedding = await get_embedding(q)
    results = await pgvector_search(embedding, str(user.id), top_k=top_k)

    formatted = []
    for r in results:
        formatted.append({
            "id": r["id"],
            "type": SearchService._source_type_to_result_type(None, r.get("source_type", "")),
            "title": r.get("title", ""),
            "content_preview": r.get("content", "")[:200],
            "subject": r.get("subject"),
            "score": r.get("similarity", 0),
            "highlights": [],
            "created_at": r.get("created_at", ""),
        })

    return {"data": formatted}
```

---

## 10. WebSocket 协议规范

### 10.1 连接地址

```
ws(s)://{host}/api/v1/ws/agent/{session_id}?token={access_token}
```

### 10.2 消息类型一览

| 方向 | type | 说明 | data 结构 |
|------|------|------|-----------|
| C→S | message | 用户发送消息 | `{ "content": "string" }` |
| C→S | cancel | 取消当前生成 | `{}` |
| S→C | thinking | Agent 正在思考 | `{ "content": "string" }` |
| S→C | tool_call_start | 开始调用工具 | `{ "tool_call_id", "tool_name", "tool_display_name", "input" }` |
| S→C | tool_call_result | 工具调用完成 | `{ "tool_call_id", "status", "output", "error_message" }` |
| S→C | token | 流式文本 token | `{ "content": "string" }` |
| S→C | done | 回复完成 | `{ "message": AgentMessage }` |
| S→C | error | 错误 | `{ "message": "string" }` |
| S→C | session_created | 会话创建确认 | `{ "session": AgentSession }` |

### 10.3 典型消息流

```
连接建立 → S→C: session_created
用户发送 "帮我复习二次函数"
  ← S→C: thinking: { content: "用户想复习二次函数，让我先查看掌握度..." }
  ← S→C: tool_call_start: { tool_call_id: "tc_1", tool_name: "get_mastery", tool_display_name: "查询掌握度", input: { node_name: "二次函数" } }
  ← S→C: tool_call_result: { tool_call_id: "tc_1", status: "success", output: "掌握度：45%（学习中）..." }
  ← S→C: thinking: { content: "掌握度 0.45，应该先巩固基础..." }
  ← S→C: tool_call_start: { tool_call_id: "tc_2", tool_name: "search_knowledge", tool_display_name: "搜索知识图谱", input: { query: "二次函数" } }
  ← S→C: tool_call_result: { tool_call_id: "tc_2", status: "success", output: "找到 3 个相关知识点..." }
  ← S→C: token: { content: "根据" }
  ← S→C: token: { content: "你的" }
  ← S→C: token: { content: "学习情况..." }
  ← S→C: done: { message: { id: "...", content: "完整回复...", tool_calls: [...], ... } }
```

### 10.4 错误处理

- 认证失败：WebSocket 关闭，code=4001
- 会话不存在：发送 error 消息后关闭，code=4004
- 会话已关闭：发送 error 消息后关闭，code=4003
- Agent 循环异常：发送 error 消息，不关闭连接（用户可继续发送消息）
- 取消生成：发送 done 消息，content="已取消生成。"

---

## 11. Prompt 模板更新

### 11.1 Agent System Prompt（升级版）

```python
# app/ai/prompts/agent.py — 升级

AGENT_SYSTEM_PROMPT = """你是青云智学AI助手，一个智能学习伙伴。你可以帮助学生解答问题、查找笔记、推荐复习内容、搜索知识点等。

## 用户学习习惯
{habit_summary}

## 当前上下文
{context_text}

## 可用工具
你可以通过以下工具访问学生的学习数据：
{tool_descriptions}

## 行为准则
1. 先理解用户的真实需求，再决定是否需要调用工具。简单问候或常识问题直接回答。
2. 调用工具前，简要告知用户你在做什么（如"让我查一下你的笔记"）。
3. 工具返回结果后，用自己的语言组织和总结，不要原样搬运工具输出。
4. 如果工具调用失败，诚实告知用户，并建议替代方案。
5. 回答要简洁、有条理，适合学习场景。使用 Markdown 格式。
6. 不要编造工具未返回的数据。如果不确定，明确说明。
7. 如果当前上下文包含笔记/讲义/路线内容，优先基于上下文回答，工具作为补充。
8. 当前时间：{current_time}
"""
```

> 与 Phase 1-2 版本的区别：新增 `{context_text}` 占位符，用于注入笔记/讲义/路线上下文；新增第 7 条行为准则。

---

## 12. Celery 任务

Phase 3 新增一个异步任务，用于 Agent 对话后的后台处理：

```python
# app/tasks/agent_tasks.py

from app.celery_app import celery_app

@celery_app.task(name="agent.update_memory_after_conversation")
def update_memory_after_conversation(session_id: str, user_id: str):
    """
    Agent 对话结束后，异步更新用户知识画像。
    分析对话中的工具调用记录，提取用户关注的知识点，
    更新 memory_index 中的相关知识画像条目。
    """
    # 1. 加载对话消息和工具调用记录
    # 2. 提取工具调用中涉及的知识点
    # 3. 更新 memory_index 中对应条目的 summary 和 embedding
    # 4. 同步到 Meilisearch
    pass


@celery_app.task(name="agent.auto_generate_session_title")
def auto_generate_session_title(session_id: str, user_id: str):
    """
    如果会话标题仍为自动生成的截断文本，
    使用 LLM 生成更有意义的标题。
    """
    # 1. 加载前 3 条消息
    # 2. 调用 LLM 生成标题（短 prompt）
    # 3. 更新 agent_sessions.title
    pass
```

---

## 13. 环境变量与配置

### 13.1 新增环境变量

```bash
# .env.example — Phase 3 新增

# Agent 编排（已有，确认保留）
AGENT_MAX_STEPS=6
AGENT_TOKEN_BUDGET=4000

# Agent 对话历史
AGENT_MAX_CONVERSATION_TURNS=10       # 注入 LLM 上下文的最大对话轮数
AGENT_AUTO_TITLE=true                  # 是否自动生成会话标题

# 搜索增强
SEARCH_HIGHLIGHT_ENABLED=true          # 全局搜索是否启用高亮
SEARCH_SEMANTIC_WEIGHT=0.3             # 语义搜索在 RRF 中的权重（0-1）
SEARCH_MEILISEARCH_TIMEOUT=5000        # Meilisearch 查询超时（ms）
```

### 13.2 Settings 类扩展

```python
# app/core/config.py — 新增字段

class Settings(BaseSettings):
    # ... 现有字段保持不变 ...

    # Agent 对话历史
    AGENT_MAX_CONVERSATION_TURNS: int = 10
    AGENT_AUTO_TITLE: bool = True

    # 搜索增强
    SEARCH_HIGHLIGHT_ENABLED: bool = True
    SEARCH_SEMANTIC_WEIGHT: float = 0.3
    SEARCH_MEILISEARCH_TIMEOUT: int = 5000
```

---

## 14. 验收标准

### 14.1 Agent 模块

- [ ] 创建会话 API：支持 general/note/lecture/route 四种 context_type，返回完整 session 对象
- [ ] 会话列表 API：支持 status 筛选和分页，按 updated_at 降序
- [ ] 会话详情 API：校验用户归属，非本人会话返回 404
- [ ] 关闭会话 API：status 变为 closed，后续消息发送返回 400
- [ ] 发送消息 API（HTTP）：保存用户消息 → Agent 推理 → 返回完整 assistant 消息
- [ ] 历史消息 API：游标分页，按时间正序返回
- [ ] 取消生成 API：Redis 设置取消令牌，AgentLoop 在下一步检测到并中断
- [ ] 工具列表 API：返回所有注册工具的 name/display_name/description/icon
- [ ] WebSocket 连接：`/ws/agent/{session_id}` 携带 token 认证
- [ ] WebSocket session_created：连接成功后立即推送
- [ ] WebSocket thinking：Agent 推理前推送思考状态
- [ ] WebSocket tool_call_start：工具调用开始前推送（含 tool_call_id、tool_name、display_name、input）
- [ ] WebSocket tool_call_result：工具调用完成后推送（含 status、output/error_message）
- [ ] WebSocket token：最终回答文本推送
- [ ] WebSocket done：推送完整 AgentMessage（含 tool_calls 数组）
- [ ] WebSocket cancel：客户端发送 cancel → AgentLoop 中断 → 推送 done
- [ ] WebSocket 认证失败：code=4001 关闭
- [ ] WebSocket 会话不存在：code=4004 关闭
- [ ] 上下文注入：context_type=note 时 system prompt 包含笔记标题/内容摘要/标签
- [ ] 上下文注入：context_type=route 时 system prompt 包含路线主题/步骤列表
- [ ] 消息持久化：所有 user/assistant 消息存入 agent_messages 表
- [ ] 自动标题：第一条用户消息的前 20 字符作为会话标题
- [ ] 端到端测试：创建会话 → WS 连接 → 发送消息 → 工具调用 → 流式回复 → 取消

### 14.2 搜索增强

- [ ] 全局搜索 API：返回结果 + 高亮片段 + 分面统计
- [ ] 全局搜索高亮：Meilisearch formatted 结果中 `<em>` 标签正确提取
- [ ] 全局搜索分面：按 type 分组计数正确
- [ ] 全局搜索分页：page + page_size 参数正确
- [ ] 语义搜索 API：返回带相似度分数的结果
- [ ] 知识节点关联 API：返回前置/后续知识 + 关联笔记 + 关联路线
- [ ] 知识节点关联：掌握度数据正确关联
- [ ] 端到端测试：搜索 → 高亮 → 跳转 → 关联展示

### 14.3 工具化

- [ ] 笔记服务：search_notes 返回笔记标题+摘要，get_note_content 返回完整内容
- [ ] 学习服务：search_knowledge 返回知识点列表，get_mastery 返回掌握度分数，get_route_progress 返回路线进度
- [ ] 答疑服务：get_qa_history 返回最近答疑摘要
- [ ] 复习服务：get_review_status 返回待复习列表，schedule_review 创建复习计划
- [ ] 搜索服务：global_search 和 semantic_search 作为 Agent 工具可用
- [ ] 记忆服务：recall_knowledge 返回知识画像，search_memory 语义搜索记忆
- [ ] 所有写操作工具（schedule_review）设置 category="write"
- [ ] 工具调用错误处理：工具异常不中断 Agent 循环，错误信息作为 tool 消息注入上下文

---

## 15. 非功能要求与技术债

### 15.1 非功能要求

1. **性能**：全局搜索 API 响应时间 < 500ms（P95），Agent 首 token 延迟 < 3s
2. **并发**：Agent WebSocket 支持单用户单会话（多会话排队），后端支持 100 并发 WS 连接
3. **安全**：Agent 不得调用删除类工具，写操作工具限流（每轮 1 次），token_budget 防资源耗尽
4. **可靠性**：Agent 循环异常不崩溃 WS 连接，发送 error 消息后等待下一条用户消息
5. **日志**：所有工具调用记录完整日志（tool_name、input、output、duration），用于审计和调试

### 15.2 技术债

1. **流式 LLM 输出**：当前 Agent 最终回答使用非流式 LLM 调用 + 一次性推送 token。后续应改为 LLM stream 模式，逐 token 推送 WS，提升用户体验。
2. **多模型 Agent**：当前 Agent 固定使用 agent_chat 路由的模型。后续应支持会话级别指定模型。
3. **工具权限分级**：当前仅区分 read/write。后续应细化为更细粒度的权限控制。
4. **Agent 消息搜索**：当前历史消息使用游标分页。大量消息时应考虑全文索引。
5. **取消机制优化**：当前通过 Redis 轮询检查取消。后续可改为 asyncio.Event 信号，减少 Redis 访问。

### 15.3 与 Phase 1-2 的兼容性

1. **现有 AI 功能不受影响**：讲义生成、苏格拉底答疑、RAG 检索、复习内容生成仍直接调用 AI 通信层，不经过 Agent。
2. **Phase 1-2 的 Agent 骨架代码**：本文档的 ToolSchema/ToolRegistry/AgentLoop 是 Phase 1-2 骨架的升级版本。原有 `POST /agent/chat` 和 `WS /ws/agent-chat` 端点废弃，替换为本文档的会话制端点。
3. **数据库迁移**：新增两张表（agent_sessions、agent_messages），不修改现有表结构。
