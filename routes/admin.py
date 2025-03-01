from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, abort
from flask_login import login_required, current_user
from models import db, User, Tenant, SubscriptionPayment, SLAConfig, Ticket
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
    tenant = current_user.tenant
    
    # Get SLA configurations
    sla_configs = {
        config.priority: config 
        for config in SLAConfig.query.filter_by(tenant_id=current_user.tenant_id).all()
    }
    
    # Format for template
    sla_config = {
        'high': sla_configs.get('high', {}),
        'medium': sla_configs.get('medium', {}),
        'low': sla_configs.get('low', {})
    }
    
    # Show success message for completed upgrade
    if request.args.get('upgrade') == 'success' and tenant.subscription_status == 'active':
        flash('Your subscription has been successfully upgraded to Pro!')
    
    return render_template('admin/index.html', 
                         users=users, 
                         tenant=tenant,
                         sla_config=sla_config)

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
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.filter_by(id=user_id, tenant_id=current_user.tenant_id).first_or_404()
    
    # Prevent deleting the last admin
    if user.role == 'admin' and User.query.filter_by(tenant_id=current_user.tenant_id, role='admin').count() <= 1:
        flash('Cannot delete the last admin user', 'error')
        return redirect(url_for('admin.index'))
    
    try:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully', 'success')
    except Exception as e:
        current_app.logger.error(f"Error deleting user: {str(e)}")
        db.session.rollback()
        flash('Error deleting user', 'error')
    
    return redirect(url_for('admin.index'))

