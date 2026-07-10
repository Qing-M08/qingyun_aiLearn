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
