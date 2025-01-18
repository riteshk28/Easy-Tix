from app import create_app
from extensions import db
from sqlalchemy import text
import sqlite3

app = create_app()

with app.app_context():
    try:
        # Add support_alias column if it doesn't exist
        db.session.execute(text("""
            ALTER TABLE tenant 
            ADD COLUMN support_alias VARCHAR(255)
        """))
        db.session.commit()
        
        # Generate aliases for existing tenants
        from models import Tenant
        tenants = Tenant.query.all()
        for tenant in tenants:
            if not tenant.support_alias:
                tenant.generate_support_alias()
        db.session.commit()
        
        # Add cloudmailin_address column
        db.session.execute(text("""
            ALTER TABLE tenant 
            ADD COLUMN cloudmailin_address VARCHAR(255) UNIQUE
        """))
        db.session.commit()
        print("CloudMailin address column added successfully!")
    except Exception as e:
        print(f"Error: {str(e)}") 