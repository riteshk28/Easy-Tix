import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import Tenant, db

def setup_tenant_domains():
    app = create_app()
    
    with app.app_context():
        print("\n=== Setting Up Tenant Domains ===\n")
        
        # Show current domains
        print("Current Tenant Domains:")
        tenants = Tenant.query.all()
        for tenant in tenants:
            print(f"- {tenant.name}: {tenant.email_domain or 'No domain set'}")
        
        print("\nUpdating domains...")
        
        # Update Pro tenant domain
        pro_tenant = Tenant.query.filter_by(name='Pro').first()
        if pro_tenant:
            pro_tenant.email_domain = 'pro.com'  # Domain from ritesh@pro.com
            db.session.commit()
            print(f"✓ Updated Pro tenant domain to: {pro_tenant.email_domain}")
        
        # Show updated domains
        print("\nUpdated Tenant Domains:")
        tenants = Tenant.query.all()
        for tenant in tenants:
            print(f"- {tenant.name}: {tenant.email_domain or 'No domain set'}")

if __name__ == '__main__':
    setup_tenant_domains() 