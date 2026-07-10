import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.ai.rag.embedding import embed_query
from app.models.knowledge import KnowledgeNode, UserKnowledgeMastery
from app.models.memory import MemoryIndex
from app.models.user import PersonalHabitProfile, UserProfile
from app.services.memory.models import MemoryEntry
from app.services.memory.repository import MemoryRepository

logger = structlog.get_logger()


class UserMemory:
    """
    用户记忆对象 — AI通过AgentLoop直接调用的统一接口。
    """

    def __init__(self, user_id: uuid.UUID, db: AsyncSession):
        self.user_id = user_id
        self.db = db
        self.repo = MemoryRepository(db)
        self._index_cache: dict[str, MemoryEntry] | None = None

    # ---------- 推送部分：个人习惯摘要 ----------

    async def get_habit_summary(self) -> str:
        """返回200-300 token的个人习惯摘要，嵌入system prompt"""
        result = await self.db.execute(
            select(PersonalHabitProfile).where(PersonalHabitProfile.user_id == self.user_id)
        )
        profile = result.scalar_one_or_none()

        if profile and profile.summary_cache:
            return profile.summary_cache

        # 无缓存，实时生成
        summary = await self._build_habit_summary()
        if profile:
            profile.summary_cache = summary
        else:
            profile = PersonalHabitProfile(user_id=self.user_id, summary_cache=summary)
            self.db.add(profile)
        await self.db.flush()
        return summary

    async def _build_habit_summary(self) -> str:
        """生成个人习惯摘要文本（严格控制在300 token以内）"""
        result = await self.db.execute(
            select(PersonalHabitProfile).where(PersonalHabitProfile.user_id == self.user_id)
        )
        profile = result.scalar_one_or_none()

        result2 = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == self.user_id)
        )
        base = result2.scalar_one_or_none()

        parts = []
        if profile:
            if profile.active_time_slot:
                parts.append(f"活跃时段：{profile.active_time_slot}")
            if profile.content_preference:
                parts.append(f"内容偏好：{profile.content_preference}")
            if profile.avg_session_minutes:
                parts.append(f"单次学习时长：{profile.avg_session_minutes}分钟")
            parts.append(f"回答详略：{profile.detail_preference or 'balanced'}")
            if profile.weak_node_names:
                parts.append(f"待加强：{'、'.join(profile.weak_node_names[:5])}")
        if base:
            parts.append(f"连续学习：{base.streak_days}天")

        return "用户画像：" + "；".join(parts) if parts else "用户画像：暂无数据"

    # ---------- 拉取部分：知识画像工具 ----------

    async def recall(self, topic: str, depth: str = "summary") -> str:
        """
        AI主动回忆知识内容。
        depth="summary" → 索引层摘要
        depth="detail"  → 全量层完整数据
        """
        results = await self.repo.search_index_by_topic(self.user_id, topic, top_k=5)
        if not results:
            # 尝试向量检索
            query_emb = await embed_query(topic)
            results = await self.repo.search_index_by_vector(self.user_id, query_emb, top_k=5)

        if not results:
            return f"未找到与'{topic}'相关的学习记忆。"

        if depth == "summary":
            return "\n".join([f"- [{r.topic}] {r.summary}" for r in results])

        # depth="detail"
        full_ids = []
        for r in results:
            idx_result = await self.db.execute(
                select(MemoryIndex).where(MemoryIndex.id == r.id)
            )
            idx = idx_result.scalar_one_or_none()
            if idx and idx.full_memory_id:
                full_ids.append(idx.full_memory_id)

        full_records = await self.repo.load_full(full_ids)
        if not full_records:
            return "\n".join([f"- [{r.topic}] {r.summary}" for r in results])

        parts = []
        for rec in full_records:
            parts.append(f"### {rec.topic}\n")
            if rec.full_data:
                parts.append(json.dumps(rec.full_data, ensure_ascii=False, indent=2)[:1500])
        return "\n".join(parts)[:4000]  # 限制总长度

    async def search_memory(self, query: str, top_k: int = 5) -> str:
        """语义搜索记忆"""
        query_embedding = await embed_query(query)
        results = await self.repo.search_index_by_vector(self.user_id, query_embedding, top_k=top_k)
        if not results:
            return "未找到相关记忆。"
        return "\n".join(
            [f"- [{r.topic}] {r.summary} (相关度: {r.relevance_score:.2f})" for r in results]
        )

    # ---------- 写入部分 ----------

    async def update(self, memory_type: str, data: dict) -> bool:
        """学习事件后更新索引层+全量层"""
        topic = data.get("topic", "")
        if not topic:
            return False

        # 1. 更新全量层
        full_id = await self.repo.upsert_full(
            memory_type=memory_type,
            topic=topic,
            content=data,
        )

        # 2. 生成摘要，更新索引层
        summary = self._generate_summary(memory_type, data)
        await self.repo.upsert_index(self.user_id, memory_type, topic, summary, full_id)

        # 3. 知识更新时刷新薄弱知识点
        if memory_type == "knowledge":
            await self._refresh_weak_nodes()

        # 4. 清缓存
        self._index_cache = None
        return True

    async def load_index(self):
        """会话初始化时加载索引层到内存"""
        result = await self.db.execute(
            select(MemoryIndex).where(MemoryIndex.user_id == self.user_id)
        )
        self._index_cache = {
            r.topic: MemoryEntry(
                id=r.id, memory_type=r.memory_type, topic=r.topic, summary=r.summary
            )
            for r in result.scalars().all()
        }

    def _generate_summary(self, memory_type: str, data: dict) -> str:
        """为索引层生成简洁摘要（≤100 token）"""
        topic = data.get("topic", "未知")
        if memory_type == "knowledge":
            mastery = data.get("mastery_score", 0)
            level = "已掌握" if mastery > 0.7 else "学习中" if mastery > 0.3 else "薄弱"
            return f"{topic}: {level}, mastery={mastery:.2f}"
        elif memory_type == "habit":
            return f"{topic}: {data.get('description', '')}"
        return f"{topic}: {str(data)[:100]}"

    async def _refresh_weak_nodes(self):
        """重新计算薄弱知识点名称列表"""
        result = await self.db.execute(
            select(UserKnowledgeMastery)
            .where(
                UserKnowledgeMastery.user_id == self.user_id,
                UserKnowledgeMastery.mastery_score < 0.4,
            )
            .order_by(UserKnowledgeMastery.mastery_score.asc())
            .limit(10)
        )
        weak_mastery = result.scalars().all()

        # 获取知识点名称
        weak_names = []
        for m in weak_mastery:
            node_result = await self.db.execute(
                select(KnowledgeNode.name).where(KnowledgeNode.id == m.node_id)
            )
            name = node_result.scalar_one_or_none()
            if name:
                weak_names.append(name)

        # 更新到personal_habit_profile
        profile_result = await self.db.execute(
            select(PersonalHabitProfile).where(PersonalHabitProfile.user_id == self.user_id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile:
            profile.weak_node_names = weak_names
            profile.summary_cache = None  # 清除缓存，下次重新生成
            await self.db.flush()
