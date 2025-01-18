from app import create_app
from models import db, User

app = create_app()

with app.app_context():
    print("Starting role fixes...")
    
    # Print current user roles
    print("\nCurrent users and their roles:")
    all_users = User.query.all()
    for user in all_users:
        print(f"User {user.email}: role = {user.role}")
    
    # Fix admin users - find users who should be admins
    print("\nFixing admin roles...")
    tenant_admins = User.query.filter(User.tenant_id.isnot(None)).all()
    admin_count = 0
    for user in tenant_admins:
        if user.role != 'admin':  # Only update if not already set
            user.role = 'admin'
            admin_count += 1
            print(f"Setting admin role for: {user.email}")
    
    print(f"Updated {admin_count} admin users")

    # Fix superadmin
    print("\nFixing superadmin role...")
    superadmin = User.query.filter_by(email='admin@example.com').first()
    if superadmin:
        if superadmin.role != 'superadmin':
            superadmin.role = 'superadmin'
            print(f"Setting superadmin role for: {superadmin.email}")
        else:
            print("Superadmin role already set correctly")
    else:
        print("Superadmin not found")

    # Commit all changes
    try:
        db.session.commit()
        print("\nAll role changes committed successfully!")
        
        # Verify changes
        print("\nVerified roles after update:")
        for user in User.query.all():
            print(f"User {user.email}: role = {user.role}")
            
    except Exception as e:
        print(f"Error committing changes: {e}")
        db.session.rollback()

print("\nRole fix script completed!") 