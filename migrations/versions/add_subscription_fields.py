"""Add subscription management fields

Revision ID: add_subscription_fields
Revises: fd6b31f3c2e2
Create Date: 2024-01-22 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_subscription_fields'
down_revision = 'fd6b31f3c2e2'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('tenant', sa.Column('subscription_starts_at', sa.DateTime(), nullable=True))
    op.add_column('tenant', sa.Column('subscription_ends_at', sa.DateTime(), nullable=True))
    op.add_column('tenant', sa.Column('trial_ends_at', sa.DateTime(), nullable=True))
    op.add_column('tenant', sa.Column('auto_renew', sa.Boolean(), server_default='false'))
    op.add_column('tenant', sa.Column('subscription_status', sa.String(20), server_default='inactive'))

def downgrade():
    op.drop_column('tenant', 'subscription_status')
    op.drop_column('tenant', 'auto_renew')
    op.drop_column('tenant', 'trial_ends_at')
    op.drop_column('tenant', 'subscription_ends_at')
    op.drop_column('tenant', 'subscription_starts_at') 