from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Ticket, TicketComment, User, Tenant, EmailConfig, SLAConfig, TicketActivity
from datetime import datetime, timedelta
from services.email_service import EmailService
from services.mailersend_service import MailerSendService

tickets = Blueprint('tickets', __name__)

@tickets.route('/')
@login_required
def index():
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    
    query = Ticket.query.filter_by(tenant_id=current_user.tenant_id)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    if priority_filter:
        query = query.filter_by(priority=priority_filter)
        
    tickets = query.order_by(Ticket.created_at.desc()).all()
    agents = User.query.filter_by(tenant_id=current_user.tenant_id).all()
    
    return render_template('tickets/index.html', 
                         tickets=tickets,
                         agents=agents,
                         status_filter=status_filter,
                         priority_filter=priority_filter,
                         now=datetime.utcnow())

@tickets.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        ticket = Ticket(
            title=request.form['title'],
            description=request.form['description'],
            priority=request.form['priority'],
            status='open',
            created_by_id=current_user.id,
            tenant_id=current_user.tenant_id
        )
        
        # Generate ticket number
        ticket.ticket_number = Ticket.generate_ticket_number(current_user.tenant_id)
        
        if request.form.get('assigned_to_id'):
            ticket.assigned_to_id = request.form['assigned_to_id']
            
        db.session.add(ticket)
        db.session.commit()  # Commit first to get the ticket ID
        
        # Calculate SLA deadlines
        ticket.calculate_sla_deadlines()
        db.session.commit()  # Commit again to save SLA deadlines
        
        log_ticket_activity(ticket, 'created', f'Ticket created by {current_user.full_name}')
        if ticket.sla_start:
            log_ticket_activity(ticket, 'sla_started', f'SLA timer started')
        
        flash('Ticket created successfully')
        return redirect(url_for('tickets.view', ticket_id=ticket.id))
    
    agents = User.query.filter_by(tenant_id=current_user.tenant_id).all()
    return render_template('tickets/create.html', agents=agents)

@tickets.route('/<int:ticket_id>')
@login_required
def view(ticket_id):
    ticket = Ticket.query.filter_by(
        id=ticket_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    agents = User.query.filter_by(tenant_id=current_user.tenant_id).all()
    comments = ticket.comments.order_by(TicketComment.created_at.desc()).all()
    
    return render_template('tickets/view.html', 
                         ticket=ticket, 
                         agents=agents, 
                         comments=comments,
                         now=datetime.utcnow())

@tickets.route('/ticket/<int:ticket_id>/update', methods=['POST'])
@login_required
def update_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    
    # Get form data
    status = request.form.get('status')
    priority = request.form.get('priority')
    assigned_to_id = request.form.get('assigned_to_id')
    
    # Update ticket
    if status:
        ticket.status = status
    if priority:
        ticket.priority = priority
        # Recalculate SLA if priority changes
        ticket.calculate_sla_deadlines()
    if assigned_to_id:
        ticket.assigned_to_id = int(assigned_to_id) if assigned_to_id != 'none' else None
    
    # Check SLA status after updates
    ticket.check_sla_status()
    
    # Log status change
    if ticket.status != status:
        log_ticket_activity(ticket, 'status_changed', 
            f'Status changed from {status} to {ticket.status}',
            status, ticket.status)
    
    # Log priority change
    if ticket.priority != priority:
        log_ticket_activity(ticket, 'priority_changed',
            f'Priority changed from {priority} to {ticket.priority}',
            priority, ticket.priority)
    
    # Log assignment change
    if ticket.assigned_to != assigned_to_id:
        new_assignee = User.query.get(ticket.assigned_to).full_name if ticket.assigned_to else 'Unassigned'
        old_assignee_name = User.query.get(assigned_to_id).full_name if assigned_to_id else 'Unassigned'
        log_ticket_activity(ticket, 'assigned',
            f'Ticket assigned from {old_assignee_name} to {new_assignee}',
            old_assignee_name, new_assignee)
    
    db.session.commit()
    flash('Ticket updated successfully', 'success')
    return redirect(url_for('tickets.view', ticket_id=ticket_id))

@tickets.route('/<int:ticket_id>/comment', methods=['POST'])
@login_required
def add_comment(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    
    # Get form data
    is_internal = bool(request.form.get('is_internal', False))
    send_email = bool(request.form.get('send_email', False))
    
    comment = TicketComment(
        ticket_id=ticket_id,
        user_id=current_user.id,
        content=request.form['content'],
        is_internal=is_internal
    )
    
    db.session.add(comment)
    
    # Check SLA status after adding comment
    ticket.check_sla_status()
    
    try:
        db.session.commit()
        
        # Only send email if requested and comment is not internal
        if send_email and not is_internal and ticket.contact_email:
            mailer = MailerSendService()
            mailer.send_ticket_notification(ticket, comment)
            
        flash('Comment added successfully')
    except Exception as e:
        db.session.rollback()
        flash('Error adding comment', 'error')
        
    return redirect(url_for('tickets.view', ticket_id=ticket_id))

@tickets.route('/track/<portal_key>/<ticket_id>', methods=['GET', 'POST'])
def track(portal_key, ticket_id):
    tenant = Tenant.query.filter_by(portal_key=portal_key).first_or_404()
    ticket = Ticket.query.filter_by(id=ticket_id, tenant_id=tenant.id).first_or_404()
    
    if request.method == 'POST':
        content = request.form.get('content')
        
        if content:
            comment = TicketComment(
                content=content,
                ticket_id=ticket.id,
                is_customer=True
            )
            db.session.add(comment)
            db.session.commit()
            flash('Comment added successfully')
            return redirect(url_for('tickets.track', portal_key=portal_key, ticket_id=ticket_id))
    
    # Get comments in reverse chronological order (latest first)
    comments = TicketComment.query.filter_by(ticket_id=ticket.id)\
        .order_by(TicketComment.created_at.desc())\
        .all()
    
    return render_template('tickets/track.html', ticket=ticket, comments=comments)

def log_ticket_activity(ticket, activity_type, description, old_value=None, new_value=None):
    activity = TicketActivity(
        ticket_id=ticket.id,
        user_id=current_user.id if not current_user.is_anonymous else None,
        activity_type=activity_type,
        description=description,
        old_value=old_value,
        new_value=new_value
    )
    db.session.add(activity)
    db.session.commit() 