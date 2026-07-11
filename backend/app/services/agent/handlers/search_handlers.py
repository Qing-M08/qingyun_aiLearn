import uuid

from sqlalchemy import select, or_

from app.database import async_session_factory
from app.models.note import Note
from app.models.knowledge import KnowledgeNode
from app.models.learning import Lecture, LearningRoute
from app.services.search_service import search_notes_meilisearch
from app.ai.rag.embedding import embed_query


async def _tool_global_search(user_id: str, query: str, search_type: str = "all", top_k: int = 5) -> str:
    """全局搜索工具 handler — 搜索笔记、讲义、知识节点、学习路线"""
    if not query.strip():
        return "请提供搜索关键词。"

    results = []
    like_q = f"%{query}%"

    try:
        async with async_session_factory() as db:
            # 搜索笔记
            if search_type in ("all", "notes"):
                # 先尝试 Meilisearch
                try:
                    ms_result = await search_notes_meilisearch(
                        query=query, user_id=user_id, page=1, page_size=max(3, top_k)
                    )
                    for hit in ms_result.get("hits", []):
                        results.append({
                            "source_type": "note",
                            "title": hit.get("title", ""),
                            "content": hit.get("content", "")[:120],
                        })
                except Exception:
                    pass

                # Meilisearch 无结果则退回 DB
                if not results:
                    note_q = select(Note).where(
                        Note.user_id == uuid.UUID(user_id),
                        or_(Note.title.ilike(like_q), Note.content.ilike(like_q)),
                    ).limit(top_k)
                    note_result = await db.execute(note_q)
                    for n in note_result.scalars().all():
                        results.append({
                            "source_type": "note",
                            "title": n.title,
                            "content": (n.content or "")[:120],
                        })

            # 搜索讲义
            if search_type in ("all", "lectures"):
                lec_q = select(Lecture).where(
                    Lecture.user_id == uuid.UUID(user_id),
                    or_(Lecture.title.ilike(like_q), Lecture.content.ilike(like_q)),
                ).limit(top_k)
                lec_result = await db.execute(lec_q)
                for lec in lec_result.scalars().all():
                    results.append({
                        "source_type": "lecture",
                        "title": lec.title,
                        "content": (lec.content or "")[:120],
                    })

            # 搜索知识节点
            if search_type in ("all", "knowledge"):
                node_q = select(KnowledgeNode).where(
                    or_(
                        KnowledgeNode.name.ilike(like_q),
                        KnowledgeNode.description.ilike(like_q),
                    )
                ).limit(top_k)
                node_result = await db.execute(node_q)
                for n in node_result.scalars().all():
                    results.append({
                        "source_type": "knowledge",
                        "title": n.name,
                        "content": (n.description or "")[:120],
                    })

            # 搜索学习路线
            if search_type in ("all", "routes"):
                route_q = select(LearningRoute).where(
                    LearningRoute.user_id == uuid.UUID(user_id),
                    LearningRoute.topic.ilike(like_q),
                ).limit(top_k)
                route_result = await db.execute(route_q)
                for r in route_result.scalars().all():
                    results.append({
                        "source_type": "route",
                        "title": r.topic,
                        "content": (r.description or "")[:120],
                    })

        if not results:
            return "未找到相关内容。"

        lines = []
        type_icons = {"note": "📝", "lecture": "📖", "knowledge": "🧠", "route": "🗺"}
        for r in results:
            icon = type_icons.get(r["source_type"], "📄")
            lines.append(f"{icon} [{r['source_type']}] {r['title']}\n  摘要: {r['content'][:120]}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"搜索失败：{str(e)}"


async def _tool_semantic_search(user_id: str, query: str, top_k: int = 5) -> str:
    """语义搜索工具 handler — 综合搜索笔记、知识节点"""
    if not query.strip():
        return "请提供搜索描述。"

    results = []
    like_q = f"%{query}%"

    try:
        # 尝试 Meilisearch 搜索笔记
        try:
            client = None
            from app.services.search_service import get_meilisearch_client
            client = get_meilisearch_client()
            ms_result = client.index("notes").search(
                query,
                {
                    "filter": [f"user_id = {user_id}"],
                    "limit": top_k,
                },
            )
            for hit in ms_result.get("hits", []):
                results.append({
                    "source_type": "note",
                    "title": hit.get("title", ""),
                    "content": hit.get("content", "")[:150],
                })
        except Exception:
            pass

        # 搜索知识节点
        async with async_session_factory() as db:
            node_q = select(KnowledgeNode).where(
                or_(
                    KnowledgeNode.name.ilike(like_q),
                    KnowledgeNode.description.ilike(like_q),
                )
            ).limit(top_k)
            node_result = await db.execute(node_q)
            for n in node_result.scalars().all():
                results.append({
                    "source_type": "knowledge",
                    "title": n.name,
                    "content": (n.description or "")[:150],
                })

            # 如果还没结果，搜索笔记 DB
            if not results:
                note_q = select(Note).where(
                    Note.user_id == uuid.UUID(user_id),
                    or_(Note.title.ilike(like_q), Note.content.ilike(like_q)),
                ).limit(top_k)
                note_result = await db.execute(note_q)
                for n in note_result.scalars().all():
                    results.append({
                        "source_type": "note",
                        "title": n.title,
                        "content": (n.content or "")[:150],
                    })

        if not results:
            return "未找到语义相关内容。"

        lines = []
        type_icons = {"note": "📝", "knowledge": "🧠"}
        for r in results:
            icon = type_icons.get(r["source_type"], "📄")
            lines.append(f"{icon} [{r['source_type']}] {r['title']}\n  {r['content'][:150]}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"语义搜索失败：{str(e)}"
