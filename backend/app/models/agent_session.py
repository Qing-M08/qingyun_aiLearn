import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    context_type: Mapped[str] = mapped_column(String(20), nullable=False, default="general")
    context_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="visible")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 关系
    messages: Mapped[list["AgentMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="AgentMessage.created_at"
    )

    __table_args__ = (
        CheckConstraint("context_type IN ('general', 'note', 'lecture', 'route')"),
        CheckConstraint("status IN ('active', 'closed')"),
        CheckConstraint("visibility IN ('visible', 'hidden')"),
        Index("idx_agent_sessions_user_status", "user_id", "status"),
        Index("idx_agent_sessions_user_updated", "user_id", text("updated_at DESC")),
        Index(
            "idx_agent_sessions_context", "context_type", "context_id",
            postgresql_where=text("context_id IS NOT NULL"),
        ),
    )
