"""allow duplicate engagement targets per community

Revision ID: 20260428_0015
Revises: 20260428_0014
Create Date: 2026-04-28
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260428_0015"
down_revision: Union[str, None] = "20260428_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "engagement_targets_community_id_key",
        "engagement_targets",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "engagement_targets_community_id_key",
        "engagement_targets",
        ["community_id"],
    )
