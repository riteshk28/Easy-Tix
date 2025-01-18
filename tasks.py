from celery import Celery
from models import EmailConfig, Ticket, TicketComment
import imaplib
import email
from email.utils import parseaddr
import re

celery = Celery('tasks', broker='redis://localhost:6379/0')

@celery.task
def check_new_emails():
    """Check for new emails for all tenants"""
    configs = EmailConfig.query.filter_by(enabled=True).all()
    
    for config in configs:
        try:
            process_tenant_emails(config)
        except Exception as e:
            logger.error(f"Error processing emails for tenant {config.tenant_id}: {e}")

def process_tenant_emails(config):
    """Process emails for a specific tenant"""
    mail = imaplib.IMAP4_SSL(config.imap_server)
    mail.login(config.imap_username, config.imap_password)
    mail.select('INBOX')
    
    # Search for unread emails
    _, messages = mail.search(None, 'UNSEEN')
    
    for num in messages[0].split():
        _, msg = mail.fetch(num, '(RFC822)')
        email_body = msg[0][1]
        email_message = email.message_from_bytes(email_body)
        
        # Process the email
        process_email(email_message, config.tenant)
        
        # Mark as read
        mail.store(num, '+FLAGS', '\\Seen')
    
    mail.close()
    mail.logout()

def process_email(email_message, tenant):
    """Process a single email"""
    subject = email_message['subject']
    from_email = parseaddr(email_message['from'])[1]
    
    # Check if this is a reply to an existing ticket
    ticket = find_ticket_from_email(email_message, tenant)
    
    if ticket:
        # Add comment to existing ticket
        comment = TicketComment(
            ticket_id=ticket.id,
            content=get_email_content(email_message),
            is_customer=True
        )
        db.session.add(comment)
    else:
        # Create new ticket
        ticket = Ticket(
            title=subject,
            description=get_email_content(email_message),
            status='open',
            tenant_id=tenant.id,
            contact_email=from_email,
            source='email'
        )
        db.session.add(ticket)
    
    db.session.commit() 