from flask import request, jsonify
from flask_jwt_extended import jwt_required
from flask_restful import Resource
from datetime import datetime, timedelta
from models import db, Tenant

class Webhooks(Resource):
    @jwt_required()
    def post(self):
        # ... existing webhook setup code ...

        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            tenant_id = session['metadata']['tenant_id']
            tenant = Tenant.query.get(tenant_id)
            
            if tenant:
                tenant.subscription_status = 'active'
                tenant.subscription_starts_at = datetime.utcnow()
                tenant.subscription_ends_at = datetime.utcnow() + timedelta(days=30)
                db.session.commit()

        elif event['type'] == 'invoice.payment_failed':
            # Handle failed payment
            tenant_id = event['data']['object']['metadata']['tenant_id']
            tenant = Tenant.query.get(tenant_id)
            if tenant:
                tenant.subscription_status = 'payment_failed'
                db.session.commit()

        return jsonify({'message': 'Webhook processed successfully'}) 