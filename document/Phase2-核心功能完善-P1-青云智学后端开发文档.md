# 青云智学 — Phase 2：核心功能完善（P1）开发文档

> 版本：1.0
> 日期：2026-07-08
> 依赖：Phase 1 开发文档（已完成）+ 青云智学-后端开发文档.md v1.0
> 用途：AI编程助手可直接依照本文档逐步开发，完成Phase 2全部3个Sprint。每个Sprint包含完整的代码实现、配置说明和验收标准。
> 前置条件：Phase 1全部4个Sprint已完成，包括ORM模型、JWT认证、笔记管理、AI基础链路、用户记忆与画像。

---

## 总览

Phase 2 覆盖 Sprint 5 ~ Sprint 7，目标是在Phase 1基础上完善三大核心学习功能：知识图谱驱动的学习路线生成、苏格拉底式智能答疑、SM-2间隔重复复习系统。

| Sprint | 主题 | 核心交付 |
|--------|------|----------|
| Sprint 5 | 学习路线与知识图谱 | Apache AGE图查询、知识图谱服务、LLM驱动学习路线生成、路线动态调整、知识图谱API |
| Sprint 6 | 智能答疑 | 苏格拉底式答疑服务、诊断性问题生成、QA流式WebSocket、答疑中实时更新知识画像 |
| Sprint 7 | 复习系统 | SM-2间隔重复算法、复习计划管理、Celery Beat定时提醒、复习内容自动生成 |

### Phase 1 遗留技术债（本阶段解决）

- 学习路线生成在Phase 1为简化版（空路线），Sprint 5接入LLM+知识图谱
- 复习系统Phase 1不实现，Sprint 7完成

---

## Sprint 5：学习路线与知识图谱

### 5.1 新增项目结构

```
backend/app/
├── services/
│   ├── knowledge_service.py      # 知识图谱服务（新增）
│   └── learning_service.py       # 学习引擎服务（升级Phase 1基础版）
├── schemas/
│   ├── knowledge.py              # 知识图谱Schema（新增）
│   └── learning.py               # 学习模块Schema（新增）
├── api/v1/
│   ├── knowledge.py              # 知识图谱路由（新增）
│   └── learning.py               # 学习路由（升级）
├── ai/
│   └── prompts/
│       └── route.py              # 路线生成Prompt模板（新增）
└── tasks/
    └── knowledge_tasks.py        # 知识图谱异步任务（新增）
```

### 5.2 Pydantic Schema 定义

#### app/schemas/knowledge.py

```python
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class KnowledgeNodeSchema(BaseModel):
    id: uuid.UUID
    subject: str
    name: str
    description: Optional[str] = None
    grade_level: Optional[str] = None
    difficulty: int = 1
    metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeNodeCreate(BaseModel):
    subject: str = Field(max_length=100)
    name: str = Field(max_length=255)
    description: Optional[str] = None
    grade_level: Optional[str] = Field(None, max_length=20)
    difficulty: int = Field(default=1, ge=1, le=5)
    metadata: Optional[dict] = None


class KnowledgeNodeUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    grade_level: Optional[str] = None
    difficulty: Optional[int] = Field(None, ge=1, le=5)
    metadata: Optional[dict] = None


class KnowledgeEdgeSchema(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    relation_type: str
    weight: float = 1.0
    metadata: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeEdgeCreate(BaseModel):
    source_id: uuid.UUID
    target_id: uuid.UUID
    relation_type: str = Field(pattern="^(prerequisite|related|subtopic|parent)$")
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
    metadata: Optional[dict] = None


class KnowledgeGraphResponse(BaseModel):
    """知识节点图结构响应"""
    node: KnowledgeNodeSchema
    prerequisites: list[KnowledgeNodeSchema] = []
    dependents: list[KnowledgeNodeSchema] = []
    related: list[KnowledgeNodeSchema] = []
    user_mastery: Optional["UserMasterySchema"] = None


class LearningPathResponse(BaseModel):
    """两节点间学习路径"""
    path: list[KnowledgeNodeSchema]
    total_difficulty: float


class UserMasterySchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    node_id: uuid.UUID
    mastery_score: float
    review_count: int
    correct_count: int
    total_count: int
    last_reviewed_at: Optional[datetime] = None
    next_review_at: Optional[datetime] = None
    ease_factor: float
    interval_days: int

    model_config = {"from_attributes": True}


class SubjectSchema(BaseModel):
    name: str
    display_name: str
    node_count: int


class GraphNodeCypher(BaseModel):
    """Apache AGE返回的图节点"""
    id: str
    name: str
    subject: str
    grade_level: Optional[str] = None
    difficulty: int = 1
    description: Optional[str] = None
    labels: list[str] = []


class GraphEdgeCypher(BaseModel):
    """Apache AGE返回的图边"""
    source_id: str
    target_id: str
    relation_type: str
    weight: float = 1.0
```

#### app/schemas/learning.py

```python
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class LearningRouteCreate(BaseModel):
    topic: str = Field(max_length=255)
    goal: Optional[str] = None
    available_hours: Optional[float] = Field(None, gt=0)
    current_level: Optional[str] = Field(None, pattern="^(beginner|intermediate|advanced)$")
    preferences: Optional[dict] = None


class LearningRouteSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    topic: str
    description: Optional[str] = None
    status: str
    total_steps: int
    current_step: int
    estimated_hours: Optional[float] = None
    metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    steps: list["LearningRouteStepSchema"] = []

    model_config = {"from_attributes": True}


class LearningRouteStepSchema(BaseModel):
    id: uuid.UUID
    route_id: uuid.UUID
    node_id: Optional[uuid.UUID] = None
    step_order: int
    title: str
    description: Optional[str] = None
    estimated_minutes: Optional[int] = None
    status: str
    prerequisites: list[uuid.UUID] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RouteStepComplete(BaseModel):
    duration_seconds: Optional[int] = None
    notes: Optional[str] = None


class LectureGenerateRequest(BaseModel):
    route_id: uuid.UUID
    step_id: uuid.UUID
    node_id: Optional[uuid.UUID] = None
    custom_instructions: Optional[str] = None


class LectureSchema(BaseModel):
    id: uuid.UUID
    route_id: Optional[uuid.UUID] = None
    step_id: Optional[uuid.UUID] = None
    user_id: uuid.UUID
    node_id: Optional[uuid.UUID] = None
    title: str
    content: str
    content_json: Optional[dict] = None
    source_urls: list[str] = []
    version: int
    status: str
    token_usage: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LectureGenerateResponse(BaseModel):
    lecture_id: uuid.UUID
    status: str


class RouteGenerationLLMResponse(BaseModel):
    """LLM返回的学习路线JSON结构"""
    title: str
    description: str
    estimated_total_hours: float
    steps: list["RouteStepLLM"]


class RouteStepLLM(BaseModel):
    order: int
    node_id: Optional[str] = None
    title: str
    description: str
    estimated_minutes: int
    prerequisite_step_orders: list[int] = []
```

### 5.3 Apache AGE 图数据库集成

#### app/services/graph_db.py — AGE封装层

```python
"""
Apache AGE 图数据库操作封装。
AGE作为PostgreSQL扩展，通过Cypher查询语言操作图数据。
本模块封装了常用的图操作，屏蔽AGE的SQL调用细节。
"""
import json
import uuid as uuid_mod
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger()

GRAPH_NAME = "knowledge_graph"


class GraphDB:
    """Apache AGE 图数据库操作封装"""

    @staticmethod
    async def execute_cypher(
        db: AsyncSession,
        cypher: str,
        params: dict | None = None,
        columns: str = "result agtype",
    ) -> list[dict]:
        """
        执行Cypher查询并返回结果列表。
        
        用法示例：
            results = await GraphDB.execute_cypher(
                db,
                "MATCH (n:KnowledgePoint {subject: 'math'}) RETURN n",
                columns="n agtype"
            )
        """
        # AGE的Cypher通过SQL函数调用
        sql = f"SELECT * FROM cypher('{GRAPH_NAME}', $$ {cypher} $$) as ({columns})"

        try:
            result = await db.execute(text(sql), params or {})
            rows = result.fetchall()
            return [GraphDB._parse_agtype_row(row) for row in rows]
        except Exception as e:
            logger.error("cypher_query_failed", cypher=cypher[:200], error=str(e))
            raise

    @staticmethod
    async def execute_cypher_write(
        db: AsyncSession,
        cypher: str,
        params: dict | None = None,
    ) -> None:
        """执行写操作的Cypher（CREATE/MERGE/DELETE等）"""
        sql = f"SELECT * FROM cypher('{GRAPH_NAME}', $$ {cypher} $$) as (result agtype)"
        try:
            await db.execute(text(sql), params or {})
        except Exception as e:
            logger.error("cypher_write_failed", cypher=cypher[:200], error=str(e))
            raise

    @staticmethod
    def _parse_agtype_row(row) -> dict:
        """解析AGE返回的agtype数据"""
        parsed = {}
        for key, value in row._mapping.items():
            if isinstance(value, str):
                try:
                    # agtype格式类似JSON但有些差异
                    parsed[key] = json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    parsed[key] = value
            else:
                parsed[key] = value
        return parsed

    @staticmethod
    async def ensure_graph_exists(db: AsyncSession) -> bool:
        """检查图是否存在，不存在则创建"""
        try:
            result = await db.execute(
                text(f"SELECT * FROM ag_catalog.ag_graph WHERE name = '{GRAPH_NAME}'")
            )
            if result.fetchone():
                return True

            # 创建图
            await db.execute(text(f"SELECT create_graph('{GRAPH_NAME}')"))
            logger.info("graph_created", graph_name=GRAPH_NAME)
            return True
        except Exception as e:
            logger.error("graph_check_failed", error=str(e))
            return False

    @staticmethod
    async def create_knowledge_node_in_graph(
        db: AsyncSession,
        node_id: str,
        name: str,
        subject: str,
        grade_level: str | None = None,
        difficulty: int = 1,
        description: str | None = None,
    ) -> None:
        """在AGE图中创建知识节点"""
        props = {
            "id": node_id,
            "name": name,
            "subject": subject,
            "grade_level": grade_level or "",
            "difficulty": difficulty,
            "description": description or "",
        }
        props_str = ", ".join(f'{k}: "{v}"' if isinstance(v, str) else f'{k}: {v}' for k, v in props.items())
        cypher = f"CREATE (kp:KnowledgePoint {{ {props_str} }}) RETURN kp"
        await GraphDB.execute_cypher_write(db, cypher)

    @staticmethod
    async def create_knowledge_edge_in_graph(
        db: AsyncSession,
        source_id: str,
        target_id: str,
        relation_type: str,
        weight: float = 1.0,
    ) -> None:
        """
        在AGE图中创建知识边。
        relation_type映射：
          prerequisite → PREREQUISITE_OF
          related → RELATED_TO
          subtopic → SUBTOPIC_OF
          parent → BELONGS_TO
        """
        type_map = {
            "prerequisite": "PREREQUISITE_OF",
            "related": "RELATED_TO",
            "subtopic": "SUBTOPIC_OF",
            "parent": "BELONGS_TO",
        }
        edge_type = type_map.get(relation_type, "RELATED_TO")
        cypher = (
            f"MATCH (a:KnowledgePoint {{id: '{source_id}'}}), "
            f"(b:KnowledgePoint {{id: '{target_id}'}}) "
            f"CREATE (a)-[:{edge_type} {{weight: {weight}}}]->(b) RETURN a"
        )
        await GraphDB.execute_cypher_write(db, cypher)

    @staticmethod
    async def get_prerequisites(db: AsyncSession, node_id: str) -> list[dict]:
        """获取某节点的所有前置依赖节点"""
        cypher = (
            f"MATCH (prereq:KnowledgePoint)-[:PREREQUISITE_OF]->(target:KnowledgePoint {{id: '{node_id}'}}) "
            f"RETURN prereq"
        )
        return await GraphDB.execute_cypher(db, cypher, columns="prereq agtype")

    @staticmethod
    async def get_dependents(db: AsyncSession, node_id: str) -> list[dict]:
        """获取某节点的所有后续依赖节点"""
        cypher = (
            f"MATCH (source:KnowledgePoint {{id: '{node_id}'}})-[:PREREQUISITE_OF]->(dep:KnowledgePoint) "
            f"RETURN dep"
        )
        return await GraphDB.execute_cypher(db, cypher, columns="dep agtype")

    @staticmethod
    async def get_related(db: AsyncSession, node_id: str) -> list[dict]:
        """获取某节点的关联节点"""
        cypher = (
            f"MATCH (source:KnowledgePoint {{id: '{node_id}'}})-[:RELATED_TO]-(related:KnowledgePoint) "
            f"RETURN related"
        )
        return await GraphDB.execute_cypher(db, cypher, columns="related agtype")

    @staticmethod
    async def get_subtopics(db: AsyncSession, node_id: str) -> list[dict]:
        """获取某节点的子知识点"""
        cypher = (
            f"MATCH (parent:KnowledgePoint {{id: '{node_id}'}})<-[:SUBTOPIC_OF]-(child:KnowledgePoint) "
            f"RETURN child"
        )
        return await GraphDB.execute_cypher(db, cypher, columns="child agtype")

    @staticmethod
    async def find_shortest_path(
        db: AsyncSession, source_id: str, target_id: str
    ) -> list[dict]:
        """查找两个知识节点之间的最短学习路径"""
        cypher = (
            f"MATCH path = shortestPath("
            f"(start:KnowledgePoint {{id: '{source_id}'}})-[*]->(target:KnowledgePoint {{id: '{target_id}'}})"
            f") "
            f"RETURN [node IN nodes(path) | properties(node)] AS node_list"
        )
        results = await GraphDB.execute_cypher(db, cypher, columns="node_list agtype")
        if results:
            return results[0].get("node_list", [])
        return []

    @staticmethod
    async def get_nodes_by_subject(db: AsyncSession, subject: str) -> list[dict]:
        """按学科获取所有知识节点"""
        cypher = f"MATCH (n:KnowledgePoint {{subject: '{subject}'}}) RETURN n"
        return await GraphDB.execute_cypher(db, cypher, columns="n agtype")

    @staticmethod
    async def get_nodes_with_prerequisites(
        db: AsyncSession, subject: str
    ) -> list[dict]:
        """获取某学科的所有节点及其前置依赖关系（用于路线生成）"""
        cypher = (
            f"MATCH (n:KnowledgePoint {{subject: '{subject}'}}) "
            f"OPTIONAL MATCH (n)-[:PREREQUISITE_OF]->(prereq:KnowledgePoint) "
            f"RETURN n, collect(prereq.name) AS prerequisites"
        )
        return await GraphDB.execute_cypher(
            db, cypher, columns="n agtype, prerequisites agtype"
        )
```

