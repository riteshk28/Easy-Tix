from mailersend import emails
from flask import current_app
import json
import logging

logger = logging.getLogger(__name__)

class MailerSendService:
    def __init__(self):
        self.api_key = current_app.config['MAILERSEND_API_KEY']
    
    def send_ticket_notification(self, ticket, comment):
        """Send email notification for ticket updates"""
        try:
            logger.info(f"Attempting to send email to {ticket.contact_email}")
            
            # Create mailer instance
            mailer = emails.NewEmail(self.api_key)
            
            # Prepare recipients
            recipients = [
                {
                    "email": ticket.contact_email,
                    "name": ticket.contact_name or ticket.contact_email
                }
            ]
            
            # Prepare email data
            mail_body = {
                "from": {
                    "email": current_app.config['MAILERSEND_FROM_EMAIL'],
                    "name": current_app.config['MAILERSEND_FROM_NAME']
                },
                "to": recipients,
                "subject": f"Re: [{ticket.ticket_number}] {ticket.title}",
                "text": comment.content,
                "html": f"<p>{comment.content}</p>"
            }
            
            # Send email
            response = mailer.send(mail_body)
            
            logger.info(f"Email sent successfully: {response}")
            return response
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            raise 