from models import db, Tenant
from datetime import datetime, timedelta
from services.email_service import send_email

def check_expiring_subscriptions():
    # Find subscriptions expiring in the next 7 days
    expiring_soon = Tenant.query.filter(
        Tenant.subscription_ends_at <= datetime.utcnow() + timedelta(days=7),
        Tenant.subscription_ends_at > datetime.utcnow(),
        Tenant.subscription_status == 'active'
    ).all()
    
    for tenant in expiring_soon:
        admin_users = [u for u in tenant.users if u.is_admin]
        for admin in admin_users:
            send_email(
                to=admin.email,
                subject="Your subscription is expiring soon",
                template="subscription_expiring",
                data={
                    "days_left": tenant.days_until_expiration,
                    "plan": tenant.subscription_plan
                }
            )

def handle_expired_subscriptions():
    # Find expired subscriptions
    expired = Tenant.query.filter(
        Tenant.subscription_ends_at <= datetime.utcnow(),
        Tenant.subscription_status == 'active'
    ).all()
    
    for tenant in expired:
        if tenant.auto_renew:
            # Attempt to process renewal
            try:
                process_renewal(tenant)
            except:
                tenant.subscription_status = 'payment_failed'
        else:
            tenant.subscription_status = 'expired'
            tenant.subscription_plan = 'free'
        db.session.commit()

def check_expired_subscriptions():
    """Check and handle expired subscriptions"""
    tenants = Tenant.query.filter(
        Tenant.subscription_ends_at <= datetime.utcnow(),
        Tenant.subscription_status == 'active',
        Tenant.subscription_plan != 'free'
    ).all()
    
    for tenant in tenants:
        tenant.handle_subscription_expiry() 