### 5.4 知识图谱服务

#### app/services/knowledge_service.py

```python
import uuid
from typing import Optional

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.models.knowledge import KnowledgeNode, KnowledgeEdge, UserKnowledgeMastery
from app.services.graph_db import GraphDB
from app.core.exceptions import NotFoundException, ConflictException

logger = structlog.get_logger()


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
            path_data = await GraphDB.find_shortest_path(db, str(source_id), str(target_id))
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
        display_names = {
            "math": "数学",
            "physics": "物理",
            "chemistry": "化学",
            "biology": "生物",
            "computer_science": "计算机科学",
            "english": "英语",
            "chinese": "语文",
            "history": "历史",
            "geography": "地理",
        }
        for row in result:
            subjects.append({
                "name": row.subject,
                "display_name": display_names.get(row.subject, row.subject),
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
    async def import_initial_data(db: AsyncSession, data: list[dict]) -> int:
        """
        导入初始知识图谱数据。
        data格式：
        [
            {
                "subject": "math",
                "nodes": [
                    {"name": "勾股定理", "grade_level": "初二", "difficulty": 2, "description": "..."},
                    ...
                ],
                "edges": [
                    {"source_name": "勾股定理", "target_name": "三角函数", "relation_type": "prerequisite"},
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
```

### 5.5 学习引擎服务升级

> 本节升级Phase 1的 `learning_service.py`，将空路线替换为LLM+知识图谱驱动的完整实现。

#### app/services/learning_service.py（Phase 2升级版）

