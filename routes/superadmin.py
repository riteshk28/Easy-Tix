import sys
import os

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, render_template, request, redirect, url_for, flash, Flask, current_app
from flask_login import login_required, current_user
from models import db, User, Tenant
from functools import wraps
from sqlalchemy.orm import joinedload
from werkzeug.security import generate_password_hash

superadmin = Blueprint('superadmin', __name__)

def superadmin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'superadmin':
            flash('Access denied')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

@superadmin.route('/')
@login_required
@superadmin_required
def index():
    # Only eager load users since we're using count() for tickets
    tenants = Tenant.query.options(
        joinedload(Tenant.users)
    ).all()
    return render_template('superadmin/index.html', tenants=tenants)

@superadmin.route('/tenants/<int:tenant_id>')
@superadmin_required
def view_tenant(tenant_id):
    tenant = Tenant.query.get_or_404(tenant_id)
    users = User.query.filter_by(tenant_id=tenant_id).all()
    return render_template('superadmin/view_tenant.html', tenant=tenant, users=users)

@superadmin.route('/tenants/<int:tenant_id>/update', methods=['POST'])
@superadmin_required
def update_tenant(tenant_id):
    tenant = Tenant.query.get_or_404(tenant_id)
    
    if 'subscription_plan' in request.form:
        tenant.subscription_plan = request.form['subscription_plan']
        db.session.commit()
        flash('Subscription plan updated successfully')
    
    return redirect(url_for('superadmin.view_tenant', tenant_id=tenant_id))

@superadmin.route('/tenants/<int:tenant_id>/delete', methods=['POST'])
@superadmin_required
def delete_tenant(tenant_id):
    tenant = Tenant.query.get_or_404(tenant_id)
    
    # Delete all users associated with the tenant
    User.query.filter_by(tenant_id=tenant_id).delete()
    
    # Delete the tenant
    db.session.delete(tenant)
    db.session.commit()
    
    flash('Tenant deleted successfully')
    return redirect(url_for('superadmin.index'))

@superadmin.route('/tenant/<int:tenant_id>/user/<int:user_id>/update', methods=['POST'])
@superadmin_required
def update_user(tenant_id, user_id):
    user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first_or_404()
    
    if 'role' in request.form:
        user.role = request.form['role']
        db.session.commit()
        flash('User role updated successfully')
    
    return redirect(url_for('superadmin.view_tenant', tenant_id=tenant_id))

@superadmin.route('/tenant/<int:tenant_id>/user/<int:user_id>/reset-password', methods=['POST'])
@superadmin_required
def reset_user_password(tenant_id, user_id):
    user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first_or_404()
    
    new_password = request.form['password']
    user.set_password(new_password)
    db.session.commit()
    
    flash('User password reset successfully')
    return redirect(url_for('superadmin.view_tenant', tenant_id=tenant_id))

@superadmin.route('/tenant/<int:tenant_id>/user/<int:user_id>/delete', methods=['POST'])
@superadmin_required
def delete_user(tenant_id, user_id):
    user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first_or_404()
    
    if user.is_admin and User.query.filter_by(tenant_id=tenant_id, is_admin=True).count() <= 1:
        flash('Cannot delete the last admin user of the tenant')
        return redirect(url_for('superadmin.view_tenant', tenant_id=tenant_id))
    
    db.session.delete(user)
    db.session.commit()
    
    flash('User deleted successfully')
    return redirect(url_for('superadmin.view_tenant', tenant_id=tenant_id))

@superadmin.route('/initialize-system', methods=['GET', 'POST'])
def initialize_system():
    setup_key = request.args.get('setup_key')
    if setup_key != current_app.config.get('SETUP_KEY'):
        return 'Unauthorized', 401

    # Create database tables
    db.create_all()
    
    # Check if superadmin exists
    if User.query.filter_by(role='superadmin').first():
        return 'System already initialized', 400

    # Create Enterprise tenant
    tenant = Tenant(
        name="System Admin",
        subscription_plan="enterprise",
        support_email=current_app.config.get('MAILERSEND_FROM_EMAIL'),
        cloudmailin_address=current_app.config.get('CLOUDMAILIN_ADDRESS')
    )
    db.session.add(tenant)
    db.session.flush()

    # Create superadmin
    superadmin = User(
        email=current_app.config.get('SUPERADMIN_EMAIL'),
        first_name='Super',
        last_name='Admin',
        role='superadmin',
        tenant_id=tenant.id
    )
    superadmin.set_password(current_app.config.get('SUPERADMIN_PASSWORD'))
    
    db.session.add(superadmin)
    db.session.commit()

    return 'System initialized successfully with superadmin account'

if __name__ == '__main__':
    app = Flask(__name__)
    
    # Configure the database
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from models import db, User
    
    # Make sure instance directory exists
    instance_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance')
    if not os.path.exists(instance_path):
        os.makedirs(instance_path)
        print("Created instance directory")
    
    # Use absolute path for database
    db_path = os.path.join(instance_path, 'servicedesk.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize the database
    db.init_app(app)
    
    with app.app_context():
        # First delete existing superadmin if it exists
        existing_admin = User.query.filter_by(email='admin@example.com').first()
        if existing_admin:
            print("Deleting existing superadmin...")
            db.session.delete(existing_admin)
            db.session.commit()
        
        try:
            # Create superadmin user with minimal fields
            superadmin = User()
            superadmin.email = 'admin@example.com'
            superadmin.set_password('admin123')
            superadmin.first_name = 'Super'
            superadmin.last_name = 'Admin'
            superadmin.role = 'superadmin'  # Changed to use role instead of boolean flags
            superadmin.tenant_id = None
            
            db.session.add(superadmin)
            db.session.commit()
            
            # Verify the user was created with correct permissions
            created_user = User.query.filter_by(email='admin@example.com').first()
            if created_user and created_user.check_password('admin123'):
                if created_user.role == 'superadmin':  # Changed verification
                    print("Superadmin created and verified successfully!")
                    print("Email: admin@example.com")
                    print("Password: admin123")
                else:
                    print("User created but superadmin role not set correctly!")
            else:
                print("User created but password verification failed!")
                
        except Exception as e:
            print(f"Error creating superadmin: {e}")
            print("Available fields:", [column.name for column in User.__table__.columns]) 