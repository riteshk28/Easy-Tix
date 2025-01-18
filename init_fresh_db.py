import os
from app import create_app
from models import db, User
from werkzeug.security import generate_password_hash

# Delete existing database
db_path = os.path.join('instance', 'servicedesk.db')
if os.path.exists(db_path):
    print(f"Deleting existing database: {db_path}")
    os.remove(db_path)

# Create instance directory if it doesn't exist
if not os.path.exists('instance'):
    os.makedirs('instance')
    print("Created instance directory")

app = create_app()

with app.app_context():
    print("Creating fresh database...")
    db.create_all()
    
    print("\nCreating superadmin user...")
    superadmin = User(
        email='admin@example.com',
        password_hash=generate_password_hash('admin123'),
        first_name='Super',
        last_name='Admin',
        role='superadmin',
        tenant_id=None
    )
    
    db.session.add(superadmin)
    db.session.commit()
    
    print("\nVerifying superadmin creation:")
    user = User.query.filter_by(email='admin@example.com').first()
    if user and user.role == 'superadmin':
        print("✓ Superadmin created successfully")
        print("Email: admin@example.com")
        print("Password: admin123")
        print("Role:", user.role)
    else:
        print("✗ Error creating superadmin!")

print("\nDatabase initialization completed!") 