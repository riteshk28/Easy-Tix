import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import Tenant, db
from services.cloudmailin_service import CloudMailinService
from sqlalchemy import text
import requests
import json

def setup_database():
    """Add required columns if they don't exist"""
    try:
        # Try to select the column to check if it exists
        db.session.execute(text('SELECT cloudmailin_address FROM tenant LIMIT 1'))
        print("✓ Database schema is up to date")
    except Exception:
        print("Adding cloudmailin_address column...")
        try:
            # First add the column without UNIQUE constraint
            db.session.execute(text("""
                ALTER TABLE tenant 
                ADD COLUMN cloudmailin_address VARCHAR(255)
            """))
            
            # Then add the UNIQUE index
            db.session.execute(text("""
                CREATE UNIQUE INDEX idx_tenant_cloudmailin_address 
                ON tenant(cloudmailin_address)
                WHERE cloudmailin_address IS NOT NULL
            """))
            
            db.session.commit()
            print("✓ Added cloudmailin_address column with UNIQUE constraint")
        except Exception as e:
            print(f"✗ Error updating database: {e}")
            return False
    return True

def test_cloudmailin_setup():
    app = create_app()
    
    with app.app_context():
        print("\n=== CloudMailin Setup Test ===\n")
        
        # Print config for verification
        print("CloudMailin Configuration:")
        print(f"API Key: {app.config['CLOUDMAILIN_API_KEY']}")
        print(f"Target URL: {app.config['CLOUDMAILIN_TARGET_URL']}\n")
        
        # Setup database first
        if not setup_database():
            print("Database setup failed. Exiting.")
            return
        
        # 1. Test address creation
        print("\nTesting address creation...")
        tenant = Tenant.query.first()
        if not tenant:
            print("✗ No tenants found in database")
            return
            
        print(f"Testing for tenant: {tenant.name}")
        
        try:
            if tenant.cloudmailin_address:
                print(f"✓ Tenant already has address: {tenant.cloudmailin_address}")
            else:
                address = tenant.generate_cloudmailin_address()
                print(f"✓ Success! New address created: {address}")
                
                db.session.refresh(tenant)
                print(f"✓ Saved address: {tenant.cloudmailin_address}\n")
            
        except Exception as e:
            print(f"✗ Error: {e}\n")
            return
            
        # 2. List all addresses
        print("Listing all tenant addresses:")
        tenants = Tenant.query.all()
        for t in tenants:
            print(f"- {t.name}: {t.cloudmailin_address}")
        print()
        
        # 3. Test webhook endpoint
        print("Testing webhook endpoint...")
        webhook_url = app.config['CLOUDMAILIN_TARGET_URL']
        
        test_data = {
            'envelope[to]': tenant.cloudmailin_address,
            'headers[from]': 'Ritesh Kankonkar <riteshknknkr@gmail.com>',
            'headers[subject]': 'Test Ticket via API',
            'plain': 'This is a test ticket created via API'
        }
        
        try:
            response = requests.post(webhook_url, data=test_data)
            print(f"✓ Webhook Response: {response.status_code}")
            print(f"✓ Response: {response.json()}\n")
        except Exception as e:
            print(f"✗ Error testing webhook: {e}\n")
        
        # 4. Generate curl command for manual testing
        print("Curl command for manual testing:")
        curl_cmd = f"""curl -X POST {webhook_url} \\
  -F "envelope[to]={tenant.cloudmailin_address}" \\
  -F "headers[from]=Ritesh Kankonkar <riteshknknkr@gmail.com>" \\
  -F "headers[subject]=Test Ticket via API" \\
  -F "plain=This is a test ticket created via API"
"""
        print(curl_cmd)

if __name__ == '__main__':
    test_cloudmailin_setup() 