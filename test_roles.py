from app import create_app
from models import db, User

app = create_app()

with app.app_context():
    print("\nTesting User Roles and Permissions:")
    print("=" * 50)

    # Test superadmin
    superadmin = User.query.filter_by(email='admin@example.com').first()
    if superadmin:
        print("\nSuperadmin User:")
        print(f"Email: {superadmin.email}")
        print(f"Role: {superadmin.role}")
        print(f"is_admin property: {superadmin.is_admin}")
        print(f"is_superadmin property: {superadmin.is_superadmin}")
    else:
        print("❌ Superadmin not found!")

    # Test tenant users
    print("\nTenant Users:")
    tenant_users = User.query.filter(User.tenant_id.isnot(None)).all()
    if tenant_users:
        for user in tenant_users:
            print(f"\nUser: {user.email}")
            print(f"Role: {user.role}")
            print(f"is_admin property: {user.is_admin}")
            print(f"is_superadmin property: {user.is_superadmin}")
            print(f"Tenant ID: {user.tenant_id}")
    else:
        print("No tenant users found")

    print("\nPermission Matrix:")
    print("=" * 50)
    print("User Type      | Admin Panel | Super Admin Panel")
    print("-" * 50)
    
    if superadmin:
        print(f"Superadmin    | {superadmin.is_admin}        | {superadmin.is_superadmin}")
    
    for user in tenant_users:
        print(f"Tenant User   | {user.is_admin}        | {user.is_superadmin}")

print("\nTest completed!") 