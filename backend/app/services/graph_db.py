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
        props_str = ", ".join(
            f'{k}: "{v}"' if isinstance(v, str) else f'{k}: {v}'
            for k, v in props.items()
        )
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
            f"MATCH (prereq:KnowledgePoint)-[:PREREQUISITE_OF]->"
            f"(target:KnowledgePoint {{id: '{node_id}'}}) "
            f"RETURN prereq"
        )
        return await GraphDB.execute_cypher(db, cypher, columns="prereq agtype")

    @staticmethod
    async def get_dependents(db: AsyncSession, node_id: str) -> list[dict]:
        """获取某节点的所有后续依赖节点"""
        cypher = (
            f"MATCH (source:KnowledgePoint {{id: '{node_id}'}})"
            f"-[:PREREQUISITE_OF]->(dep:KnowledgePoint) "
            f"RETURN dep"
        )
        return await GraphDB.execute_cypher(db, cypher, columns="dep agtype")

    @staticmethod
    async def get_related(db: AsyncSession, node_id: str) -> list[dict]:
        """获取某节点的关联节点"""
        cypher = (
            f"MATCH (source:KnowledgePoint {{id: '{node_id}'}})"
            f"-[:RELATED_TO]-(related:KnowledgePoint) "
            f"RETURN related"
        )
        return await GraphDB.execute_cypher(db, cypher, columns="related agtype")

    @staticmethod
    async def get_subtopics(db: AsyncSession, node_id: str) -> list[dict]:
        """获取某节点的子知识点"""
        cypher = (
            f"MATCH (parent:KnowledgePoint {{id: '{node_id}'}})"
            f"<-[:SUBTOPIC_OF]-(child:KnowledgePoint) "
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
            f"(start:KnowledgePoint {{id: '{source_id}'}})"
            f"-[*]->(target:KnowledgePoint {{id: '{target_id}'}})"
            f") "
            f"RETURN [node IN nodes(path) | properties(node)] AS node_list"
        )
        results = await GraphDB.execute_cypher(
            db, cypher, columns="node_list agtype"
        )
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
