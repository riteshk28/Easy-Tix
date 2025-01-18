import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # Add unique index on ticket_number
        db.session.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ticket_number 
            ON ticket(ticket_number)
        """))
        db.session.commit()
        print("✓ Added unique index on ticket_number")
    except Exception as e:
        print(f"Error: {e}") 