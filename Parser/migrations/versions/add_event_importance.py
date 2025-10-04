"""Add event importance table

Revision ID: add_event_importance_20250103
Revises: add_events_table
Create Date: 2025-01-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_event_importance_20250103'
down_revision = 'add_events_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создаем таблицу важности событий
    op.create_table(
        'event_importance',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('importance_score', sa.Float(), nullable=False),
        sa.Column('novelty', sa.Float(), nullable=False),
        sa.Column('burst', sa.Float(), nullable=False),
        sa.Column('credibility', sa.Float(), nullable=False),
        sa.Column('breadth', sa.Float(), nullable=False),
        sa.Column('price_impact', sa.Float(), nullable=False),
        sa.Column('components_details', postgresql.JSONB, nullable=True),
        sa.Column('calculation_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('weights_version', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Создаем индексы
    op.create_index('ix_event_importance_event_id', 'event_importance', ['event_id'])
    op.create_index('ix_event_importance_score', 'event_importance', ['importance_score'])
    op.create_index('ix_event_importance_timestamp', 'event_importance', ['calculation_timestamp'])
    
    # Создаем таблицу для watcher'ов
    op.create_table(
        'triggered_watches',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rule_id', sa.String(100), nullable=False),
        sa.Column('rule_name', sa.String(200), nullable=False),
        sa.Column('watch_level', sa.String(10), nullable=False),  # L0, L1, L2
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('trigger_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('auto_expire_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),  # triggerd, notified, expired
        sa.Column('notifications_sent', sa.Boolean(), nullable=False, default=False),
        sa.Column('context', postgresql.JSONB, nullable=True),
        sa.Column('alerts', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('notified_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Создаем индексы для watcher'ов
    op.create_index('ix_triggered_watches_rule_id', 'triggered_watches', ['rule_id'])
    op.create_index('ix_triggered_watches_level', 'triggered_watches', ['watch_level'])
    op.create_index('ix_triggered_watches_event_id', 'triggered_watches', ['event_id'])
    op.create_index('ix_triggered_watches_trigger_time', 'triggered_watches', ['trigger_time'])
    op.create_index('ix_triggered_watches_status', 'triggered_watches', ['status'])
    
    # Создаем таблицу для прогнозов L2
    op.create_table(
        'event_predictions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('watch_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('base_event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('predicted_event_type', sa.String(100), nullable=False),
        sa.Column('prediction_probability', sa.Float(), nullable=False),
        sa.Column('prediction_window_days', sa.Integer(), nullable=False),
        sa.Column('target_date_estimate', sa.DateTime(timezone=True), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),  # pending, fulfilled, expired
        sa.Column('fulfilled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_event_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('prediction_context', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['watch_id'], ['triggered_watches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['base_event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['actual_event_id'], ['events.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Создаем индексы для прогнозов
    op.create_index('ix_event_predictions_watch_id', 'event_predictions', ['watch_id'])
    op.create_index('ix_event_predictions_base_event_id', 'event_predictions', ['base_event_id'])
    op.create_index('ix_event_predictions_status', 'event_predictions', ['status'])
    op.create_index('ix_event_predictions_target_date', 'event_predictions', ['target_date_estimate'])


def downgrade() -> None:
    # Удаляем таблицы в обратном порядке
    op.drop_index('ix_event_predictions_target_date', table_name='event_predictions')
    op.drop_index('ix_event_predictions_status', table_name='event_predictions')
    op.drop_index('ix_event_predictions_base_event_id', table_name='event_predictions')
    op.drop_index('ix_event_predictions_watch_id', table_name='event_predictions')
    op.drop_table('event_predictions')
    
    op.drop_index('ix_triggered_watches_status', table_name='triggered_watches')
    op.drop_index('ix_triggered_watches_trigger_time', table_name='triggered_watches')
    op.drop_index('ix_triggered_watches_event_id', table_name='triggered_watches')
    op.drop_index('ix_triggered_watches_level', table_name='triggered_watches')
    op.drop_index('ix_triggered_watches_rule_id', table_name='triggered_watches')
    op.drop_table('triggered_watches')
    
    op.drop_index('ix_event_importance_timestamp', table_name='event_importance')
    op.drop_index('ix_event_importance_score', table_name='event_importance')
    op.drop_index('ix_event_importance_event_id', table_name='event_importance')
    op.drop_table('event_importance')
