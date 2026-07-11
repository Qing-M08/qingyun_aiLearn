import uuid

from app.database import async_session_factory
from app.services.user_memory_service import UserMemoryService


async def _tool_recall_knowledge(user_id: str, topic: str, depth: str = "brief") -> str:
    """回忆知识画像工具 handler"""
    async with async_session_factory() as db:
        service = UserMemoryService(db)
        user_memory = await service.get_user_memory(uuid.UUID(user_id))
        result = await user_memory.recall(topic, depth=depth)
        if not result:
            return f"未找到关于「{topic}」的知识画像。"
        return result


async def _tool_search_memory(user_id: str, query: str, top_k: int = 3) -> str:
    """搜索记忆工具 handler"""
    async with async_session_factory() as db:
        service = UserMemoryService(db)
        user_memory = await service.get_user_memory(uuid.UUID(user_id))
        results = await user_memory.search_memory(query, top_k=top_k)
        if not results:
            return "未找到相关记忆。"
        return results