@admin.route('/update-subscription', methods=['POST'])
@admin_required
def update_subscription():
    plan = request.form.get('subscription_plan')
    tenant = current_user.tenant
    current_plan = tenant.subscription_plan
    
    # If downgrading to free
    if plan == 'free':
        if tenant.subscription_active and current_plan in ['pro', 'enterprise']:
            days_left = tenant.days_until_expiration
            message = f'You have an active {current_plan.title()} subscription'
            if tenant.subscription_ends_at:
                message += f' with {days_left} days remaining. '
                if tenant.auto_renew:
                    message += f'Your subscription will automatically renew on {tenant.subscription_ends_at.strftime("%Y-%m-%d")}.'
                else:
                    message += f'Your plan will automatically switch to Free when it expires on {tenant.subscription_ends_at.strftime("%Y-%m-%d")}.'
            flash(message)
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
        if tenant.subscription_active and current_plan == 'pro':
            flash('You already have an active Pro subscription')
            return redirect(url_for('admin.index'))
            
        # If they had a previous pro subscription that hasn't expired
        if (tenant.subscription_ends_at and 
            tenant.subscription_ends_at > datetime.utcnow() and 
            tenant.subscription_plan == 'pro'):
            # Reactivate their subscription
            tenant.subscription_status = 'active'
            db.session.commit()
            flash('Your Pro subscription has been reactivated')
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
                success_url=url_for('admin.index', _external=True) + '?upgrade=success',
                cancel_url=url_for('admin.index', _external=True),
                metadata={
                    'tenant_id': str(tenant.id),
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

@admin.route('/team')
@login_required
def team():
    if not current_user.is_admin:
        flash('Permission denied', 'error')
        return redirect(url_for('dashboard.index'))
        
    users = User.query.filter_by(tenant_id=current_user.tenant_id).all()
    return render_template('admin/team.html', users=users)

@admin.route('/team/<int:user_id>/role', methods=['POST'])
@login_required
def update_user_role(user_id):
    if not current_user.is_admin:
        flash('Permission denied', 'error')
        return redirect(url_for('admin.index'))
        
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role')
    
    # Security checks
    if user.tenant_id != current_user.tenant_id:
        flash('Cannot modify users from other tenants', 'error')
        return redirect(url_for('admin.team'))
        
    # Prevent changing superadmin roles
    if user.is_superadmin or new_role == 'superadmin':
        flash('Cannot modify superadmin roles', 'error')
        return redirect(url_for('admin.team'))
        
    # Ensure at least one admin remains
    if user.role == 'admin' and new_role != 'admin':
        admin_count = User.query.filter_by(
            tenant_id=current_user.tenant_id, 
            role='admin'
        ).count()
        if admin_count <= 1:
            flash('Cannot remove the last admin', 'error')
            return redirect(url_for('admin.team'))
    
    # Update role
    user.role = new_role
    db.session.commit()
    
    flash(f'Role updated for {user.email}', 'success')
    return redirect(url_for('admin.index') + '#team')

@admin.route('/team/member/<int:user_id>', methods=['DELETE'])
@login_required
def delete_team_member(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Permission denied'}), 403
        
    if user_id == current_user.id:
        return jsonify({'error': 'Cannot delete yourself'}), 400
        
    user = User.query.get_or_404(user_id)
    
    if user.tenant_id != current_user.tenant_id:
        return jsonify({'error': 'Cannot delete users from other tenants'}), 403
        
    if user.is_superadmin:
        return jsonify({'error': 'Cannot delete superadmin'}), 403
        
    # Check if this is the last admin
    if user.role == 'admin':
        admin_count = User.query.filter_by(
            tenant_id=current_user.tenant_id, 
            role='admin'
        ).count()
        if admin_count <= 1:
            return jsonify({'error': 'Cannot delete the last admin'}), 400
    
    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({'message': 'User deleted successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting user: {str(e)}")
        return jsonify({'error': 'Error deleting user'}), 500

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
    
    # Add message based on new auto_renew status
    if tenant.auto_renew:
        flash(f'Auto-renewal enabled. Your subscription will automatically renew on {tenant.subscription_ends_at.strftime("%Y-%m-%d")}.')
    else:
        flash(f'Auto-renewal disabled. Your plan will automatically switch to Free when it expires on {tenant.subscription_ends_at.strftime("%Y-%m-%d")}.')
    
    return redirect(url_for('admin.index'))

@admin.route('/update-sla-config', methods=['POST'])
@admin_required
def update_sla_config():
    try:
        priorities = ['high', 'medium', 'low']
        
        for priority in priorities:
            # Convert days/hours/minutes to total minutes
            days = int(request.form.get(f'{priority}_resolution_days', 0))
            hours = int(request.form.get(f'{priority}_resolution_hours', 0))
            response_hours = int(request.form.get(f'{priority}_response_hours', 0))
            response_minutes = int(request.form.get(f'{priority}_response_minutes', 0))
            
            resolution_time = (days * 1440) + (hours * 60)  # Convert to minutes
            response_time = (response_hours * 60) + response_minutes
            
            # Update or create SLA config
            sla_config = db.session.query(SLAConfig).filter_by(
                tenant_id=current_user.tenant_id,
                priority=priority
            ).first()
            
            if sla_config:
                sla_config.response_time = response_time
                sla_config.resolution_time = resolution_time
            else:
                sla_config = SLAConfig(
                    tenant_id=current_user.tenant_id,
                    priority=priority,
                    response_time=response_time,
                    resolution_time=resolution_time
                )
                db.session.add(sla_config)
        
        db.session.commit()
        flash('SLA configuration updated successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Error updating SLA configuration', 'error')
        current_app.logger.error(f"Error updating SLA config: {str(e)}")
    
    return redirect(url_for('admin.index')) 

@admin.route('/recalculate-sla', methods=['POST'])
@admin_required
def recalculate_sla():
    """Admin route to recalculate SLA for all tenant's tickets."""
    try:
        # Only recalculate for tickets in the current tenant
        tickets = Ticket.query.filter_by(tenant_id=current_user.tenant_id).all()
        for ticket in tickets:
            ticket.calculate_sla_deadlines()
        db.session.commit()
        flash(f'Successfully recalculated SLA for {len(tickets)} tickets', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error recalculating SLA settings', 'error')
        current_app.logger.error(f"Error in recalculate_sla: {str(e)}")
    
    return redirect(url_for('admin.index')) 

@admin.route('/settings/metabase', methods=['POST'])
@login_required
def update_metabase_settings():
    """Update Metabase settings"""
    if not current_user.role == 'admin':
        abort(403)
        
    try:
        tenant = current_user.tenant
        tenant.metabase_url = request.form.get('metabase_url')
        tenant.metabase_secret_key = request.form.get('metabase_secret_key')
        tenant.metabase_dashboard_ids = request.form.get('dashboard_ids')
        db.session.commit()
        flash('Metabase settings updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating Metabase settings: {str(e)}', 'error')
    
    return redirect(url_for('admin.settings')) 