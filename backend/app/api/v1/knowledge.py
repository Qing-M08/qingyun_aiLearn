import uuid
from fastapi import APIRouter, Depends, Query
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeNodeSchema,
    KnowledgeNodeCreate,
    KnowledgeNodeUpdate,
    KnowledgeEdgeSchema,
    KnowledgeEdgeCreate,
    KnowledgeGraphResponse,
    LearningPathResponse,
    UserMasterySchema,
    SubjectSchema,
)
from app.schemas.common import PaginatedResponse
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["知识图谱"])


@router.get("/subjects", response_model=list[SubjectSchema])
async def get_subjects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有学科列表"""
    return await KnowledgeService.get_subjects(db)


@router.get("/nodes", response_model=PaginatedResponse[KnowledgeNodeSchema])
async def list_nodes(
    subject: Optional[str] = None,
    grade_level: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询知识节点"""
    items, total = await KnowledgeService.list_nodes(
        db, subject=subject, grade_level=grade_level,
        search=search, page=page, page_size=page_size,
    )
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/nodes", response_model=KnowledgeNodeSchema, status_code=201)
async def create_node(
    data: KnowledgeNodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建知识节点（管理员）"""
    return await KnowledgeService.create_node(db, **data.model_dump())


@router.get("/nodes/{node_id}/graph", response_model=KnowledgeGraphResponse)
async def get_node_graph(
    node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取知识节点的图结构"""
    return await KnowledgeService.get_node_graph(db, node_id, user_id=current_user.id)


@router.get("/nodes/{node_id}/path", response_model=LearningPathResponse)
async def get_learning_path(
    node_id: uuid.UUID,
    target_id: uuid.UUID = Query(..., description="目标节点ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取两个知识节点之间的学习路径"""
    return await KnowledgeService.get_learning_path(db, node_id, target_id)


@router.post("/edges", response_model=KnowledgeEdgeSchema, status_code=201)
async def create_edge(
    data: KnowledgeEdgeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建知识边（管理员）"""
    return await KnowledgeService.create_edge(db, **data.model_dump())
