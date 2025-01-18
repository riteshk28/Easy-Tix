from flask import Flask, request, jsonify
from datetime import datetime
import json
import os

app = Flask(__name__)

def save_raw_data(data_dict):
    """Save the raw webhook data to a file"""
    # Create logs directory if it doesn't exist
    if not os.path.exists('email_logs'):
        os.makedirs('email_logs')
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'email_logs/email_data_{timestamp}.json'
    
    # Prepare data structure
    webhook_data = {
        'timestamp': datetime.now().isoformat(),
        'form_data': {},
        'headers': {},
        'files': [],
        'raw_data': data_dict
    }
    
    # Get form data
    for key, value in request.form.items():
        webhook_data['form_data'][key] = value
    
    # Get headers
    for key, value in request.headers.items():
        webhook_data['headers'][key] = value
    
    # Get files
    for key, file in request.files.items():
        webhook_data['files'].append({
            'name': key,
            'filename': file.filename
        })
    
    # Save to file with pretty printing
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(webhook_data, f, indent=2, ensure_ascii=False)
    
    print(f"Data saved to {filename}")
    return filename

@app.route('/webhook/email', methods=['POST'])
def test_webhook():
    try:
        # Get the raw data
        if request.is_json:
            data = request.get_json()
        else:
            data = dict(request.form)
        
        # Save the raw data
        filename = save_raw_data(data)
        
        print("\n=== Email Webhook Data ===")
        print(f"Saved to: {filename}")
        print("Headers:")
        for key, value in request.headers.items():
            print(f"{key}: {value}")
        print("\nForm Data:")
        for key, value in request.form.items():
            print(f"{key}: {value}")
        print("=== End Data ===\n")
        
        return jsonify({
            'status': 'success',
            'message': 'Data saved successfully',
            'file': filename
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting test webhook server...")
    print("Webhook URL: http://localhost:5001/webhook/email")
    app.run(port=5001, debug=True) 