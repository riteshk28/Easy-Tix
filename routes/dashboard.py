from flask import Blueprint, render_template, flash
from flask_login import login_required, current_user
from models import Ticket
from services import AnalyticsService

dashboard = Blueprint('dashboard', __name__)

@dashboard.route('/')
@login_required
def index():
    """Dashboard landing page"""
    metrics = {
        'open_tickets': AnalyticsService.get_open_tickets_count(current_user.tenant_id),
        'resolved_today': AnalyticsService.get_resolved_today_count(current_user.tenant_id),
        'sla_compliance': AnalyticsService.get_sla_compliance_rate(current_user.tenant_id),
        'avg_response_time': AnalyticsService.get_avg_response_time(current_user.tenant_id)
    }
    
    recent_tickets = Ticket.query.filter_by(tenant_id=current_user.tenant_id)\
        .order_by(Ticket.created_at.desc())\
        .limit(5)\
        .all()
        
    return render_template('dashboard/index.html',
                         metrics=metrics,
                         recent_tickets=recent_tickets) 