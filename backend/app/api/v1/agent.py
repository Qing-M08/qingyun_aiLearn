import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.api.deps import get_current_user
from app.config import settings
from app.core.cancel_token import clear_cancel_token, set_cancel_token
from app.core.security import decode_token
from app.database import async_session_factory, get_db
from app.models.user import User
from app.schemas.agent import (
    AgentMessageResponse,
    AgentSessionResponse,
    BatchDeleteSessionsRequest,
    BatchDeleteSessionsResponse,
    CreateAgentSessionRequest,
    SendMessageRequest,
    SendMessageResponse,
    ToolDefinitionResponse,
)
from app.services.agent.agent_loop import AgentLoop
from app.services.agent.agent_service import AgentService
from app.services.agent.tool_registry import init_tool_registry

logger = structlog.get_logger()
router = APIRouter(prefix="/agent", tags=["Agent"])
ws_router = APIRouter(tags=["Agent"])


# ---- 会话管理 ----

@router.post("/sessions", status_code=201)
async def create_session(
    request: CreateAgentSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建 Agent 会话"""
    service = AgentService(db)
    session = await service.create_session(
        user_id=str(user.id),
        context_type=request.context_type,
        context_id=request.context_id,
        initial_message=request.initial_message,
    )
    return {"data": AgentSessionResponse.model_validate(session)}


@router.get("/sessions")
async def list_sessions(
    status: str | None = None,
    visibility: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取会话列表

    Args:
        visibility: 可选筛选。'visible' 只返回普通会话，'hidden' 只返回隐藏会话，
                    不传则返回所有会话（默认行为，向后兼容）。
    """
    service = AgentService(db)
    sessions, total = await service.list_sessions(
        user_id=str(user.id),
        status=status,
        visibility=visibility,
        page=page,
        page_size=page_size,
    )
    return {
        "data": {
            "items": [AgentSessionResponse.model_validate(s) for s in sessions],
            "total": total,
        }
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取会话详情"""
    service = AgentService(db)
    session = await service.get_session(session_id, str(user.id))
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"data": AgentSessionResponse.model_validate(session)}


@router.post("/sessions/{session_id}/close")
async def close_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """关闭会话"""
    service = AgentService(db)
    session = await service.close_session(session_id, str(user.id))
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"data": AgentSessionResponse.model_validate(session)}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除单个会话（级联删除消息）"""
    service = AgentService(db)
    success = await service.delete_session(session_id, str(user.id))
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"data": {"deleted": True}}


@router.post("/sessions/batch-delete")
async def batch_delete_sessions(
    request: BatchDeleteSessionsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    批量删除会话（级联删除消息）。
    支持部分成功：返回成功删除的数量和失败的 ID 列表。
    """
    service = AgentService(db)
    deleted_count, failed_ids = await service.batch_delete_sessions(
        session_ids=request.session_ids,
        user_id=str(user.id),
    )
    return {
        "data": BatchDeleteSessionsResponse(
            deleted_count=deleted_count,
            failed_ids=failed_ids,
        ).model_dump()
    }


# ---- 消息管理 ----

@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发送消息（HTTP 非流式）"""
    from app.ai.llm_client import get_llm_client

    service = AgentService(db)

    # 校验会话
    session = await service.get_session(session_id, str(user.id))
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.status == "closed":
        raise HTTPException(status_code=400, detail="会话已关闭")

    # 清除取消令牌
    await clear_cancel_token(session_id)

    # 保存用户消息
    user_msg = await service.save_user_message(session_id, request.content)

    # 构建对话历史
    history = await service.build_conversation_history(session_id)

    # 初始化工具注册表
    registry = await init_tool_registry()

    # 运行 Agent 循环（非流式，等待完整回复）
    agent = AgentLoop(
        registry=registry,
        llm_client=get_llm_client(),
        session=session,
        db=db,
        cancel_key=f"agent_cancel:{session_id}",
        max_steps=settings.AGENT_MAX_STEPS,
        token_budget=settings.AGENT_TOKEN_BUDGET,
    )
    assistant_msg = await agent.run(request.content, history[:-1])

    return {
        "data": {
            "user_message": AgentMessageResponse.model_validate(user_msg),
            "assistant_message": AgentMessageResponse.model_validate(assistant_msg),
        }
    }


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    before: str | None = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取历史消息"""
    service = AgentService(db)
    messages = await service.get_messages(session_id, str(user.id), before=before, limit=limit)
    return {
        "data": [AgentMessageResponse.model_validate(m) for m in messages],
    }


# ---- 取消生成 ----

@router.post("/sessions/{session_id}/cancel")
async def cancel_generation(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消当前生成"""
    service = AgentService(db)
    success = await service.cancel_generation(session_id, str(user.id))
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"data": {"cancelled": True}}


# ---- 工具列表 ----

@router.get("/tools")
async def get_available_tools(
    user: User = Depends(get_current_user),
):
    """获取可用工具列表"""
    registry = await init_tool_registry()
    tools = registry.get_all_schemas()
    return {
        "data": [
            ToolDefinitionResponse(
                name=t.name,
                display_name=t.display_name,
                description=t.description,
                icon=t.icon,
            )
            for t in tools
        ]
    }


# ---- WebSocket ----

@ws_router.websocket("/ws/agent/{session_id}")
async def ws_agent_chat(
    ws: WebSocket,
    session_id: str,
    token: str = Query(...),
):
    """
    Agent WebSocket 对话端点。

    连接地址：ws(s)://{host}/api/v1/ws/agent/{session_id}?token={access_token}

    客户端 -> 服务端：
      - { "type": "message", "content": "用户消息" }
      - { "type": "cancel" }

    服务端 -> 客户端：
      - thinking / tool_call_start / tool_call_result / token / done / error / session_created
    """
    from app.ai.llm_client import get_llm_client

    # 1. 认证：先 accept，验证失败再 close
    await ws.accept()
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await ws.close(code=4001, reason="认证失败")
            return
    except Exception:
        await ws.close(code=4001, reason="认证失败")
        return

    # 2. 获取数据库会话和 Agent 会话
    async with async_session_factory() as db:
        agent_service = AgentService(db)
        session = await agent_service.get_session(session_id, user_id)

        if not session:
            await ws.send_json({"type": "error", "data": {"message": "会话不存在"}})
            await ws.close(code=4004, reason="会话不存在")
            return

        if session.status == "closed":
            await ws.send_json({"type": "error", "data": {"message": "会话已关闭"}})
            await ws.close(code=4003, reason="会话已关闭")
            return

        # 3. 推送 session_created 确认
        await ws.send_json({
            "type": "session_created",
            "data": {
                "session": AgentSessionResponse.model_validate(session).model_dump(),
            },
        })

        # 4. 初始化工具注册表
        registry = await init_tool_registry()

        # 5. 消息循环
        try:
            while True:
                raw = await ws.receive_text()

                # 处理客户端心跳 ping（非 JSON 文本）
                if raw == "ping":
                    await ws.send_text("pong")
                    continue

                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("agent_ws_invalid_json", session_id=session_id, raw=raw[:100])
                    continue

                msg_type = data.get("type")

                if msg_type == "message":
                    content = data.get("content", "").strip()
                    if not content:
                        await ws.send_json({"type": "error", "data": {"message": "消息内容不能为空"}})
                        continue

                    # 清除取消令牌
                    await clear_cancel_token(session_id)

                    # 保存用户消息
                    await agent_service.save_user_message(session_id, content)

                    # 构建对话历史
                    history = await agent_service.build_conversation_history(session_id)

                    # 运行 Agent 循环
                    agent = AgentLoop(
                        registry=registry,
                        llm_client=get_llm_client(),
                        session=session,
                        db=db,
                        ws=ws,
                        cancel_key=f"agent_cancel:{session_id}",
                        max_steps=settings.AGENT_MAX_STEPS,
                        token_budget=settings.AGENT_TOKEN_BUDGET,
                    )

                    try:
                        await agent.run(content, history[:-1])
                    except Exception as e:
                        logger.error("agent_loop_error", session_id=session_id, error=str(e), exc_info=True)
                        await ws.send_json({
                            "type": "error",
                            "data": {"message": "处理消息时发生错误，请重试。"},
                        })

                elif msg_type == "pong":
                    pass  # 心跳响应，忽略

                elif msg_type == "cancel":
                    await set_cancel_token(session_id)
                    await ws.send_json({
                        "type": "done",
                        "data": {
                            "message": {
                                "id": "",
                                "session_id": session_id,
                                "role": "assistant",
                                "content": "已取消生成。",
                                "tool_calls": [],
                                "metadata": {},
                                "created_at": datetime.utcnow().isoformat() + "Z",
                            }
                        },
                    })

        except WebSocketDisconnect:
            logger.info("agent_ws_disconnected", session_id=session_id)
        except Exception as e:
            logger.error("agent_ws_error", session_id=session_id, error=str(e), exc_info=True)
