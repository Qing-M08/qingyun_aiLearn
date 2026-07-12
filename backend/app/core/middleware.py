import os
import time
import uuid

import structlog
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

logger = structlog.get_logger()


def _parse_cors_origins() -> list[str]:
    """
    解析 CORS 允许的来源列表。

    优先级：CORS_ORIGINS 环境变量 > 默认 "*"
    生产环境应配置为前端 EXE 的实际协议来源，如：
      - Electron: "app://.,file://"
      - Tauri:    "tauri://localhost,https://tauri.localhost"
      - Web:      "https://your-domain.com"
    多个来源用逗号分隔。
    """
    raw = os.getenv("CORS_ORIGINS", "*")
    return [o.strip() for o in raw.split(",") if o.strip()]


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # BaseHTTPMiddleware 与 WebSocket 不兼容，直接放行
        if request.scope["type"] == "websocket":
            return await call_next(request)

        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        structlog.contextvars.bind_contextvars(request_id=request_id)

        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )

        response.headers["X-Request-ID"] = request_id
        structlog.contextvars.clear_contextvars()
        return response


def setup_middlewares(app: FastAPI):
    origins = _parse_cors_origins()
    logger.info("cors_configured", origins=origins if origins != ["*"] else "* (all)")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
