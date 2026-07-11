"""change embedding dimension from 1024 to 512

Revision ID: 20260711_emb_dim
Revises: 20260710_agent
Create Date: 2026-07-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '20260711_emb_dim'
down_revision: Union[str, None] = '20260710_agent'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # memory_index.embedding: vector(1024) -> vector(512)
    op.alter_column(
        'memory_index',
        'embedding',
        type_=Vector(512),
        postgresql_using='embedding::vector(512)',
    )
    # document_chunks.embedding: vector(1024) -> vector(512)
    op.alter_column(
        'document_chunks',
        'embedding',
        type_=Vector(512),
        postgresql_using='embedding::vector(512)',
    )


def downgrade() -> None:
    # memory_index.embedding: vector(512) -> vector(1024)
    op.alter_column(
        'memory_index',
        'embedding',
        type_=Vector(1024),
        postgresql_using='embedding::vector(1024)',
    )
    # document_chunks.embedding: vector(512) -> vector(1024)
    op.alter_column(
        'document_chunks',
        'embedding',
        type_=Vector(1024),
        postgresql_using='embedding::vector(1024)',
    )
