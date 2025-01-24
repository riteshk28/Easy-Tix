from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Ticket, TicketComment, User, Tenant, EmailConfig, SLAConfig
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

@tickets.route('/<int:ticket_id>/update', methods=['POST'])
@login_required
def update_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    
    try:
        # Update ticket fields
        if 'status' in request.form:
            ticket.status = request.form['status']
        if 'assigned_to_id' in request.form:
            ticket.assigned_to_id = request.form['assigned_to_id'] or None
            
        # Ensure SLA deadlines exist
        if not ticket.sla_response_due_at or not ticket.sla_resolution_due_at:
            ticket.calculate_sla_deadlines()
            
        # Check SLA status after updates
        ticket.check_sla_status()
        
        db.session.commit()
        flash('Ticket updated successfully')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating ticket: {str(e)}")
        flash('Error updating ticket', 'error')
        
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