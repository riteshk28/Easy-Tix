from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required
from models import db, User, Tenant
import stripe  # Add stripe for payments
from utils import get_stripe_price_id, get_plan_amount
import logging
from datetime import datetime, timedelta

auth = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    
    if request.method == 'POST':
        plan = request.form.get('subscription_plan', 'free')
        form_data = request.form
        current_app.logger.info(f"Registration attempt with plan: {plan}")
        
        if plan != 'free':
            try:
                price_id = current_app.config['STRIPE_PRICE_IDS'].get(plan)
                current_app.logger.info(f"Looking up price ID for plan {plan}: {price_id}")
                
                if not price_id:
                    current_app.logger.error(f"No price ID configured for plan: {plan}")
                    flash('Invalid subscription plan selected.')
                    return redirect(url_for('auth.register'))

                # Create checkout session
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price': price_id,
                        'quantity': 1,
                    }],
                    mode='subscription',
                    success_url=url_for('auth.login', _external=True) + "?registration=success",
                    cancel_url=url_for('auth.register', _external=True),
                    metadata={
                        'email': form_data['email'],
                        'company_name': form_data['company_name'],
                        'first_name': form_data['first_name'],
                        'last_name': form_data['last_name'],
                        'password': form_data['password'],
                        'plan': plan
                    }
                )
                current_app.logger.info(f"Created checkout session: {checkout_session.id}")
                return redirect(checkout_session.url)
            except Exception as e:
                current_app.logger.error(f"Error creating checkout session: {str(e)}")
                flash('An error occurred during registration. Please try again.')
                return redirect(url_for('auth.register'))
        else:
            return create_tenant_and_admin(request.form)
            
    return render_template('auth/register.html', plan=request.args.get('plan', 'free'))

@auth.route('/complete-registration')
def complete_registration():
    session_id = request.args.get('session_id')
    if not session_id:
        return redirect(url_for('auth.register'))
        
    try:
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        if checkout_session.payment_status == 'paid':
            flash('Registration successful! Please login with your credentials.')
            return redirect(url_for('auth.login'))
        else:
            flash('Payment pending. Please contact support if this persists.')
            return redirect(url_for('auth.register'))
            
    except Exception as e:
        flash('Error completing registration. Please contact support.')
        return redirect(url_for('auth.register'))

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard.index'))
        
        flash('Invalid email or password')
    else:
        # Show success message for completed registration
        if request.args.get('registration') == 'success':
            flash('Registration successful! Please log in with your credentials.')
    
    return render_template('auth/login.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login')) 

def create_tenant_and_admin(form_data):
    """Create a new tenant and admin user"""
    # Check if email already exists
    if User.query.filter_by(email=form_data['email']).first():
        flash('Email already exists')
        return redirect(url_for('auth.register'))
    
    # Create new tenant
    tenant = Tenant(
        name=form_data['company_name'],
        subscription_plan=form_data.get('subscription_plan', 'free'),
        subscription_status='active',
        subscription_starts_at=datetime.utcnow(),
        trial_ends_at=datetime.utcnow() + timedelta(days=14)  # 14-day trial
    )
    
    # Set subscription_ends_at based on plan
    if tenant.subscription_plan == 'pro':
        tenant.subscription_ends_at = datetime.utcnow() + timedelta(days=30)
    
    db.session.add(tenant)
    db.session.flush()  # Get tenant ID without committing
    
    # Create admin user
    user = User(
        email=form_data['email'],
        first_name=form_data['first_name'],
        last_name=form_data['last_name'],
        role='admin',
        tenant_id=tenant.id
    )
    user.set_password(form_data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    flash('Registration successful')
    return redirect(url_for('auth.login')) 