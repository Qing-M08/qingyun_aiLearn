import uuid
import structlog

from app.tasks.celery_app import celery_app, run_async

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
        # 在子进程中重新初始化数据库引擎，避免事件循环冲突
        import app.database as db_module
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from app.config import settings

        db_module.engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )
        db_module.async_session_factory = async_sessionmaker(
            db_module.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

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

    run_async(_run())


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def generate_lecture_content_task(
    self,
    lecture_id: str,
    user_id: str,
    node_id: str | None = None,
    route_id: str | None = None,
    step_id: str | None = None,
    custom_instructions: str | None = None,
):
    """异步生成讲义内容（升级版，使用知识图谱上下文）"""
    async def _run():
        # 在子进程中重新初始化数据库引擎
        import app.database as db_module
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from app.config import settings

        logger.info("lecture_task_started", lecture_id=lecture_id, node_id=node_id, route_id=route_id, step_id=step_id)

        db_module.engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )
        db_module.async_session_factory = async_sessionmaker(
            db_module.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        from app.database import async_session_factory
        from app.services.learning_service import LearningService

        async with async_session_factory() as db:
            try:
                await LearningService.generate_lecture_content(
                    db=db,
                    lecture_id=uuid.UUID(lecture_id),
                    user_id=uuid.UUID(user_id),
                    node_id=uuid.UUID(node_id) if node_id else None,
                    route_id=uuid.UUID(route_id) if route_id else None,
                    step_id=uuid.UUID(step_id) if step_id else None,
                    custom_instructions=custom_instructions,
                )
            except Exception as exc:
                logger.error("generate_lecture_content_task_failed", lecture_id=lecture_id, error=str(exc))
                raise

    run_async(_run())
