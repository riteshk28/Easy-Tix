"""Add support email and fix relationships

Revision ID: new_migration_id
Revises: b47658dbe4ed
Create Date: 2024-01-09 11:50:00.000000
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add support email columns to tenant
    with op.batch_alter_table('tenant', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_domain', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('support_email', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('support_alias', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('cloudmailin_address', sa.String(length=255), nullable=True))
        
        # Add unique constraints with names
        batch_op.create_unique_constraint('uq_tenant_support_email', ['support_email'])
        batch_op.create_unique_constraint('uq_tenant_support_alias', ['support_alias'])
        batch_op.create_unique_constraint('uq_tenant_cloudmailin_address', ['cloudmailin_address'])

    # Fix ticket relationships
    with op.batch_alter_table('ticket', schema=None) as batch_op:
        # First drop existing constraints if any
        batch_op.drop_constraint('ticket_created_by_id_fkey', type_='foreignkey')
        
        # Recreate with proper relationship
        batch_op.create_foreign_key(
            'fk_ticket_created_by_id',
            'user',
            ['created_by_id'], ['id']
        )

def downgrade():
    with op.batch_alter_table('tenant', schema=None) as batch_op:
        batch_op.drop_constraint('uq_tenant_cloudmailin_address', type_='unique')
        batch_op.drop_constraint('uq_tenant_support_alias', type_='unique')
        batch_op.drop_constraint('uq_tenant_support_email', type_='unique')
        batch_op.drop_column('cloudmailin_address')
        batch_op.drop_column('support_alias')
        batch_op.drop_column('support_email')
        batch_op.drop_column('email_domain')

    with op.batch_alter_table('ticket', schema=None) as batch_op:
        batch_op.drop_constraint('fk_ticket_created_by_id', type_='foreignkey')
        batch_op.create_foreign_key(
            'ticket_created_by_id_fkey',
            'user',
            ['created_by_id'], ['id']
        ) 