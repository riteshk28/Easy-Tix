from extensions import db
from flask_login import UserMixin
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from sqlalchemy import select, func
import re
from sqlalchemy.dialects.postgresql import JSONB

class Tenant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    subscription_plan = db.Column(db.String(20), default='free')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    portal_key = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))
    users = db.relationship('User', backref='tenant', lazy=True)
    tickets = db.relationship(
        'Ticket',
        backref='tenant',
        lazy='dynamic',
        order_by='desc(Ticket.created_at)'
    )
    email_domain = db.Column(db.String(255))
    support_email = db.Column(db.String(255), unique=True)  # The tenant's support email
    support_alias = db.Column(db.String(255), unique=True)
    cloudmailin_address = db.Column(db.String(255), unique=True)
    subscription_starts_at = db.Column(db.DateTime)
    subscription_ends_at = db.Column(db.DateTime)
    trial_ends_at = db.Column(db.DateTime)
    auto_renew = db.Column(db.Boolean, default=False)
    subscription_status = db.Column(db.String(20), default='inactive')
    
    def get_ticket_quota(self):
        """Return the maximum number of tickets allowed per month"""
        quotas = {
            'free': 1000,       # Changed from 100 to 1000
            'pro': 999999,      # Unlimited
            'enterprise': 999999 # Unlimited (unchanged)
        }
        return quotas.get(self.subscription_plan, 100)
    
    def get_team_quota(self):
        """Return the maximum number of team members allowed for the subscription plan"""
        quotas = {
            'free': 3,          # Changed from 1 to 3
            'pro': 10,          # Changed from 3 to 10
            'enterprise': 999999 # Unlimited (unchanged)
        }
        return quotas.get(self.subscription_plan, 1)

    @property
    def ticket_count(self):
        return db.session.query(func.count(Ticket.id)).filter(Ticket.tenant_id == self.id).scalar()

    @property
    def recent_tickets(self):
        """Get the 5 most recent tickets"""
        return self.tickets.order_by(Ticket.created_at.desc()).limit(5).all()

    def set_email_domain(self, domain):
        """Validate and set email domain"""
        # Basic validation
        if not domain or '@' in domain:
            raise ValueError("Invalid domain format")
            
        # Check if domain is already used
        existing = Tenant.query.filter(
            Tenant.email_domain == domain,
            Tenant.id != self.id
        ).first()
        
        if existing:
            raise ValueError("Domain already in use")
            
        self.email_domain = domain

    def set_support_email(self, email):
        """Set the tenant's support email"""
        if not email or '@' not in email:
            raise ValueError("Invalid email format")
            
        # Check if email is already used
        existing = Tenant.query.filter(
            Tenant.support_email == email,
            Tenant.id != self.id
        ).first()
        
        if existing:
            raise ValueError(f"Email {email} is already in use by another tenant")
            
        self.support_email = email.lower()

    def generate_support_alias(self):
        """Generate a unique support email alias for this tenant"""
        unique_id = str(uuid.uuid4())[:8]  # Use first 8 chars for shorter alias
        self.support_alias = f'support-{self.id}-{unique_id}@cloudmailin.net'
        return self.support_alias

    def generate_cloudmailin_address(self):
        """Generate a unique CloudMailin address for this tenant"""
        if not self.cloudmailin_address:
            from services.cloudmailin_service import CloudMailinService
            self.cloudmailin_address = CloudMailinService.create_address(self.id)
            db.session.commit()
        return self.cloudmailin_address

    @property
    def is_trial(self):
        return (
            self.trial_ends_at and 
            self.trial_ends_at > datetime.utcnow()
        )
    
    @property
    def subscription_active(self):
        return (
            self.subscription_status == 'active' and
            (self.subscription_ends_at is None or 
             self.subscription_ends_at > datetime.utcnow())
        )
    
    @property
    def days_until_expiration(self):
        if not self.subscription_ends_at:
            return None
        delta = self.subscription_ends_at - datetime.utcnow()
        return max(0, delta.days)

    def handle_subscription_expiry(self):
        """Check and handle subscription expiration"""
        if (self.subscription_ends_at and 
            self.subscription_ends_at <= datetime.utcnow() and 
            self.subscription_status == 'active' and
            self.subscription_plan != 'free'):
            
            # Downgrade to free plan
            self.subscription_plan = 'free'
            self.subscription_status = 'expired'
            self.subscription_ends_at = None
            db.session.commit()
            
            # Send notification to admin users
            admin_users = [u for u in self.users if u.is_admin]
            for admin in admin_users:
                # You can implement email notification here
                pass
            
            return True
        return False

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    role = db.Column(db.String(20))  # superadmin, admin, agent, user
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_tickets = db.relationship('Ticket', backref='assigned_to', foreign_keys='Ticket.assigned_to_id', lazy=True)
    reset_token = db.Column(db.String(32), unique=True)
    reset_token_expires_at = db.Column(db.DateTime)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        """Admin access for both admin and superadmin roles"""
        return self.role in ['admin', 'superadmin']

    @property
    def is_superadmin(self):
        """Superadmin access only for superadmin role"""
        return self.role == 'superadmin'

    @property
    def full_name(self):
        """Return user's full name or email if name not set"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        return self.email

class Ticket(db.Model):
    __tablename__ = 'ticket'
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True)  # e.g., TENANT1-001
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='open')
    priority = db.Column(db.String(20), default='medium')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'))
    comments = db.relationship(
        'TicketComment',
        backref='ticket',
        lazy='dynamic',
        order_by='desc(TicketComment.created_at)'
    )
    activities = db.relationship(
        'TicketActivity', 
        backref='ticket', 
        lazy=True,
        foreign_keys='TicketActivity.ticket_id',
        order_by='desc(TicketActivity.created_at)'
    )
    contact_name = db.Column(db.String(100))
    contact_email = db.Column(db.String(100))
    source = db.Column(db.String(20), default='portal')  # portal, email, chat
    first_response_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)
    sla_response_due_at = db.Column(db.DateTime)
    sla_resolution_due_at = db.Column(db.DateTime)
    sla_response_met = db.Column(db.Boolean, default=None)
    sla_resolution_met = db.Column(db.Boolean, default=None)
    
    @staticmethod
    def generate_ticket_number(tenant_id):
        """Generate a unique ticket number for the tenant"""
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            raise ValueError("Invalid tenant ID")
            
        # Use tenant ID and first 2 letters of name for unique prefix
        prefix = f"{tenant.name[:2].upper()}{tenant.id}"
        
        # Find the highest ticket number for this tenant
        latest_ticket = Ticket.query.filter(
            Ticket.tenant_id == tenant_id,
            Ticket.ticket_number.like(f'{prefix}-%')
        ).order_by(Ticket.ticket_number.desc()).first()
        
        if latest_ticket:
            try:
                # Extract number from ticket_number (e.g., 'FR5-001' -> 1)
                last_num = int(latest_ticket.ticket_number.split('-')[1])
                new_num = last_num + 1
            except (IndexError, ValueError):
                new_num = 1
        else:
            new_num = 1
            
        # Generate new ticket number with padding
        new_ticket_number = f"{prefix}-{new_num:03d}"
        
        # Double-check uniqueness
        while Ticket.query.filter_by(ticket_number=new_ticket_number).first():
            new_num += 1
            new_ticket_number = f"{prefix}-{new_num:03d}"
            
        return new_ticket_number

    def calculate_sla_deadlines(self):
        """Calculate SLA deadlines based on priority and tenant configuration"""
        # Get tenant's SLA config for this priority
        sla_config = SLAConfig.query.filter_by(
            tenant_id=self.tenant_id,
            priority=self.priority
        ).first()
        
        if not sla_config:
            # If no specific config found, use default values
            response_time = {
                'low': 24 * 60,     # 24 hours in minutes
                'medium': 12 * 60,  # 12 hours in minutes
                'high': 4 * 60      # 4 hours in minutes
            }.get(self.priority, 24 * 60)  # Default to 24 hours
            
            resolution_time = {
                'low': 72 * 60,     # 72 hours in minutes
                'medium': 48 * 60,  # 48 hours in minutes
                'high': 24 * 60     # 24 hours in minutes
            }.get(self.priority, 72 * 60)  # Default to 72 hours
        else:
            response_time = sla_config.response_time
            resolution_time = sla_config.resolution_time
        
        # Calculate deadlines from ticket creation time
        if not self.sla_response_due_at:
            self.sla_response_due_at = self.created_at + timedelta(minutes=response_time)
        if not self.sla_resolution_due_at:
            self.sla_resolution_due_at = self.created_at + timedelta(minutes=resolution_time)

    def check_sla_status(self):
        """Check and update SLA status"""
        now = datetime.utcnow()
        
        # Calculate SLA deadlines if they're not set
        if not self.sla_response_due_at or not self.sla_resolution_due_at:
            self.calculate_sla_deadlines()
        
        # Response SLA
        if not self.first_response_at:
            # Check for first response conditions
            first_response = (
                TicketComment.query.filter_by(
                    ticket_id=self.id,
                    is_internal=True
                ).order_by(TicketComment.created_at.asc()).first()
            )
            
            if first_response or (self.assigned_to_id and self.status != 'open'):
                self.first_response_at = first_response.created_at if first_response else now
                self.sla_response_met = self.first_response_at <= self.sla_response_due_at
        
        # Resolution SLA
        if self.status == 'resolved' and not self.resolved_at:
            self.resolved_at = now
            self.sla_resolution_met = now <= self.sla_resolution_due_at
        elif self.status != 'resolved' and self.resolved_at:
            # If ticket is reopened, reset resolution fields
            self.resolved_at = None
            self.sla_resolution_met = None

    def get_sla_status(self):
        """Get current SLA status for display"""
        now = datetime.utcnow()
        
        response_status = {
            'status': 'in_progress',
            'overdue': False
        }
        
        resolution_status = {
            'status': 'in_progress',
            'overdue': False
        }
        
        # Response SLA
        if self.first_response_at:
            response_status['status'] = 'met' if self.sla_response_met else 'missed'
        elif now > self.sla_response_due_at:
            response_status['overdue'] = True
            
        # Resolution SLA
        if self.resolved_at:
            resolution_status['status'] = 'met' if self.sla_resolution_met else 'missed'
        elif self.status != 'resolved' and now > self.sla_resolution_due_at:
            resolution_status['overdue'] = True
            
        return {
            'response': response_status,
            'resolution': resolution_status
        }

class TicketComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Can be null for customer comments
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_internal = db.Column(db.Boolean, default=False)
    is_customer = db.Column(db.Boolean, default=False)

    # Add back the user relationship
    user = db.relationship('User', backref='comments')

    @property
    def author_name(self):
        """Get the name of the comment author"""
        if self.is_customer:
            return "Customer"
        return self.user.full_name if self.user else "System"

class SubscriptionPayment(db.Model):
    __tablename__ = 'subscription_payments'  # SQLAlchemy convention is plural
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'))
    plan = db.Column(db.String(20))  # free, pro, enterprise
    amount = db.Column(db.Float)
    status = db.Column(db.String(20))  # pending, completed, failed
    payment_id = db.Column(db.String(100))  # Payment gateway reference
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime) 

class EmailConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'))
    email_address = db.Column(db.String(255))  # support@company.com
    imap_server = db.Column(db.String(255))
    imap_port = db.Column(db.Integer)
    imap_username = db.Column(db.String(255))
    imap_password = db.Column(db.String(255))  # encrypted
    postmark_api_key = db.Column(db.String(255))
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_check = db.Column(db.DateTime)
    
    tenant = db.relationship('Tenant', backref='email_config') 

class SLAConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=False)
    priority = db.Column(db.String(20), nullable=False)
    response_time = db.Column(db.Integer, nullable=False)  # in minutes
    resolution_time = db.Column(db.Integer, nullable=False)  # in minutes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    tenant = db.relationship('Tenant', backref='sla_configs')
    
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'priority', name='uq_tenant_priority_sla'),
    ) 

class TicketActivity(db.Model):
    __tablename__ = 'ticket_activity'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    activity_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    old_value = db.Column(db.String(255))
    new_value = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationship to user who performed the action
    user = db.relationship('User', 
        backref='activities',
        foreign_keys=[user_id]
    ) 

class ReportConfig(db.Model):
    __tablename__ = 'report_config'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # e.g., 'tickets_by_status', 'response_times'
    query_config = db.Column(JSONB, nullable=False, default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = db.relationship('Tenant', backref=db.backref('reports', lazy=True))

class Dashboard(db.Model):
    __tablename__ = 'dashboard'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    layout_config = db.Column(JSONB, nullable=False, default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = db.relationship('Tenant', backref=db.backref('dashboards', lazy=True))
    reports = db.relationship('ReportConfig', secondary='dashboard_report', lazy='subquery',
                            backref=db.backref('dashboards', lazy=True))

class DashboardReport(db.Model):
    __tablename__ = 'dashboard_report'
    
    id = db.Column(db.Integer, primary_key=True)
    dashboard_id = db.Column(db.Integer, db.ForeignKey('dashboard.id'), nullable=False)
    report_id = db.Column(db.Integer, db.ForeignKey('report_config.id'), nullable=False)
    position_config = db.Column(JSONB, nullable=False, default={})  # Stores position, size, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow) 

class AnalyticsDashboard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(255))
    layout_config = db.Column(db.JSON)  # Stores chart positions, sizes, visibility
    chart_config = db.Column(db.JSON)   # Stores chart types, colors, metrics
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow) 