import structlog

from app.tasks.celery_app import celery_app, run_async

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

                logger.info("review_reminders_sent", count=len(due_plans))

            except Exception as e:
                logger.error("review_reminder_failed", error=str(e))

    run_async(_run())
