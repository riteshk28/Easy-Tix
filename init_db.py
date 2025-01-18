import os
from app import create_app
from models import db

# Create instance directory if it doesn't exist
if not os.path.exists('instance'):
    os.makedirs('instance')
    print("Created instance directory")

app = create_app()

with app.app_context():
    print("Creating database tables...")
    db.create_all()
    print("Database tables created successfully!") 