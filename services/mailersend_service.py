from mailersend import emails
from flask import current_app, url_for
import json
import logging
from flask_login import current_user
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

logger = logging.getLogger(__name__)
db = SQLAlchemy()

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

    def send_password_change_otp(self, email, otp):
        """Send password change OTP email"""
        try:
            mailer = emails.NewEmail(self.api_key)
            # Get user's tenant name
            tenant_name = current_user.tenant.name if current_user.tenant else "Support"
            
            mailer.send({
                "from": {
                    "email": current_app.config['MAILERSEND_FROM_EMAIL'],
                    "name": f"Easy-Tix-{tenant_name}"
                },
                "to": [
                    {
                        "email": email
                    }
                ],
                "subject": "Easy-Tix: Password Change Verification Code",
                "text": f"Your OTP for password change is: {otp}",
                "html": f"""
                    <div style="font-family: Arial, sans-serif; padding: 20px;">
                        <h2>Password Change Request</h2>
                        <p>Hello {current_user.first_name},</p>
                        <p>We received a request to change your password for your Easy-Tix account.</p>
                        <p>Your verification code is: <strong style="font-size: 24px; color: #007bff;">{otp}</strong></p>
                        <p>This code will expire in 10 minutes.</p>
                        <p>If you didn't request this change, please ignore this email or contact support.</p>
                        <br>
                        <p>Best regards,<br>Easy-Tix Team</p>
                    </div>
                """
            })
            return True
        except Exception as e:
            current_app.logger.error(f"Error sending password change OTP email: {str(e)}")
            raise 

    def send_password_reset_link(self, email, token):
        """Send password reset link email"""
        try:
            mailer = emails.NewEmail(self.api_key)
            # Get user's tenant name
            user = User.query.filter_by(email=email).first()
            tenant_name = user.tenant.name if user and user.tenant else "Support"
            
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            mailer.send({
                "from": {
                    "email": current_app.config['MAILERSEND_FROM_EMAIL'],
                    "name": f"Easy-Tix-{tenant_name}"
                },
                "to": [
                    {
                        "email": email
                    }
                ],
                "subject": "Easy-Tix: Password Reset Request",
                "html": f"""
                    <div style="font-family: Arial, sans-serif; padding: 20px;">
                        <h2>Password Reset Request</h2>
                        <p>Hello,</p>
                        <p>We received a request to reset your password for your Easy-Tix account.</p>
                        <p>Click the button below to reset your password:</p>
                        <p style="margin: 25px 0;">
                            <a href="{reset_url}" 
                               style="background-color: #007bff; color: white; padding: 12px 24px; 
                                      text-decoration: none; border-radius: 4px;">
                                Reset Password
                            </a>
                        </p>
                        <p>This link will expire in 1 hour.</p>
                        <p>If you didn't request this change, please ignore this email or contact support.</p>
                        <br>
                        <p>Best regards,<br>Easy-Tix Team</p>
                    </div>
                """
            })
            return True
        except Exception as e:
            current_app.logger.error(f"Error sending password reset email: {str(e)}")
            raise 