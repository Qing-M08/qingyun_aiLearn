import json
import uuid

import redis.asyncio as redis
import redis as sync_redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import structlog

from app.config import settings
from app.core.security import decode_token

logger = structlog.get_logger()

router = APIRouter()

# 同步 Redis 客户端（用于 PUBLISH 操作，避免跨 event loop 冲突）
# 异步 redis.asyncio 客户端会绑定到创建时的 event loop，
# 而 Celery worker 每次任务都创建新 loop，旧 loop 关闭后连接不可用。
# 同步客户端不依赖 event loop，可安全在任意进程/线程中使用。
_sync_redis = sync_redis.Redis.from_url(
    settings.REDIS_URL.replace("/0", "/3"), decode_responses=True
)


def publish_lecture_progress(lecture_id: str, data: dict):
    """
    发布讲义进度消息到 Redis Pub/Sub 频道（同步，跨进程安全）。

    使用同步 Redis 客户端避免 Celery worker 中的 event loop 冲突：
    Celery 每次任务创建新 event loop 并在完成后关闭，
    redis.asyncio 客户端缓存的连接会绑定到已关闭的 loop 导致 RuntimeError。
    """
    _sync_redis.publish(f"lecture_progress:{lecture_id}", json.dumps(data))


class ConnectionManager:
    """WebSocket连接管理器（Sprint 5升级）"""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)

    async def send_json(self, client_id: str, data: dict):
        """向指定连接发送消息"""
        ws = self.active_connections.get(client_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(client_id)

    async def broadcast_to_prefix(self, prefix: str, data: dict):
        """向所有匹配前缀的连接广播消息"""
        for cid, ws in list(self.active_connections.items()):
            if cid.startswith(prefix):
                try:
                    await ws.send_json(data)
                except Exception:
                    self.disconnect(cid)


manager = ConnectionManager()


async def verify_ws_token(websocket: WebSocket) -> str | None:
    """从WebSocket首条消息或URL参数中验证token"""
    token = websocket.query_params.get("token")
    if not token:
        return None
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except Exception:
        return None


@router.websocket("/ws/lecture-progress/{lecture_id}")
async def ws_lecture_progress(websocket: WebSocket, lecture_id: str):
    """
    讲义生成进度推送（Sprint 8 升级：使用 Redis Pub/Sub 跨进程通信）。
    Celery worker 通过 Redis 发布进度，WebSocket 订阅并转发给前端。
    """
    await websocket.accept()
    client_id = f"lecture_{lecture_id}"

    # 注册到连接管理器
    manager.active_connections[client_id] = websocket

    # 订阅 Redis Pub/Sub 频道（每次连接创建新的 async Redis 客户端，避免 event loop 冲突）
    async_redis = redis.Redis.from_url(
        settings.REDIS_URL.replace("/0", "/3"), decode_responses=True
    )
    pubsub = async_redis.pubsub()
    await pubsub.subscribe(f"lecture_progress:{lecture_id}")

    try:
        await websocket.send_json({
            "type": "progress",
            "data": {"stage": "connecting", "percent": 0},
        })

        # 监听 Redis 频道消息并转发到 WebSocket
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)
                # 收到 complete 或 error 消息后停止监听
                if data.get("type") in ("complete", "error"):
                    break
    except WebSocketDisconnect:
        logger.info("lecture_progress_ws_disconnected", lecture_id=lecture_id)
    finally:
        await pubsub.unsubscribe(f"lecture_progress:{lecture_id}")
        manager.disconnect(client_id)


@router.websocket("/ws/route-progress/{route_id}")
async def ws_route_progress(websocket: WebSocket, route_id: str):
    """
    学习路线生成进度推送。
    注册到连接管理器，由 Celery 任务完成后直接推送结果。
    """
    await websocket.accept()
    client_id = f"route_{route_id}"

    # 注册到连接管理器
    manager.active_connections[client_id] = websocket

    try:
        await websocket.send_json({
            "type": "progress",
            "data": {"stage": "generating", "percent": 0},
        })
        # 保持连接，等待关闭
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        logger.info("route_progress_ws_disconnected", route_id=route_id)
    finally:
        manager.disconnect(client_id)