```python
import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.models.learning import LearningRoute, LearningRouteStep, Lecture, LearningRecord
from app.models.knowledge import KnowledgeNode, KnowledgeEdge, UserKnowledgeMastery
from app.services.knowledge_service import KnowledgeService
from app.services.graph_db import GraphDB
from app.ai.llm_client import get_llm_client
from app.ai.prompts.route import ROUTE_GENERATION_PROMPT
from app.core.exceptions import NotFoundException, BadRequestException
from app.config import settings

logger = structlog.get_logger()


class LearningService:

    # ==================== 学习路线生成（升级） ====================

    @staticmethod
    async def create_route(
        db: AsyncSession,
        user_id: uuid.UUID,
        topic: str,
        goal: str | None = None,
        available_hours: float | None = None,
        current_level: str | None = None,
        preferences: dict | None = None,
    ) -> LearningRoute:
        """
        创建学习路线（Phase 2升级版）。
        流程：
        1. 创建路线记录（status="generating"）
        2. 异步触发LLM+知识图谱生成路线步骤
        3. 返回路线记录（前端轮询或WebSocket获取结果）
        """
        route = LearningRoute(
            user_id=user_id,
            topic=topic,
            description=goal or "",
            status="generating",
            estimated_hours=available_hours,
            metadata_=preferences or {},
        )
        db.add(route)
        await db.flush()
        await db.refresh(route)

        # 异步触发路线生成（通过Celery任务）
        from app.tasks.learning_tasks import generate_learning_route
        generate_learning_route.delay(
            str(route.id), str(user_id), topic,
            goal=goal,
            available_hours=available_hours,
            current_level=current_level,
        )

        return route

    @staticmethod
    async def generate_route_with_llm(
        db: AsyncSession,
        route_id: uuid.UUID,
        user_id: uuid.UUID,
        topic: str,
        goal: str | None = None,
        available_hours: float | None = None,
        current_level: str | None = None,
    ) -> LearningRoute:
        """
        LLM+知识图谱生成学习路线（由Celery任务调用）。
        完整流程：
        1. 获取用户知识画像（已有知识基础）
        2. 查询知识图谱中与该topic相关的节点
        3. 通过图遍历确定知识点前置依赖关系
        4. 构建Prompt
        5. 调用LLM生成结构化学习路线
        6. 解析输出，创建步骤记录
        """
        # 1. 获取用户已掌握的知识点
        mastery_result = await db.execute(
            select(UserKnowledgeMastery).where(
                UserKnowledgeMastery.user_id == user_id,
                UserKnowledgeMastery.mastery_score > 0.5,
            )
        )
        known_masteries = mastery_result.scalars().all()
        known_node_ids = [str(m.node_id) for m in known_masteries]

        # 获取已知节点名称
        known_nodes_text = "暂无"
        if known_node_ids:
            nodes_result = await db.execute(
                select(KnowledgeNode).where(KnowledgeNode.id.in_(
                    [uuid.UUID(nid) for nid in known_node_ids[:20]]
                ))
            )
            known_nodes = nodes_result.scalars().all()
            known_nodes_text = "、".join([f"{n.name}({n.subject})" for n in known_nodes])

        # 2. 推断学科（从topic关键词匹配）
        subject = LearningService._infer_subject(topic)

        # 3. 从知识图谱获取相关节点及前置依赖
        try:
            nodes_with_prereqs = await GraphDB.get_nodes_with_prerequisites(db, subject)
            available_nodes_text = ""
            for item in nodes_with_prereqs:
                node_data = item.get("n", {})
                prereqs = item.get("prerequisites", [])
                if isinstance(node_data, dict):
                    available_nodes_text += (
                        f"- {node_data.get('name', '未知')} "
                        f"(难度:{node_data.get('difficulty', 1)}, "
                        f"年级:{node_data.get('grade_level', '未指定')}) "
                        f"前置: {prereqs if prereqs else '无'}\n"
                    )
        except Exception as e:
            logger.warning("graph_query_fallback", error=str(e))
            # 降级：从关系表查询
            nodes_result = await db.execute(
                select(KnowledgeNode).where(KnowledgeNode.subject == subject).limit(30)
            )
            nodes = nodes_result.scalars().all()
            available_nodes_text = "\n".join([
                f"- {n.name} (难度:{n.difficulty}, 年级:{n.grade_level or '未指定'})"
                for n in nodes
            ])

        if not available_nodes_text:
            available_nodes_text = "（知识图谱中暂无相关节点，请基于通用知识生成路线）"

        # 4. 构建Prompt
        prompt = ROUTE_GENERATION_PROMPT.format(
            current_level=current_level or "beginner",
            known_nodes=known_nodes_text,
            goal=goal or f"掌握{topic}",
            available_hours=available_hours or 10,
            topic=topic,
            available_nodes_with_prerequisites=available_nodes_text,
        )

        # 5. 调用LLM
        try:
            llm = get_llm_client()
            response = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4000,
            )

            # 6. 解析LLM输出
            route_data = LearningService._parse_route_response(response)

            # 7. 更新路线记录
            route = await db.execute(
                select(LearningRoute).where(LearningRoute.id == route_id)
            )
            route = route.scalar_one()
            route.description = route_data.get("description", "")
            route.estimated_hours = route_data.get("estimated_total_hours", available_hours)
            route.status = "active"

            # 8. 创建步骤
            for step_data in route_data.get("steps", []):
                # 尝试匹配知识节点
                node_id = None
                if step_data.get("node_id"):
                    try:
                        node_id = uuid.UUID(step_data["node_id"])
                    except (ValueError, AttributeError):
                        # node_id可能是名称，尝试匹配
                        node_result = await db.execute(
                            select(KnowledgeNode).where(
                                KnowledgeNode.name == step_data.get("node_id")
                            )
                        )
                        matched_node = node_result.scalar_one_or_none()
                        if matched_node:
                            node_id = matched_node.id

                step = LearningRouteStep(
                    route_id=route_id,
                    node_id=node_id,
                    step_order=step_data["order"],
                    title=step_data["title"],
                    description=step_data.get("description", ""),
                    estimated_minutes=step_data.get("estimated_minutes", 30),
                    status="pending",
                    prerequisites=[
                        uuid.UUID(str(p)) if isinstance(p, uuid.UUID) else p
                        for p in step_data.get("prerequisite_step_orders", [])
                    ],
                )
                db.add(step)

            route.total_steps = len(route_data.get("steps", []))
            route.current_step = 0

            await db.commit()
            logger.info("route_generated", route_id=str(route_id), steps=route.total_steps)

            # 推送WebSocket通知
            from app.api.v1.websocket import manager
            await manager.send_json(
                f"route_{route_id}",
                {"type": "complete", "data": {"route_id": str(route_id), "status": "active"}},
            )

            return route

        except Exception as e:
            logger.error("route_generation_failed", route_id=str(route_id), error=str(e))
            # 标记为失败
            result = await db.execute(
                select(LearningRoute).where(LearningRoute.id == route_id)
            )
            route = result.scalar_one_or_none()
            if route:
                route.status = "failed"
                await db.commit()
            raise

    @staticmethod
    def _infer_subject(topic: str) -> str:
        """从学习主题推断学科"""
        topic_lower = topic.lower()
        subject_keywords = {
            "math": ["数学", "代数", "几何", "微积分", "概率", "统计", "方程", "函数"],
            "physics": ["物理", "力学", "电磁", "光学", "热学", "量子"],
            "chemistry": ["化学", "有机", "无机", "反应", "元素"],
            "biology": ["生物", "细胞", "基因", "生态", "进化"],
            "computer_science": ["编程", "算法", "数据结构", "python", "java", "计算机"],
            "english": ["英语", "english", "语法", "阅读", "写作"],
            "chinese": ["语文", "作文", "文言文", "诗词"],
            "history": ["历史", "朝代", "战争", "革命"],
            "geography": ["地理", "气候", "地形", "板块"],
        }
        for subject, keywords in subject_keywords.items():
            if any(kw in topic_lower for kw in keywords):
                return subject
        return "general"

    @staticmethod
    def _parse_route_response(response_text: str) -> dict:
        """解析LLM返回的路线JSON"""
        # 尝试直接解析
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # 尝试从markdown代码块中提取JSON
        import re
        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试找到第一个{和最后一个}之间的内容
        start = response_text.find('{')
        end = response_text.rfind('}')
        if start != -1 and end != -1:
            try:
                return json.loads(response_text[start:end + 1])
            except json.JSONDecodeError:
                pass

        logger.error("route_parse_failed", response_preview=response_text[:200])
        raise BadRequestException("LLM返回格式异常，无法解析学习路线")

    # ==================== 路线操作 ====================

    @staticmethod
    async def get_route(db: AsyncSession, route_id: uuid.UUID, user_id: uuid.UUID) -> LearningRoute:
        result = await db.execute(
            select(LearningRoute)
            .options(selectinload(LearningRoute.steps))
            .where(LearningRoute.id == route_id, LearningRoute.user_id == user_id)
        )
        route = result.scalar_one_or_none()
        if not route:
            raise NotFoundException("学习路线不存在")
        return result

    @staticmethod
    async def get_user_routes(
        db: AsyncSession, user_id: uuid.UUID, status: str | None = None
    ) -> list[LearningRoute]:
        query = select(LearningRoute).where(LearningRoute.user_id == user_id)
        if status:
            query = query.where(LearningRoute.status == status)
        query = query.order_by(LearningRoute.created_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def complete_step(
        db: AsyncSession,
        route_id: uuid.UUID,
        step_id: uuid.UUID,
        user_id: uuid.UUID,
        duration_seconds: int | None = None,
        notes: str | None = None,
    ) -> dict:
        """
        标记步骤完成，触发路线动态调整。
        返回：更新后的步骤Schema + 下一步骤建议
        """
        route = await LearningService.get_route(db, route_id, user_id)
        if isinstance(route, LearningRoute):
            route_obj = route
        else:
            route_obj = route.scalar_one()

        # 查找步骤
        step = None
        for s in route_obj.steps:
            if s.id == step_id:
                step = s
                break
        if not step:
            raise NotFoundException("步骤不存在")

        # 标记完成
        step.status = "completed"
        route_obj.current_step = step.step_order

        # 记录学习活动
        record = LearningRecord(
            user_id=user_id,
            route_id=route_id,
            step_id=step_id,
            node_id=step.node_id,
            activity_type="step_complete",
            duration_seconds=duration_seconds,
            content_summary=notes or f"完成步骤：{step.title}",
        )
        db.add(record)

        # 如果步骤关联了知识节点，更新掌握度
        if step.node_id:
            mastery = await KnowledgeService.get_or_create_mastery(db, user_id, step.node_id)
            mastery.mastery_score += (1.0 - mastery.mastery_score) * 0.2
            mastery.review_count += 1
            mastery.last_reviewed_at = func.now()

        await db.flush()

        # 动态调整路线
        performance = 0.75  # 默认良好表现
        if duration_seconds and step.estimated_minutes:
            # 根据实际用时/预估用时估算表现
            ratio = duration_seconds / (step.estimated_minutes * 60)
            if ratio > 2.0:
                performance = 0.5  # 用时过长，表现不佳
            elif ratio < 0.5:
                performance = 0.95  # 很快完成，表现优秀

        next_step_suggestion = None
        if performance < 0.6:
            next_step_suggestion = await LearningService._adjust_for_struggling(
                db, route_obj, step
            )
        elif performance > 0.9:
            next_step_suggestion = await LearningService._adjust_for_excelling(
                db, route_obj, step
            )

        # 获取下一步骤
        next_steps = [
            s for s in route_obj.steps
            if s.step_order > step.step_order and s.status == "pending"
        ]
        next_step = next_steps[0] if next_steps else None

        await db.commit()

        return {
            "step": step,
            "next_step": next_step,
            "next_step_suggestion": next_step_suggestion,
            "route_status": route_obj.status,
        }

    @staticmethod
    async def _adjust_for_struggling(
        db: AsyncSession, route: LearningRoute, current_step: LearningRouteStep
    ) -> str:
        """表现不佳时调整路线：增加补充练习"""
        # 在当前步骤后插入一个补充练习步骤
        new_step = LearningRouteStep(
            route_id=route.id,
            node_id=current_step.node_id,
            step_order=current_step.step_order + 1,
            title=f"补充练习：{current_step.title}",
            description="针对当前知识点的巩固练习，建议重新复习核心概念后完成此步骤。",
            estimated_minutes=max(15, (current_step.estimated_minutes or 30) // 2),
            status="pending",
        )
        db.add(new_step)

        # 后续步骤顺延
        for s in route.steps:
            if s.step_order > current_step.step_order and s.id != new_step.id:
                s.step_order += 1

        route.total_steps += 1
        await db.flush()

        return "已为你添加补充练习步骤，建议先巩固基础概念再继续"

    @staticmethod
    async def _adjust_for_excelling(
        db: AsyncSession, route: LearningRoute, current_step: LearningRouteStep
    ) -> str:
        """表现优秀时调整路线：合并后续简单步骤"""
        # 找到后续连续两个pending步骤，如果都是低难度则合并
        upcoming = [
            s for s in route.steps
            if s.step_order > current_step.step_order and s.status == "pending"
        ]
        if len(upcoming) >= 2:
            first = upcoming[0]
            second = upcoming[1]
            # 合并：将第二步内容并入第一步，删除第二步
            first.title = f"{first.title} + {second.title}"
            first.description = f"{first.description}\n\n{second.description}"
            first.estimated_minutes = (first.estimated_minutes or 30) + (second.estimated_minutes or 30)
            second.status = "skipped"
            route.total_steps -= 1
            await db.flush()
            return "你掌握得很快！已将后续两个步骤合并，继续加油"

        return "表现很棒！继续保持"

    # ==================== 讲义生成（升级） ====================

    @staticmethod
    async def create_lecture(
        db: AsyncSession,
        user_id: uuid.UUID,
        route_id: uuid.UUID | None = None,
        step_id: uuid.UUID | None = None,
        node_id: uuid.UUID | None = None,
        title: str = "",
        custom_instructions: str | None = None,
    ) -> Lecture:
        """创建讲义记录并触发异步生成任务"""
        lecture = Lecture(
            user_id=user_id,
            route_id=route_id,
            step_id=step_id,
            node_id=node_id,
            title=title,
            content="",
            status="generating",
        )
        db.add(lecture)
        await db.flush()
        await db.refresh(lecture)

        # 异步生成讲义
        from app.tasks.learning_tasks import generate_lecture_task
        generate_lecture_task.delay(
            str(lecture.id), str(user_id),
            str(node_id) if node_id else None,
            custom_instructions=custom_instructions,
        )

        return lecture

    @staticmethod
    async def generate_lecture_content(
        db: AsyncSession,
        lecture_id: uuid.UUID,
        user_id: uuid.UUID,
        node_id: uuid.UUID | None = None,
        custom_instructions: str | None = None,
    ) -> Lecture:
        """
        生成讲义内容（由Celery任务调用）。
        使用RAG管道检索相关知识内容，然后调用LLM生成讲义。
        """
        from app.ai.rag.pipeline import RAGPipeline
        from app.ai.prompts.lecture import LECTURE_GENERATION_PROMPT

        # 1. 获取知识节点信息
        node_context = ""
        if node_id:
            try:
                node = await KnowledgeService.get_node(db, node_id)
                node_context = f"知识点：{node.name}\n描述：{node.description or '无'}\n难度：{node.difficulty}"

                # 获取前置依赖节点作为上下文
                prereqs = await GraphDB.get_prerequisites(db, str(node_id))
                if prereqs:
                    prereq_names = []
                    for p in prereqs:
                        for k, v in p.items():
                            if isinstance(v, dict) and "name" in v:
                                prereq_names.append(v["name"])
                    if prereq_names:
                        node_context += f"\n前置知识：{'、'.join(prereq_names)}"
            except Exception as e:
                logger.warning("node_context_failed", error=str(e))

        # 2. RAG检索相关内容
        rag_context = ""
        if node_id:
            try:
                node = await KnowledgeService.get_node(db, node_id)
                pipeline = RAGPipeline()
                chunks = await pipeline.search(
                    query=f"{node.name} {node.description or ''}",
                    user_id=user_id,
                    top_k=5,
                )
                rag_context = "\n\n---\n\n".join([c.text for c in chunks[:5]])
            except Exception as e:
                logger.warning("rag_search_failed", error=str(e))

        # 3. 获取用户水平
        user_level = "中级"
        if node_id:
            mastery_result = await db.execute(
                select(UserKnowledgeMastery).where(
                    UserKnowledgeMastery.user_id == user_id,
                    UserKnowledgeMastery.node_id == node_id,
                )
            )
            mastery = mastery_result.scalar_one_or_none()
            if mastery:
                if mastery.mastery_score < 0.3:
                    user_level = "初级（对该知识点较陌生）"
                elif mastery.mastery_score > 0.7:
                    user_level = "高级（已有较好基础）"

        # 4. 构建Prompt
        prompt = LECTURE_GENERATION_PROMPT.format(
            node_context=node_context or "通用主题",
            rag_context=rag_context or "（无额外参考资料）",
            user_level=user_level,
            custom_instructions=custom_instructions or "无",
        )

        # 5. 调用LLM生成
        try:
            llm = get_llm_client()

            # 推送进度
            from app.api.v1.websocket import manager
            await manager.send_json(
                f"lecture_{lecture_id}",
                {"type": "progress", "data": {"stage": "generating_content", "percent": 30}},
            )

            response = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=6000,
            )

            await manager.send_json(
                f"lecture_{lecture_id}",
                {"type": "progress", "data": {"stage": "finalizing", "percent": 80}},
            )

            # 6. 更新讲义
            result = await db.execute(
                select(Lecture).where(Lecture.id == lecture_id)
            )
            lecture = result.scalar_one()
            lecture.content = response
            lecture.status = "generated"

            await db.commit()

            await manager.send_json(
                f"lecture_{lecture_id}",
                {"type": "complete", "data": {"lecture_id": str(lecture_id)}},
            )

            return lecture

        except Exception as e:
            logger.error("lecture_generation_failed", lecture_id=str(lecture_id), error=str(e))
            result = await db.execute(
                select(Lecture).where(Lecture.id == lecture_id)
            )
            lecture = result.scalar_one_or_none()
            if lecture:
                lecture.status = "failed"
                await db.commit()
            raise

    @staticmethod
    async def get_lecture(db: AsyncSession, lecture_id: uuid.UUID, user_id: uuid.UUID) -> Lecture:
        result = await db.execute(
            select(Lecture).where(Lecture.id == lecture_id, Lecture.user_id == user_id)
        )
        lecture = result.scalar_one_or_none()
        if not lecture:
            raise NotFoundException("讲义不存在")
        return lecture

    # ==================== Agent工具接口 ====================

    @classmethod
    def as_tools(cls) -> list:
        """暴露给Agent模块的工具列表"""
        from app.agent.tool_schema import ToolSchema
        return [
            ToolSchema(
                name="get_learning_routes",
                description="获取用户当前的学习路线列表和进度",
                parameters={"status": str},
                handler=cls._get_routes_for_agent,
            ),
            ToolSchema(
                name="get_exercises",
                description="获取某知识点的练习题",
                parameters={"node_id": str, "difficulty": int},
                handler=cls._get_exercises_for_agent,
            ),
        ]

    @classmethod
    async def _get_routes_for_agent(cls, args: dict, ctx) -> str:
        routes = await cls.get_user_routes(ctx.db, ctx.user_id, args.get("status", "active"))
        if not routes:
            return "暂无学习路线"
        return "\n".join([
            f"- {r.topic}：{r.current_step}/{r.total_steps}步，状态:{r.status}"
            for r in routes
        ])

    @classmethod
    async def _get_exercises_for_agent(cls, args: dict, ctx) -> str:
        # 基于知识节点生成练习题（调用LLM）
        node_id = args.get("node_id")
        if not node_id:
            return "请指定知识点ID"
        try:
            node = await KnowledgeService.get_node(ctx.db, uuid.UUID(node_id))
            prompt = f"请为知识点「{node.name}」生成3道练习题（难度{args.get('difficulty', 2)}/5），包含答案和解析。"
            llm = get_llm_client()
            response = await llm.chat(messages=[{"role": "user", "content": prompt}])
            return response
        except Exception as e:
            return f"生成练习题失败：{str(e)}"
```

