from mailersend import emails
from flask import current_app, url_for
import json
import logging
from flask_login import current_user
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from mailersend import MailerSend

logger = logging.getLogger(__name__)
db = SQLAlchemy()

class MailerSendService:
    def __init__(self):
        self.api_key = current_app.config['MAILERSEND_API_KEY']
        self.client = MailerSend(self.api_key)
    
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
                "text": f"Click this link to reset your password: {reset_url}",
                "html": f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="text-align: center; margin-bottom: 30px;">
                            <h1 style="color: #333;">Password Reset</h1>
                        </div>
                        <div style="background: #fff; padding: 20px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <p>Hello,</p>
                            <p>We received a request to reset your password for your Easy-Tix account.</p>
                            <p>Click the button below to reset your password:</p>
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{reset_url}" 
                                   style="background-color: #007bff; color: white; padding: 12px 24px; 
                                          text-decoration: none; border-radius: 4px; display: inline-block;">
                                    Reset Password
                                </a>
                            </div>
                            <p style="color: #666; font-size: 14px;">This link will expire in 1 hour.</p>
                            <p style="color: #666; font-size: 14px;">If you didn't request this change, please ignore this email or contact support.</p>
                            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                            <p style="color: #666; font-size: 14px; text-align: center;">
                                Best regards,<br>Easy-Tix Team
                            </p>
                        </div>
                    </div>
                """
            })
            return True
        except Exception as e:
            current_app.logger.error(f"Error sending password reset email: {str(e)}", exc_info=True)
            raise 

    def send_email_verification_otp(self, email, otp):
        """Send email verification OTP"""
        try:
            mailer = emails.NewEmail(self.api_key)
            
            mailer.send({
                "from": {
                    "email": current_app.config['MAILERSEND_FROM_EMAIL'],
                    "name": "Easy-Tix"
                },
                "to": [
                    {
                        "email": email
                    }
                ],
                "subject": "Easy-Tix: Verify Your Email",
                "text": f"Your verification code is: {otp}",
                "html": f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="text-align: center; margin-bottom: 30px;">
                            <h1 style="color: #333;">Verify Your Email</h1>
                        </div>
                        <div style="background: #fff; padding: 20px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <p>Hello,</p>
                            <p>Your verification code is:</p>
                            <div style="text-align: center; margin: 30px 0;">
                                <span style="font-size: 32px; font-weight: bold; color: #007bff;">{otp}</span>
                            </div>
                            <p style="color: #666; font-size: 14px;">This code will expire in 10 minutes.</p>
                            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                            <p style="color: #666; font-size: 14px; text-align: center;">
                                Best regards,<br>Easy-Tix Team
                            </p>
                        </div>
                    </div>
                """
            })
            return True
        except Exception as e:
            current_app.logger.error(f"Error sending verification email: {str(e)}", exc_info=True)
            raise 

    def send_password_reset(self, user, token):
        """Send password reset email"""
        reset_link = url_for('auth.reset_password', 
                           token=token, 
                           _external=True)
        
        variables = [
            {
                "email": user.email,
                "substitutions": [
                    {"var": "first_name", "value": user.first_name},
                    {"var": "reset_link", "value": reset_link},
                ],
            }
        ]
        
        try:
            self.client.email.send({
                "from": {"email": "support@easy-tix.com", "name": "Easy-Tix Support"},
                "to": [{"email": user.email}],
                "subject": "Password Reset Instructions",
                "template_id": current_app.config['MAILERSEND_PASSWORD_RESET_TEMPLATE_ID'],
                "variables": variables
            })
        except Exception as e:
            current_app.logger.error(f"MailerSend Error: {str(e)}")
            raise