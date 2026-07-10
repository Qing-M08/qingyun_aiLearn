import meilisearch

from app.config import settings

_client: meilisearch.Client | None = None


def get_meilisearch_client() -> meilisearch.Client:
    global _client
    if _client is None:
        _client = meilisearch.Client(settings.MEILISEARCH_URL, settings.MEILISEARCH_MASTER_KEY)
    return _client


async def init_meilisearch_indexes():
    """初始化Meilisearch索引（应用启动时调用）"""
    client = get_meilisearch_client()

    # 笔记索引
    try:
        client.create_index("notes", {"primary_key": "id"})
    except Exception:
        pass  # 索引已存在

    notes_index = client.index("notes")
    notes_index.update_searchable_attributes(["title", "content"])
    notes_index.update_filterable_attributes(["user_id", "subject", "created_at", "updated_at"])
    notes_index.update_sortable_attributes(["created_at", "updated_at", "word_count"])


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
