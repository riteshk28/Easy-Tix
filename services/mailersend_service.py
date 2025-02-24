from mailersend import emails
from flask import current_app, url_for
import json
import logging
from flask_login import current_user
from models import Tenant
import time

logger = logging.getLogger(__name__)

class MailerSendService:
    def __init__(self):
        self.api_key = current_app.config['MAILERSEND_API_KEY']
        self.mailer = emails.NewEmail(self.api_key)
    
    def send_ticket_notification(self, ticket, comment):
        """Send email notification for ticket updates"""
        try:
            logger.info(f"Attempting to send email to {ticket.contact_email}")
            
            # Get tenant for portal URL
            tenant = Tenant.query.get(ticket.tenant_id)
            portal_url = url_for('public.track_ticket', 
                               portal_key=tenant.portal_key,
                               ticket_id=ticket.id,
                               _external=True)
            
            # Prepare recipients
            recipients = [
                {
                    "email": ticket.contact_email,
                    "name": ticket.contact_name or ticket.contact_email
                }
            ]
            
            # Create HTML content with better formatting
            html_content = f"""
                <div style="font-family: Arial, sans-serif; padding: 20px;">
                    <h2>New Update on Ticket #{ticket.ticket_number}</h2>
                    
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;">
                        <p>{comment.content}</p>
                    </div>

                    <div style="margin: 20px 0; padding-top: 15px; border-top: 1px solid #eee;">
                        <p><strong>Ticket Details:</strong></p>
                        <ul>
                            <li>Title: {ticket.title}</li>
                            <li>Status: {ticket.status}</li>
                            <li>Priority: {ticket.priority}</li>
                        </ul>
                    </div>

                    <div style="background: #e9ecef; padding: 15px; border-radius: 5px;">
                        <p><strong>How to Respond:</strong></p>
                        <p>View or update your ticket here: <a href="{portal_url}">View Ticket</a></p>
                        <p>You can also reply to this email to add your response.</p>
                    </div>
                </div>
            """
            
            # Plain text version
            text_content = f"""
New Update on Ticket #{ticket.ticket_number}

{comment.content}

Ticket Details:
- Title: {ticket.title}
- Status: {ticket.status}
- Priority: {ticket.priority}

How to Respond:
View or update your ticket at: {portal_url}
You can also reply to this email to add your response.
            """
            
            # Prepare email data
            mail_body = {
                "from": {
                    "email": tenant.support_email or current_app.config['MAILERSEND_FROM_EMAIL'],
                    "name": f"{tenant.name} Support"
                },
                "to": recipients,
                "subject": f"Re: [{ticket.ticket_number}] {ticket.title}",
                "text": text_content,
                "html": html_content
            }
            
            # Send email
            response = self.mailer.send(mail_body)
            
            logger.info(f"Email sent successfully: {response}")
            return response
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            raise

    def send_password_change_otp(self, email, otp, user=None):
        """Send password change OTP email"""
        max_retries = 3
        retry_delay = 1  # seconds
        
        current_app.logger.info(f"Starting password change OTP email send to {email}")
        current_app.logger.info(f"API Key last 4 chars: ...{self.api_key[-4:]}")
        
        for attempt in range(max_retries):
            try:
                current_app.logger.info(f"Attempt {attempt + 1} of {max_retries}")
                # Use provided user info or defaults
                tenant_name = user.tenant.name if user and hasattr(user, 'tenant') else 'Support'
                user_name = user.first_name if user and hasattr(user, 'first_name') else 'User'
                current_app.logger.info(f"Sending as Easy-Tix-{tenant_name} to {user_name}")

                response = self.mailer.send({
                    "from": {
                        "email": current_app.config['MAILERSEND_FROM_EMAIL'],
                        "name": f"Easy-Tix-{tenant_name}"
                    },
                    "to": [{"email": email}],
                    "subject": "Easy-Tix: Password Change Verification Code",
                    "text": f"Your OTP for password change is: {otp}",
                    "html": f"""
                        <div style="font-family: Arial, sans-serif; padding: 20px;">
                            <h2>Password Change Request</h2>
                            <p>Hello {user_name},</p>
                            <p>We received a request to change your password for your Easy-Tix account.</p>
                            <p>Your verification code is: <strong style="font-size: 24px; color: #007bff;">{otp}</strong></p>
                            <p>This code will expire in 10 minutes.</p>
                            <p>If you didn't request this change, please ignore this email or contact support.</p>
                            <br>
                            <p>Best regards,<br>Easy-Tix Team</p>
                        </div>
                    """
                })
                current_app.logger.info(f"MailerSend Response: {response}")
                return True
            except Exception as e:
                if attempt == max_retries - 1:  # Last attempt
                    current_app.logger.error(f"All {max_retries} attempts failed for {email}")
                    current_app.logger.error(f"Error sending password change OTP email: {str(e)}")
                    raise
                current_app.logger.warning(f"Attempt {attempt + 1} failed, retrying in {retry_delay}s")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff

    def send_password_reset_link(self, email, token):
        """Send password reset link email"""
        try:
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            self.mailer.send({
                "from": {
                    "email": current_app.config['MAILERSEND_FROM_EMAIL'],
                    "name": "Easy-Tix Support"
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
                            <p style="color: #666; font-size: 14px;">If you didn't request this change, please ignore this email.</p>
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
            self.mailer.send({
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
        
        try:
            self.mailer.send({
                "from": {"email": "support@easy-tix.com", "name": "Easy-Tix Support"},
                "to": [{"email": user.email}],
                "subject": "Password Reset Instructions",
                "html": f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="text-align: center; margin-bottom: 30px;">
                            <h1 style="color: #333;">Password Reset</h1>
                        </div>
                        <div style="background: #fff; padding: 20px; border-radius: 5px;">
                            <p>Hello {user.first_name},</p>
                            <p>We received a request to reset your password for your Easy-Tix account.</p>
                            <p>Click the button below to reset your password:</p>
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{reset_link}" 
                                   style="background-color: #007bff; color: white; padding: 12px 24px; 
                                          text-decoration: none; border-radius: 4px; display: inline-block;">
                                    Reset Password
                                </a>
                            </div>
                            <p>This link will expire in 1 hour.</p>
                            <p>If you didn't request this change, please ignore this email.</p>
                            <br>
                            <p>Best regards,<br>Easy-Tix Team</p>
                        </div>
                    </div>
                """
            })
        except Exception as e:
            current_app.logger.error(f"MailerSend Error: {str(e)}")
            raise

    def send_ticket_confirmation(self, ticket):
        """Send confirmation email to ticket creator with tracking link"""
        current_app.logger.info(f"Attempting to send confirmation email for ticket {ticket.ticket_number}")
        current_app.logger.info(f"Using API key: {'*' * (len(self.api_key) - 4) + self.api_key[-4:]}")
        
        tenant = Tenant.query.get(ticket.tenant_id)
        if not tenant:
            current_app.logger.error(f"No tenant found for ID: {ticket.tenant_id}")
            raise ValueError(f"No tenant found for ID: {ticket.tenant_id}")

        portal_url = url_for('public.track_ticket', 
                            portal_key=tenant.portal_key,
                            ticket_id=ticket.id,
                            _external=True)
        
        sender = {
            "email": current_app.config['MAILERSEND_FROM_EMAIL'],
            "name": f"Easy-Tix-{tenant.name}"
        }
        current_app.logger.info(f"Sending from: {sender}")
        current_app.logger.info(f"Sending to: {ticket.contact_email}")
        
        recipients = [{"email": ticket.contact_email}]
        
        subject = f"Ticket #{ticket.ticket_number} Created - {ticket.title}"
        
        html_content = f"""
            <h2>Ticket Created Successfully</h2>
            <p>Your ticket has been created with the following details:</p>
            <ul>
                <li><strong>Ticket Number:</strong> #{ticket.ticket_number}</li>
                <li><strong>Title:</strong> {ticket.title}</li>
                <li><strong>Priority:</strong> {ticket.priority}</li>
                <li><strong>Status:</strong> {ticket.status}</li>
            </ul>
            <p>You can track your ticket status using this link:</p>
            <p><a href="{portal_url}">{portal_url}</a></p>
            <p>We'll notify you of any updates to your ticket.</p>
        """
        
        try:
            response = self.mailer.send({
                "from": sender,
                "to": recipients,
                "subject": subject,
                "html": html_content
            })
            current_app.logger.info(f"Email sent successfully: {response}")
            return response
        except Exception as e:
            current_app.logger.error(f"Error sending confirmation email: {str(e)}", exc_info=True)
            raise