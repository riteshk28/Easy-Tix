from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, Tenant
import stripe  # Add stripe for payments
from utils import get_stripe_price_id, get_plan_amount
import logging
from datetime import datetime, timedelta
import random
from services.mailersend_service import MailerSendService

auth = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    
    if request.method == 'POST':
        # Check if email was verified
        verified_email = session.get('email_verified')
        if not verified_email or verified_email != request.form.get('email'):
            flash('Please verify your email before proceeding')
            return redirect(url_for('auth.register'))
        
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

@auth.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash('You have been successfully logged out', 'success')
    return redirect(url_for('auth.login'))

@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        
        # Validate email not taken by another user
        if email != current_user.email:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Email already in use', 'error')
                return redirect(url_for('auth.profile'))
        
        current_user.email = email
        current_user.first_name = first_name
        current_user.last_name = last_name
        db.session.commit()
        flash('Profile updated successfully', 'success')
        
    return render_template('auth/profile.html')

@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'send_otp':
            # Generate a more secure OTP
            otp = ''.join(random.SystemRandom().choices('0123456789', k=6))
            # Store OTP in session with timestamp and track failed attempts
            session['password_change_otp'] = {
                'code': otp,
                'expires_at': (datetime.utcnow() + timedelta(minutes=10)).timestamp(),
                'attempts': 0  # Track failed attempts
            }
            
            # Send OTP email using MailerSend
            try:
                mailer = MailerSendService()
                mailer.send_password_change_otp(current_user.email, otp)
                flash('OTP sent to your email', 'success')
            except Exception as e:
                flash('Error sending OTP email', 'error')
                
        elif action == 'verify_otp':
            otp = request.form.get('otp')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if new_password != confirm_password:
                flash('Passwords do not match', 'error')
                return redirect(url_for('auth.change_password'))
                
            stored_otp = session.get('password_change_otp')
            if not stored_otp or stored_otp['expires_at'] < datetime.utcnow().timestamp():
                flash('OTP expired', 'error')
                return redirect(url_for('auth.change_password'))
                
            if otp != stored_otp['code']:
                flash('Invalid OTP', 'error')
                return redirect(url_for('auth.change_password'))
                
            # Change password
            current_user.set_password(new_password)
            db.session.commit()
            
            # Clear OTP from session
            session.pop('password_change_otp', None)
            
            flash('Password changed successfully', 'success')
            return redirect(url_for('auth.profile'))
            
    return render_template('auth/change_password.html')

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        try:
            current_app.logger.info("Forgot password POST request received")
            email = request.form.get('email')
            current_app.logger.info(f"Processing reset request for email: {email}")
            user = User.query.filter_by(email=email).first()
            
            if user:
                current_app.logger.info(f"User found for email: {email}")
                # Generate reset token
                reset_token = ''.join(random.SystemRandom().choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=32))
                
                # Store token in database
                user.reset_token = reset_token
                user.reset_token_expires_at = datetime.utcnow() + timedelta(hours=1)
                db.session.commit()
                current_app.logger.info("Reset token stored in database")
                
                # Send reset email
                try:
                    mailer = MailerSendService()
                    current_app.logger.info("Attempting to send reset email")
                    mailer.send_password_reset_link(user.email, reset_token)
                    current_app.logger.info("Reset email sent successfully")
                    flash('Password reset instructions have been sent to your email', 'success')
                except Exception as e:
                    current_app.logger.error(f"Error sending reset email: {str(e)}", exc_info=True)
                    db.session.rollback()  # Rollback the token if email fails
                    flash('Error sending reset instructions', 'error')
                    return redirect(url_for('auth.forgot_password'))
            else:
                current_app.logger.info(f"No user found for email: {email}")
                # Still show success to prevent email enumeration
                flash('If an account exists with this email, reset instructions have been sent', 'info')
                
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            current_app.logger.error(f"Error in forgot password: {str(e)}", exc_info=True)
            flash('An error occurred. Please try again.', 'error')
            
    return render_template('auth/forgot_password.html')

@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # Find user with this reset token
    user = User.query.filter_by(reset_token=token).first()
    
    if not user or not user.reset_token_expires_at or user.reset_token_expires_at < datetime.utcnow():
        flash('Invalid or expired reset link. Please request a new one.', 'error')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not password or not confirm_password:
            flash('Please enter both password fields', 'error')
            return render_template('auth/reset_password.html', token=token)
            
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/reset_password.html', token=token)
            
        try:
            # Update password
            user.set_password(password)
            # Clear reset token
            user.reset_token = None
            user.reset_token_expires_at = None
            db.session.commit()
            
            flash('Your password has been reset successfully. Please login with your new password.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            current_app.logger.error(f"Error resetting password: {str(e)}")
            flash('An error occurred. Please try again.', 'error')
            
    # Show reset password form for GET request
    return render_template('auth/reset_password.html', token=token)

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

@auth.route('/verify-email', methods=['POST'])
def verify_email():
    try:
        current_app.logger.info("Verify email endpoint hit")
        current_app.logger.info(f"Request headers: {dict(request.headers)}")
        current_app.logger.info(f"Request body: {request.get_data(as_text=True)}")
        data = request.get_json()
        current_app.logger.info(f"Received data: {data}")
        email = data.get('email')
        
        # Check if email already exists
        if User.query.filter_by(email=email).first():
            current_app.logger.info(f"Email {email} already exists")
            return jsonify({'message': 'Email already registered'}), 400
        
        # Generate OTP
        otp = ''.join(random.SystemRandom().choices('0123456789', k=6))
        current_app.logger.info(f"Generated OTP for {email}")
        
        # Store OTP in session with timestamp
        session['email_verification'] = {
            'email': email,
            'otp': otp,
            'expires_at': (datetime.utcnow() + timedelta(minutes=10)).timestamp()
        }
        
        # Send OTP email
        mailer = MailerSendService()
        mailer.send_email_verification_otp(email, otp)
        current_app.logger.info(f"OTP sent to {email}")
        
        return jsonify({'message': 'OTP sent successfully'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error in email verification: {str(e)}", exc_info=True)
        return jsonify({'message': f'Error: {str(e)}'}), 500

@auth.route('/verify-email-otp', methods=['POST'])
def verify_email_otp():
    try:
        data = request.get_json()
        email = data.get('email')
        otp = data.get('otp')
        
        verification_data = session.get('email_verification')
        if not verification_data:
            return jsonify({'message': 'Verification session expired'}), 400
            
        if verification_data['email'] != email:
            return jsonify({'message': 'Email mismatch'}), 400
            
        if verification_data['otp'] != otp:
            return jsonify({'message': 'Invalid OTP'}), 400
            
        if verification_data['expires_at'] < datetime.utcnow().timestamp():
            session.pop('email_verification', None)
            return jsonify({'message': 'OTP expired'}), 400
            
        # Store verification status
        session['email_verified'] = email
        
        return jsonify({'message': 'Email verified successfully'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error in OTP verification: {str(e)}", exc_info=True)
        return jsonify({'message': 'Error verifying OTP'}), 500

def generate_reset_token():
    """Generate a secure reset token"""
    reset_token = ''.join(random.SystemRandom().choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=32))
    # Store token in session with expiry
    session['password_reset'] = {
        'token': reset_token,
        'user_id': user.id,  # Add user ID to session
        'expires_at': (datetime.utcnow() + timedelta(hours=1)).timestamp()
    }
    return reset_token 