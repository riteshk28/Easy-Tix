from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import db, User, Tenant, SubscriptionPayment
from werkzeug.security import generate_password_hash
from functools import wraps
import stripe  # Add stripe for payments
from utils import get_stripe_price_id, get_plan_amount, can_downgrade_to_free, cancel_subscription
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta  # Add this import if not present
import logging

# Set up logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

admin = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['admin', 'superadmin']:
            flash('Access denied')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

@admin.route('/')
@admin_required
def index():
    users = User.query.filter_by(tenant_id=current_user.tenant_id).all()
    
    # For super admin, ensure they have an Enterprise tenant
    if current_user.is_superadmin and not current_user.tenant:
        # Create Enterprise tenant for super admin if doesn't exist
        tenant = Tenant(
            name="System Admin",
            subscription_plan="enterprise",
            support_email=current_app.config.get('SUPPORT_EMAIL'),
            cloudmailin_address=current_app.config.get('CLOUDMAILIN_ADDRESS')
        )
        db.session.add(tenant)
        db.session.flush()  # Get tenant ID
        
        # Associate super admin with this tenant
        current_user.tenant_id = tenant.id
        db.session.commit()
    
    tenant = current_user.tenant
    return render_template('admin/index.html', users=users, tenant=tenant)

@admin.route('/users/create', methods=['GET', 'POST'])
@admin_required
def create_user():
    tenant = Tenant.query.get(current_user.tenant_id)
    current_users = User.query.filter_by(tenant_id=current_user.tenant_id).count()
    
    if current_users >= tenant.get_team_quota():
        flash('Team member quota exceeded for your subscription plan', 'error')
        return redirect(url_for('admin.index'))
    
    if request.method == 'POST':
        email = request.form['email']
        
        # Check if email already exists
        if User.query.filter_by(email=email).first():
            flash('A user with this email already exists', 'error')
            return render_template('admin/create_user.html')
        
        try:
            user = User(
                email=email,
                first_name=request.form['first_name'],
                last_name=request.form['last_name'],
                role=request.form['role'],
                tenant_id=current_user.tenant_id
            )
            user.set_password(request.form['password'])
            
            db.session.add(user)
            db.session.commit()
            
            flash('User created successfully', 'success')
            return redirect(url_for('admin.index'))
            
        except IntegrityError:
            db.session.rollback()
            flash('A user with this email already exists', 'error')
            return render_template('admin/create_user.html')
    
    return render_template('admin/create_user.html')

@admin.route('/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_password(user_id):
    user = User.query.filter_by(
        id=user_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    new_password = request.form['password']
    user.set_password(new_password)
    db.session.commit()
    
    flash('Password reset successfully')
    return redirect(url_for('admin.index'))

@admin.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('Cannot delete your own account')
        return redirect(url_for('admin.index'))
        
    user = User.query.filter_by(
        id=user_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    db.session.delete(user)
    db.session.commit()
    
    flash('User deleted successfully')
    return redirect(url_for('admin.index'))

@admin.route('/update-subscription', methods=['POST'])
@admin_required
def update_subscription():
    plan = request.form.get('subscription_plan')
    tenant = current_user.tenant
    current_plan = tenant.subscription_plan
    
    # If downgrading to free
    if plan == 'free':
        if current_plan in ['pro', 'enterprise']:
            flash('Please contact support to downgrade your plan')
            return redirect(url_for('admin.index'))
        tenant.subscription_plan = 'free'
        tenant.subscription_status = 'active'
        tenant.subscription_ends_at = None
        db.session.commit()
        flash('Successfully updated to Free plan')
        return redirect(url_for('admin.index'))
    
    # If upgrading to pro
    if plan == 'pro':
        # Check if already on pro with active subscription
        if current_plan == 'pro' and tenant.subscription_active:
            flash('You already have an active Pro subscription')
            return redirect(url_for('admin.index'))
            
        # Create Stripe checkout session for upgrade
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': current_app.config['STRIPE_PRICE_IDS']['pro'],
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=url_for('admin.index', _external=True),
                cancel_url=url_for('admin.index', _external=True),
                metadata={
                    'tenant_id': tenant.id,
                    'plan': 'pro'
                }
            )
            return redirect(checkout_session.url)
        except Exception as e:
            current_app.logger.error(f"Stripe error: {str(e)}")
            flash('Payment processing error. Please try again.')
            return redirect(url_for('admin.index'))
    
    # If enterprise plan
    if plan == 'enterprise':
        flash('Please contact sales for Enterprise plan upgrade')
        return redirect(url_for('admin.index'))
    
    flash('Invalid subscription plan selected')
    return redirect(url_for('admin.index'))

@admin.route('/subscription/update', methods=['POST'])
@admin_required
def update_subscription_old():
    # Set stripe API key at the start of the function
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    
    tenant = Tenant.query.get(current_user.tenant_id)
    new_plan = request.form.get('subscription_plan')
    current_plan = tenant.subscription_plan
    
    # Only process if actually changing plans
    if new_plan != current_plan:
        if new_plan == 'free':
            # Handle downgrade to free
            if can_downgrade_to_free(tenant):
                cancel_subscription(tenant)
                tenant.subscription_plan = 'free'
                db.session.commit()
                flash('Successfully downgraded to free plan')
            else:
                flash('Cannot downgrade: Please reduce team members first')
        else:
            # Handle upgrade/downgrade between paid plans
            try:
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price': get_stripe_price_id(new_plan),
                        'quantity': 1,
                    }],
                    mode='subscription',
                    success_url=url_for('admin.complete_upgrade', 
                                      _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
                    cancel_url=url_for('admin.index', _external=True),
                    metadata={
                        'tenant_id': tenant.id,
                        'plan': new_plan
                    }
                )
                return redirect(checkout_session.url)
            except Exception as e:
                flash('Payment processing error. Please try again.')
    
    return redirect(url_for('admin.index'))

