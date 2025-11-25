"""merge multiple migration heads

Revision ID: b959e26248d5
Revises: 001, ddbbd5fb0625
Create Date: 2025-11-16 15:36:59.763823

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b959e26248d5'
down_revision: Union[str, None] = ('001', 'ddbbd5fb0625')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