### 5.6 Prompt 模板

#### app/ai/prompts/route.py

```python
ROUTE_GENERATION_PROMPT = """你是一位学习规划专家。请根据以下信息为学生生成学习路线。

## 学生信息
- 当前水平：{current_level}
- 已掌握的知识点：{known_nodes}
- 学习目标：{goal}
- 每周可用时间：{available_hours}小时

## 学习主题
{topic}

## 可用知识点（来自知识图谱）
{available_nodes_with_prerequisites}

## 输出要求
输出JSON格式：
{{
    "title": "路线标题",
    "description": "路线描述",
    "estimated_total_hours": 数字,
    "steps": [
        {{
            "order": 1,
            "node_id": "知识点ID（如有）",
            "title": "步骤标题",
            "description": "学习内容和目标",
            "estimated_minutes": 数字,
            "prerequisite_step_orders": [前置步骤序号]
        }}
    ]
}}

## 注意事项
- 步骤数量建议5-15个
- 确保前置依赖关系正确
- 时间分配要合理
- 从学生已知的内容出发，循序渐进
"""
```

### 5.7 Celery 异步任务

#### app/tasks/learning_tasks.py

```python
import asyncio
import uuid
import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def generate_learning_route(
    self,
    route_id: str,
    user_id: str,
    topic: str,
    goal: str | None = None,
    available_hours: float | None = None,
    current_level: str | None = None,
):
    """异步生成学习路线"""
    async def _run():
        from app.database import async_session_factory
        from app.services.learning_service import LearningService

        async with async_session_factory() as db:
            try:
                await LearningService.generate_route_with_llm(
                    db=db,
                    route_id=uuid.UUID(route_id),
                    user_id=uuid.UUID(user_id),
                    topic=topic,
                    goal=goal,
                    available_hours=available_hours,
                    current_level=current_level,
                )
            except Exception as exc:
                logger.error("generate_route_task_failed", route_id=route_id, error=str(exc))
                raise

    asyncio.run(_run())


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def generate_lecture_task(
    self,
    lecture_id: str,
    user_id: str,
    node_id: str | None = None,
    custom_instructions: str | None = None,
):
    """异步生成讲义"""
    async def _run():
        from app.database import async_session_factory
        from app.services.learning_service import LearningService

        async with async_session_factory() as db:
            try:
                await LearningService.generate_lecture_content(
                    db=db,
                    lecture_id=uuid.UUID(lecture_id),
                    user_id=uuid.UUID(user_id),
                    node_id=uuid.UUID(node_id) if node_id else None,
                    custom_instructions=custom_instructions,
                )
            except Exception as exc:
                logger.error("generate_lecture_task_failed", lecture_id=lecture_id, error=str(exc))
                raise

    asyncio.run(_run())
```

### 5.8 API 路由

#### app/api/v1/knowledge.py

```python
import uuid
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeNodeSchema,
    KnowledgeNodeCreate,
    KnowledgeNodeUpdate,
    KnowledgeEdgeSchema,
    KnowledgeEdgeCreate,
    KnowledgeGraphResponse,
    LearningPathResponse,
    UserMasterySchema,
    SubjectSchema,
)
from app.schemas.common import PaginatedResponse
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["知识图谱"])


@router.get("/subjects", response_model=list[SubjectSchema])
async def get_subjects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有学科列表"""
    return await KnowledgeService.get_subjects(db)


@router.get("/nodes", response_model=PaginatedResponse[KnowledgeNodeSchema])
async def list_nodes(
    subject: Optional[str] = None,
    grade_level: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询知识节点"""
    items, total = await KnowledgeService.list_nodes(
        db, subject=subject, grade_level=grade_level,
        search=search, page=page, page_size=page_size,
    )
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/nodes", response_model=KnowledgeNodeSchema, status_code=201)
async def create_node(
    data: KnowledgeNodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建知识节点（管理员）"""
    return await KnowledgeService.create_node(db, **data.model_dump())


@router.get("/nodes/{node_id}/graph", response_model=KnowledgeGraphResponse)
async def get_node_graph(
    node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取知识节点的图结构"""
    return await KnowledgeService.get_node_graph(db, node_id, user_id=current_user.id)


@router.get("/nodes/{node_id}/path", response_model=LearningPathResponse)
async def get_learning_path(
    node_id: uuid.UUID,
    target_id: uuid.UUID = Query(..., description="目标节点ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取两个知识节点之间的学习路径"""
    return await KnowledgeService.get_learning_path(db, node_id, target_id)


@router.post("/edges", response_model=KnowledgeEdgeSchema, status_code=201)
async def create_edge(
    data: KnowledgeEdgeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建知识边（管理员）"""
    return await KnowledgeService.create_edge(db, **data.model_dump())
```

#### app/api/v1/learning.py（Phase 2升级版）

```python
import uuid
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.learning import (
    LearningRouteCreate,
    LearningRouteSchema,
    LearningRouteStepSchema,
    RouteStepComplete,
    LectureGenerateRequest,
    LectureSchema,
    LectureGenerateResponse,
)
from app.services.learning_service import LearningService

router = APIRouter(prefix="/learning", tags=["学习引擎"])


@router.post("/routes", response_model=LearningRouteSchema, status_code=202)
async def create_route(
    data: LearningRouteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建学习路线。
    异步生成：返回status="generating"的路线，通过WebSocket推送完成状态。
    """
    route = await LearningService.create_route(
        db=db,
        user_id=current_user.id,
        topic=data.topic,
        goal=data.goal,
        available_hours=data.available_hours,
        current_level=data.current_level,
        preferences=data.preferences,
    )
    return route


@router.get("/routes", response_model=list[LearningRouteSchema])
async def list_routes(
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用户学习路线列表"""
    return await LearningService.get_user_routes(db, current_user.id, status_filter)


@router.get("/routes/{route_id}", response_model=LearningRouteSchema)
async def get_route(
    route_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取学习路线详情（含步骤列表）"""
    return await LearningService.get_route(db, route_id, current_user.id)


@router.patch("/routes/{route_id}/steps/{step_id}/complete")
async def complete_step(
    route_id: uuid.UUID,
    step_id: uuid.UUID,
    data: RouteStepComplete = RouteStepComplete(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    标记步骤完成。
    副作用：触发AI动态调整后续路线（表现不佳加练习，表现优秀合并步骤）。
    """
    return await LearningService.complete_step(
        db=db,
        route_id=route_id,
        step_id=step_id,
        user_id=current_user.id,
        duration_seconds=data.duration_seconds,
        notes=data.notes,
    )


@router.post("/lectures/generate", response_model=LectureGenerateResponse, status_code=202)
async def generate_lecture(
    data: LectureGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    为某个学习步骤生成讲义。
    异步任务，通过WebSocket推送生成进度和结果。
    """
    lecture = await LearningService.create_lecture(
        db=db,
        user_id=current_user.id,
        route_id=data.route_id,
        step_id=data.step_id,
        node_id=data.node_id,
        custom_instructions=data.custom_instructions,
    )
    return LectureGenerateResponse(lecture_id=lecture.id, status="generating")


@router.get("/lectures/{lecture_id}", response_model=LectureSchema)
async def get_lecture(
    lecture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取讲义内容"""
    return await LearningService.get_lecture(db, lecture_id, current_user.id)
```

### 5.9 WebSocket 升级

#### app/api/v1/websocket.py（Sprint 5新增端点）

在Phase 1的 `websocket.py` 中追加以下端点：

```python
@router.websocket("/ws/lecture-progress/{lecture_id}")
async def ws_lecture_progress(websocket: WebSocket, lecture_id: str):
    """
    讲义生成进度推送（Sprint 5升级版）。
    通过Redis pub/sub接收Celery任务的进度通知。
    """
    await websocket.accept()
    client_id = f"lecture_{lecture_id}"

    # 注册到连接管理器
    manager.active_connections[client_id] = websocket

    try:
        # 从Redis订阅进度消息
        redis = await get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"lecture_progress:{lecture_id}")

        await websocket.send_json({
            "type": "progress",
            "data": {"stage": "connecting", "percent": 0},
        })

        async for message in pubsub.listen():
            if message["type"] == "message":
                import json
                data = json.loads(message["data"])
                await websocket.send_json(data)
                # 如果完成或出错，关闭订阅
                if data.get("type") in ("complete", "error"):
                    break
    except WebSocketDisconnect:
        logger.info("lecture_progress_ws_disconnected", lecture_id=lecture_id)
    finally:
        manager.disconnect(client_id)
        try:
            await pubsub.unsubscribe(f"lecture_progress:{lecture_id}")
        except Exception:
            pass
```

同时更新 `ConnectionManager` 支持按前缀广播：

```python
class ConnectionManager:
    """WebSocket连接管理器（Sprint 5升级）"""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)

    async def send_json(self, client_id: str, data: dict):
        """向指定连接发送消息"""
        ws = self.active_connections.get(client_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(client_id)

    async def broadcast_to_prefix(self, prefix: str, data: dict):
        """向所有匹配前缀的连接广播消息"""
        for cid, ws in list(self.active_connections.items()):
            if cid.startswith(prefix):
                try:
                    await ws.send_json(data)
                except Exception:
                    self.disconnect(cid)
```

### 5.10 更新路由注册

更新 `app/api/v1/router.py`：

```python
from fastapi import APIRouter
from app.api.v1 import auth, notes, tags, learning, users, knowledge

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(notes.router)
api_router.include_router(tags.router)
api_router.include_router(users.router)
api_router.include_router(learning.router)
api_router.include_router(knowledge.router)  # Sprint 5 新增
```

### 5.11 Sprint 5 验收标准

