"""add agent_sessions and agent_messages tables

Revision ID: 20260710_agent
Revises: c0826ebcce52
Create Date: 2026-07-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260710_agent"
down_revision: Union[str, None] = "c0826ebcce52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("context_type", sa.String(20), nullable=False, server_default="general"),
        sa.Column("context_id", postgresql.UUID(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("context_type IN ('general', 'note', 'lecture', 'route')"),
        sa.CheckConstraint("status IN ('active', 'closed')"),
    )
    op.create_index("idx_agent_sessions_user_status", "agent_sessions", ["user_id", "status"])
    op.create_index(
        "idx_agent_sessions_user_updated",
        "agent_sessions",
        ["user_id", sa.text("updated_at DESC")],
    )
    op.create_index(
        "idx_agent_sessions_context",
        "agent_sessions",
        ["context_type", "context_id"],
        postgresql_where=sa.text("context_id IS NOT NULL"),
    )

    op.create_table(
        "agent_messages",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", postgresql.UUID(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("tool_calls", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')"),
    )
    op.create_index("idx_agent_messages_session_created", "agent_messages", ["session_id", "created_at"])
    op.create_index("idx_agent_messages_session_role", "agent_messages", ["session_id", "role"])


def downgrade() -> None:
    op.drop_table("agent_messages")
    op.drop_table("agent_sessions")
