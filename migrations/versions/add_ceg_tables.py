"""add_ceg_tables_events_importance_watches_predictions

Revision ID: ceg_001
Revises:
Create Date: 2025-01-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ceg_001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create events table
    op.create_table(
        'events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('news_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('news.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attrs', postgresql.JSONB(), default={}),
        sa.Column('is_anchor', sa.Boolean(), default=False),
        sa.Column('confidence', sa.Float(), default=0.8),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Create indexes for events
    op.create_index('idx_events_news', 'events', ['news_id'])
    op.create_index('idx_events_type', 'events', ['event_type'])
    op.create_index('idx_events_ts', 'events', ['ts'])
    op.create_index('idx_events_is_anchor', 'events', ['is_anchor'])
    op.create_index('idx_events_type_ts', 'events', ['event_type', 'ts'])

    # Create event_importance table
    op.create_table(
        'event_importance',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('importance_score', sa.Float(), nullable=False),
        sa.Column('novelty', sa.Float(), nullable=False),
        sa.Column('burst', sa.Float(), nullable=False),
        sa.Column('credibility', sa.Float(), nullable=False),
        sa.Column('breadth', sa.Float(), nullable=False),
        sa.Column('price_impact', sa.Float(), nullable=False),
        sa.Column('components_details', postgresql.JSONB()),
        sa.Column('calculation_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('weights_version', sa.String(50)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create indexes for event_importance
    op.create_index('ix_event_importance_event_id', 'event_importance', ['event_id'])
    op.create_index('ix_event_importance_score', 'event_importance', ['importance_score'])
    op.create_index('ix_event_importance_timestamp', 'event_importance', ['calculation_timestamp'])

    # Create triggered_watches table
    op.create_table(
        'triggered_watches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('rule_id', sa.String(100), nullable=False),
        sa.Column('rule_name', sa.String(200), nullable=False),
        sa.Column('watch_level', sa.String(10), nullable=False),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('trigger_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('auto_expire_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='triggered'),
        sa.Column('notifications_sent', sa.Boolean(), nullable=False, default=False),
        sa.Column('context', postgresql.JSONB()),
        sa.Column('alerts', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('notified_at', sa.DateTime(timezone=True)),
    )

    # Create indexes for triggered_watches
    op.create_index('ix_triggered_watches_rule_id', 'triggered_watches', ['rule_id'])
    op.create_index('ix_triggered_watches_level', 'triggered_watches', ['watch_level'])
    op.create_index('ix_triggered_watches_event_id', 'triggered_watches', ['event_id'])
    op.create_index('ix_triggered_watches_trigger_time', 'triggered_watches', ['trigger_time'])
    op.create_index('ix_triggered_watches_status', 'triggered_watches', ['status'])

    # Create event_predictions table
    op.create_table(
        'event_predictions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('watch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('triggered_watches.id', ondelete='CASCADE'), nullable=False),
        sa.Column('base_event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('predicted_event_type', sa.String(100), nullable=False),
        sa.Column('prediction_probability', sa.Float(), nullable=False),
        sa.Column('prediction_window_days', sa.Integer(), nullable=False),
        sa.Column('target_date_estimate', sa.DateTime(timezone=True), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('fulfilled_at', sa.DateTime(timezone=True)),
        sa.Column('actual_event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('events.id', ondelete='SET NULL')),
        sa.Column('prediction_context', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create indexes for event_predictions
    op.create_index('ix_event_predictions_watch_id', 'event_predictions', ['watch_id'])
    op.create_index('ix_event_predictions_base_event_id', 'event_predictions', ['base_event_id'])
    op.create_index('ix_event_predictions_status', 'event_predictions', ['status'])
    op.create_index('ix_event_predictions_target_date', 'event_predictions', ['target_date_estimate'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('event_predictions')
    op.drop_table('triggered_watches')
    op.drop_table('event_importance')
    op.drop_table('events')
