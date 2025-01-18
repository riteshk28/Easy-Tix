from app import create_app
from extensions import db
from models import User, Tenant

app = create_app()

with app.app_context():
    # Create the main ServiceDesk tenant
    tenant = Tenant(
        name='ServiceDesk',
        subscription_plan='enterprise'
    )
    db.session.add(tenant)
    db.session.flush()

    # Create superadmin user
    superadmin = User(
        email='admin@servicedesk.com',
        first_name='Super',
        last_name='Admin',
        role='superadmin',
        tenant_id=tenant.id
    )
    superadmin.set_password('admin123')
    db.session.add(superadmin)
    db.session.commit()
    print("Superadmin account created successfully!") 