- [ ] `GET /api/v1/knowledge/subjects` 返回学科列表及节点数量
- [ ] `GET /api/v1/knowledge/nodes?subject=math` 返回数学知识节点列表
- [ ] `POST /api/v1/knowledge/nodes` 创建节点并同步到AGE图
- [ ] `GET /api/v1/knowledge/nodes/{id}/graph` 返回节点的前置依赖、后续依赖、关联节点
- [ ] `GET /api/v1/knowledge/nodes/{id}/path?target_id=xxx` 返回两节点间最短学习路径
- [ ] `POST /api/v1/learning/routes` 创建路线后，Celery异步调用LLM生成步骤
- [ ] 路线生成结果包含正确的步骤顺序、前置依赖、预估时间
- [ ] `PATCH /api/v1/learning/routes/{id}/steps/{id}/complete` 标记步骤完成
- [ ] 步骤完成后，表现不佳时自动添加补充练习步骤
- [ ] 步骤完成后，表现优秀时自动合并后续简单步骤
- [ ] `POST /api/v1/learning/lectures/generate` 触发讲义异步生成
- [ ] WebSocket `/ws/lecture-progress/{id}` 推送生成进度
- [ ] 知识图谱数据同步：关系表创建节点/边时，AGE图同步更新
- [ ] Agent工具接口 `get_learning_routes` 和 `get_exercises` 可正常调用

---

## Sprint 6：智能答疑

### 6.1 新增项目结构

```
backend/app/
├── services/
│   └── qa_service.py             # 智能答疑服务（新增）
├── schemas/
│   └── qa.py                     # 答疑Schema（新增）
├── api/v1/
│   └── qa.py                     # 答疑路由（新增）
├── ai/
│   └── prompts/
│       ├── qa.py                 # 苏格拉底式答疑Prompt（新增）
│       └── diagnosis.py          # 诊断性问题Prompt（新增）
└── tasks/
    └── qa_tasks.py               # 答疑异步任务（新增）
```

### 6.2 Pydantic Schema 定义

#### app/schemas/qa.py

```python
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class QASessionCreate(BaseModel):
    lecture_id: Optional[uuid.UUID] = None
    node_id: Optional[uuid.UUID] = None
    topic: Optional[str] = Field(None, max_length=255)


class QASessionSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    lecture_id: Optional[uuid.UUID] = None
    node_id: Optional[uuid.UUID] = None
    topic: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QAMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class QAMessageSchema(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str  # "user" | "assistant"
    content: str
    metadata: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class QAMessagePair(BaseModel):
    """发送消息后的响应（用户消息 + AI回复）"""
    user_message: QAMessageSchema
    assistant_message: QAMessageSchema


class DiagnosticQuestion(BaseModel):
    type: str = Field(pattern="^(choice|short_answer)$")
    question: str
    options: Optional[list[str]] = None  # 仅选择题
    correct_answer: str
    explanation: str
    target_concept: str
    difficulty: int = Field(ge=1, le=5)


class DiagnosticQuestionsResponse(BaseModel):
    questions: list[DiagnosticQuestion]


class QASessionListResponse(BaseModel):
    items: list[QASessionSchema]
    total: int
```

### 6.3 Prompt 模板

#### app/ai/prompts/qa.py

```python
QA_SYSTEM_PROMPT = """你是一位苏格拉底式的学习导师。你的目标不是直接告诉学生答案，而是通过提问和引导帮助他们自己发现答案。

## 行为准则
1. 当学生提出问题时，不要直接给出答案。先问一个引导性问题，帮助学生思考。
2. 使用类比和生活中的例子来解释抽象概念。
3. 如果学生回答正确，给予肯定并提出更深层次的问题。
4. 如果学生回答错误，不要否定，而是提出新的引导问题帮助其发现错误。
5. 每次回复控制在200字以内，保持对话节奏。
6. 在适当时候总结知识点的关键要点。

## 当前学习上下文
- 正在学习的知识点：{node_name}
- 讲义内容摘要：{lecture_summary}
- 学生对该知识点的掌握度：{mastery_score}

## 回答格式
使用Markdown格式，公式使用LaTeX。
"""
```

#### app/ai/prompts/diagnosis.py

```python
DIAGNOSIS_PROMPT = """你是一位评估专家。请根据以下讲义内容和学生情况，生成诊断性问题。

## 讲义内容摘要：{lecture_summary}
## 知识点：{node_name}
## 学生当前掌握度：{mastery_score}

## 要求
生成3-5个诊断性问题，用于评估学生对本知识点的理解程度。

输出JSON格式：
{{
    "questions": [
        {{
            "type": "choice|short_answer",
            "question": "问题内容",
            "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
            "correct_answer": "正确答案",
            "explanation": "解析",
            "target_concept": "考查的具体概念",
            "difficulty": 1-5
        }}
    ]
}}

## 注意
- 问题应覆盖不同认知层次（记忆、理解、应用、分析）
- 针对学生掌握度较低的概念出更多基础题
- 选择题要有干扰性强的干扰项
"""
```

### 6.4 智能答疑服务

#### app/services/qa_service.py

```python
import json
import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.models.learning import QASession, QAMessage, Lecture
from app.models.knowledge import KnowledgeNode, UserKnowledgeMastery
from app.services.knowledge_service import KnowledgeService
from app.ai.llm_client import get_llm_client
from app.ai.prompts.qa import QA_SYSTEM_PROMPT
from app.ai.prompts.diagnosis import DIAGNOSIS_PROMPT
from app.core.exceptions import NotFoundException

logger = structlog.get_logger()


class QAService:

    # ==================== 会话管理 ====================

    @staticmethod
    async def create_session(
        db: AsyncSession,
        user_id: uuid.UUID,
        lecture_id: uuid.UUID | None = None,
        node_id: uuid.UUID | None = None,
        topic: str | None = None,
    ) -> QASession:
        """创建答疑会话"""
        session = QASession(
            user_id=user_id,
            lecture_id=lecture_id,
            node_id=node_id,
            topic=topic,
            status="active",
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        return session

    @staticmethod
    async def get_session(
        db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> QASession:
        result = await db.execute(
            select(QASession)
            .options(selectinload(QASession.messages))
            .where(QASession.id == session_id, QASession.user_id == user_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise NotFoundException("答疑会话不存在")
        return session

    @staticmethod
    async def list_sessions(
        db: AsyncSession, user_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[QASession], int]:
        query = select(QASession).where(QASession.user_id == user_id)
        count_query = select(func.count()).select_from(QASession).where(
            QASession.user_id == user_id
        )

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(QASession.updated_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        items = list(result.scalars().all())

        return items, total

    @staticmethod
    async def close_session(db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID):
        session = await QAService.get_session(db, session_id, user_id)
        session.status = "closed"
        await db.flush()

    # ==================== 消息处理（苏格拉底式答疑） ====================

    @staticmethod
    async def handle_message(
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
    ) -> tuple[QAMessage, QAMessage]:
        """
        处理答疑消息。
        1. 保存用户消息
        2. 构建苏格拉底式Prompt
        3. 调用LLM生成回复
        4. 保存AI回复
        5. 分析是否需要更新知识画像
        返回：(用户消息, AI回复)
        """
        session = await QAService.get_session(db, session_id, user_id)

        # 保存用户消息
        user_msg = QAMessage(
            session_id=session_id,
            role="user",
            content=content,
        )
        db.add(user_msg)
        await db.flush()

        # 构建上下文
        context = await QAService._build_context(db, session, user_id)

        # 构建消息列表
        messages = [
            {"role": "system", "content": context["system_prompt"]},
        ]

        # 添加历史消息（最近10轮）
        history = session.messages[-20:] if session.messages else []
        for msg in history[:-1]:  # 排除刚添加的用户消息
            messages.append({"role": msg.role, "content": msg.content})

        # 添加当前用户消息
        messages.append({"role": "user", "content": content})

        # 调用LLM
        try:
            llm = get_llm_client()
            response = await llm.chat(
                messages=messages,
                temperature=0.7,
                max_tokens=1000,
            )
        except Exception as e:
            logger.error("qa_llm_failed", error=str(e))
            response = "抱歉，我暂时无法回答。请稍后再试。"

        # 保存AI回复
        assistant_msg = QAMessage(
            session_id=session_id,
            role="assistant",
            content=response,
            metadata_={"context_summary": context.get("node_name", "")},
        )
        db.add(assistant_msg)
        session.status = "active"
        await db.flush()
        await db.refresh(user_msg)
        await db.refresh(assistant_msg)

        # 异步分析用户回答，更新知识画像
        if context.get("node_id"):
            try:
                await QAService._analyze_and_update_mastery(
                    db, user_id, content, response, uuid.UUID(context["node_id"])
                )
            except Exception as e:
                logger.warning("mastery_update_failed", error=str(e))

        return user_msg, assistant_msg

    @staticmethod
    async def handle_message_stream(
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
        ws_manager,
    ):
        """
        流式处理答疑消息（通过WebSocket逐token推送）。
        """
        session = await QAService.get_session(db, session_id, user_id)

        # 保存用户消息
        user_msg = QAMessage(
            session_id=session_id,
            role="user",
            content=content,
        )
        db.add(user_msg)
        await db.flush()
        await db.refresh(user_msg)

        # 构建上下文
        context = await QAService._build_context(db, session, user_id)

        # 构建消息列表
        messages = [
            {"role": "system", "content": context["system_prompt"]},
        ]
        history = session.messages[-20:] if session.messages else []
        for msg in history[:-1]:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": content})

        # 流式调用LLM
        full_response = ""
        try:
            llm = get_llm_client()
            async for token in llm.chat_stream(
                messages=messages,
                temperature=0.7,
                max_tokens=1000,
            ):
                full_response += token
                # 通过WebSocket推送token
                await ws_manager.send_json(
                    f"qa_{session_id}",
                    {"type": "token", "data": {"content": token}},
                )
        except Exception as e:
            logger.error("qa_stream_failed", error=str(e))
            full_response = "抱歉，生成回复时出错。"
            await ws_manager.send_json(
                f"qa_{session_id}",
                {"type": "error", "data": {"message": str(e)}},
            )

        # 保存完整回复
        assistant_msg = QAMessage(
            session_id=session_id,
            role="assistant",
            content=full_response,
            metadata_={"context_summary": context.get("node_name", "")},
        )
        db.add(assistant_msg)
        await db.flush()
        await db.refresh(assistant_msg)

        # 推送完成消息
        await ws_manager.send_json(
            f"qa_{session_id}",
            {
                "type": "done",
                "data": {"message": {
                    "id": str(assistant_msg.id),
                    "role": "assistant",
                    "content": full_response,
                }},
            },
        )

        # 分析并更新掌握度
        if context.get("node_id"):
            try:
                mastery_update = await QAService._analyze_and_update_mastery(
                    db, user_id, content, full_response, uuid.UUID(context["node_id"])
                )
                if mastery_update:
                    await ws_manager.send_json(
                        f"qa_{session_id}",
                        {
                            "type": "diagnosis",
                            "data": {
                                "node_id": context["node_id"],
                                "mastery_update": mastery_update,
                            },
                        },
                    )
            except Exception as e:
                logger.warning("stream_mastery_update_failed", error=str(e))

    @staticmethod
    async def _build_context(
        db: AsyncSession, session: QASession, user_id: uuid.UUID
    ) -> dict:
        """构建答疑上下文"""
        context = {
            "node_name": "通用知识",
            "lecture_summary": "无",
            "mastery_score": "未知",
            "node_id": None,
        }

        # 获取知识节点信息
        if session.node_id:
            try:
                node = await KnowledgeService.get_node(db, session.node_id)
                context["node_name"] = node.name
                context["node_id"] = str(node.id)

                # 获取掌握度
                mastery_result = await db.execute(
                    select(UserKnowledgeMastery).where(
                        UserKnowledgeMastery.user_id == user_id,
                        UserKnowledgeMastery.node_id == session.node_id,
                    )
                )
                mastery = mastery_result.scalar_one_or_none()
                if mastery:
                    context["mastery_score"] = f"{mastery.mastery_score:.2f}"
            except Exception:
                pass

        # 获取关联讲义摘要
        if session.lecture_id:
            try:
                result = await db.execute(
                    select(Lecture).where(Lecture.id == session.lecture_id)
                )
                lecture = result.scalar_one_or_none()
                if lecture:
                    # 取讲义前500字作为摘要
                    context["lecture_summary"] = lecture.content[:500] if lecture.content else "无内容"
            except Exception:
                pass

        # 构建System Prompt
        context["system_prompt"] = QA_SYSTEM_PROMPT.format(
            node_name=context["node_name"],
            lecture_summary=context["lecture_summary"],
            mastery_score=context["mastery_score"],
        )

        return context

    @staticmethod
    async def _analyze_and_update_mastery(
        db: AsyncSession,
        user_id: uuid.UUID,
        user_answer: str,
        ai_response: str,
        node_id: uuid.UUID,
    ) -> float | None:
        """
        分析用户回答质量，更新知识掌握度。
        通过LLM判断用户回答的正确性。
        返回掌握度变化量，如果无法判断返回None。
        """
        try:
            llm = get_llm_client()
            eval_prompt = f"""请评估以下学生对知识点的回答质量。

学生回答：{user_answer}
导师回复：{ai_response}

请判断学生的理解程度，输出一个0.0到1.0之间的分数：
- 1.0: 完全正确，理解深入
- 0.7: 基本正确，有小错误
- 0.4: 部分正确，存在明显误解
- 0.0: 完全错误或未回答

只输出数字，不要其他内容。"""

            score_text = await llm.chat(
                messages=[{"role": "user", "content": eval_prompt}],
                temperature=0.1,
                max_tokens=10,
            )

            # 解析分数
            try:
                quality = float(score_text.strip())
                quality = max(0.0, min(1.0, quality))
            except ValueError:
                return None

            # 更新掌握度
            mastery = await KnowledgeService.get_or_create_mastery(db, user_id, node_id)
            old_score = mastery.mastery_score

            if quality >= 0.7:
                mastery.correct_count += 1
                mastery.mastery_score += (1.0 - mastery.mastery_score) * 0.3
            elif quality >= 0.4:
                mastery.mastery_score += (0.5 - mastery.mastery_score) * 0.2
            else:
                mastery.mastery_score *= 0.7

            mastery.mastery_score = max(0.0, min(1.0, mastery.mastery_score))
            mastery.total_count += 1
            mastery.review_count += 1
            mastery.last_reviewed_at = func.now()

            await db.flush()
            return mastery.mastery_score - old_score

        except Exception as e:
            logger.warning("mastery_analysis_failed", error=str(e))
            return None

    # ==================== 诊断性问题生成 ====================

    @staticmethod
    async def generate_diagnostic_questions(
        db: AsyncSession,
        lecture_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[dict]:
        """
        为讲义生成诊断性问题。
        基于讲义内容和用户掌握度，生成3-5个诊断性问题。
        """
        # 获取讲义
        result = await db.execute(
            select(Lecture).where(Lecture.id == lecture_id, Lecture.user_id == user_id)
        )
        lecture = result.scalar_one_or_none()
        if not lecture:
            raise NotFoundException("讲义不存在")

        # 获取知识节点
        node_name = "通用知识"
        mastery_score = "未知"
        if lecture.node_id:
            try:
                node = await KnowledgeService.get_node(db, lecture.node_id)
                node_name = node.name

                mastery_result = await db.execute(
                    select(UserKnowledgeMastery).where(
                        UserKnowledgeMastery.user_id == user_id,
                        UserKnowledgeMastery.node_id == lecture.node_id,
                    )
                )
                mastery = mastery_result.scalar_one_or_none()
                if mastery:
                    mastery_score = f"{mastery.mastery_score:.2f}"
            except Exception:
                pass

        # 构建Prompt
        lecture_summary = lecture.content[:1000] if lecture.content else "无内容"
        prompt = DIAGNOSIS_PROMPT.format(
            lecture_summary=lecture_summary,
            node_name=node_name,
            mastery_score=mastery_score,
        )

        # 调用LLM
        try:
            llm = get_llm_client()
            response = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
            )

            # 解析JSON
            try:
                data = json.loads(response)
                return data.get("questions", [])
            except json.JSONDecodeError:
                # 尝试从文本中提取JSON
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                        return data.get("questions", [])
                    except json.JSONDecodeError:
                        pass

            logger.warning("diagnosis_parse_failed", response_preview=response[:200])
            return []

        except Exception as e:
            logger.error("diagnosis_generation_failed", error=str(e))
            return []

    # ==================== 消息历史 ====================

    @staticmethod
    async def get_messages(
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        before: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[QAMessage]:
        """获取会话历史消息"""
        # 验证会话归属
        await QAService.get_session(db, session_id, user_id)

        query = (
            select(QAMessage)
            .where(QAMessage.session_id == session_id)
            .order_by(QAMessage.created_at.desc())
            .limit(limit)
        )
        if before:
            # 获取before消息的时间戳
            before_result = await db.execute(
                select(QAMessage.created_at).where(QAMessage.id == before)
            )
            before_time = before_result.scalar()
            if before_time:
                query = query.where(QAMessage.created_at < before_time)

        result = await db.execute(query)
        messages = list(result.scalars().all())
        return list(reversed(messages))  # 按时间正序返回

    # ==================== Agent工具接口 ====================

    @classmethod
    def as_tools(cls) -> list:
        from app.agent.tool_schema import ToolSchema
        return [
            ToolSchema(
                name="create_qa_session",
                description="为用户创建一个答疑会话，关联到某个知识点",
                parameters={"node_id": str, "topic": str},
                handler=cls._create_session_for_agent,
            ),
        ]

    @classmethod
    async def _create_session_for_agent(cls, args: dict, ctx) -> str:
        session = await cls.create_session(
            ctx.db,
            ctx.user_id,
            node_id=uuid.UUID(args["node_id"]) if args.get("node_id") else None,
            topic=args.get("topic"),
        )
        return f"已创建答疑会话，ID: {session.id}，主题: {args.get('topic', '未指定')}"
```

