import asyncio
from typing import Any, Coroutine

from celery import Celery
from celery.signals import worker_process_init

from app.config import settings

celery_app = Celery(
    "qingyun",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.learning_tasks",
        "app.tasks.review_tasks",
    ],
)


@worker_process_init.connect
def init_worker_process(**kwargs):
    """
    Celery worker 子进程初始化时重新创建异步数据库引擎。

    ForkPoolWorker 会继承父进程的 asyncpg 引擎，但引擎内部的事件循环
    在子进程中已损坏，导致 "Future attached to a different loop" 错误。
    此信号在子进程 fork 后、任务执行前触发，用于重新初始化引擎。
    """
    import app.database as db_module
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    # 关闭父进程继承的引擎（如果存在）
    if hasattr(db_module, 'engine'):
        try:
            # 同步关闭（在子进程中安全）
            db_module.engine.sync_engine.dispose()
        except Exception:
            pass

    # 重新创建引擎和会话工厂
    db_module.engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=10,
        pool_pre_ping=True,
        echo=settings.APP_DEBUG,
    )
    db_module.async_session_factory = async_sessionmaker(
        db_module.engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def run_async(coro: Coroutine) -> Any:
    """
    在 Celery ForkPoolWorker 中安全运行异步协程。

    直接调用 asyncio.run() 会因 ForkPoolWorker 继承了父进程的事件循环
    而引发 "Future attached to a different loop" 错误。
    本函数显式创建新的事件循环，避免与父进程循环冲突。
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
)

# Sprint 7: Celery Beat 定时调度
celery_app.conf.beat_schedule = {
    # 每5分钟检查到期复习计划并推送提醒
    "check-review-reminders": {
        "task": "app.tasks.review_tasks.check_review_reminders",
        "schedule": 300.0,  # 每300秒（5分钟）
    },
}
