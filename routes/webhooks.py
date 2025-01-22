from flask import Blueprint, request, jsonify, current_app
from models import db, Tenant, User
import stripe
from datetime import datetime, timedelta

webhooks = Blueprint('webhooks', __name__)

@webhooks.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, current_app.config['STRIPE_WEBHOOK_SECRET']
        )
    except ValueError as e:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        return jsonify({'error': 'Invalid signature'}), 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        metadata = session.metadata
        
        # Check if this is a new registration
        if 'email' in metadata:
            # Create new tenant and user
            tenant = Tenant(
                name=metadata['company_name'],
                subscription_plan='pro',
                subscription_status='active',
                subscription_starts_at=datetime.utcnow(),
                subscription_ends_at=datetime.utcnow() + timedelta(days=30)
            )
            db.session.add(tenant)
            db.session.flush()  # Get tenant ID
            
            user = User(
                email=metadata['email'],
                first_name=metadata['first_name'],
                last_name=metadata['last_name'],
                role='admin',
                tenant_id=tenant.id
            )
            user.set_password(metadata['password'])
            db.session.add(user)
            db.session.commit()
        else:
            # Handle plan upgrade
            tenant_id = int(metadata['tenant_id'])
            tenant = Tenant.query.get(tenant_id)
            if tenant:
                tenant.subscription_plan = 'pro'
                tenant.subscription_status = 'active'
                tenant.subscription_starts_at = datetime.utcnow()
                tenant.subscription_ends_at = datetime.utcnow() + timedelta(days=30)
                db.session.commit()

    return jsonify({'status': 'success'}) 