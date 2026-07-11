import uuid
from typing import Optional

from sqlalchemy import desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.models.knowledge import KnowledgeNode, KnowledgeEdge, UserKnowledgeMastery
from app.models.learning import LearningRoute, LearningRouteStep
from app.models.note import Note
from app.services.graph_db import GraphDB
from app.core.exceptions import NotFoundException, ConflictException

logger = structlog.get_logger()

# 学科英文名 → 中文显示名映射
SUBJECT_DISPLAY_NAMES = {
    "math": "数学",
    "physics": "物理",
    "chemistry": "化学",
    "biology": "生物",
    "computer_science": "计算机科学",
    "english": "英语",
    "chinese": "语文",
    "history": "历史",
    "geography": "地理",
    "economics": "经济学",
}


class KnowledgeService:

    # ==================== 知识节点 CRUD ====================

    @staticmethod
    async def create_node(db: AsyncSession, **kwargs) -> KnowledgeNode:
        """创建知识节点，同步写入AGE图"""
        node = KnowledgeNode(**kwargs)
        db.add(node)
        await db.flush()
        await db.refresh(node)

        # 同步到AGE图
        try:
            await GraphDB.create_knowledge_node_in_graph(
                db,
                node_id=str(node.id),
                name=node.name,
                subject=node.subject,
                grade_level=node.grade_level,
                difficulty=node.difficulty,
                description=node.description,
            )
        except Exception as e:
            logger.warning("age_sync_failed", node_id=str(node.id), error=str(e))
            # AGE同步失败不阻塞主流程，后续可手动同步

        return node

    @staticmethod
    async def get_node(db: AsyncSession, node_id: uuid.UUID) -> KnowledgeNode:
        result = await db.execute(
            select(KnowledgeNode).where(KnowledgeNode.id == node_id)
        )
        node = result.scalar_one_or_none()
        if not node:
            raise NotFoundException("知识节点不存在")
        return node

    @staticmethod
    async def list_nodes(
        db: AsyncSession,
        subject: str | None = None,
        grade_level: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KnowledgeNode], int]:
        query = select(KnowledgeNode)
        count_query = select(func.count()).select_from(KnowledgeNode)

        if subject:
            query = query.where(KnowledgeNode.subject == subject)
            count_query = count_query.where(KnowledgeNode.subject == subject)
        if grade_level:
            query = query.where(KnowledgeNode.grade_level == grade_level)
            count_query = count_query.where(KnowledgeNode.grade_level == grade_level)
        if search:
            query = query.where(KnowledgeNode.name.ilike(f"%{search}%"))
            count_query = count_query.where(KnowledgeNode.name.ilike(f"%{search}%"))

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        items = list(result.scalars().all())

        return items, total

    @staticmethod
    async def update_node(
        db: AsyncSession, node_id: uuid.UUID, **kwargs
    ) -> KnowledgeNode:
        node = await KnowledgeService.get_node(db, node_id)
        for key, value in kwargs.items():
            if value is not None and hasattr(node, key):
                setattr(node, key, value)
        await db.flush()
        await db.refresh(node)
        return node

    # ==================== 知识边 CRUD ====================

    @staticmethod
    async def create_edge(db: AsyncSession, **kwargs) -> KnowledgeEdge:
        """创建知识边，同步写入AGE图"""
        edge = KnowledgeEdge(**kwargs)
        db.add(edge)
        await db.flush()
        await db.refresh(edge)

        # 同步到AGE图
        try:
            await GraphDB.create_knowledge_edge_in_graph(
                db,
                source_id=str(edge.source_id),
                target_id=str(edge.target_id),
                relation_type=edge.relation_type,
                weight=edge.weight,
            )
        except Exception as e:
            logger.warning("age_edge_sync_failed", edge_id=str(edge.id), error=str(e))

        return edge

    # ==================== 图查询 ====================

    @staticmethod
    async def get_node_graph(
        db: AsyncSession, node_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> dict:
        """获取知识节点的图结构（前置依赖、后续依赖、关联节点）"""
        node = await KnowledgeService.get_node(db, node_id)
        node_str_id = str(node_id)

        # 从AGE图查询关系
        try:
            prereqs_raw = await GraphDB.get_prerequisites(db, node_str_id)
            dependents_raw = await GraphDB.get_dependents(db, node_str_id)
            related_raw = await GraphDB.get_related(db, node_str_id)
        except Exception as e:
            logger.warning("age_query_failed", error=str(e))
            # Cypher查询失败会污染PostgreSQL事务状态，必须先回滚
            await db.rollback()
            # 降级到关系表查询
            prereqs_raw, dependents_raw, related_raw = [], [], []

        # 提取节点ID列表
        def extract_ids(raw_list):
            ids = []
            for item in raw_list:
                for key, value in item.items():
                    if isinstance(value, dict) and "id" in value:
                        ids.append(uuid.UUID(value["id"]))
                        break
            return ids

        prereq_ids = extract_ids(prereqs_raw)
        dependent_ids = extract_ids(dependents_raw)
        related_ids = extract_ids(related_raw)

        # 批量查询节点详情
        prerequisites = []
        if prereq_ids:
            result = await db.execute(
                select(KnowledgeNode).where(KnowledgeNode.id.in_(prereq_ids))
            )
            prerequisites = list(result.scalars().all())

        dependents = []
        if dependent_ids:
            result = await db.execute(
                select(KnowledgeNode).where(KnowledgeNode.id.in_(dependent_ids))
            )
            dependents = list(result.scalars().all())

        related = []
        if related_ids:
            result = await db.execute(
                select(KnowledgeNode).where(KnowledgeNode.id.in_(related_ids))
            )
            related = list(result.scalars().all())

        # 获取用户掌握度
        user_mastery = None
        if user_id:
            result = await db.execute(
                select(UserKnowledgeMastery).where(
                    UserKnowledgeMastery.user_id == user_id,
                    UserKnowledgeMastery.node_id == node_id,
                )
            )
            mastery = result.scalar_one_or_none()
            if mastery:
                user_mastery = mastery

        return {
            "node": node,
            "prerequisites": prerequisites,
            "dependents": dependents,
            "related": related,
            "user_mastery": user_mastery,
        }

    @staticmethod
    async def get_learning_path(
        db: AsyncSession, source_id: uuid.UUID, target_id: uuid.UUID
    ) -> dict:
        """获取两个知识节点之间的学习路径"""
        try:
            path_data = await GraphDB.find_shortest_path(
                db, str(source_id), str(target_id)
            )
            if not path_data:
                return {"path": [], "total_difficulty": 0.0}

            # 提取路径中的节点ID
            node_ids = []
            total_difficulty = 0.0
            for node_props in path_data:
                if isinstance(node_props, dict) and "id" in node_props:
                    node_ids.append(uuid.UUID(node_props["id"]))
                    total_difficulty += node_props.get("difficulty", 1)

            # 查询完整节点信息
            result = await db.execute(
                select(KnowledgeNode).where(KnowledgeNode.id.in_(node_ids))
            )
            nodes = list(result.scalars().all())
            # 保持路径顺序
            node_map = {n.id: n for n in nodes}
            ordered_path = [node_map[nid] for nid in node_ids if nid in node_map]

            return {"path": ordered_path, "total_difficulty": total_difficulty}
        except Exception as e:
            logger.error("learning_path_failed", error=str(e))
            return {"path": [], "total_difficulty": 0.0}

    @staticmethod
    async def get_node_relation(db: AsyncSession, node_id: str, user_id: str) -> dict:
        """
        获取知识节点的关联内容视图。
        返回：中心节点信息 + 前置知识 + 后续知识 + 关联笔记 + 关联路线。
        """
        node_uuid = uuid.UUID(node_id)
        user_uuid = uuid.UUID(user_id)

        # 1. 获取中心节点
        node = await KnowledgeService.get_node(db, node_uuid)

        # 2. 获取前置知识
        prereq_query = (
            select(KnowledgeNode)
            .join(KnowledgeEdge, KnowledgeEdge.source_id == KnowledgeNode.id)
            .where(
                KnowledgeEdge.target_id == node_uuid,
                KnowledgeEdge.relation_type == "prerequisite",
            )
        )
        prereq_result = await db.execute(prereq_query)
        prerequisite_nodes = []
        for node_obj in prereq_result.scalars().all():
            mastery = await db.execute(
                select(UserKnowledgeMastery).where(
                    UserKnowledgeMastery.user_id == user_uuid,
                    UserKnowledgeMastery.node_id == node_obj.id,
                )
            )
            m = mastery.scalar_one_or_none()
            prerequisite_nodes.append({
                "id": str(node_obj.id),
                "name": node_obj.name,
                "mastery_score": m.mastery_score if m else None,
            })

        # 3. 获取后续知识
        dep_query = (
            select(KnowledgeNode)
            .join(KnowledgeEdge, KnowledgeEdge.target_id == KnowledgeNode.id)
            .where(
                KnowledgeEdge.source_id == node_uuid,
                KnowledgeEdge.relation_type == "prerequisite",
            )
        )
        dep_result = await db.execute(dep_query)
        dependent_nodes = []
        for node_obj in dep_result.scalars().all():
            mastery = await db.execute(
                select(UserKnowledgeMastery).where(
                    UserKnowledgeMastery.user_id == user_uuid,
                    UserKnowledgeMastery.node_id == node_obj.id,
                )
            )
            m = mastery.scalar_one_or_none()
            dependent_nodes.append({
                "id": str(node_obj.id),
                "name": node_obj.name,
                "mastery_score": m.mastery_score if m else None,
            })

        # 4. 获取关联笔记
        note_result = await db.execute(
            select(Note.id, Note.title, Note.updated_at)
            .where(
                Note.user_id == user_uuid,
                Note.title.ilike(f"%{node.name}%"),
            )
            .order_by(desc(Note.updated_at))
            .limit(10)
        )
        related_notes = [
            {"id": str(r.id), "title": r.title, "updated_at": r.updated_at.isoformat() + "Z"}
            for r in note_result.fetchall()
        ]

        # 5. 获取关联学习路线
        route_result = await db.execute(
            select(LearningRoute.id, LearningRoute.topic, LearningRoute.status)
            .join(LearningRouteStep, LearningRouteStep.route_id == LearningRoute.id)
            .where(LearningRouteStep.node_id == node_uuid)
            .distinct()
            .limit(10)
        )
        related_routes = [
            {"id": str(r.id), "topic": r.topic, "status": r.status}
            for r in route_result.fetchall()
        ]

        return {
            "center_node": {
                "id": str(node.id),
                "name": node.name,
                "subject": node.subject,
            },
            "related_notes": related_notes,
            "related_routes": related_routes,
            "prerequisite_nodes": prerequisite_nodes,
            "dependent_nodes": dependent_nodes,
        }

    # ==================== 学科列表 ====================

    @staticmethod
    async def get_subjects(db: AsyncSession) -> list[dict]:
        """获取所有学科及其节点数量"""
        result = await db.execute(
            select(
                KnowledgeNode.subject,
                func.count(KnowledgeNode.id).label("node_count"),
            ).group_by(KnowledgeNode.subject)
        )
        subjects = []
        for row in result:
            subjects.append({
                "name": row.subject,
                "display_name": SUBJECT_DISPLAY_NAMES.get(row.subject, row.subject),
                "node_count": row.node_count,
            })
        return subjects

    # ==================== 掌握度管理 ====================

    @staticmethod
    async def get_or_create_mastery(
        db: AsyncSession, user_id: uuid.UUID, node_id: uuid.UUID
    ) -> UserKnowledgeMastery:
        """获取或创建用户知识掌握度记录"""
        result = await db.execute(
            select(UserKnowledgeMastery).where(
                UserKnowledgeMastery.user_id == user_id,
                UserKnowledgeMastery.node_id == node_id,
            )
        )
        mastery = result.scalar_one_or_none()
        if not mastery:
            mastery = UserKnowledgeMastery(
                user_id=user_id,
                node_id=node_id,
                mastery_score=0.0,
            )
            db.add(mastery)
            await db.flush()
            await db.refresh(mastery)
        return mastery

    @staticmethod
    async def update_mastery_score(
        db: AsyncSession,
        user_id: uuid.UUID,
        node_id: uuid.UUID,
        is_correct: bool,
    ) -> UserKnowledgeMastery:
        """
        根据答题正确性更新掌握度。
        使用指数移动平均：
          正确：mastery += (1 - mastery) * 0.3
          错误：mastery *= 0.7
        """
        mastery = await KnowledgeService.get_or_create_mastery(db, user_id, node_id)

        mastery.total_count += 1
        if is_correct:
            mastery.correct_count += 1
            mastery.mastery_score += (1.0 - mastery.mastery_score) * 0.3
        else:
            mastery.mastery_score *= 0.7

        mastery.mastery_score = max(0.0, min(1.0, mastery.mastery_score))
        mastery.last_reviewed_at = func.now()
        mastery.review_count += 1

        await db.flush()
        await db.refresh(mastery)
        return mastery

    # ==================== 初始数据导入 ====================

    @staticmethod
    async def get_node_relation(self, node_id: str, user_id: str) -> dict:
        """
        获取知识节点的关联内容视图。
        返回：中心节点信息 + 前置知识 + 后续知识 + 关联笔记 + 关联路线。
        """
        node_uuid = uuid.UUID(node_id)
        user_uuid = uuid.UUID(user_id)

        # 1. 获取中心节点
        node = await self.get_node(self.db, node_uuid)

        # 2. 获取前置知识（通过 knowledge_edges 的 relation_type = 'prerequisite'）
        prereq_result = await self.db.execute(
            select(KnowledgeNode, KnowledgeEdge.weight)
            .join(KnowledgeEdge, KnowledgeEdge.source_id == KnowledgeNode.id)
            .where(
                KnowledgeEdge.target_id == node_uuid,
                KnowledgeEdge.relation_type == "prerequisite",
            )
        )
        prerequisite_nodes = []
        for node_obj, weight in prereq_result.fetchall():
            mastery = await self.db.execute(
                select(UserKnowledgeMastery).where(
                    UserKnowledgeMastery.user_id == user_uuid,
                    UserKnowledgeMastery.node_id == node_obj.id,
                )
            )
            m = mastery.scalar_one_or_none()
            prerequisite_nodes.append({
                "id": str(node_obj.id),
                "name": node_obj.name,
                "mastery_score": m.mastery_score if m else None,
            })

        # 3. 获取后续知识
        dep_result = await self.db.execute(
            select(KnowledgeNode, KnowledgeEdge.weight)
            .join(KnowledgeEdge, KnowledgeEdge.target_id == KnowledgeNode.id)
            .where(
                KnowledgeEdge.source_id == node_uuid,
                KnowledgeEdge.relation_type == "prerequisite",
            )
        )
        dependent_nodes = []
        for node_obj, weight in dep_result.fetchall():
            mastery = await self.db.execute(
                select(UserKnowledgeMastery).where(
                    UserKnowledgeMastery.user_id == user_uuid,
                    UserKnowledgeMastery.node_id == node_obj.id,
                )
            )
            m = mastery.scalar_one_or_none()
            dependent_nodes.append({
                "id": str(node_obj.id),
                "name": node_obj.name,
                "mastery_score": m.mastery_score if m else None,
            })

        # 4. 获取关联笔记
        note_result = await self.db.execute(
            select(Note.id, Note.title, Note.updated_at)
            .where(
                Note.user_id == user_uuid,
                Note.title.ilike(f"%{node.name}%"),
            )
            .order_by(desc(Note.updated_at))
            .limit(10)
        )
        related_notes = [
            {"id": str(r.id), "title": r.title, "updated_at": r.updated_at.isoformat() + "Z"}
            for r in note_result.fetchall()
        ]

        # 5. 获取关联学习路线
        route_result = await self.db.execute(
            select(LearningRoute.id, LearningRoute.topic, LearningRoute.status)
            .join(LearningRouteStep, LearningRouteStep.route_id == LearningRoute.id)
            .where(LearningRouteStep.node_id == node_uuid)
            .distinct()
            .limit(10)
        )
        related_routes = [
            {"id": str(r.id), "topic": r.topic, "status": r.status}
            for r in route_result.fetchall()
        ]

        return {
            "center_node": {
                "id": str(node.id),
                "name": node.name,
                "subject": node.subject,
            },
            "related_notes": related_notes,
            "related_routes": related_routes,
            "prerequisite_nodes": prerequisite_nodes,
            "dependent_nodes": dependent_nodes,
        }

    @staticmethod
    async def import_initial_data(db: AsyncSession, data: list[dict]) -> int:
        """
        导入初始知识图谱数据。
        data格式：
        [
            {
                "subject": "math",
                "nodes": [
                    {"name": "勾股定理", "grade_level": "初二", "difficulty": 2},
                    ...
                ],
                "edges": [
                    {"source_name": "勾股定理", "target_name": "三角函数",
                     "relation_type": "prerequisite"},
                    ...
                ]
            }
        ]
        """
        imported_count = 0
        name_to_id: dict[str, uuid.UUID] = {}

        for subject_data in data:
            subject = subject_data["subject"]

            # 创建节点
            for node_data in subject_data.get("nodes", []):
                node = await KnowledgeService.create_node(
                    db,
                    subject=subject,
                    name=node_data["name"],
                    grade_level=node_data.get("grade_level"),
                    difficulty=node_data.get("difficulty", 1),
                    description=node_data.get("description"),
                )
                name_to_id[f"{subject}:{node_data['name']}"] = node.id
                imported_count += 1

            # 创建边
            for edge_data in subject_data.get("edges", []):
                source_key = f"{subject}:{edge_data['source_name']}"
                target_key = f"{subject}:{edge_data['target_name']}"
                if source_key in name_to_id and target_key in name_to_id:
                    await KnowledgeService.create_edge(
                        db,
                        source_id=name_to_id[source_key],
                        target_id=name_to_id[target_key],
                        relation_type=edge_data.get("relation_type", "related"),
                        weight=edge_data.get("weight", 1.0),
                    )

        return imported_count
