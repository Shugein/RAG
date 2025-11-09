"""merge_heads

Revision ID: 988357bc7543
Revises: 304b11a2c5b3, add_event_importance_20250103
Create Date: 2025-10-04 21:56:48.606456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '988357bc7543'
down_revision: Union[str, Sequence[str], None] = ('304b11a2c5b3', 'add_event_importance_20250103')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
