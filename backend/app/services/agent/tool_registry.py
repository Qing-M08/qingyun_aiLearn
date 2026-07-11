from collections.abc import Callable
from typing import Any

import structlog

from app.services.agent.tool_schemas import ToolResult, ToolSchema

logger = structlog.get_logger()


class ToolRegistry:
    """
    工具注册表 — 管理所有 Agent 可调用的工具。

    每个工具包含：
        - schema: ToolSchema（名称、描述、参数定义）
        - handler: 可调用对象，接收 user_id 和其他参数，返回 ToolResult 或 str
    """

    def __init__(self):
        self._tools: dict[str, tuple[ToolSchema, Callable]] = {}

    def register(self, schema: ToolSchema, handler: Callable):
        """注册一个工具"""
        self._tools[schema.name] = (schema, handler)
        logger.debug("tool_registered", name=schema.name, category=schema.category)

    def register_from_service(self, service_cls: type, handler_map: dict[str, Callable]):
        """
        从业务服务的 as_tools() 类方法批量注册工具。
        handler_map: {tool_name: handler_function}
        """
        tools = service_cls.as_tools()
        for tool in tools:
            handler = handler_map.get(tool.name)
            if handler:
                self.register(tool, handler)
            else:
                logger.warning("tool_handler_missing", tool_name=tool.name)

    def get_tool(self, name: str) -> ToolSchema | None:
        """获取工具 Schema"""
        entry = self._tools.get(name)
        return entry[0] if entry else None

    def get_all_schemas(self) -> list[ToolSchema]:
        """获取所有已注册工具 Schema"""
        return [schema for schema, _ in self._tools.values()]

    async def execute(self, name: str, user_id: str = "", **kwargs: Any) -> ToolResult:
        """
        执行指定工具。
        自动注入 user_id 作为第一个位置参数。

        返回 ToolResult，即使 handler 返回 str 也会包装为 ToolResult。
        """
        entry = self._tools.get(name)
        if not entry:
            return ToolResult(success=False, error_message=f"工具 '{name}' 不存在")

        schema, handler = entry
        try:
            # 注入 user_id 作为第一个参数
            result = await handler(user_id, **kwargs)

            # 标准化为 ToolResult
            if isinstance(result, ToolResult):
                return result
            if isinstance(result, str):
                return ToolResult(success=True, data=result)
            if isinstance(result, dict):
                return ToolResult(success=result.get("success", True), data=str(result.get("data", "")))

            return ToolResult(success=True, data=str(result))
        except Exception as e:
            logger.error("tool_execution_failed", tool_name=name, error=str(e))
            return ToolResult(success=False, error_message=str(e))


async def init_tool_registry() -> ToolRegistry:
    """
    初始化工具注册表，注册所有业务服务的工具。
    应用启动时调用一次，或在 Agent WebSocket 连接时调用。
    """
    registry = ToolRegistry()

    # 延迟导入避免循环依赖
    from app.services.note_service import NoteService
    from app.services.learning_service import LearningService
    from app.services.qa_service import QAService
    from app.services.review_service import ReviewService
    from app.services.search_service import SearchService
    from app.services.user_memory_service import UserMemoryService

    from app.services.agent.handlers.note_handlers import _tool_search_notes, _tool_get_note_content
    from app.services.agent.handlers.learning_handlers import (
        _tool_search_knowledge, _tool_get_mastery, _tool_get_route_progress,
    )
    from app.services.agent.handlers.qa_handlers import _tool_get_qa_history
    from app.services.agent.handlers.review_handlers import _tool_get_review_status, _tool_schedule_review
    from app.services.agent.handlers.search_handlers import _tool_global_search, _tool_semantic_search
    from app.services.agent.handlers.memory_handlers import _tool_recall_knowledge, _tool_search_memory

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
