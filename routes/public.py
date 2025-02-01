from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Ticket, Tenant, User, TicketComment
from datetime import datetime
from services.mailersend_service import MailerSendService
from flask import current_app

public = Blueprint('public', __name__)

@public.route('/<portal_key>/submit', methods=['GET', 'POST'])
def submit_ticket(portal_key):
    tenant = Tenant.query.filter_by(portal_key=portal_key).first_or_404()
    
    if request.method == 'POST':
        ticket = Ticket(
            title=request.form['title'],
            description=request.form['description'],
            status='open',
            priority=request.form['priority'],
            tenant_id=tenant.id,
            contact_name=request.form['name'],
            contact_email=request.form['email'],
            source='portal'
        )
        
        ticket.ticket_number = Ticket.generate_ticket_number(tenant.id)
        
        db.session.add(ticket)
        db.session.commit()
        
        # Send confirmation email
        try:
            mailer = MailerSendService()
            mailer.send_ticket_confirmation(ticket)
        except Exception as e:
            current_app.logger.error(f"Error sending confirmation: {str(e)}")
        
        flash(f'Ticket submitted successfully. Your ticket number is: {ticket.ticket_number}. Please save this number for tracking your ticket.')
        return redirect(url_for('public.view_ticket_status', 
                              portal_key=portal_key, 
                              ticket_id=ticket.id,
                              email=ticket.contact_email))
    
    return render_template('public/submit_ticket.html', tenant=tenant)

@public.route('/<portal_key>/track', methods=['GET', 'POST'])
def track_ticket(portal_key):
    tenant = Tenant.query.filter_by(portal_key=portal_key).first_or_404()
    
    if request.method == 'POST':
        email = request.form.get('email')
        if email:
            tickets = Ticket.query.filter_by(
                tenant_id=tenant.id,
                contact_email=email
            ).order_by(Ticket.created_at.desc()).all()
            
            return render_template('public/my_tickets.html', 
                                 tenant=tenant, 
                                 tickets=tickets, 
                                 email=email)
    
    return render_template('public/track_ticket.html', tenant=tenant)

@public.route('/<portal_key>/status/<int:ticket_id>', methods=['GET', 'POST'])
def view_ticket_status(portal_key, ticket_id):
    tenant = Tenant.query.filter_by(portal_key=portal_key).first_or_404()
    ticket = Ticket.query.filter_by(id=ticket_id, tenant_id=tenant.id).first_or_404()
    email = request.args.get('email')
    
    # Check if this is the ticket owner
    if not email or email != ticket.contact_email:
        flash(f'Please enter the email address ({ticket.contact_email}) used to create this ticket', 'warning')
        return redirect(url_for('public.track_ticket', 
                              portal_key=portal_key,
                              ticket_number=ticket.ticket_number))
    
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
            return redirect(url_for('public.view_ticket_status', 
                                  portal_key=portal_key, 
                                  ticket_id=ticket_id,
                                  email=email))
    
    return render_template('public/ticket_status.html',
                         tenant=tenant,
                         ticket=ticket,
                         email=email) 