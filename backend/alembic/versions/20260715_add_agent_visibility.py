"""add agent_sessions visibility column

Revision ID: 20260715_visibility
Revises: 20260711_organize
Create Date: 2026-07-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260715_visibility"
down_revision: Union[str, None] = "20260711_organize"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_sessions",
        sa.Column("visibility", sa.String(20), nullable=False, server_default="visible"),
    )
    op.create_check_constraint(
        "ck_agent_sessions_visibility",
        "agent_sessions",
        "visibility IN ('visible', 'hidden')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_agent_sessions_visibility", "agent_sessions", type_="check")
    op.drop_column("agent_sessions", "visibility")
