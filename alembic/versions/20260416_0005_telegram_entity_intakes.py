"""add telegram entity intakes

Revision ID: 20260416_0005
Revises: 20260415_0004
Create Date: 2026-04-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260416_0005"
down_revision: Union[str, None] = "20260415_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_entity_intakes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("raw_value", sa.Text(), nullable=False),
        sa.Column("normalized_key", sa.Text(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("telegram_url", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("entity_type", sa.Text()),
        sa.Column("community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("requested_by", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("normalized_key"),
    )
    op.create_index(
        "ix_telegram_entity_intakes_status",
        "telegram_entity_intakes",
        ["status"],
    )
    op.create_index(
        "ix_telegram_entity_intakes_entity_type",
        "telegram_entity_intakes",
        ["entity_type"],
    )
    op.create_index(
        "ix_telegram_entity_intakes_community_id",
        "telegram_entity_intakes",
        ["community_id"],
    )
    op.create_index(
        "ix_telegram_entity_intakes_user_id",
        "telegram_entity_intakes",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("telegram_entity_intakes")
