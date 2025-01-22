from flask import Blueprint, request, jsonify, current_app
from models import db, Tenant, User
import stripe
from datetime import datetime, timedelta

webhooks = Blueprint('webhooks', __name__)

@webhooks.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    current_app.logger.info("Received webhook")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, current_app.config['STRIPE_WEBHOOK_SECRET']
        )
        current_app.logger.info(f"Webhook event type: {event['type']}")
    except ValueError as e:
        current_app.logger.error(f"Invalid payload: {str(e)}")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        current_app.logger.error(f"Invalid signature: {str(e)}")
        return jsonify({'error': 'Invalid signature'}), 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        metadata = session.metadata
        current_app.logger.info(f"Processing completed checkout. Metadata: {metadata}")
        
        try:
            # Check if this is a new registration
            if 'email' in metadata:
                current_app.logger.info(f"Creating new tenant for {metadata['email']}")
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
                current_app.logger.info(f"Successfully created tenant and user for {metadata['email']}")
            else:
                # Handle plan upgrade
                tenant_id = int(metadata['tenant_id'])
                current_app.logger.info(f"Upgrading tenant {tenant_id} to pro")
                tenant = Tenant.query.get(tenant_id)
                if tenant:
                    tenant.subscription_plan = 'pro'
                    tenant.subscription_status = 'active'
                    tenant.subscription_starts_at = datetime.utcnow()
                    tenant.subscription_ends_at = datetime.utcnow() + timedelta(days=30)
                    db.session.commit()
                    current_app.logger.info(f"Successfully upgraded tenant {tenant_id} to pro")
                else:
                    current_app.logger.error(f"Tenant {tenant_id} not found")
        except Exception as e:
            current_app.logger.error(f"Error processing webhook: {str(e)}")
            return jsonify({'error': str(e)}), 500

    return jsonify({'status': 'success'})

@webhooks.route('/test-webhook', methods=['GET'])
def test_webhook():
    if not current_app.debug:
        return jsonify({'error': 'Only available in debug mode'}), 403
        
    try:
        # Create a test tenant
        tenant = Tenant(
            name="Test Company",
            subscription_plan='pro',
            subscription_status='active',
            subscription_starts_at=datetime.utcnow(),
            subscription_ends_at=datetime.utcnow() + timedelta(days=30)
        )
        db.session.add(tenant)
        db.session.flush()
        
        # Create a test user
        user = User(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            role='admin',
            tenant_id=tenant.id
        )
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Test tenant and user created successfully',
            'tenant_id': tenant.id,
            'user_email': user.email
        })
    except Exception as e:
        current_app.logger.error(f"Test webhook error: {str(e)}")
        return jsonify({'error': str(e)}), 500 