import json
import uuid

from sqlalchemy import select, text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.embedding import embed_query
from app.models.memory import MemoryFull, MemoryIndex
from app.services.memory.models import MemoryEntry


class MemoryRepository:
    """记忆存储层 — 封装索引层和全量层的CRUD"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_index_by_topic(self, user_id: uuid.UUID, topic: str, top_k: int = 5) -> list[MemoryEntry]:
        """索引层精确/模糊主题匹配"""
        result = await self.db.execute(
            select(MemoryIndex)
            .where(
                MemoryIndex.user_id == user_id,
                MemoryIndex.topic.ilike(f"%{topic}%"),
            )
            .order_by(MemoryIndex.relevance_score.desc())
            .limit(top_k)
        )
        rows = result.scalars().all()
        return [
            MemoryEntry(
                id=r.id,
                memory_type=r.memory_type,
                topic=r.topic,
                summary=r.summary,
                relevance_score=r.relevance_score or 0.0,
            )
            for r in rows
        ]

    async def search_index_by_vector(
        self, user_id: uuid.UUID, query_embedding: list[float], top_k: int = 5
    ) -> list[MemoryEntry]:
        """索引层向量检索"""
        sql = """
            SELECT id, memory_type, topic, summary, relevance_score, full_memory_id,
                   1 - (embedding <=> :query_vec::vector) as similarity
            FROM memory_index
            WHERE user_id = :user_id AND embedding IS NOT NULL
            ORDER BY embedding <=> :query_vec2::vector
            LIMIT :top_k
        """
        result = await self.db.execute(
            sql_text(sql),
            {
                "query_vec": str(query_embedding),
                "user_id": str(user_id),
                "query_vec2": str(query_embedding),
                "top_k": top_k,
            },
        )
        rows = result.fetchall()
        return [
            MemoryEntry(
                id=row[0],
                memory_type=row[1],
                topic=row[2],
                summary=row[3],
                relevance_score=float(row[4] or 0),
            )
            for row in rows
        ]

    async def load_full(self, full_ids: list[uuid.UUID]) -> list[MemoryEntry]:
        """全量层批量加载"""
        if not full_ids:
            return []
        result = await self.db.execute(
            select(MemoryFull).where(MemoryFull.id.in_(full_ids))
        )
        rows = result.scalars().all()
        return [
            MemoryEntry(
                id=r.id,
                memory_type=r.memory_type,
                topic=r.topic,
                summary="",
                full_data=r.content,
            )
            for r in rows
        ]

    async def upsert_full(
        self, memory_type: str, topic: str, content: dict, source_records: list | None = None
    ) -> uuid.UUID:
        """创建或更新全量记忆"""
        # 查找是否已存在
        result = await self.db.execute(
            select(MemoryFull).where(
                MemoryFull.memory_type == memory_type,
                MemoryFull.topic == topic,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.content = content
            if source_records:
                existing.source_records = source_records
            await self.db.flush()
            return existing.id
        else:
            new_record = MemoryFull(
                memory_type=memory_type,
                topic=topic,
                content=content,
                source_records=source_records or [],
            )
            self.db.add(new_record)
            await self.db.flush()
            return new_record.id

    async def upsert_index(
        self,
        user_id: uuid.UUID,
        memory_type: str,
        topic: str,
        summary: str,
        full_memory_id: uuid.UUID | None = None,
    ):
        """创建或更新索引条目（含embedding）"""
        # 生成embedding
        embedding = await embed_query(summary)

        # 查找是否已存在
        result = await self.db.execute(
            select(MemoryIndex).where(
                MemoryIndex.user_id == user_id,
                MemoryIndex.memory_type == memory_type,
                MemoryIndex.topic == topic,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.summary = summary
            existing.embedding = embedding
            existing.full_memory_id = full_memory_id
            await self.db.flush()
        else:
            new_entry = MemoryIndex(
                user_id=user_id,
                memory_type=memory_type,
                topic=topic,
                summary=summary,
                embedding=embedding,
                full_memory_id=full_memory_id,
            )
            self.db.add(new_entry)
            await self.db.flush()
