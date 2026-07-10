import structlog

from app.tasks.celery_app import celery_app, run_async

logger = structlog.get_logger()


@celery_app.task(bind=True, name="generate_lecture")
def generate_lecture_task(self, lecture_id: str, user_id: str, topic: str, node_name: str = "", difficulty: int = 3):
    """异步生成讲义"""
    return run_async(_generate_lecture(self, lecture_id, user_id, topic, node_name, difficulty))


async def _generate_lecture(self, lecture_id, user_id, topic, node_name, difficulty):
    import uuid

    from sqlalchemy import select

    from app.ai.llm_client import get_llm_client
    from app.ai.prompts.lecture import LECTURE_GENERATION_PROMPT
    from app.ai.rag.pipeline import RAGPipeline
    from app.ai.web_search.searcher import WebSearcher
    from app.database import async_session_factory
    from app.models.learning import Lecture

    logger.info("lecture_generation_started", lecture_id=lecture_id, topic=topic)

    async with async_session_factory() as db:
        try:
            # 1. RAG检索相关内容
            rag = RAGPipeline(db)
            context_results = await rag.retrieve(query=f"{topic} {node_name}", top_k=5)
            retrieved_context = "\n\n".join([r["content"][:500] for r in context_results])

            # 2. 网络搜索补充
            searcher = WebSearcher()
            web_results = await searcher.search(f"{topic} 教程", num_results=3)
            if web_results:
                retrieved_context += "\n\n## 网络参考\n"
                for r in web_results:
                    retrieved_context += f"- {r.title}: {r.snippet}\n"

            # 3. 构建Prompt
            prompt = LECTURE_GENERATION_PROMPT.format(
                topic=topic,
                node_name=node_name or topic,
                difficulty=difficulty,
                student_level="中等",
                retrieved_context=retrieved_context or "暂无参考材料，请基于你的知识生成。",
            )

            # 4. 调用LLM
            llm = get_llm_client()
            response = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4096,
            )

            # 5. 保存讲义
            result = await db.execute(select(Lecture).where(Lecture.id == uuid.UUID(lecture_id)))
            lecture = result.scalar_one_or_none()
            if lecture:
                lecture.content = response.content
                lecture.status = "generated"
                lecture.token_usage = response.usage.get("total_tokens", 0)
                await db.commit()

            logger.info("lecture_generation_completed", lecture_id=lecture_id)
            return {"lecture_id": lecture_id, "status": "generated", "token_usage": response.usage}

        except Exception as e:
            logger.error("lecture_generation_failed", lecture_id=lecture_id, error=str(e))
            # 更新状态为失败
            result = await db.execute(select(Lecture).where(Lecture.id == uuid.UUID(lecture_id)))
            lecture = result.scalar_one_or_none()
            if lecture:
                lecture.status = "failed"
                await db.commit()
            raise


@celery_app.task(bind=True, name="generate_personalized_summary")
def generate_personalized_summary_task(self, lecture_id: str, prompt: str):
    """异步生成个性化知识梳理"""
    return run_async(_generate_summary(self, lecture_id, prompt))


async def _generate_summary(self, lecture_id, prompt):
    import uuid

    from sqlalchemy import select

    from app.ai.llm_client import get_llm_client
    from app.database import async_session_factory
    from app.models.learning import Lecture

    async with async_session_factory() as db:
        try:
            llm = get_llm_client()
            response = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=4096,
            )

            result = await db.execute(select(Lecture).where(Lecture.id == uuid.UUID(lecture_id)))
            lecture = result.scalar_one_or_none()
            if lecture:
                lecture.content = response.content
                lecture.status = "personalized"
                lecture.token_usage = response.usage.get("total_tokens", 0)
                await db.commit()

            return {"lecture_id": lecture_id, "status": "personalized"}
        except Exception as e:
            logger.error("personalized_summary_failed", lecture_id=lecture_id, error=str(e))
            raise
