import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
import requests

def test_email_webhook():
    app = create_app()
    
    with app.app_context():
        print("\n=== Testing Email Webhook ===\n")
        
        webhook_url = app.config['CLOUDMAILIN_WEBHOOK_URL']
        print(f"Webhook URL: {webhook_url}")
        
        # Test data
        test_data = {
            'headers[from]': 'Ritesh Kankonkar <riteshknknkr@gmail.com>',
            'headers[subject]': 'Test Ticket via Email',
            'plain': 'This is a test ticket'
        }
        
        try:
            response = requests.post(webhook_url, data=test_data)
            print(f"\nResponse Status: {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == '__main__':
    test_email_webhook() 