> **注意：** qa_service的核心功能（苏格拉底式答疑、诊断性问题生成）不经过Agent，由学习模块的API端点直接调用。Agent工具接口仅提供创建会话的入口，实际的答疑对话仍通过qa-stream WebSocket进行。

### 6.5 API 路由

#### app/api/v1/qa.py

```python
import uuid
from fastapi import APIRouter, Depends, Query
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.qa import (
    QASessionCreate,
    QASessionSchema,
    QAMessageCreate,
    QAMessageSchema,
    QAMessagePair,
    DiagnosticQuestionsResponse,
    QASessionListResponse,
)
from app.schemas.common import PaginatedResponse
from app.services.qa_service import QAService

router = APIRouter(prefix="/learning/qa", tags=["智能答疑"])


@router.post("/sessions", response_model=QASessionSchema, status_code=201)
async def create_session(
    data: QASessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建答疑会话"""
    return await QAService.create_session(
        db=db,
        user_id=current_user.id,
        lecture_id=data.lecture_id,
        node_id=data.node_id,
        topic=data.topic,
    )


@router.get("/sessions", response_model=QASessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取答疑会话列表"""
    items, total = await QAService.list_sessions(db, current_user.id, page, page_size)
    return QASessionListResponse(items=items, total=total)


@router.post("/sessions/{session_id}/messages", response_model=QAMessagePair)
async def send_message(
    session_id: uuid.UUID,
    data: QAMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    发送消息（非流式）。
    返回用户消息和AI回复。
    如需流式输出，请使用WebSocket /ws/qa-stream/{session_id}
    """
    user_msg, assistant_msg = await QAService.handle_message(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
        content=data.content,
    )
    return QAMessagePair(
        user_message=user_msg,
        assistant_message=assistant_msg,
    )


@router.get("/sessions/{session_id}/messages", response_model=list[QAMessageSchema])
async def get_messages(
    session_id: uuid.UUID,
    before: Optional[uuid.UUID] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取会话历史消息"""
    return await QAService.get_messages(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
        before=before,
        limit=limit,
    )


@router.post("/diagnostic-questions", response_model=DiagnosticQuestionsResponse)
async def generate_diagnostic_questions(
    lecture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """为讲义生成诊断性问题"""
    questions = await QAService.generate_diagnostic_questions(
        db=db, lecture_id=lecture_id, user_id=current_user.id,
    )
    return DiagnosticQuestionsResponse(questions=questions)
```

### 6.6 WebSocket 答疑流

#### app/api/v1/websocket.py（Sprint 6新增端点）

在 `websocket.py` 中追加：

```python
@router.websocket("/ws/qa-stream/{session_id}")
async def ws_qa_stream(websocket: WebSocket, session_id: str):
    """
    答疑对话流式输出。
    客户端发送用户消息，服务端流式返回AI回复。
    """
    # 验证token
    user_id = await verify_ws_token(websocket)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    client_id = f"qa_{session_id}"
    manager.active_connections[client_id] = websocket

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "message":
                content = data.get("data", {}).get("content", "")
                if not content:
                    await websocket.send_json({
                        "type": "error",
                        "data": {"message": "消息内容不能为空"},
                    })
                    continue

                # 异步处理消息（流式输出）
                from app.database import async_session_factory
                async with async_session_factory() as db:
                    try:
                        await QAService.handle_message_stream(
                            db=db,
                            session_id=uuid.UUID(session_id),
                            user_id=uuid.UUID(user_id),
                            content=content,
                            ws_manager=manager,
                        )
                    except Exception as e:
                        logger.error("qa_ws_error", error=str(e))
                        await websocket.send_json({
                            "type": "error",
                            "data": {"message": str(e)},
                        })

            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("qa_stream_disconnected", session_id=session_id)
    finally:
        manager.disconnect(client_id)
```

### 6.7 更新路由注册

更新 `app/api/v1/router.py`：

```python
from app.api.v1 import auth, notes, tags, learning, users, knowledge, qa

api_router.include_router(qa.router)  # Sprint 6 新增
```

### 6.8 Sprint 6 验收标准

- [ ] `POST /api/v1/learning/qa/sessions` 创建答疑会话
- [ ] `POST /api/v1/learning/qa/sessions/{id}/messages` 发送消息并获取苏格拉底式回复
- [ ] AI回复体现苏格拉底式引导风格（不直接给答案，通过提问引导）
- [ ] `GET /api/v1/learning/qa/sessions/{id}/messages` 获取历史消息，支持分页
- [ ] `POST /api/v1/learning/qa/diagnostic-questions?lecture_id=xxx` 生成诊断性问题
- [ ] 诊断性问题包含选择题和简答题混合，覆盖不同认知层次
- [ ] WebSocket `/ws/qa-stream/{session_id}` 流式输出AI回复
- [ ] 流式输出逐token推送（type="token"），完成后推送（type="done"）
- [ ] 答疑过程中自动分析用户回答质量
- [ ] 分析结果更新到 `user_knowledge_mastery` 表
- [ ] 掌握度变化通过WebSocket推送（type="diagnosis"）
- [ ] Agent工具接口 `create_qa_session` 可正常调用

---

## Sprint 7：复习系统

### 7.1 新增项目结构

```
backend/app/
├── services/
│   └── review_service.py         # 复习服务（新增）
├── schemas/
│   └── review.py                 # 复习Schema（新增）
├── api/v1/
│   └── review.py                 # 复习路由（新增）
├── ai/
│   └── prompts/
│       └── review.py             # 复习内容生成Prompt（新增）
└── tasks/
    └── review_tasks.py           # 复习定时任务（新增）
```

### 7.2 Pydantic Schema 定义

#### app/schemas/review.py

