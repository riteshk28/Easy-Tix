from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import Ticket

dashboard = Blueprint('dashboard', __name__)

@dashboard.route('/')
@login_required
def index():
    # Get ticket counts for different statuses
    open_tickets = Ticket.query.filter_by(
        tenant_id=current_user.tenant_id,
        status='open'
    ).count()
    
    in_progress_tickets = Ticket.query.filter_by(
        tenant_id=current_user.tenant_id,
        status='in_progress'
    ).count()
    
    on_hold_tickets = Ticket.query.filter_by(
        tenant_id=current_user.tenant_id,
        status='on_hold'
    ).count()
    
    closed_tickets = Ticket.query.filter_by(
        tenant_id=current_user.tenant_id,
        status='closed'
    ).count()
    
    # Get recent tickets
    recent_tickets = Ticket.query.filter_by(
        tenant_id=current_user.tenant_id
    ).order_by(Ticket.created_at.desc()).limit(5).all()
    
    return render_template('dashboard/index.html',
                         open_tickets=open_tickets,
                         in_progress_tickets=in_progress_tickets,
                         on_hold_tickets=on_hold_tickets,
                         closed_tickets=closed_tickets,
                         recent_tickets=recent_tickets) 