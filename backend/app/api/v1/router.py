from fastapi import APIRouter

from app.api.v1 import auth, learning, notes, tags, users, websocket, knowledge

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth")
api_router.include_router(users.router, prefix="/users")
api_router.include_router(notes.router, prefix="/notes")
api_router.include_router(tags.router, prefix="/tags")
api_router.include_router(learning.router)
api_router.include_router(knowledge.router)
api_router.include_router(websocket.router)

# Sprint 6 新增：智能答疑
from app.api.v1 import qa
api_router.include_router(qa.router)

# Sprint 7 新增：复习系统
from app.api.v1 import review
api_router.include_router(review.router)

# Phase 3 新增：搜索增强
from app.api.v1 import search
api_router.include_router(search.router)

# Phase 3 新增：Agent 会话
from app.api.v1 import agent
api_router.include_router(agent.router)
api_router.include_router(agent.ws_router)

# Sprint 11 新增：笔记本
from app.api.v1 import notebooks
api_router.include_router(notebooks.router, prefix="/notebooks", tags=["notebooks"])
