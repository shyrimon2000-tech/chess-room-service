"""add player nicknames

Revision ID: a3c812fe9b01
Revises: e5f454dc2f56
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c812fe9b01'
down_revision: Union[str, Sequence[str], None] = 'e5f454dc2f56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rooms', sa.Column('white_player_nickname', sa.String(length=50), nullable=True))
    op.add_column('rooms', sa.Column('black_player_nickname', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('rooms', 'black_player_nickname')
    op.drop_column('rooms', 'white_player_nickname')
