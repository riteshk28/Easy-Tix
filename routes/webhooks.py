from flask import Blueprint, request, jsonify, current_app
from models import db, Tenant, User, Ticket, TicketComment
import stripe
from datetime import datetime, timedelta
import json

webhooks = Blueprint('webhooks', __name__, url_prefix='/api')

@webhooks.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    current_app.logger.info("Received webhook")
    
    # Skip signature verification in development
    if current_app.debug:
        try:
            event = json.loads(payload)
        except:
            return jsonify({'error': 'Invalid payload'}), 400
    else:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, current_app.config['STRIPE_WEBHOOK_SECRET']
            )
        except ValueError as e:
            current_app.logger.error(f"Invalid payload: {str(e)}")
            return jsonify({'error': 'Invalid payload'}), 400
        except stripe.error.SignatureVerificationError as e:
            current_app.logger.error(f"Invalid signature: {str(e)}")
            return jsonify({'error': 'Invalid signature'}), 400

    current_app.logger.info(f"Webhook event type: {event['type']}")

    if event['type'] == 'checkout.session.completed':
        try:
            session = event['data']['object']
            metadata = session.get('metadata', {})
            current_app.logger.info(f"Processing completed checkout. Metadata: {metadata}")
            
            # Check if this is a new registration
            if metadata.get('email'):
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
                
            elif metadata.get('tenant_id'):
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
            else:
                current_app.logger.error("No email or tenant_id in metadata")
                
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

@webhooks.route('/email/incoming', methods=['POST'])
def email_webhook():
    try:
        data = request.get_json()
        
        # Extract email data
        from_email = data.get('from')
        subject = data.get('subject', 'No Subject')
        text_body = data.get('plain', '')
        
        # Create ticket
        ticket = Ticket(
            title=subject,
            description=text_body,
            status='open',
            priority='medium',  # Default priority
            contact_email=from_email,
            tenant_id=1  # Need to determine tenant from support email
        )
        
        # Generate ticket number
        ticket.ticket_number = Ticket.generate_ticket_number(ticket.tenant_id)
        
        db.session.add(ticket)
        db.session.commit()
        
        # Calculate SLA deadlines
        ticket.calculate_sla_deadlines()
        db.session.commit()
        
        return jsonify({'status': 'success', 'ticket_id': ticket.id}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500 