@admin.route('/subscription/complete-upgrade')
@admin_required
def complete_upgrade():
    session_id = request.args.get('session_id')
    if not session_id:
        flash('No session ID provided', 'error')
        return redirect(url_for('admin.index'))
        
    try:
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        if checkout_session.payment_status == 'paid':
            tenant = Tenant.query.get(checkout_session.metadata['tenant_id'])
            if not tenant:
                raise ValueError(f"Tenant not found: {checkout_session.metadata['tenant_id']}")
                
            tenant.subscription_plan = checkout_session.metadata['plan']
            
            # Create payment record
            payment = SubscriptionPayment(
                tenant_id=tenant.id,
                plan=tenant.subscription_plan,
                amount=get_plan_amount(tenant.subscription_plan),
                status='completed',
                payment_id=checkout_session.subscription,
                completed_at=datetime.utcnow()
            )
            
            db.session.add(payment)
            db.session.commit()
            
            flash(f'Successfully upgraded to {tenant.subscription_plan.title()} plan!', 'success')
        else:
            flash('Payment not completed. Please try again or contact support.', 'warning')
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Subscription upgrade error: {str(e)}")
        flash(f'Error updating subscription: {str(e)}. Please contact support.', 'error')
        
    return redirect(url_for('admin.index'))

@admin.route('/contact-sales', methods=['POST'])
@admin_required
def contact_sales():
    # Here you would typically send an email to your sales team
    # For now, we'll just show a success message
    flash('Thank you for your interest! Our sales team will contact you soon.')
    return redirect(url_for('admin.index'))

@admin.route('/team/add', methods=['POST'])
@login_required
@admin_required
def add_team_member():
    email = request.form.get('email')
    
    # Check if email already exists
    if User.query.filter_by(email=email).first():
        flash('A user with this email already exists', 'error')
        return redirect(url_for('admin.team'))
    
    try:
        user = User(
            email=email,
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            role=request.form.get('role'),
            tenant_id=current_user.tenant_id
        )
        user.set_password(request.form.get('password'))
        db.session.add(user)
        db.session.commit()
        flash('Team member added successfully')
        
    except IntegrityError:
        db.session.rollback()
        flash('A user with this email already exists', 'error')
    
    return redirect(url_for('admin.team')) 

@admin.route('/update-email-settings', methods=['POST'])
@admin_required
def update_email_settings():
    tenant = Tenant.query.get(current_user.tenant_id)
    
    if 'support_email' in request.form:
        try:
            email = request.form['support_email'].strip()
            tenant.set_support_email(email)
            db.session.commit()
            flash('Support email updated successfully')
            
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating email settings', 'error')
            current_app.logger.error(f"Error updating support email: {str(e)}")
    
    return redirect(url_for('admin.index')) 

@admin.route('/toggle-auto-renew', methods=['POST'])
@admin_required
def toggle_auto_renew():
    tenant = current_user.tenant
    tenant.auto_renew = not tenant.auto_renew
    db.session.commit()
    flash('Auto-renewal settings updated')
    return redirect(url_for('admin.index')) 