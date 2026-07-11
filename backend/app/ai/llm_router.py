# 模型路由配置
MODEL_ROUTING = {
    "default": "deepseek-chat",
    "long_context": "deepseek-chat",
    "chinese_education": "deepseek-chat",
    "high_precision": "deepseek-chat",
    "embedding": "bge-small-zh-v1.5",
    "agent_chat": "deepseek-chat",
}


async def route_model(task_type: str, context_length: int = 0, **kwargs) -> str:
    """根据任务类型选择模型"""
    if context_length > 32000:
        return MODEL_ROUTING["long_context"]
    return MODEL_ROUTING.get(task_type, MODEL_ROUTING["default"])
