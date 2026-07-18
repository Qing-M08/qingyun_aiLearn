"""add notebook tables

Revision ID: 20260716_notebook
Revises: 20260715_visibility
Create Date: 2026-07-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "20260716_notebook"
down_revision: Union[str, None] = "20260715_visibility"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 notebooks 表
    op.create_table(
        "notebooks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("cover_color", sa.String(20), nullable=False, server_default="#F59E0B"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notebooks_user_id", "notebooks", ["user_id"])
    op.create_index("ix_notebooks_user_updated", "notebooks", ["user_id", "updated_at"])

    # 创建 notebook_notes 表
    op.create_table(
        "notebook_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("notebook_id", UUID(as_uuid=True), sa.ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note_id", UUID(as_uuid=True), sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("notebook_id", "note_id", name="uq_notebook_note"),
    )
    op.create_index("ix_notebook_notes_notebook_sort", "notebook_notes", ["notebook_id", "sort_order"])
    op.create_index("ix_notebook_notes_note_id", "notebook_notes", ["note_id"])


def downgrade() -> None:
    op.drop_table("notebook_notes")
    op.drop_table("notebooks")
