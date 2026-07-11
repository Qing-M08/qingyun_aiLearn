from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.config import settings
from app.core.exceptions import AppException, app_exception_handler, validation_exception_handler
from app.core.middleware import setup_middlewares
from app.database import close_db

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    logger.info("application_starting", app_name=settings.APP_NAME)
    # 初始化Meilisearch索引
    try:
        from app.services.search_service import init_meilisearch_indexes, sync_all_to_meilisearch
        await init_meilisearch_indexes()
        # 启动时全量同步一次，确保索引与数据库一致
        await sync_all_to_meilisearch()
    except Exception as e:
        logger.warning("meilisearch_init_failed", error=str(e))
    yield
    # 关闭
    await close_db()
    logger.info("application_shutdown")


app = FastAPI(
    title="青云智学 API",
    description="AI驱动的全流程学习辅助软件后端",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,  # 禁用默认docs，使用本地静态文件
)

# 挂载本地 Swagger UI 静态文件，解决国内 CDN 不通的问题
_static_dir = Path(__file__).parent / "static" / "swagger"
if _static_dir.exists():
    app.mount("/static/swagger", StaticFiles(directory=str(_static_dir)), name="swagger-static")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html() -> HTMLResponse:
    """使用本地静态 Swagger UI 资源"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_js_url="/static/swagger/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger/swagger-ui.css",
    )

# 注册异常处理器
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(AppException, app_exception_handler)

# 中间件
setup_middlewares(app)

# 路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}