```python
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class ReviewPlanSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    node_id: uuid.UUID
    review_type: str
    scheduled_at: datetime
    completed_at: Optional[datetime] = None
    status: str  # pending / completed / skipped
    priority: int
    metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    # 关联信息（可选）
    node_name: Optional[str] = None
    node_subject: Optional[str] = None

    model_config = {"from_attributes": True}


class ReviewCompleteRequest(BaseModel):
    performance: Optional[float] = Field(None, ge=0.0, le=1.0, description="本次复习表现 0.0~1.0")
    notes: Optional[str] = None


class ReviewContentRequest(BaseModel):
    node_id: uuid.UUID
    review_type: Optional[str] = Field(None, pattern="^(flashcard|quiz|explanation)$")


class ReviewContentResponse(BaseModel):
    content: str
    type: str  # flashcard / quiz / explanation
    node_name: str


class ReviewStatsResponse(BaseModel):
    today_due: int
    this_week_completed: int
    overdue_count: int
    mastery_distribution: dict  # { not_started: int, learning: int, familiar: int, mastered: int }


class ReviewPlanListResponse(BaseModel):
    items: list[ReviewPlanSchema]
    total: int
```

### 7.3 Prompt 模板

#### app/ai/prompts/review.py

```python
REVIEW_GENERATION_PROMPT = """你是一位复习辅导老师。请根据学生的掌握情况生成针对性的复习内容。

## 知识点：{node_name}
## 学生掌握度：{mastery_score} (0.0~1.0)
## 历史复习次数：{review_count}
## 上次复习表现：{last_performance}

## 生成策略
{review_strategy}

## 输出格式（Markdown）
根据复习类型输出相应内容：
- flashcard: 正面（问题）和背面（答案）的卡片，3-5张
- quiz: 选择题/填空题，3-5道，附答案和解析
- explanation: 重新讲解 + 新的类比/例子 + 练习题
"""
```

### 7.4 复习服务

#### app/services/review_service.py

```python
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.models.review import ReviewPlan
from app.models.knowledge import KnowledgeNode, UserKnowledgeMastery
from app.services.knowledge_service import KnowledgeService
from app.ai.llm_client import get_llm_client
from app.ai.prompts.review import REVIEW_GENERATION_PROMPT
from app.core.exceptions import NotFoundException

logger = structlog.get_logger()


class ReviewService:

    # ==================== SM-2 间隔重复算法 ====================

    @staticmethod
    def calculate_next_review(
        mastery: UserKnowledgeMastery,
        quality_rating: int,
    ) -> tuple[datetime, float, int]:
        """
        SM-2间隔重复算法。
        
        参数：
            mastery: 当前掌握度记录
            quality_rating: 0-5，本次复习质量评分
                0-2: 完全不会
                3: 勉强记住
                4: 有些犹豫
                5: 轻松记住
        
        返回：
            (next_review_time, new_ease_factor, new_interval_days)
        """
        ef = mastery.ease_factor
        interval = mastery.interval_days

        if quality_rating >= 3:
            # 回答正确
            if interval == 0:
                interval = 1
            elif interval == 1:
                interval = 6
            else:
                interval = round(interval * ef)

            # 更新难度因子（EF）
            ef = ef + (0.1 - (5 - quality_rating) * (0.08 + (5 - quality_rating) * 0.02))
            ef = max(1.3, ef)  # 最低1.3
        else:
            # 回答错误，重置间隔
            interval = 1
            ef = max(1.3, ef - 0.2)

        next_review = datetime.utcnow() + timedelta(days=interval)
        return next_review, ef, interval

    @staticmethod
    def quality_from_performance(performance: float) -> int:
        """将0.0~1.0的表现分数转换为SM-2的0~5质量评分"""
        if performance >= 0.9:
            return 5
        elif performance >= 0.75:
            return 4
        elif performance >= 0.6:
            return 3
        elif performance >= 0.4:
            return 2
        elif performance >= 0.2:
            return 1
        else:
            return 0

    # ==================== 复习计划管理 ====================

    @staticmethod
    async def schedule_review(
        db: AsyncSession,
        user_id: uuid.UUID,
        node_id: uuid.UUID,
        initial_mastery: float = 0.0,
    ) -> ReviewPlan:
        """
        创建或更新复习计划。
        根据mastery_score计算初始复习间隔。
        """
        # 获取或创建掌握度记录
        mastery = await KnowledgeService.get_or_create_mastery(db, user_id, node_id)

        # 检查是否已有pending的复习计划
        existing = await db.execute(
            select(ReviewPlan).where(
                ReviewPlan.user_id == user_id,
                ReviewPlan.node_id == node_id,
                ReviewPlan.status == "pending",
            )
        )
        plan = existing.scalar_one_or_none()

        if plan:
            # 更新现有计划
            interval = max(1, mastery.interval_days)
            plan.scheduled_at = datetime.utcnow() + timedelta(days=interval)
            plan.priority = ReviewService._calculate_priority(mastery.mastery_score)
        else:
            # 创建新计划
            interval = max(1, mastery.interval_days)
            plan = ReviewPlan(
                user_id=user_id,
                node_id=node_id,
                review_type="spaced",
                scheduled_at=datetime.utcnow() + timedelta(days=interval),
                status="pending",
                priority=ReviewService._calculate_priority(mastery.mastery_score),
            )
            db.add(plan)

        await db.flush()
        await db.refresh(plan)
        return plan

    @staticmethod
    def _calculate_priority(mastery_score: float) -> int:
        """根据掌握度计算复习优先级"""
        if mastery_score < 0.3:
            return 1  # 高优先
        elif mastery_score < 0.6:
            return 3  # 中优先
        else:
            return 5  # 低优先

    @staticmethod
    async def get_review_plans(
        db: AsyncSession,
        user_id: uuid.UUID,
        status: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """获取复习计划列表（含节点名称）"""
        query = select(ReviewPlan).where(ReviewPlan.user_id == user_id)
        count_query = select(func.count()).select_from(ReviewPlan).where(
            ReviewPlan.user_id == user_id
        )

        if status:
            query = query.where(ReviewPlan.status == status)
            count_query = count_query.where(ReviewPlan.status == status)
        if from_date:
            query = query.where(ReviewPlan.scheduled_at >= from_date)
            count_query = count_query.where(ReviewPlan.scheduled_at >= from_date)
        if to_date:
            query = query.where(ReviewPlan.scheduled_at <= to_date)
            count_query = count_query.where(ReviewPlan.scheduled_at <= to_date)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(ReviewPlan.priority.asc(), ReviewPlan.scheduled_at.asc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        plans = list(result.scalars().all())

        # 批量获取节点名称
        node_ids = [p.node_id for p in plans]
        node_map = {}
        if node_ids:
            nodes_result = await db.execute(
                select(KnowledgeNode).where(KnowledgeNode.id.in_(node_ids))
            )
            node_map = {n.id: n for n in nodes_result.scalars().all()}

        # 组装响应
        items = []
        for plan in plans:
            plan_dict = {
                "id": plan.id,
                "user_id": plan.user_id,
                "node_id": plan.node_id,
                "review_type": plan.review_type,
                "scheduled_at": plan.scheduled_at,
                "completed_at": plan.completed_at,
                "status": plan.status,
                "priority": plan.priority,
                "metadata": plan.metadata_,
                "created_at": plan.created_at,
                "updated_at": plan.updated_at,
                "node_name": node_map.get(plan.node_id, {}).name if plan.node_id in node_map else None,
                "node_subject": node_map.get(plan.node_id, {}).subject if plan.node_id in node_map else None,
            }
            items.append(plan_dict)

        return items, total

    @staticmethod
    async def complete_review(
        db: AsyncSession,
        plan_id: uuid.UUID,
        user_id: uuid.UUID,
        performance: float | None = None,
        notes: str | None = None,
    ) -> dict:
        """
        完成一次复习。
        1. 标记复习计划为completed
        2. 使用SM-2算法计算下次复习时间
        3. 更新掌握度
        4. 创建下一次复习计划
        """
        # 获取复习计划
        result = await db.execute(
            select(ReviewPlan).where(
                ReviewPlan.id == plan_id,
                ReviewPlan.user_id == user_id,
            )
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise NotFoundException("复习计划不存在")

        # 标记完成
        plan.status = "completed"
        plan.completed_at = datetime.utcnow()
        if notes:
            plan.metadata_ = {**(plan.metadata_ or {}), "notes": notes, "performance": performance}

        # 更新掌握度
        mastery = await KnowledgeService.get_or_create_mastery(db, user_id, plan.node_id)

        # 计算质量评分
        if performance is not None:
            quality = ReviewService.quality_from_performance(performance)
        else:
            quality = 3  # 默认中等

        # SM-2算法计算下次复习时间
        next_review, new_ef, new_interval = ReviewService.calculate_next_review(mastery, quality)

        # 更新掌握度记录
        mastery.ease_factor = new_ef
        mastery.interval_days = new_interval
        mastery.next_review_at = next_review
        mastery.last_reviewed_at = datetime.utcnow()
        mastery.review_count += 1

        if quality >= 3:
            mastery.correct_count += 1
            mastery.mastery_score += (1.0 - mastery.mastery_score) * 0.2
        else:
            mastery.mastery_score *= 0.8

        mastery.mastery_score = max(0.0, min(1.0, mastery.mastery_score))

        await db.flush()

        # 自动创建下一次复习计划
        next_plan = ReviewPlan(
            user_id=user_id,
            node_id=plan.node_id,
            review_type="spaced",
            scheduled_at=next_review,
            status="pending",
            priority=ReviewService._calculate_priority(mastery.mastery_score),
        )
        db.add(next_plan)
        await db.flush()
        await db.refresh(plan)
        await db.refresh(mastery)

        return {
            "plan": plan,
            "mastery": mastery,
            "next_review_at": next_review,
            "next_interval_days": new_interval,
        }

    # ==================== 复习统计 ====================

    @staticmethod
    async def get_review_stats(db: AsyncSession, user_id: uuid.UUID) -> dict:
        """获取复习统计"""
        now = datetime.utcnow()
        week_start = now - timedelta(days=now.weekday())

        # 今日到期
        today_end = now.replace(hour=23, minute=59, second=59)
        today_result = await db.execute(
            select(func.count()).select_from(ReviewPlan).where(
                ReviewPlan.user_id == user_id,
                ReviewPlan.status == "pending",
                ReviewPlan.scheduled_at <= today_end,
            )
        )
        today_due = today_result.scalar() or 0

        # 本周完成
        week_result = await db.execute(
            select(func.count()).select_from(ReviewPlan).where(
                ReviewPlan.user_id == user_id,
                ReviewPlan.status == "completed",
                ReviewPlan.completed_at >= week_start,
            )
        )
        this_week_completed = week_result.scalar() or 0

        # 逾期
        overdue_result = await db.execute(
            select(func.count()).select_from(ReviewPlan).where(
                ReviewPlan.user_id == user_id,
                ReviewPlan.status == "pending",
                ReviewPlan.scheduled_at < now,
            )
        )
        overdue_count = overdue_result.scalar() or 0

        # 掌握度分布
        mastery_result = await db.execute(
            select(UserKnowledgeMastery).where(
                UserKnowledgeMastery.user_id == user_id,
            )
        )
        masteries = mastery_result.scalars().all()

        distribution = {
            "not_started": 0,  # mastery_score == 0
            "learning": 0,     # 0 < score < 0.4
            "familiar": 0,     # 0.4 <= score < 0.7
            "mastered": 0,     # score >= 0.7
        }
        for m in masteries:
            if m.mastery_score == 0:
                distribution["not_started"] += 1
            elif m.mastery_score < 0.4:
                distribution["learning"] += 1
            elif m.mastery_score < 0.7:
                distribution["familiar"] += 1
            else:
                distribution["mastered"] += 1

        return {
            "today_due": today_due,
            "this_week_completed": this_week_completed,
            "overdue_count": overdue_count,
            "mastery_distribution": distribution,
        }

    # ==================== 复习内容生成 ====================

    @staticmethod
    async def generate_review_content(
        db: AsyncSession,
        node_id: uuid.UUID,
        user_id: uuid.UUID,
        review_type: str | None = None,
    ) -> dict:
        """
        生成复习内容。
        根据掌握度自动选择复习形式：
          mastery > 0.7: 快速回顾（闪卡）
          mastery 0.4~0.7: 中等难度练习（选择题）
          mastery < 0.4: 详细重新讲解（explanation）
        """
        # 获取知识节点
        node = await KnowledgeService.get_node(db, node_id)

        # 获取掌握度
        mastery = await KnowledgeService.get_or_create_mastery(db, user_id, node_id)

        # 自动选择复习类型
        if not review_type:
            if mastery.mastery_score > 0.7:
                review_type = "flashcard"
            elif mastery.mastery_score > 0.4:
                review_type = "quiz"
            else:
                review_type = "explanation"

        # 构建复习策略描述
        strategy_map = {
            "flashcard": "生成3-5张闪卡，每张包含正面（问题）和背面（答案）。问题要简洁，答案要准确。适合快速回顾。",
            "quiz": "生成3-5道选择题/填空题，包含答案和详细解析。题目应有一定难度，考查理解深度。",
            "explanation": "重新讲解核心概念，使用新的类比和生活例子。讲解后附2-3道基础练习题。适合基础薄弱的学生。",
        }
        review_strategy = strategy_map.get(review_type, strategy_map["quiz"])

        # 获取上次复习表现
        last_performance = "未知"
        if mastery.metadata_ if hasattr(mastery, 'metadata_') else {}:
            pass  # 可从metadata中获取

        # 构建Prompt
        prompt = REVIEW_GENERATION_PROMPT.format(
            node_name=node.name,
            mastery_score=f"{mastery.mastery_score:.2f}",
            review_count=mastery.review_count,
            last_performance=last_performance,
            review_strategy=review_strategy,
        )

        # 调用LLM
        try:
            llm = get_llm_client()
            content = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=3000,
            )

            return {
                "content": content,
                "type": review_type,
                "node_name": node.name,
            }
        except Exception as e:
            logger.error("review_content_generation_failed", error=str(e))
            return {
                "content": f"生成复习内容失败：{str(e)}",
                "type": review_type,
                "node_name": node.name,
            }

    # ==================== 复习提醒（Celery Beat） ====================

    @staticmethod
    async def check_due_reviews(db: AsyncSession) -> list[ReviewPlan]:
        """
        检查到期的复习计划。
        由Celery Beat定时调用（每5分钟一次）。
        返回需要提醒的复习计划列表。
        """
        now = datetime.utcnow()
        result = await db.execute(
            select(ReviewPlan)
            .options(selectinload(ReviewPlan.__mapper__.relationships))
            .where(
                ReviewPlan.status == "pending",
                ReviewPlan.scheduled_at <= now,
            )
            .order_by(ReviewPlan.priority.asc(), ReviewPlan.scheduled_at.asc())
            .limit(50)
        )
        due_plans = list(result.scalars().all())
        return due_plans

    # ==================== Agent工具接口 ====================

    @classmethod
    def as_tools(cls) -> list:
        from app.agent.tool_schema import ToolSchema
        return [
            ToolSchema(
                name="get_review_plans",
                description="获取用户待复习的复习计划列表",
                parameters={"status": str},
                handler=cls._get_plans_for_agent,
            ),
            ToolSchema(
                name="generate_review_content",
                description="为某知识点生成复习内容（闪卡/选择题/讲解）",
                parameters={"node_id": str, "review_type": str},
                handler=cls._generate_content_for_agent,
            ),
        ]

    @classmethod
    async def _get_plans_for_agent(cls, args: dict, ctx) -> str:
        plans, _ = await cls.get_review_plans(
            ctx.db, ctx.user_id, status=args.get("status", "pending"),
        )
        if not plans:
            return "暂无复习计划"
        return "\n".join([
            f"- {p.get('node_name', '未知')}：{p['review_type']}，计划时间{p['scheduled_at']}"
            for p in plans[:10]
        ])

    @classmethod
    async def _generate_content_for_agent(cls, args: dict, ctx) -> str:
        result = await cls.generate_review_content(
            ctx.db,
            uuid.UUID(args["node_id"]),
            ctx.user_id,
            review_type=args.get("review_type"),
        )
        return result["content"]
```

