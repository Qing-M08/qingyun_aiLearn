from app.config import settings

# 模型路由配置
MODEL_ROUTING = {
    "default": settings.DEEPSEEK_MODEL,
    "long_context": settings.DEEPSEEK_MODEL,
    "chinese_education": settings.DEEPSEEK_MODEL,
    "high_precision": settings.DEEPSEEK_MODEL,
    "embedding": "bge-small-zh-v1.5",
    "agent_chat": settings.DEEPSEEK_MODEL,
}


async def route_model(task_type: str, context_length: int = 0, **kwargs) -> str:
    """根据任务类型选择模型"""
    if context_length > 32000:
        return MODEL_ROUTING["long_context"]
    return MODEL_ROUTING.get(task_type, MODEL_ROUTING["default"])
