import asyncio
from typing import Any, Coroutine

from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown

from app.config import settings

celery_app = Celery(
    "qingyun",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.learning_tasks",
        "app.tasks.review_tasks",
        "app.tasks.note_tasks",
    ],
)

# Worker 子进程级别的事件循环引用，整个子进程生命周期内复用
_worker_loop: asyncio.AbstractEventLoop | None = None


@worker_process_init.connect
def init_worker_process(**kwargs):
    """
    Celery worker 子进程初始化时重新创建异步资源。

    ForkPoolWorker 会继承父进程的异步对象（数据库引擎、LLM客户端等），
    但这些对象内部绑定到父进程的事件循环，在子进程中已损坏，
    导致 "Future attached to a different loop" 错误。
    此信号在子进程 fork 后、任务执行前触发，重新初始化所有异步资源。
    """
    global _worker_loop

    import app.database as db_module
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    # 关闭父进程继承的数据库引擎
    if hasattr(db_module, 'engine'):
        try:
            db_module.engine.sync_engine.dispose()
        except Exception:
            pass

    # 创建子进程专属事件循环并设置为当前，整个子进程生命周期内复用
    _worker_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_worker_loop)

    # 重新创建数据库引擎和会话工厂
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

    # 重置 LLM 客户端单例（其内部 AsyncOpenAI 绑定了父进程事件循环）
    import app.ai.llm_client as llm_module
    llm_module._llm_client = None


@worker_process_shutdown.connect
def shutdown_worker_process(**kwargs):
    """
    Worker 子进程关闭前优雅清理异步资源。

    必须先 dispose 数据库引擎（释放连接池中的连接），再关闭事件循环，
    否则 asyncpg 连接关闭时会尝试在已关闭的事件循环上创建 task，
    导致 RuntimeError: Event loop is closed。
    """
    global _worker_loop

    import app.database as db_module

    # 1. 先关闭数据库引擎——这会释放连接池中的所有连接
    if hasattr(db_module, 'engine') and _worker_loop is not None:
        try:
            _worker_loop.run_until_complete(db_module.engine.dispose())
        except Exception:
            pass

    # 2. 清理 LLM 客户端
    import app.ai.llm_client as llm_module
    if hasattr(llm_module, '_llm_client') and llm_module._llm_client is not None:
        try:
            _worker_loop.run_until_complete(llm_module._llm_client.close())
        except Exception:
            pass
        llm_module._llm_client = None

    # 3. 最后关闭事件循环
    if _worker_loop is not None:
        try:
            _worker_loop.close()
        except Exception:
            pass
        _worker_loop = None


def run_async(coro: Coroutine) -> Any:
    """
    在 Celery ForkPoolWorker 中安全运行异步协程。

    使用 worker_process_init 中创建的持久事件循环，整个子进程生命周期
    内复用同一个 loop，避免每次任务都创建/关闭 loop 导致连接池清理
    时遇到 "Event loop is closed" 错误。
    """
    global _worker_loop

    if _worker_loop is None:
        # 兜底：如果 worker_process_init 未执行（例如测试环境）
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)

    return _worker_loop.run_until_complete(coro)

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
