"""add reset token fields

Revision ID: 2024_01_31_add_reset_token
Revises: <your_previous_revision_id>
Create Date: 2024-01-31 22:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2024_01_31_add_reset_token'
down_revision = '<your_previous_revision_id>'  # Replace with your last migration's revision ID
branch_labels = None
depends_on = None

def upgrade():
    # Add columns with nullable=True to allow existing records
    op.add_column('user', sa.Column('reset_token', sa.String(32), unique=True, nullable=True))
    op.add_column('user', sa.Column('reset_token_expires_at', sa.DateTime(), nullable=True))

def downgrade():
    op.drop_column('user', 'reset_token')
    op.drop_column('user', 'reset_token_expires_at') 