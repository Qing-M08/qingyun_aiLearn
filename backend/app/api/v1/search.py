import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.note import Note
from app.models.knowledge import KnowledgeNode
from app.models.learning import LearningRoute, Lecture
from app.services.search_service import (
    SearchService,
    search_notes_meilisearch,
    sync_all_to_meilisearch,
)

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/global")
async def global_search(
    q: str = Query(..., min_length=1),
    type: str = Query(default="all", pattern="^(all|notes|lectures|knowledge|routes)$"),
    subject: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    highlight: bool = Query(default=True),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """全局搜索（带高亮和分面统计）"""
    results = []
    facets: dict[str, int] = {}

    user_id = user.id
    user_id_str = str(user.id)

    # 1. 先尝试 Meilisearch 搜索
    ms_results = await _search_meilisearch(q, type, user_id_str, page_size, subject, highlight)
    results.extend(ms_results)
    for item in ms_results:
        t = item["type"]
        facets[t] = facets.get(t, 0) + 1

    # 2. Meilisearch 无结果或索引不存在时，退回数据库模糊搜索
    if not results:
        db_results = await _search_database(db, q, type, user_id, user_id_str, page_size, subject)
        results.extend(db_results)
        for item in db_results:
            t = item["type"]
            facets[t] = facets.get(t, 0) + 1

    total = len(results)

    # 分页
    start = (page - 1) * page_size
    paged = results[start:start + page_size]

    facet_list = [{"type": k, "count": v} for k, v in facets.items()]

    return {
        "data": {
            "results": paged,
            "total": total,
            "facets": facet_list,
        }
    }


async def _search_meilisearch(
    q: str, type: str, user_id: str, page_size: int, subject: str | None, highlight: bool
) -> list[dict]:
    """通过 Meilisearch 搜索各索引"""
    results = []
    import meilisearch
    from app.services.search_service import get_meilisearch_client

    client = get_meilisearch_client()

    indexes_map = {
        "notes": ("note", [f"user_id = {user_id}"]),
        "lectures": ("lecture", [f"user_id = {user_id}"]),
        "knowledge_nodes": ("knowledge", []),
        "learning_routes": ("route", [f"user_id = {user_id}"]),
    }

    indexes_to_search = []
    if type == "all":
        indexes_to_search = list(indexes_map.keys())
    elif type == "notes":
        indexes_to_search = ["notes"]
    elif type == "lectures":
        indexes_to_search = ["lectures"]
    elif type == "knowledge":
        indexes_to_search = ["knowledge_nodes"]
    elif type == "routes":
        indexes_to_search = ["learning_routes"]

    search_params = {
        "limit": page_size,
    }
    if highlight:
        search_params["attributesToHighlight"] = ["title", "content", "name", "description", "topic"]
        search_params["highlightPreTag"] = "<em>"
        search_params["highlightPostTag"] = "</em>"

    for idx_name in indexes_to_search:
        result_type, base_filters = indexes_map[idx_name]
        if subject and idx_name != "learning_routes":
            base_filters.append(f'subject = "{subject}"')
        if base_filters:
            search_params["filter"] = base_filters
        else:
            search_params.pop("filter", None)

        try:
            ms_result = client.index(idx_name).search(q, search_params)
            for hit in ms_result.get("hits", []):
                results.append(_format_hit(hit, idx_name, result_type))
        except Exception:
            pass  # 索引不存在或查询失败，跳过

    return results


async def _search_database(
    db: AsyncSession, q: str, type: str, user_id: uuid.UUID, user_id_str: str,
    page_size: int, subject: str | None,
) -> list[dict]:
    """数据库模糊搜索兜底"""
    results = []
    like_q = f"%{q}%"

    # 搜索笔记
    if type in ("all", "notes"):
        try:
            note_q = select(Note).where(
                Note.user_id == user_id,
                or_(Note.title.ilike(like_q), Note.content.ilike(like_q)),
            ).limit(page_size)
            note_result = await db.execute(note_q)
            for n in note_result.scalars().all():
                results.append({
                    "id": str(n.id),
                    "type": "note",
                    "title": n.title,
                    "content_preview": (n.content or "")[:200],
                    "subject": n.subject,
                    "highlights": [],
                    "created_at": n.created_at.isoformat() if n.created_at else "",
                })
        except Exception:
            pass

    # 搜索讲义
    if type in ("all", "lectures"):
        try:
            lec_q = select(Lecture).where(
                Lecture.user_id == user_id,
                or_(Lecture.title.ilike(like_q), Lecture.content.ilike(like_q)),
            ).limit(page_size)
            lec_result = await db.execute(lec_q)
            for lec in lec_result.scalars().all():
                results.append({
                    "id": str(lec.id),
                    "type": "lecture",
                    "title": lec.title,
                    "content_preview": (lec.content or "")[:200],
                    "subject": None,
                    "highlights": [],
                    "created_at": lec.created_at.isoformat() if lec.created_at else "",
                })
        except Exception:
            pass

    # 搜索知识节点
    if type in ("all", "knowledge"):
        try:
            node_q = select(KnowledgeNode).where(
                or_(
                    KnowledgeNode.name.ilike(like_q),
                    KnowledgeNode.description.ilike(like_q),
                )
            )
            if subject:
                node_q = node_q.where(KnowledgeNode.subject == subject)
            node_q = node_q.limit(page_size)
            node_result = await db.execute(node_q)
            for n in node_result.scalars().all():
                results.append({
                    "id": str(n.id),
                    "type": "knowledge",
                    "title": n.name,
                    "content_preview": (n.description or "")[:200],
                    "subject": n.subject,
                    "highlights": [],
                    "created_at": n.created_at.isoformat() if n.created_at else "",
                })
        except Exception:
            pass

    # 搜索学习路线
    if type in ("all", "routes"):
        try:
            route_q = select(LearningRoute).where(
                LearningRoute.user_id == user_id,
                LearningRoute.topic.ilike(like_q),
            ).limit(page_size)
            route_result = await db.execute(route_q)
            for r in route_result.scalars().all():
                results.append({
                    "id": str(r.id),
                    "type": "route",
                    "title": r.topic,
                    "content_preview": (r.description or "")[:200],
                    "subject": None,
                    "highlights": [],
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                })
        except Exception:
            pass

    return results


@router.get("/semantic")
async def semantic_search(
    q: str = Query(..., min_length=1),
    type: str | None = None,
    top_k: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """语义搜索"""
    try:
        from app.ai.rag.embedding import embed_query
        query_embedding = await embed_query(q)

        # 使用 Meilisearch 做关键词搜索作为语义搜索的近似
        ms_result = await search_notes_meilisearch(
            query=q, user_id=str(user.id), page=1, page_size=top_k
        )

        formatted = []
        for hit in ms_result.get("hits", []):
            formatted.append({
                "id": hit.get("id", ""),
                "type": "note",
                "title": hit.get("title", ""),
                "content_preview": (hit.get("content", "") or "")[:200],
                "subject": hit.get("subject"),
                "score": 0.8,  # 近似分数
                "highlights": [],
                "created_at": hit.get("created_at", ""),
            })

        # 如果 Meilisearch 无结果，退回数据库搜索
        if not formatted:
            like_q = f"%{q}%"
            note_q = select(Note).where(
                Note.user_id == user.id,
                or_(Note.title.ilike(like_q), Note.content.ilike(like_q)),
            ).limit(top_k)
            note_result = await db.execute(note_q)
            for n in note_result.scalars().all():
                formatted.append({
                    "id": str(n.id),
                    "type": "note",
                    "title": n.title,
                    "content_preview": (n.content or "")[:200],
                    "subject": n.subject,
                    "score": 0.5,
                    "highlights": [],
                    "created_at": n.created_at.isoformat() if n.created_at else "",
                })

        return {"data": formatted}
    except Exception as e:
        return {"data": [], "error": str(e)}


@router.post("/reindex")
async def reindex_all(
    user: User = Depends(get_current_user),
):
    """手动触发全量重建 Meilisearch 索引"""
    count = await sync_all_to_meilisearch()
    return {"data": {"synced": count, "message": f"已同步 {count} 条记录到搜索引擎"}}


def _format_hit(hit: dict, index_name: str, result_type: str) -> dict:
    """将 Meilisearch 命中结果格式化为统一结构"""
    title = hit.get("title") or hit.get("name") or hit.get("topic") or ""
    content = hit.get("content") or hit.get("description") or ""

    # 提取高亮
    highlights = []
    formatted = hit.get("_formatted", {})
    if formatted:
        for key in ["title", "content", "name", "description", "topic"]:
            val = formatted.get(key)
            if val and "<em>" in val:
                highlights.append({"field": key, "snippet": val})

    return {
        "id": hit.get("id", ""),
        "type": result_type,
        "title": title,
        "content_preview": content[:200],
        "subject": hit.get("subject"),
        "highlights": highlights,
        "created_at": hit.get("created_at", ""),
    }
