import redis.asyncio as redis

from app.config import settings


async def _get_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def set_cancel_token(session_id: str):
    """设置取消令牌，Agent 循环每步检查此 key"""
    r = await _get_redis()
    await r.set(f"agent_cancel:{session_id}", "1", ex=settings.AGENT_CANCEL_TTL)
    await r.aclose()


async def clear_cancel_token(session_id: str):
    """清除取消令牌（新一轮对话开始时）"""
    r = await _get_redis()
    await r.delete(f"agent_cancel:{session_id}")
    await r.aclose()


async def is_cancelled(session_id: str) -> bool:
    """检查是否已取消"""
    r = await _get_redis()
    result = await r.get(f"agent_cancel:{session_id}")
    await r.aclose()
    return result is not None
