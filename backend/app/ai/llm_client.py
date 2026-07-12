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
            self._clients[settings.DEEPSEEK_MODEL] = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com/v1",
            )

    def _get_client(self, model: str) -> AsyncOpenAI | None:
        """根据模型名称获取客户端"""
        if model.startswith("deepseek"):
            return self._clients.get(settings.DEEPSEEK_MODEL)
        return self._clients.get(settings.DEEPSEEK_MODEL)

    async def chat(
        self,
        messages: list[dict],
        model: str = settings.DEEPSEEK_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
    ) -> LLMResponse:
        client = self._get_client(model)
        if not client:
            raise RuntimeError(f"LLM client for model '{model}' not configured")

        kwargs: dict = {
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
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
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

    async def chat_stream(
        self,
        messages: list[dict],
        model: str = settings.DEEPSEEK_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        """
        流式聊天 — 异步生成器，逐token产出。
        用于WebSocket流式推送场景。
        """
        client = self._get_client(model)
        if not client:
            raise RuntimeError(f"LLM client for model '{model}' not configured")

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            stream = await client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error("llm_stream_chat_failed", error=str(e), model=model)
            raise

    async def embed(self, texts: list[str], model: str = "bge-small-zh-v1.5") -> list[list[float]]:
        """
        文本嵌入。使用本地模型（sentence-transformers），懒加载。
        """
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
