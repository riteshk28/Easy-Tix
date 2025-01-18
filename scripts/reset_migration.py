import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # Check if support_email column exists
        db.session.execute(text('SELECT support_email FROM tenant LIMIT 1'))
        print("✓ Support email column already exists")
    except Exception:
        print("Adding support_email column...")
        # Add column without UNIQUE constraint first
        db.session.execute(text("""
            ALTER TABLE tenant 
            ADD COLUMN support_email VARCHAR(255)
        """))
        
        # Add UNIQUE index
        db.session.execute(text("""
            CREATE UNIQUE INDEX idx_tenant_support_email 
            ON tenant(support_email)
            WHERE support_email IS NOT NULL
        """))
        db.session.commit()
        print("✓ Added support_email column with UNIQUE constraint")

    print("\nMigration complete!") 