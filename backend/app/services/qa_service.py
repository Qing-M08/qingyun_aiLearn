import json
import re
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
            ai_content = response.content
        except Exception as e:
            logger.error("qa_llm_failed", error=str(e))
            ai_content = "抱歉，我暂时无法回答。请稍后再试。"

        # 保存AI回复
        assistant_msg = QAMessage(
            session_id=session_id,
            role="assistant",
            content=ai_content,
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
                    db, user_id, content, ai_content, uuid.UUID(context["node_id"])
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

            score_response = await llm.chat(
                messages=[{"role": "user", "content": eval_prompt}],
                temperature=0.1,
                max_tokens=10,
            )
            score_text = score_response.content

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
        """为讲义生成诊断性问题"""
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
            response_text = response.content

            # 解析JSON
            try:
                data = json.loads(response_text)
                return data.get("questions", [])
            except json.JSONDecodeError:
                # 尝试从文本中提取JSON
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                        return data.get("questions", [])
                    except json.JSONDecodeError:
                        pass

            logger.warning("diagnosis_parse_failed", response_preview=response_text[:200])
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
            before_result = await db.execute(
                select(QAMessage.created_at).where(QAMessage.id == before)
            )
            before_time = before_result.scalar()
            if before_time:
                query = query.where(QAMessage.created_at < before_time)

        result = await db.execute(query)
        messages = list(result.scalars().all())
        return list(reversed(messages))  # 按时间正序返回
