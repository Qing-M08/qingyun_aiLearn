import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class KnowledgeNodeSchema(BaseModel):
    id: uuid.UUID
    subject: str
    name: str
    description: Optional[str] = None
    grade_level: Optional[str] = None
    difficulty: int = 1
    metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeNodeCreate(BaseModel):
    subject: str = Field(max_length=100)
    name: str = Field(max_length=255)
    description: Optional[str] = None
    grade_level: Optional[str] = Field(None, max_length=20)
    difficulty: int = Field(default=1, ge=1, le=5)
    metadata: Optional[dict] = None


class KnowledgeNodeUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    grade_level: Optional[str] = None
    difficulty: Optional[int] = Field(None, ge=1, le=5)
    metadata: Optional[dict] = None


class KnowledgeEdgeSchema(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    relation_type: str
    weight: float = 1.0
    metadata: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeEdgeCreate(BaseModel):
    source_id: uuid.UUID
    target_id: uuid.UUID
    relation_type: str = Field(pattern="^(prerequisite|related|subtopic|parent)$")
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
    metadata: Optional[dict] = None


class KnowledgeGraphResponse(BaseModel):
    """知识节点图结构响应"""
    node: KnowledgeNodeSchema
    prerequisites: list[KnowledgeNodeSchema] = []
    dependents: list[KnowledgeNodeSchema] = []
    related: list[KnowledgeNodeSchema] = []
    user_mastery: Optional["UserMasterySchema"] = None


class LearningPathResponse(BaseModel):
    """两节点间学习路径"""
    path: list[KnowledgeNodeSchema]
    total_difficulty: float


class UserMasterySchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    node_id: uuid.UUID
    mastery_score: float
    review_count: int
    correct_count: int
    total_count: int
    last_reviewed_at: Optional[datetime] = None
    next_review_at: Optional[datetime] = None
    ease_factor: float
    interval_days: int

    model_config = {"from_attributes": True}


class SubjectSchema(BaseModel):
    name: str
    display_name: str
    node_count: int


class GraphNodeCypher(BaseModel):
    """Apache AGE返回的图节点"""
    id: str
    name: str
    subject: str
    grade_level: Optional[str] = None
    difficulty: int = 1
    description: Optional[str] = None
    labels: list[str] = []


class GraphEdgeCypher(BaseModel):
    """Apache AGE返回的图边"""
    source_id: str
    target_id: str
    relation_type: str
    weight: float = 1.0
