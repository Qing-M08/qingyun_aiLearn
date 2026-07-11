import math
import os

import structlog

from app.config import settings

logger = structlog.get_logger()

_embedder = None


def get_embedder():
    """获取全局嵌入模型（懒加载单例，首次调用时才加载模型）"""
    global _embedder
    if _embedder is None:
        # 设置 HuggingFace 镜像地址（国内环境）
        os.environ.setdefault("HF_ENDPOINT", settings.HF_ENDPOINT)
        logger.info("loading_embedding_model", model="BAAI/bge-small-zh-v1.5")
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("BAAI/bge-small-zh-v1.5")
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