@router.websocket("/ws/notifications")
async def ws_notifications(websocket: WebSocket):
    """
    系统通知推送（Sprint 7升级：支持按用户推送）。
    使用 user_{user_id} 作为client_id，支持按用户推送复习提醒等。
    """
    user_id = await verify_ws_token(websocket)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    # 使用 user_{user_id} 作为client_id，支持按用户推送
    client_id = f"user_{user_id}"
    manager.active_connections[client_id] = websocket

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        logger.info("notifications_ws_disconnected", user_id=user_id)
    finally:
        manager.disconnect(client_id)


@router.websocket("/ws/qa-stream/{session_id}")
async def ws_qa_stream(websocket: WebSocket, session_id: str):
    """
    答疑对话流式输出（Sprint 6）。
    客户端发送用户消息，服务端流式返回AI回复。
    """
    # 验证token
    user_id = await verify_ws_token(websocket)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    client_id = f"qa_{session_id}"
    manager.active_connections[client_id] = websocket

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "message":
                content = data.get("data", {}).get("content", "")
                if not content:
                    await websocket.send_json({
                        "type": "error",
                        "data": {"message": "消息内容不能为空"},
                    })
                    continue

                # 异步处理消息（流式输出）
                from app.database import async_session_factory
                from app.services.qa_service import QAService

                async with async_session_factory() as db:
                    try:
                        await QAService.handle_message_stream(
                            db=db,
                            session_id=uuid.UUID(session_id),
                            user_id=uuid.UUID(user_id),
                            content=content,
                            ws_manager=manager,
                        )
                    except Exception as e:
                        logger.error("qa_ws_error", error=str(e))
                        await websocket.send_json({
                            "type": "error",
                            "data": {"message": str(e)},
                        })

            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("qa_stream_disconnected", session_id=session_id)
    finally:
        manager.disconnect(client_id)


@router.websocket("/ws/organize-progress/{task_id}")
async def organize_progress_ws(
    websocket: WebSocket,
    task_id: str,
    token: str = Query(...),
):
    """AI 整理笔记进度 WebSocket（Sprint 9）

    客户端连接后订阅 Redis Pub/Sub 频道 organize_progress:{task_id}，
    实时接收 Celery 任务推送的进度消息。

    消息格式:
    {
        "stage": "preparing" | "generating" | "complete" | "error",
        "percent": 0-100,
        "message": "进度描述",
        "note_id": "成果笔记 ID（仅 complete 时）",
        "title": "笔记标题（仅 complete 时）",
        "word_count": 字数（仅 complete 时）,
        "source_count": 源笔记数（仅 complete 时）,
        "error": "错误信息（仅 error 时）"
    }
    """
    # Token 验证：先 accept，验证失败再 close
    await websocket.accept()
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=4001, reason="Token verification failed")
        return

    # 订阅 Redis Pub/Sub
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL, decode_responses=True
    )
    pubsub = redis_client.pubsub()
    channel = f"organize_progress:{task_id}"

    try:
        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)

                # 完成或失败时关闭连接
                if data.get("stage") in ("complete", "error"):
                    break

    except WebSocketDisconnect:
        logger.info("organize_progress_ws_disconnected", task_id=task_id)
    except Exception as e:
        logger.error("organize_progress_ws_error", task_id=task_id, error=str(e))
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await redis_client.close()
        except Exception:
            pass


@router.websocket("/ws/organize-from-chat/{task_id}")
async def organize_from_chat_progress_ws(
    websocket: WebSocket,
    task_id: str,
    token: str = Query(...),
):
    """整理到笔记进度 WebSocket（Sprint 10）

    客户端连接后订阅 Redis Pub/Sub 频道 organize_from_chat_progress:{task_id}，
    实时接收 Celery 任务推送的进度消息。

    前端连接路径: /api/v1/ws/organize-from-chat/{task_id}?token={access_token}
    """
    # Token 验证：先 accept，验证失败再 close
    await websocket.accept()
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=4001, reason="Token verification failed")
        return

    # 订阅 Redis Pub/Sub（使用 DB 3，与 Celery 发布端一致）
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL.replace("/0", "/3"), decode_responses=True
    )
    pubsub = redis_client.pubsub()
    channel = f"organize_from_chat_progress:{task_id}"

    try:
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)
                # 完成或失败时关闭连接
                if data.get("stage") in ("complete", "error"):
                    break
    except WebSocketDisconnect:
        logger.info("organize_from_chat_progress_ws_disconnected", task_id=task_id)
    except Exception as e:
        logger.error("organize_from_chat_progress_ws_error", task_id=task_id, error=str(e))
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await redis_client.close()
        except Exception:
            pass
