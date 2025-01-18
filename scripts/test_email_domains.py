import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import Tenant
import requests

def test_email_domains():
    app = create_app()
    
    with app.app_context():
        print("\n=== Testing Email Tickets from Different Domains ===\n")
        
        # First, show configured domains
        print("Configured Tenant Domains:")
        tenants = Tenant.query.all()
        for tenant in tenants:
            print(f"- {tenant.name}: {tenant.email_domain or 'No domain set'}")
        print()
        
        webhook_url = app.config['CLOUDMAILIN_WEBHOOK_URL']
        print(f"Webhook URL: {webhook_url}")
        
        # Use actual tenant domains for testing
        test_cases = []
        for tenant in tenants:
            if tenant.email_domain:
                test_cases.append({
                    'name': tenant.name,
                    'from': f'Test User <test@{tenant.email_domain}>',
                    'subject': f'Test from {tenant.name}',
                    'content': f'This is a test ticket for {tenant.name}'
                })
        
        if not test_cases:
            print("\nNo tenant domains configured. Please set email domains first.")
            return
            
        for test in test_cases:
            print(f"\nTesting: {test['name']}")
            print(f"From: {test['from']}")
            
            test_data = {
                'envelope[from]': test['from'].split('<')[1].strip('>'),
                'envelope[to]': app.config['CLOUDMAILIN_ADDRESS'],
                'headers[from]': test['from'],
                'headers[subject]': test['subject'],
                'headers[to]': app.config['CLOUDMAILIN_ADDRESS'],
                'plain': test['content'],
                'html': f"<p>{test['content']}</p>"
            }
            
            try:
                response = requests.post(webhook_url, data=test_data)
                print(f"Status: {response.status_code}")
                
                if response.status_code != 404:
                    print(f"Response: {response.json()}")
                
                if response.status_code == 404:
                    print("Note: No tenant found for this domain")
                elif response.status_code == 200:
                    print("✓ Ticket created successfully")
                else:
                    print("✗ Unexpected response")
                    
            except Exception as e:
                print(f"Error: {e}")

if __name__ == '__main__':
    test_email_domains() 