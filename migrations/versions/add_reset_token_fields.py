"""add reset token fields

Revision ID: xyz123
Revises: previous_revision
Create Date: 2024-01-31 22:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('user', sa.Column('reset_token', sa.String(32), unique=True))
    op.add_column('user', sa.Column('reset_token_expires_at', sa.DateTime()))

def downgrade():
    op.drop_column('user', 'reset_token')
    op.drop_column('user', 'reset_token_expires_at') 