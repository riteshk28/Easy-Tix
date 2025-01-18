from flask import current_app
from models import User, SubscriptionPayment
import stripe

def get_stripe_price_id(plan):
    """Get Stripe Price ID for a given plan"""
    return current_app.config['STRIPE_PRICE_IDS'].get(plan)

def get_plan_amount(plan):
    """Get plan amount in dollars"""
    amounts = {
        'free': 0,
        'pro': 49,
        'enterprise': 199
    }
    return amounts.get(plan, 0)

def can_downgrade_to_free(tenant):
    """Check if tenant can downgrade to free plan"""
    current_team_size = User.query.filter_by(tenant_id=tenant.id).count()
    return current_team_size <= 1

def cancel_subscription(tenant):
    """Cancel existing Stripe subscription"""
    # Get the latest payment record
    payment = SubscriptionPayment.query.filter_by(
        tenant_id=tenant.id,
        status='completed'
    ).order_by(SubscriptionPayment.created_at.desc()).first()
    
    if payment and payment.payment_id:
        try:
            stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
            stripe.Subscription.delete(payment.payment_id)
        except stripe.error.StripeError:
            # Log the error but continue with downgrade
            pass 