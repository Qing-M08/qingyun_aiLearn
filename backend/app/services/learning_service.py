import json
import re
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.models.learning import LearningRoute, LearningRouteStep, Lecture, LearningRecord
from app.models.knowledge import KnowledgeNode, KnowledgeEdge, UserKnowledgeMastery
from app.models.note import Note
from app.services.knowledge_service import KnowledgeService, SUBJECT_DISPLAY_NAMES
from app.services.note_service import NoteService
from app.services.graph_db import GraphDB
from app.ai.llm_client import get_llm_client
from app.ai.prompts.route import ROUTE_GENERATION_PROMPT
from app.core.exceptions import NotFoundException, BadRequestException

logger = structlog.get_logger()


class LearningService:

    @classmethod
    def as_tools(cls) -> list:
        """暴露学习相关工具供 Agent 调用"""
        from app.services.agent.tool_schemas import ToolParameter, ToolSchema
        return [
            ToolSchema(
                name="search_knowledge",
                display_name="搜索知识图谱",
                description="按关键词搜索知识图谱中的知识点，返回名称、学科和描述",
                parameters={
                    "query": ToolParameter(type="string", description="搜索关键词"),
                    "subject": ToolParameter(type="string", description="学科筛选", required=False),
                    "limit": ToolParameter(type="integer", description="返回数量", required=False, default=5),
                },
                category="read",
                module="learning",
                icon="apartment",
            ),
            ToolSchema(
                name="get_mastery",
                display_name="查询掌握度",
                description="查询用户对指定知识点的掌握度分数",
                parameters={
                    "node_name": ToolParameter(type="string", description="知识点名称"),
                },
                category="read",
                module="learning",
                icon="dashboard",
            ),
            ToolSchema(
                name="get_route_progress",
                display_name="查看学习路线进度",
                description="获取用户当前学习路线的进度概况",
                parameters={
                    "topic": ToolParameter(type="string", description="路线主题（可选，不传则返回所有进行中路线）", required=False),
                },
                category="read",
                module="learning",
                icon="flag",
            ),
        ]

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
        # 注意：先 try dispatch，失败时标记路线为 failed 而非回滚事务
        try:
            from app.tasks.learning_tasks import generate_learning_route
            generate_learning_route.delay(
                str(route.id), str(user_id), topic,
                goal=goal,
                available_hours=available_hours,
                current_level=current_level,
            )
        except Exception as dispatch_error:
            logger.error(
                "celery_dispatch_failed",
                route_id=str(route.id),
                error=str(dispatch_error),
            )
            # Celery broker 不可达时，标记路线为失败，让用户稍后重试
            route.status = "failed"
            route.metadata_["error"] = f"异步任务调度失败: {str(dispatch_error)}"
            await db.flush()

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

        # 2. 推断学科
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
            # Cypher查询失败会污染PostgreSQL事务状态，必须先回滚才能执行后续查询
            await db.rollback()
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
            route_data = LearningService._parse_route_response(response.content)

            # 7. 更新路线记录
            route_result = await db.execute(
                select(LearningRoute).where(LearningRoute.id == route_id)
            )
            route = route_result.scalar_one()
            route.description = route_data.get("description", "")
            route.estimated_hours = route_data.get("estimated_total_hours", available_hours)
            route.status = "active"

            # 8. 创建步骤（先创建，后回填 prerequisites）
            # LLM 返回的 prerequisite_step_orders 是整数序号，需要映射为实际步骤 UUID
            created_steps = []  # (step_order, step_obj, prerequisite_orders)
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
                    prerequisites=[],  # 先留空，后面回填
                )
                db.add(step)
                created_steps.append((
                    step_data["order"],
                    step,
                    step_data.get("prerequisite_step_orders", []),
                ))

            # 9. flush 生成步骤 ID，然后回填 prerequisites
            await db.flush()
            order_to_id = {order: step.id for order, step, _ in created_steps}
            for order, step, prereq_orders in created_steps:
                step.prerequisites = [
                    order_to_id[po] for po in prereq_orders if po in order_to_id
                ]

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
            # 事务可能已被污染，必须先回滚才能执行更新
            await db.rollback()
            # 标记为失败
            result = await db.execute(
                select(LearningRoute).where(LearningRoute.id == route_id)
            )
            route = result.scalar_one_or_none()
            if route:
                route.status = "failed"
                route.metadata_ = {**(route.metadata_ or {}), "error": str(e)}
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
        return route

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
        返回：更新后的步骤 + 下一步骤建议
        """
        route = await LearningService.get_route(db, route_id, user_id)

        # 查找步骤
        step = None
        for s in route.steps:
            if s.id == step_id:
                step = s
                break
        if not step:
            raise NotFoundException("步骤不存在")

        # 标记完成
        step.status = "completed"
        route.current_step = step.step_order

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
            ratio = duration_seconds / (step.estimated_minutes * 60)
            if ratio > 2.0:
                performance = 0.5
            elif ratio < 0.5:
                performance = 0.95

        next_step_suggestion = None
        if performance < 0.6:
            next_step_suggestion = await LearningService._adjust_for_struggling(
                db, route, step
            )
        elif performance > 0.9:
            next_step_suggestion = await LearningService._adjust_for_excelling(
                db, route, step
            )

        # 获取下一步骤
        next_steps = [
            s for s in route.steps
            if s.step_order > step.step_order and s.status == "pending"
        ]
        next_step = next_steps[0] if next_steps else None

        await db.commit()

        return {
            "step": step,
            "next_step": next_step,
            "next_step_suggestion": next_step_suggestion,
            "route_status": route.status,
        }

    @staticmethod
    async def _adjust_for_struggling(
        db: AsyncSession, route: LearningRoute, current_step: LearningRouteStep
    ) -> str:
        """表现不佳时调整路线：增加补充练习"""
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
        upcoming = [
            s for s in route.steps
            if s.step_order > current_step.step_order and s.status == "pending"
        ]
        if len(upcoming) >= 2:
            first = upcoming[0]
            second = upcoming[1]
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
        # 设置默认标题：讲义 - {知识节点名称}
        if not title and node_id:
            try:
                node = await KnowledgeService.get_node(db, node_id)
                title = f"讲义 - {node.name}"
            except Exception:
                title = "未命名讲义"
        elif not title:
            title = "未命名讲义"

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
        try:
            from app.tasks.learning_tasks import generate_lecture_content_task
            generate_lecture_content_task.delay(
                str(lecture.id), str(user_id),
                str(node_id) if node_id else None,
                route_id=str(route_id) if route_id else None,
                step_id=str(step_id) if step_id else None,
                custom_instructions=custom_instructions,
            )
        except Exception as dispatch_error:
            logger.error(
                "lecture_celery_dispatch_failed",
                lecture_id=str(lecture.id),
                error=str(dispatch_error),
            )
            lecture.status = "failed"
            await db.flush()

        return lecture

    @staticmethod
    async def generate_lecture_content(
        db: AsyncSession,
        lecture_id: uuid.UUID,
        user_id: uuid.UUID,
        node_id: uuid.UUID | None = None,
        route_id: uuid.UUID | None = None,
        step_id: uuid.UUID | None = None,
        custom_instructions: str | None = None,
    ) -> Lecture:
        """
        生成讲义内容（由Celery任务调用）。
        使用知识图谱上下文 + RAG检索 + LLM生成讲义。
        """
        from app.ai.prompts.lecture import LECTURE_GENERATION_PROMPT

        logger.info("lecture_generation_started", lecture_id=str(lecture_id),
                     node_id=str(node_id) if node_id else None,
                     route_id=str(route_id) if route_id else None,
                     step_id=str(step_id) if step_id else None)

        # 推送初始进度
        from app.api.v1.websocket import publish_lecture_progress
        publish_lecture_progress(
            str(lecture_id),
            {"type": "progress", "data": {"stage": "preparing_context", "percent": 10}},
        )

        # 1. 获取路线主题
        route_topic = "通用主题"
        if route_id:
            try:
                route_result = await db.execute(
                    select(LearningRoute).where(LearningRoute.id == route_id)
                )
                route = route_result.scalar_one_or_none()
                if route:
                    route_topic = route.topic
            except Exception as e:
                logger.warning("route_lookup_failed", error=str(e))

        # 2. 获取步骤上下文
        step_title = ""
        step_description = ""
        if step_id:
            try:
                step_result = await db.execute(
                    select(LearningRouteStep).where(LearningRouteStep.id == step_id)
                )
                step = step_result.scalar_one_or_none()
                if step:
                    step_title = step.title or ""
                    step_description = step.description or ""
            except Exception as e:
                logger.warning("step_lookup_failed", error=str(e))

        # 3. 获取知识节点信息
        node_name = ""
        node_description = ""
        node_difficulty = 3
        if node_id:
            try:
                node = await KnowledgeService.get_node(db, node_id)
                node_name = node.name
                node_description = node.description or ""
                node_difficulty = node.difficulty or 3
            except Exception as e:
                logger.warning("node_context_failed", error=str(e))

        # 4. 获取前置依赖节点
        prereqs_text = "无"
        if node_id:
            try:
                prereqs = await GraphDB.get_prerequisites(db, str(node_id))
                if prereqs:
                    prereq_names = []
                    for p in prereqs:
                        for k, v in p.items():
                            if isinstance(v, dict) and "name" in v:
                                prereq_names.append(v["name"])
                    if prereq_names:
                        prereqs_text = "、".join(prereq_names)
            except Exception as e:
                logger.warning("prereq_lookup_failed", error=str(e))
                await db.rollback()

        # 5. 获取用户水平
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

        # 6. RAG检索 + 网络搜索获取参考材料
        retrieved_context = ""
        search_query = f"{route_topic} {node_name}" if node_name else route_topic
        try:
            from app.ai.rag.pipeline import RAGPipeline
            rag = RAGPipeline(db)
            context_results = await rag.retrieve(query=search_query, top_k=5)
            if context_results:
                retrieved_context = "\n\n".join([r["content"][:500] for r in context_results])
        except Exception as e:
            logger.warning("rag_retrieval_failed", error=str(e))

        try:
            from app.ai.web_search.searcher import WebSearcher
            searcher = WebSearcher()
            web_results = await searcher.search(f"{search_query} 教程", num_results=3)
            if web_results:
                retrieved_context += "\n\n## 网络参考\n"
                for r in web_results:
                    retrieved_context += f"- {r.title}: {r.snippet}\n"
        except Exception as e:
            logger.warning("web_search_failed", error=str(e))

        # 合并用户自定义指令
        if custom_instructions:
            retrieved_context += f"\n\n## 用户额外要求\n{custom_instructions}"

        if not retrieved_context:
            retrieved_context = "暂无参考材料，请基于你的知识生成。"

        # 7. 构建Prompt
        prompt = LECTURE_GENERATION_PROMPT.format(
            topic=route_topic,
            step_title=step_title or "（无特定步骤）",
            step_description=step_description or "（无特定步骤描述）",
            node_name=node_name or route_topic,
            node_description=node_description or "（无详细描述）",
            difficulty=node_difficulty,
            student_level=user_level,
            prerequisites=prereqs_text,
            retrieved_context=retrieved_context,
        )

        # 8. 调用LLM生成
        try:
            llm = get_llm_client()

            # 推送进度（使用 Redis Pub/Sub 跨进程通信）
            from app.api.v1.websocket import publish_lecture_progress
            publish_lecture_progress(
                str(lecture_id),
                {"type": "progress", "data": {"stage": "generating_content", "percent": 30}},
            )

            logger.info("lecture_llm_call_started", lecture_id=str(lecture_id))
            response = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=6000,
            )
            logger.info("lecture_llm_call_completed", lecture_id=str(lecture_id))

            publish_lecture_progress(
                str(lecture_id),
                {"type": "progress", "data": {"stage": "finalizing", "percent": 80}},
            )

            # 9. 更新讲义
            result = await db.execute(
                select(Lecture).where(Lecture.id == lecture_id)
            )
            lecture = result.scalar_one()
            lecture.content = response.content
            lecture.status = "generated"
            lecture.token_usage = response.usage.get("total_tokens", 0)

            # === 新增：自动创建笔记 ===
            try:
                note = await LearningService._create_note_from_lecture(db, lecture)
                lecture.note_id = note.id
                logger.info("note_auto_created_for_lecture",
                             lecture_id=str(lecture_id), note_id=note.id)
            except Exception as e:
                logger.warning("failed_to_create_note_for_lecture",
                               lecture_id=str(lecture_id), error=str(e))
                # 笔记创建失败不阻塞讲义生成

            await db.commit()
            await db.refresh(lecture)

            # 序列化 lecture 对象（包含 note_id），前端据此跳转笔记页
            from app.schemas.learning import LectureSchema
            lecture_data = LectureSchema.model_validate(lecture).model_dump(mode="json")
            publish_lecture_progress(
                str(lecture_id),
                {
                    "type": "complete",
                    "data": {
                        "lecture": lecture_data,
                        "note_id": str(lecture.note_id) if lecture.note_id else None,
                    },
                },
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
            # 推送错误消息
            try:
                from app.api.v1.websocket import publish_lecture_progress
                publish_lecture_progress(
                    str(lecture_id),
                    {"type": "error", "data": {"message": str(e)}},
                )
            except Exception:
                pass
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

    @staticmethod
    async def _create_note_from_lecture(
        db: AsyncSession, lecture: Lecture
    ) -> Note:
        """从讲义创建笔记，并打上知识节点+学科标签"""
        # 获取路线所属用户
        route = await db.get(LearningRoute, lecture.route_id) if lecture.route_id else None
        user_id = route.user_id if route else lecture.user_id

        # 笔记标题 = 讲义标题
        title = lecture.title or "未命名讲义"

        # 创建笔记
        note = await NoteService.create_note(
            db, user_id,
            title=title,
            content=lecture.content,
        )

        # 自动标签：知识节点名称 + 学科中文名
        tag_names = []
        if lecture.node_id:
            node = await db.get(KnowledgeNode, lecture.node_id)
            if node:
                tag_names.append(node.name)
                if node.subject:
                    subject_display = SUBJECT_DISPLAY_NAMES.get(node.subject, node.subject)
                    tag_names.append(subject_display)

        for tag_name in tag_names:
            tag = await NoteService.get_or_create_tag(db, tag_name, user_id=user_id)
            await NoteService.add_tag_to_note(db, note.id, tag.id)

        return note

    # ==================== 路线删除 ====================

    @staticmethod
    async def delete_route(
        db: AsyncSession, route_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """
        删除单条学习路线（级联删除 steps + 清理关联讲义）。
        返回 True 表示删除成功，False 表示路线不存在。
        """
        result = await db.execute(
            select(LearningRoute).where(
                LearningRoute.id == route_id,
                LearningRoute.user_id == user_id,
            )
        )
        route = result.scalar_one_or_none()
        if not route:
            return False
        # 清理关联讲义及其 Meilisearch 索引
        await LearningService._delete_route_lectures(db, route_id)
        await db.delete(route)
        await db.commit()
        logger.info("route_deleted", route_id=str(route_id), user_id=str(user_id))
        return True

    @staticmethod
    async def batch_delete_routes(
        db: AsyncSession, route_ids: list[uuid.UUID], user_id: uuid.UUID
    ) -> dict:
        """
        批量删除学习路线，允许部分成功。
        返回 {"deleted_count": int, "failed_ids": [{"id": uuid, "reason": str}, ...]}
        """
        deleted_count = 0
        failed_ids = []

        for rid in route_ids:
            result = await db.execute(
                select(LearningRoute).where(
                    LearningRoute.id == rid,
                    LearningRoute.user_id == user_id,
                )
            )
            route = result.scalar_one_or_none()
            if not route:
                failed_ids.append({"id": rid, "reason": "ROUTE_NOT_FOUND"})
                continue
            # 清理关联讲义
            await LearningService._delete_route_lectures(db, rid)
            await db.delete(route)
            deleted_count += 1

        await db.commit()
        logger.info(
            "routes_batch_deleted",
            deleted_count=deleted_count,
            failed_count=len(failed_ids),
            user_id=str(user_id),
        )
        return {"deleted_count": deleted_count, "failed_ids": failed_ids}

    @staticmethod
    async def _delete_route_lectures(db: AsyncSession, route_id: uuid.UUID):
        """删除路线关联的所有讲义及其 Meilisearch 索引"""
        try:
            lecture_result = await db.execute(
                select(Lecture).where(Lecture.route_id == route_id)
            )
            lectures = lecture_result.scalars().all()
            for lecture in lectures:
                try:
                    from app.services.search_service import get_meilisearch_client
                    client = get_meilisearch_client()
                    client.index("lectures").delete_document(str(lecture.id))
                except Exception as e:
                    logger.warning("meilisearch_lecture_delete_failed",
                                 lecture_id=str(lecture.id), error=str(e))
                await db.delete(lecture)
            if lectures:
                logger.info("route_lectures_deleted",
                           route_id=str(route_id), count=len(lectures))
        except Exception as e:
            logger.warning("route_lecture_cleanup_failed",
                         route_id=str(route_id), error=str(e))
