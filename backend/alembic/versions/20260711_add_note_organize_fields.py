"""add note organize fields

Revision ID: 20260711_organize
Revises: 20260711_emb_dim
Create Date: 2026-07-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID

# revision identifiers, used by Alembic.
revision: str = "20260711_organize"
down_revision: Union[str, None] = "20260711_emb_dim"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notes",
        sa.Column(
            "origin_type",
            sa.String(20),
            server_default="user",
            nullable=False,
            comment="来源类型: user / ai_organized",
        ),
    )
    op.add_column(
        "notes",
        sa.Column(
            "source_note_ids",
            ARRAY(UUID(as_uuid=True)),
            nullable=True,
            comment="AI 整理时的源笔记 ID 列表",
        ),
    )


def downgrade() -> None:
    op.drop_column("notes", "source_note_ids")
    op.drop_column("notes", "origin_type")
