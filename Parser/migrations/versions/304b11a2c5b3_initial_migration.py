"""Initial migration

Revision ID: 304b11a2c5b3
Revises: 
Create Date: 2025-09-30 23:35:55.561845

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '304b11a2c5b3'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create sources table
    op.create_table('sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('base_url', sa.Text(), nullable=True),
        sa.Column('tg_chat_id', sa.String(length=100), nullable=True),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('trust_level', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.Index('idx_sources_kind_enabled', 'kind', 'enabled')
    )

    # Create news table
    op.create_table('news',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('external_id', sa.String(length=500), nullable=False),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('text_html', sa.Text(), nullable=True),
        sa.Column('text_plain', sa.Text(), nullable=True),
        sa.Column('lang', sa.String(length=10), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('hash_content', sa.CHAR(length=64), nullable=True),
        sa.Column('is_updated', sa.Boolean(), nullable=True),
        sa.Column('is_ad', sa.Boolean(), nullable=True),
        sa.Column('ad_score', sa.Float(), nullable=True),
        sa.Column('ad_reasons', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('tsv', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_id', 'external_id', name='uq_source_external_id'),
        sa.Index('idx_news_published_at', 'published_at'),
        sa.Index('idx_news_source_published', 'source_id', 'published_at'),
        sa.Index('idx_news_hash_content', 'hash_content'),
        sa.Index('idx_news_tsv', 'tsv')
    )

    # Create images table
    op.create_table('images',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sha256', sa.CHAR(length=64), nullable=False),
        sa.Column('mime_type', sa.String(length=50), nullable=False),
        sa.Column('bytes', postgresql.BYTEA(), nullable=False),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('thumbnail', postgresql.BYTEA(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sha256'),
        sa.Index('idx_images_sha256', 'sha256')
    )

    # Create news_images association table
    op.create_table('news_images',
        sa.Column('news_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('image_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ord', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['image_id'], ['images.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['news_id'], ['news.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('news_id', 'image_id', name='uq_news_image')
    )

    # Create entities table
    op.create_table('entities',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('news_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('norm', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('start_pos', sa.Integer(), nullable=True),
        sa.Column('end_pos', sa.Integer(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['news_id'], ['news.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_entities_news_type', 'news_id', 'type'),
        sa.Index('idx_entities_type', 'type')
    )

    # Create linked_companies table
    op.create_table('linked_companies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('news_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('secid', sa.String(length=50), nullable=True),
        sa.Column('isin', sa.String(length=20), nullable=True),
        sa.Column('board', sa.String(length=20), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('short_name', sa.String(length=100), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('is_traded', sa.Boolean(), nullable=True),
        sa.Column('match_method', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['news_id'], ['news.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_linked_companies_news', 'news_id'),
        sa.Index('idx_linked_companies_secid', 'secid'),
        sa.Index('idx_linked_companies_isin', 'isin')
    )

    # Create topics table
    op.create_table('topics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('news_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('topic', sa.String(length=50), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['news_id'], ['news.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('news_id', 'topic', name='uq_news_topic'),
        sa.Index('idx_topics_news', 'news_id'),
        sa.Index('idx_topics_topic', 'topic')
    )

    # Create sector_constituents table
    op.create_table('sector_constituents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sector_code', sa.String(length=50), nullable=False),
        sa.Column('secid', sa.String(length=50), nullable=False),
        sa.Column('isin', sa.String(length=20), nullable=True),
        sa.Column('board', sa.String(length=20), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('weight', sa.Float(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sector_code', 'secid', name='uq_sector_secid'),
        sa.Index('idx_sector_constituents_sector', 'sector_code'),
        sa.Index('idx_sector_constituents_secid', 'secid')
    )

    # Create company_aliases table
    op.create_table('company_aliases',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('secid', sa.String(length=50), nullable=False),
        sa.Column('alias', sa.String(length=200), nullable=False),
        sa.Column('alias_normalized', sa.String(length=200), nullable=False),
        sa.Column('lang', sa.String(length=10), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('alias_normalized', 'secid', name='uq_alias_secid'),
        sa.Index('idx_company_aliases_secid', 'secid'),
        sa.Index('idx_company_aliases_normalized', 'alias_normalized')
    )

    # Create outbox table
    op.create_table('outbox',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('aggregate_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('payload_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('max_retries', sa.Integer(), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['aggregate_id'], ['news.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_outbox_status_next_retry', 'status', 'next_retry_at'),
        sa.Index('idx_outbox_created_at', 'created_at')
    )

    # Create parser_states table
    op.create_table('parser_states',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('last_parsed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_external_id', sa.String(length=500), nullable=True),
        sa.Column('cursor_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('backfill_completed', sa.Boolean(), nullable=True),
        sa.Column('backfill_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('backfill_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_error_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_id'),
        sa.Index('idx_parser_states_source', 'source_id')
    )

    # Create GIN index for full-text search
    op.execute("CREATE INDEX idx_news_tsv_gin ON news USING gin (to_tsvector('russian', title || ' ' || COALESCE(text_plain, '')))")


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order
    op.drop_table('parser_states')
    op.drop_table('outbox')
    op.drop_table('company_aliases')
    op.drop_table('sector_constituents')
    op.drop_table('topics')
    op.drop_table('linked_companies')
    op.drop_table('entities')
    op.drop_table('news_images')
    op.drop_table('images')
    op.drop_table('news')
    op.drop_table('sources')