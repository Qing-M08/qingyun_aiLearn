import uuid
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import WebSocket

from app.ai.llm_client import get_llm_client, LLMClient
from app.config import settings
from app.core.cancel_token import is_cancelled as check_cancel
from app.models.agent_message import AgentMessage
from app.models.agent_session import AgentSession
from app.services.agent.context_builder import ContextBuilder
from app.services.agent.tool_registry import ToolRegistry
from app.services.user_memory_service import UserMemoryService

logger = structlog.get_logger()


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
        llm_client: LLMClient | None = None,
        session: AgentSession | None = None,
        db: AsyncSession | None = None,
        ws: WebSocket | None = None,
        cancel_key: str | None = None,
        max_steps: int | None = None,
        token_budget: int | None = None,
    ):
        self.registry = registry
        self.llm = llm_client or get_llm_client()
        self.session = session
        self.db = db
        self.ws = ws
        self.cancel_key = cancel_key
        self.max_steps = max_steps or settings.AGENT_MAX_STEPS
        self.token_budget = token_budget or settings.AGENT_TOKEN_BUDGET
        self.total_tokens_used = 0

    async def run(self, user_message: str, conversation_history: list[dict]) -> AgentMessage:
        """
        执行一次完整的 Agent 循环。
        返回持久化后的 assistant AgentMessage。
        """
        user_id = str(self.session.user_id) if self.session else ""
        memory_service = UserMemoryService(self.db) if self.db else None

        # 1. 加载用户记忆（Push 模式：习惯摘要注入 system prompt）
        habit_summary = ""
        if memory_service and user_id:
            try:
                user_memory = await memory_service.get_user_memory(uuid.UUID(user_id))
                habit_summary = await user_memory.get_habit_summary()
            except Exception:
                habit_summary = "暂无用户习惯数据"

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
            if self.cancel_key and await check_cancel(self.cancel_key):
                await self._push_ws("done", {
                    "message": self._build_message_dict("已取消生成。", all_tool_calls, step + 1)
                })
                return await self._save_assistant_message("已取消生成。", all_tool_calls, step + 1)

            # 检查 token 预算
            if self.total_tokens_used >= self.token_budget:
                final_answer = "已达到本次对话的 token 上限，以下是我目前的回答。"
                break

            # 调用 LLM
            try:
                response = await self.llm.chat(
                    messages=messages,
                    tools=self._format_tools_for_llm(),
                    tool_choice="auto",
                    stream=False,
                )
                self.total_tokens_used += response.usage.get("total_tokens", 0)
            except Exception as e:
                logger.error("agent_llm_error", error=str(e))
                final_answer = "抱歉，AI 服务暂时不可用，请稍后重试。"
                break

            # 情况 A：LLM 决定调用工具
            if response.tool_calls:
                thinking_text = response.content or "让我使用工具来查找相关信息..."
                await self._push_ws("thinking", {"content": thinking_text})

                # 必须先将 assistant 的 tool_calls 消息加入上下文，
                # 否则后续的 tool 消息会因缺少前置 assistant(tool_calls) 而报错
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": tc["arguments"] if isinstance(tc["arguments"], str) else str(tc["arguments"]),
                            },
                        }
                        for tc in response.tool_calls
                    ],
                })

                write_call_count = 0
                for tool_call in response.tool_calls:
                    tc_id = str(uuid.uuid4())
                    tc_start_time = datetime.utcnow()

                    tool_schema = self.registry.get_tool(tool_call.get("name", ""))

                    # 写操作限流
                    if tool_schema and tool_schema.category == "write":
                        write_call_count += 1
                        if write_call_count > 1:
                            await self._push_ws("thinking", {
                                "content": "写操作已限流，跳过后续写操作。"
                            })
                            continue

                    # 解析 arguments（可能是 JSON 字符串）
                    args = tool_call.get("arguments", {})
                    if isinstance(args, str):
                        import json as _json
                        try:
                            args = _json.loads(args)
                        except Exception:
                            args = {}

                    # 推送 tool_call_start
                    await self._push_ws("tool_call_start", {
                        "tool_call_id": tc_id,
                        "tool_name": tool_call.get("name", ""),
                        "tool_display_name": tool_schema.display_name if tool_schema else tool_call.get("name", ""),
                        "input": args,
                    })

                    # 执行工具
                    result = await self.registry.execute(
                        tool_call.get("name", ""),
                        user_id=user_id,
                        **args,
                    )
                    self.total_tokens_used += result.token_count

                    tc_end_time = datetime.utcnow()

                    # 记录工具调用
                    tc_record = {
                        "id": tc_id,
                        "tool_name": tool_call.get("name", ""),
                        "tool_display_name": tool_schema.display_name if tool_schema else tool_call.get("name", ""),
                        "input": args,
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
                        "tool_call_id": tool_call.get("id", ""),
                        "content": result.data if result.success else f"工具调用失败: {result.error_message}",
                    })

                continue  # 继续下一轮推理

            # 情况 B：LLM 给出最终回答
            else:
                final_answer = response.content or ""
                break

        # 7. 循环结束
        if not final_answer:
            final_answer = "抱歉，我暂时无法完成这个请求，请尝试换一种方式提问。"

        # 8. 流式推送最终回答
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
        if not self.session or not self.db:
            return ""
        if self.session.context_type == "general" or not self.session.context_id:
            return ""

        builder = ContextBuilder(self.db)
        return await builder.build_context(
            context_type=self.session.context_type,
            context_id=str(self.session.context_id),
            user_id=str(self.session.user_id),
        )

    async def _save_assistant_message(
        self, content: str, tool_calls: list[dict], steps: int
    ) -> AgentMessage:
        """持久化 assistant 消息到数据库"""
        if not self.db:
            raise RuntimeError("AgentLoop 未绑定数据库会话")

        msg = AgentMessage(
            session_id=self.session.id,
            role="assistant",
            content=content,
            tool_calls=tool_calls,
            metadata_={
                "total_steps": steps,
                "tokens_used": self.total_tokens_used,
                "model": self.llm._get_client("deepseek-chat") and "deepseek-chat" or "unknown",
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
                    AgentMessage.role == "user",
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
            "created_at": msg.created_at.isoformat() + "Z" if msg.created_at else "",
        }

    def _build_message_dict(self, content: str, tool_calls: list, steps: int) -> dict:
        """构建消息 dict（用于取消等场景）"""
        return {
            "id": "",
            "session_id": str(self.session.id) if self.session else "",
            "role": "assistant",
            "content": content,
            "tool_calls": tool_calls,
            "metadata": {"total_steps": steps, "tokens_used": self.total_tokens_used},
            "created_at": datetime.utcnow().isoformat() + "Z",
        }

    def _build_system_prompt(self, habit_summary: str, context_text: str) -> str:
        """构建包含用户习惯和上下文的 system prompt"""
        tools = self.registry.get_all_schemas()
        tool_descriptions = "\n".join([
            f"- **{t.display_name}** (`{t.name}`): {t.description}"
            for t in tools
        ])
        return f"""你是青云智学AI助手，一个智能学习伙伴。你可以帮助学生解答问题、查找笔记、推荐复习内容、搜索知识点等。

## 用户学习习惯
{habit_summary or '暂无用户习惯数据'}

## 当前上下文
{context_text or '无额外上下文'}

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
8. 当前时间：{datetime.utcnow().isoformat()}
"""

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
            try:
                await self.ws.send_json({"type": event_type, "data": data})
            except Exception:
                pass
