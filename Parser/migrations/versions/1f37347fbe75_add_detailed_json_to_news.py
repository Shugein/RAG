"""add_detailed_json_to_news

Revision ID: 1f37347fbe75
Revises: 988357bc7543
Create Date: 2025-10-04 21:56:55.620869

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '1f37347fbe75'
down_revision: Union[str, Sequence[str], None] = '988357bc7543'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add detailed_json column to news table
    op.add_column('news', sa.Column('detailed_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Add index for the new JSONB column for better query performance
    op.create_index('idx_news_detailed_json', 'news', ['detailed_json'], postgresql_using='gin')


def downgrade() -> None:
    """Downgrade schema."""
    # Drop index first
    op.drop_index('idx_news_detailed_json', table_name='news')
    
    # Drop the column
    op.drop_column('news', 'detailed_json')
