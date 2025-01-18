import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import Tenant, db

def setup_tenant_support():
    app = create_app()
    
    with app.app_context():
        print("\n=== Setting Up Tenant Support Emails ===\n")
        
        # Show current settings
        print("Current Support Emails:")
        tenants = Tenant.query.all()
        for tenant in tenants:
            print(f"- {tenant.name}: {tenant.support_email or 'No support email set'}")
        
        print("\nUpdating support emails...")
        
        # Update Pro tenant
        pro_tenant = Tenant.query.filter_by(name='Pro').first()
        if pro_tenant:
            pro_tenant.set_support_email('support@pro.com')
            db.session.commit()
            print(f"✓ Updated Pro tenant support email to: {pro_tenant.support_email}")
            print(f"  Forward emails from this address to: {app.config['CLOUDMAILIN_ADDRESS']}")
        
        # Show updated settings
        print("\nUpdated Support Emails:")
        tenants = Tenant.query.all()
        for tenant in tenants:
            print(f"- {tenant.name}: {tenant.support_email or 'No support email set'}")
            if tenant.support_email:
                print(f"  Forward to: {app.config['CLOUDMAILIN_ADDRESS']}")

if __name__ == '__main__':
    setup_tenant_support() 