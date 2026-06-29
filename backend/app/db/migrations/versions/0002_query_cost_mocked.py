"""add mocked flag to query_costs

Revision ID: 0002_query_cost_mocked
Revises: 0001_initial
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_query_cost_mocked"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "query_costs",
        sa.Column(
            "mocked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # Drop the server_default after backfill so the application layer owns the
    # value going forward (matches how the model declares it).
    op.alter_column("query_costs", "mocked", server_default=None)


def downgrade() -> None:
    op.drop_column("query_costs", "mocked")