### 7.5 Celery Beat 定时任务

#### app/tasks/review_tasks.py

```python
import asyncio
import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task
def check_review_reminders():
    """
    定时检查到期复习计划并发送提醒。
    由Celery Beat每5分钟调用一次。
    """
    async def _run():
        from app.database import async_session_factory
        from app.services.review_service import ReviewService

        async with async_session_factory() as db:
            try:
                due_plans = await ReviewService.check_due_reviews(db)

                if not due_plans:
                    return

                logger.info("review_reminders", count=len(due_plans))

                # 通过WebSocket推送复习提醒
                from app.api.v1.websocket import manager
                for plan in due_plans:
                    await manager.broadcast_to_prefix(
                        f"user_{plan.user_id}",
                        {
                            "type": "review_reminder",
                            "data": {
                                "plan_id": str(plan.id),
                                "node_id": str(plan.node_id),
                                "priority": plan.priority,
                                "scheduled_at": plan.scheduled_at.isoformat(),
                            },
                        },
                    )

                # 如果有Tauri桌面端，发送系统通知
                # （通过HTTP回调通知Tauri客户端）
                logger.info("review_reminders_sent", count=len(due_plans))

            except Exception as e:
                logger.error("review_reminder_failed", error=str(e))

    asyncio.run(_run())
```

#### Celery Beat 配置

在 `app/tasks/celery_app.py` 中添加定时调度：

```python
from celery import Celery
from celery.schedules import crontab

celery_app = Celery("qingyunzhixue")

celery_app.conf.beat_schedule = {
    # 每5分钟检查到期复习
    "check-review-reminders": {
        "task": "app.tasks.review_tasks.check_review_reminders",
        "schedule": 300.0,  # 每300秒（5分钟）
    },
}

celery_app.conf.timezone = "Asia/Shanghai"
```

### 7.6 API 路由

#### app/api/v1/review.py

```python
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.review import (
    ReviewPlanSchema,
    ReviewCompleteRequest,
    ReviewContentRequest,
    ReviewContentResponse,
    ReviewStatsResponse,
    ReviewPlanListResponse,
)
from app.services.review_service import ReviewService

router = APIRouter(prefix="/review", tags=["复习系统"])


@router.get("/plans", response_model=ReviewPlanListResponse)
async def get_review_plans(
    status: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取复习计划列表"""
    items, total = await ReviewService.get_review_plans(
        db=db,
        user_id=current_user.id,
        status=status,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )
    return ReviewPlanListResponse(items=items, total=total)


@router.post("/plans/{plan_id}/complete")
async def complete_review(
    plan_id: uuid.UUID,
    data: ReviewCompleteRequest = ReviewCompleteRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    完成一次复习。
    使用SM-2算法重新计算下次复习时间。
    """
    return await ReviewService.complete_review(
        db=db,
        plan_id=plan_id,
        user_id=current_user.id,
        performance=data.performance,
        notes=data.notes,
    )


@router.post("/generate-content", response_model=ReviewContentResponse)
async def generate_review_content(
    data: ReviewContentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    为复习生成针对性内容。
    根据掌握度自动选择复习形式（闪卡/选择题/讲解），也可手动指定。
    """
    return await ReviewService.generate_review_content(
        db=db,
        node_id=data.node_id,
        user_id=current_user.id,
        review_type=data.review_type,
    )


@router.get("/stats", response_model=ReviewStatsResponse)
async def get_review_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取复习统计"""
    return await ReviewService.get_review_stats(db, current_user.id)
```

### 7.7 更新路由注册

更新 `app/api/v1/router.py`：

```python
from app.api.v1 import auth, notes, tags, learning, users, knowledge, qa, review

api_router.include_router(review.router)  # Sprint 7 新增
```

### 7.8 WebSocket 通知升级

更新 `/ws/notifications` 端点，支持按用户推送：

```python
@router.websocket("/ws/notifications")
async def ws_notifications(websocket: WebSocket):
    """系统通知推送（Sprint 7升级：支持按用户推送）"""
    user_id = await verify_ws_token(websocket)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    # 使用 user_{user_id} 作为client_id，支持按用户推送
    client_id = f"user_{user_id}"
    manager.active_connections[client_id] = websocket

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        logger.info("notifications_ws_disconnected", user_id=user_id)
    finally:
        manager.disconnect(client_id)
```

### 7.9 Sprint 7 验收标准

- [ ] `GET /api/v1/review/plans` 返回复习计划列表，支持按状态和日期筛选
- [ ] `POST /api/v1/review/plans/{id}/complete` 完成复习，SM-2算法正确计算下次复习时间
- [ ] SM-2算法：quality>=3时间隔递增，quality<3时重置为1天
- [ ] 完成复习后自动创建下一次复习计划
- [ ] `POST /api/v1/review/generate-content` 根据掌握度自动选择复习形式
- [ ] mastery>0.7 生成闪卡，0.4~0.7 生成选择题，<0.4 生成详细讲解
- [ ] `GET /api/v1/review/stats` 返回今日到期数、本周完成数、逾期数、掌握度分布
- [ ] Celery Beat 每5分钟检查到期复习计划
- [ ] 到期复习通过WebSocket推送复习提醒（type="review_reminder"）
- [ ] 复习提醒包含plan_id、node_id、priority、scheduled_at
- [ ] Agent工具接口 `get_review_plans` 和 `generate_review_content` 可正常调用
- [ ] 复习完成后 `user_knowledge_mastery` 表正确更新

---

## Phase 2 整体验收

完成全部3个Sprint后，以下端到端流程应全部跑通：

1. **知识图谱驱动学习路线**：创建学习路线→Celery异步调用LLM+知识图谱生成步骤→WebSocket推送完成→查看路线详情含步骤列表
2. **路线动态调整**：完成步骤→表现不佳自动添加补充练习→表现优秀自动合并步骤
3. **讲义生成升级**：触发讲义生成→RAG检索+知识图谱上下文→LLM生成讲义→WebSocket推送进度
4. **苏格拉底式答疑**：创建答疑会话→发送问题→AI通过提问引导（不直接给答案）→流式WebSocket输出→自动更新知识画像
5. **诊断性问题**：基于讲义生成诊断性问题→选择题+简答题混合→覆盖不同认知层次
6. **SM-2复习系统**：到期复习提醒→完成复习→SM-2计算下次复习→自动生成复习内容（闪卡/选择题/讲解）
7. **知识图谱API**：查看学科列表→查询节点→查看节点图结构→获取学习路径
8. **Agent工具**：所有服务暴露的Agent工具接口可正常调用

### 技术债记录（Phase 3解决）

- 知识图谱初始数据需手动导入公开教材数据，后续考虑自动化导入工具
- RAG管道Phase 2仍为单路向量检索，Phase 3 Sprint 8扩展混合检索+Reranker
- 多模型适配Phase 2仅DeepSeek，Phase 3 Sprint 9接入通义千问、Claude
- Agent编排模块Phase 2不实现，Phase 3 Sprint 10完成ReAct模式AgentLoop
- 复习内容生成Phase 2为单次LLM调用，Phase 3可考虑增加图片/公式渲染
- WebSocket连接管理Phase 2为单进程内存管理，Phase 3需引入Redis pub/sub支持多实例
