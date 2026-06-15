"""create_sales_schema_orders_tables

Revision ID: 8a763f7290f3
Revises: b136c030a891
Create Date: 2026-06-15 16:09:05.802992

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a763f7290f3'
down_revision: Union[str, None] = 'b136c030a891'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with open(f"alembic/sql/{revision}/up.sql") as file:
        op.execute(file.read())


def downgrade() -> None:
    with open(f"alembic/sql/{revision}/down.sql") as file:
        op.execute(file.read())