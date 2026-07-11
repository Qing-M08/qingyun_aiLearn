import meilisearch
import structlog
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory

logger = structlog.get_logger()

_client: meilisearch.Client | None = None


def get_meilisearch_client() -> meilisearch.Client:
    global _client
    if _client is None:
        _client = meilisearch.Client(settings.MEILISEARCH_URL, settings.MEILISEARCH_MASTER_KEY)
    return _client


class SearchService:

    @classmethod
    def as_tools(cls) -> list:
        """暴露搜索相关工具供 Agent 调用"""
        from app.services.agent.tool_schemas import ToolParameter, ToolSchema
        return [
            ToolSchema(
                name="global_search",
                display_name="全局搜索",
                description="全局搜索用户的笔记、讲义、知识点、学习路线，返回匹配摘要",
                parameters={
                    "query": ToolParameter(type="string", description="搜索关键词"),
                    "search_type": ToolParameter(
                        type="string",
                        description="搜索范围",
                        enum=["notes", "lectures", "knowledge", "routes", "all"],
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

    @staticmethod
    def _source_type_to_result_type(source_type: str) -> str:
        mapping = {
            "user_note": "note",
            "note": "note",
            "lecture": "lecture",
            "knowledge_node": "knowledge",
            "learning_route": "route",
        }
        return mapping.get(source_type, source_type)


async def _ensure_index(client: meilisearch.Client, uid: str, primary_key: str = "id"):
    """确保索引存在且 primaryKey 正确，若 primaryKey 为 null 则删除重建"""
    try:
        info = client.get_index(uid)
        if info.primary_key is None:
            # primaryKey 为 null，需要删除重建
            client.delete_index(uid)
            import time
            time.sleep(1)  # 等待删除完成
            client.create_index(uid, {"primary_key": primary_key})
            logger.info("index_recreated", uid=uid, primary_key=primary_key)
    except Exception:
        # 索引不存在，创建新的
        try:
            client.create_index(uid, {"primary_key": primary_key})
        except Exception:
            pass


async def init_meilisearch_indexes():
    """初始化Meilisearch索引（应用启动时调用）"""
    client = get_meilisearch_client()

    # 笔记索引
    await _ensure_index(client, "notes")
    notes_index = client.index("notes")
    notes_index.update_searchable_attributes(["title", "content", "subject"])
    notes_index.update_filterable_attributes(["user_id", "subject", "created_at", "updated_at"])
    notes_index.update_sortable_attributes(["created_at", "updated_at", "word_count"])

    # 讲义索引
    await _ensure_index(client, "lectures")
    lectures_index = client.index("lectures")
    lectures_index.update_searchable_attributes(["title", "content"])
    lectures_index.update_filterable_attributes(["user_id", "status", "created_at"])

    # 知识节点索引
    await _ensure_index(client, "knowledge_nodes")
    knowledge_index = client.index("knowledge_nodes")
    knowledge_index.update_searchable_attributes(["name", "description", "subject"])
    knowledge_index.update_filterable_attributes(["subject", "grade_level", "difficulty"])

    # 学习路线索引
    await _ensure_index(client, "learning_routes")
    routes_index = client.index("learning_routes")
    routes_index.update_searchable_attributes(["topic", "description"])
    routes_index.update_filterable_attributes(["user_id", "status"])

    logger.info("meilisearch_indexes_initialized")


async def sync_all_notes_to_meilisearch():
    """将数据库中所有笔记同步到 Meilisearch（启动时或手动触发）"""
    from app.models.note import Note

    client = get_meilisearch_client()
    async with async_session_factory() as db:
        result = await db.execute(select(Note))
        notes = result.scalars().all()

    if not notes:
        logger.info("no_notes_to_sync")
        return 0

    docs = []
    for n in notes:
        docs.append({
            "id": str(n.id),
            "user_id": str(n.user_id),
            "title": n.title or "",
            "content": (n.content or "")[:5000],  # 截断过长内容
            "subject": n.subject,
            "word_count": n.word_count or 0,
            "created_at": n.created_at.isoformat() if n.created_at else "",
            "updated_at": n.updated_at.isoformat() if n.updated_at else "",
        })

    client.index("notes").add_documents(docs)
    logger.info("notes_synced_to_meilisearch", count=len(docs))
    return len(docs)


async def sync_all_knowledge_nodes():
    """将数据库中所有知识节点同步到 Meilisearch"""
    from app.models.knowledge import KnowledgeNode

    client = get_meilisearch_client()
    async with async_session_factory() as db:
        result = await db.execute(select(KnowledgeNode))
        nodes = result.scalars().all()

    if not nodes:
        logger.info("no_knowledge_nodes_to_sync")
        return 0

    docs = []
    for n in nodes:
        docs.append({
            "id": str(n.id),
            "name": n.name,
            "description": (n.description or "")[:2000],
            "subject": n.subject,
            "grade_level": n.grade_level,
            "difficulty": n.difficulty,
        })

    client.index("knowledge_nodes").add_documents(docs)
    logger.info("knowledge_nodes_synced", count=len(docs))
    return len(docs)


async def sync_all_lectures():
    """将数据库中所有讲义同步到 Meilisearch"""
    from app.models.learning import Lecture

    client = get_meilisearch_client()
    async with async_session_factory() as db:
        result = await db.execute(select(Lecture))
        lectures = result.scalars().all()

    if not lectures:
        logger.info("no_lectures_to_sync")
        return 0

    docs = []
    for lec in lectures:
        docs.append({
            "id": str(lec.id),
            "user_id": str(lec.user_id),
            "title": lec.title or "",
            "content": (lec.content or "")[:5000],
            "status": lec.status,
            "created_at": lec.created_at.isoformat() if lec.created_at else "",
        })

    client.index("lectures").add_documents(docs)
    logger.info("lectures_synced", count=len(docs))
    return len(docs)


async def sync_all_learning_routes():
    """将数据库中所有学习路线同步到 Meilisearch"""
    from app.models.learning import LearningRoute

    client = get_meilisearch_client()
    async with async_session_factory() as db:
        result = await db.execute(select(LearningRoute))
        routes = result.scalars().all()

    if not routes:
        logger.info("no_routes_to_sync")
        return 0

    docs = []
    for r in routes:
        docs.append({
            "id": str(r.id),
            "user_id": str(r.user_id),
            "topic": r.topic or "",
            "description": (r.description or "")[:2000],
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        })

    client.index("learning_routes").add_documents(docs)
    logger.info("learning_routes_synced", count=len(docs))
    return len(docs)


async def sync_all_to_meilisearch():
    """全量同步所有数据到 Meilisearch"""
    total = 0
    total += await sync_all_notes_to_meilisearch()
    total += await sync_all_knowledge_nodes()
    total += await sync_all_lectures()
    total += await sync_all_learning_routes()
    logger.info("full_sync_completed", total=total)
    return total


async def index_note(note_data: dict):
    """索引一条笔记"""
    client = get_meilisearch_client()
    client.index("notes").add_documents([note_data])


async def delete_note_index(note_id: str):
    """删除笔记索引"""
    client = get_meilisearch_client()
    client.index("notes").delete_document(note_id)


async def search_notes_meilisearch(
    query: str,
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    subject: str | None = None,
) -> dict:
    """Meilisearch全文搜索笔记"""
    client = get_meilisearch_client()
    filters = [f"user_id = {user_id}"]
    if subject:
        filters.append(f'subject = "{subject}"')

    results = client.index("notes").search(
        query,
        {
            "filter": filters,
            "offset": (page - 1) * page_size,
            "limit": page_size,
        },
    )
    return results
