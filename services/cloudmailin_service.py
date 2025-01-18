import requests
from flask import current_app

class CloudMailinService:
    @staticmethod
    def create_address(tenant_id):
        """Create a new CloudMailin address for a tenant"""
        url = f"{current_app.config['CLOUDMAILIN_BASE_URL']}/addresses"
        
        payload = {
            'address': {
                'target': current_app.config['CLOUDMAILIN_TARGET_URL'],
                'name': f'tenant-{tenant_id}',
                'format': 'multipart'  # or 'raw' or 'json'
            }
        }
        
        headers = {
            'Authorization': f"Basic {current_app.config['CLOUDMAILIN_API_KEY']}"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 201:
            data = response.json()
            return data['address']['email']
        else:
            raise Exception(f"Failed to create CloudMailin address: {response.text}") 