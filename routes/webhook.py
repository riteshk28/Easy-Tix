from flask import Blueprint, request, jsonify, current_app
import stripe
from models import db, Tenant, SubscriptionPayment, User, Ticket, TicketComment
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from utils import get_plan_amount  # Add this import
import logging
import re
from email import message_from_string, policy
from email.parser import Parser
from email.policy import default
from html2text import HTML2Text  # pip install html2text
from bs4 import BeautifulSoup  # pip install beautifulsoup4
from flask_wtf.csrf import csrf_exempt
from services.mailersend_service import MailerSendService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

webhook = Blueprint('webhook', __name__)

def extract_email_content(text_content, html_content):
    """Extract clean email content from forwarded messages"""
    try:
        # If HTML content is available, use it
        if html_content:
            h = HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.body_width = 0
            h.unicode_snob = True
            h.protect_links = True
            text_content = h.handle(html_content)

        # Log the initial content for debugging
        current_app.logger.debug(f"Initial content:\n{text_content[:500]}...")

        # Handle Office 365 forwarded emails
        if '* * *' in text_content:  # Office 365 separator
            # Split on the Office 365 markers
            parts = text_content.split('* * *')
            if len(parts) > 1:
                # Look for the part that contains the original email
                for part in parts:
                    if 'From:' in part and 'Subject:' in part:
                        # Extract the content after the email headers
                        header_end = part.find('Subject:')
                        if header_end != -1:
                            # Find the next newline after Subject:
                            content_start = part.find('\n', header_end)
                            if content_start != -1:
                                text_content = part[content_start:].strip()
                                break

        # Handle Gmail forwarded emails
        elif '---------- Forwarded message ---------' in text_content:
            parts = text_content.split('---------- Forwarded message ---------')
            if len(parts) > 1:
                text_content = parts[-1]

        # Process the content line by line
        lines = text_content.split('\n')
        clean_lines = []
        in_header = True
        found_content = False
        
        for line in lines:
            line = line.rstrip()
            
            # Skip empty lines until we find content
            if not line:
                continue

            # Skip quoted content and common markers
            if (line.startswith('>') or 
                line.startswith('On ') or 
                line.endswith('wrote:') or
                line.startswith('From:') or
                line.startswith('Sent:') or
                line.startswith('To:') or
                line.startswith('Subject:')):
                continue

            # Skip signature lines and footers
            if any(sig in line for sig in [
                'Thanks & Regards',
                'Best regards',
                'Regards',
                '--',
                'Service Delivery Coordinator',
                'Bounteous merges with Accolite',
                'Get Outlook for',
                '+1',
                '![](cid:'  # Skip image references
            ]):
                continue

            # Found actual content
            found_content = True
            clean_lines.append(line)

        # Join lines with proper spacing
        result = '\n'.join(line for line in clean_lines if line.strip())
        
        # Log the final content for debugging
        current_app.logger.debug(f"Cleaned content:\n{result}")
        
        return result.strip()

    except Exception as e:
        current_app.logger.error(f"Error extracting email content: {e}")
        current_app.logger.error(f"Original content: {text_content[:500]}...")
        return text_content

def format_email_content(text_content):
    """Format the content to look like a real email"""
    try:
        if '<html' in text_content:
            soup = BeautifulSoup(text_content, 'html.parser')
            
            # First, get all the text content preserving structure
            all_content = []
            for element in soup.stripped_strings:
                text = element.strip()
                if text:
                    all_content.append(text)
            
            # Join all content with newlines
            full_content = '\n'.join(all_content)
            current_app.logger.info(f"Full content:\n{full_content}")
            
            # Look for email sections
            sections = re.split(r'(?:From:|Begin forwarded message:|---------- Forwarded message ----------)', full_content)
            
            # Get the original email section (first section after the split that has content)
            original_section = None
            for section in sections:
                if section.strip():
                    original_section = section
                    break
            
            if original_section:
                # Extract headers from the original section
                headers = {}
                lines = original_section.split('\n')
                message_lines = []
                in_headers = True
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                        
                    if in_headers:
                        # Look for header patterns
                        header_match = re.match(r'^(From|To|Subject|Date|Sent):\s*(.+)$', line)
                        if header_match:
                            key, value = header_match.groups()
                            headers[key] = value.strip()
                            continue
                        else:
                            in_headers = False
                    
                    # If we're past headers and it's not a signature line
                    if not any(sig in line for sig in ['Thanks & Regards', 'Best regards', '+1', 'http://']):
                        message_lines.append(line)
                
                # Format the output
                formatted_parts = []
                
                # Add headers in order
                for header in ['From', 'To', 'Date', 'Subject']:
                    if header in headers:
                        formatted_parts.append(f"{header}: {headers[header]}")
                
                # Add separator
                formatted_parts.append("\n" + "-" * 50 + "\n")
                
                # Add message body
                if message_lines:
                    formatted_parts.append('\n'.join(message_lines).strip())
                
                return '\n'.join(formatted_parts)
            
            return full_content
            
        else:
            # Handle plain text emails using the same logic
            sections = re.split(r'(?:From:|Begin forwarded message:|---------- Forwarded message ----------)', text_content)
            
            # Get the original email section
            original_section = None
            for section in reversed(sections):
                if not section.strip():
                    continue
                if all(line.strip().startswith(('Thanks', 'Best', 'Regards', '+1')) 
                      for line in section.strip().split('\n')):
                    continue
                original_section = section
                break
            
            if original_section:
                # Process the section same as HTML content
                headers = {}
                lines = original_section.split('\n')
                message_lines = []
                in_headers = True
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                        
                    if in_headers:
                        header_match = re.match(r'^(From|To|Subject|Date|Sent):\s*(.+)$', line)
                        if header_match:
                            key, value = header_match.groups()
                            headers[key] = value.strip()
                            continue
                        else:
                            in_headers = False
                    
                    if not any(sig in line for sig in ['Thanks & Regards', 'Best regards', '+1', 'http://']):
                        message_lines.append(line)
                
                formatted_parts = []
                for header in ['From', 'To', 'Date', 'Subject']:
                    if header in headers:
                        formatted_parts.append(f"{header}: {headers[header]}")
                
                formatted_parts.append("\n" + "-" * 50 + "\n")
                
                if message_lines:
                    formatted_parts.append('\n'.join(message_lines).strip())
                
                return '\n'.join(formatted_parts)
            
            return text_content
            
    except Exception as e:
        current_app.logger.error(f"Error formatting email: {e}")
        return text_content

def get_original_sender(email_content, support_email):
    """
    Extract the original sender from any type of forwarded email.
    Returns tuple of (sender_name, sender_email)
    """
    try:
        if '<html' in email_content:
            soup = BeautifulSoup(email_content, 'html.parser')
            
            # Get all text content first
            full_text = soup.get_text()
            
            # Common forwarded message patterns
            forwarded_patterns = [
                r'From:\s*(?:"?([^"<]*)"?\s*)?<?([^>\s]+@[^>\s]+)>?',
                r'To:\s*(?:"?([^"<]*)"?\s*)?<?([^>\s]+@[^>\s]+)>?',
                r'(?:Reply-To|Return-Path):\s*(?:"?([^"<]*)"?\s*)?<?([^>\s]+@[^>\s]+)>?',
                r'(?:[^@\s]+@[^@\s]+\.[^@\s]+)',  # Generic email pattern
            ]
            
            # Find all email addresses and associated names
            candidates = []
            for pattern in forwarded_patterns:
                matches = re.finditer(pattern, full_text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    if len(match.groups()) >= 2:
                        name = match.group(1).strip() if match.group(1) else ''
                        email = match.group(2).strip()
                    else:
                        email = match.group(0).strip()
                        name = ''
                    
                    # Skip system emails and support email
                    if (not email.endswith(('.mlsender.net', '.mailersend.net', 'cloudmailin.net')) and 
                        email.lower() != support_email.lower()):
                        candidates.append((name, email))
            
            # Try to find the most likely original sender
            for name, email in candidates:
                # Skip obvious system or notification emails
                if not any(skip in email.lower() for skip in ['noreply', 'no-reply', 'notification', 'alert']):
                    current_app.logger.info(f"Found likely sender: {name} <{email}>")
                    return name, email
            
            # If no good candidates, try one more generic search
            email_matches = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', full_text)
            for email in email_matches:
                if (not email.endswith(('.mlsender.net', '.mailersend.net', 'cloudmailin.net')) and 
                    email.lower() != support_email.lower() and
                    not any(skip in email.lower() for skip in ['noreply', 'no-reply', 'notification', 'alert'])):
                    name = email.split('@')[0]
                    current_app.logger.info(f"Found email in content: {name} <{email}>")
                    return name, email

        current_app.logger.error("Could not find original sender")
        current_app.logger.error("Email content:")
        current_app.logger.error(email_content)
        return None, None
        
    except Exception as e:
        current_app.logger.error(f"Error extracting original sender: {e}")
        current_app.logger.error("Email content:")
        current_app.logger.error(email_content)
        return None, None

def get_original_message(email_content):
    """
    Extract the original message from a forwarded email.
    Returns the original message content.
    """
    try:
        if '<html' in email_content:
            # Parse HTML content
            soup = BeautifulSoup(email_content, 'html.parser')
            
            # First try to find the message in the main content area
            main_content = soup.find('div', class_='elementToProof')
            if main_content and main_content.get_text().strip():
                return main_content.get_text().strip()
            
            # If not found, look for the forwarded message
            reply_div = soup.find('div', id='divRplyFwdMsg')
            if reply_div:
                # Get all divs after the reply div
                message_div = reply_div.find_next('div')
                while message_div:
                    # Skip if this div is empty or contains a signature
                    text = message_div.get_text().strip()
                    if text and not any(sig in text.lower() for sig in [
                        'thanks & regards',
                        'best regards',
                        'regards',
                        '--',
                        '+1'
                    ]):
                        # Found the message content
                        return text
                    message_div = message_div.find_next('div')
            
            # If still not found, try to find any div with content
            for div in soup.find_all('div', dir='ltr'):
                text = div.get_text().strip()
                if text and not any(sig in text.lower() for sig in [
                    'thanks & regards',
                    'best regards',
                    'regards',
                    '--',
                    '+1'
                ]) and not div.find(class_='x_gmail_signature'):
                    return text
            
            current_app.logger.error("Could not find original message in HTML")
            return "No message content found"
            
        else:
            # Handle plain text content
            lines = email_content.split('\n')
            message_lines = []
            found_message = False
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Skip headers and signatures
                if any(line.startswith(prefix) for prefix in ['From:', 'To:', 'Subject:', 'Date:', 'Sent:']):
                    continue
                    
                if any(sig in line for sig in ['Thanks & Regards', 'Best regards', 'Regards', '--', '+1']):
                    continue
                    
                message_lines.append(line)
            
            if message_lines:
                return '\n'.join(message_lines)
            
            current_app.logger.error("Could not find original message in text")
            return "No message content found"
        
    except Exception as e:
        current_app.logger.error(f"Error extracting original message: {e}")
        current_app.logger.error(f"Content: {email_content[:500]}...")  # Log first 500 chars
        return "Error extracting message content"

def extract_original_sender(plain_text, html_content, envelope_from, envelope_to):
    """Extract original sender and tenant info from forwarded message"""
    try:
        original_sender = None
        forwarding_email = envelope_from

        # Gmail format
        if '---------- Forwarded message ---------' in plain_text:
            match = re.search(
                r'From: [^<]*<([^>]+)>.*?(?=\nTo:)',
                plain_text,
                re.DOTALL
            )
            if match:
                original_sender = match.group(1)

        # MS365 format
        elif 'From:' in plain_text and '________________________________' in plain_text:
            match = re.search(
                r'From: [^<]*<([^>]+)>.*?(?=\nTo:|\nSent:)',
                plain_text,
                re.DOTALL
            )
            if match:
                original_sender = match.group(1)

        # If no match found, try HTML content
        if not original_sender and html_content:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Try Gmail format
            gmail_div = soup.find('div', class_='gmail_quote')
            if gmail_div:
                email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', gmail_div.get_text())
                if email_match:
                    original_sender = email_match.group(0)
            
            # Try MS365 format
            if not original_sender:
                divRplyFwdMsg = soup.find('div', id='divRplyFwdMsg')
                if divRplyFwdMsg:
                    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', divRplyFwdMsg.get_text())
                    if email_match:
                        original_sender = email_match.group(0)

        return {
            'original_sender': original_sender or envelope_from,
            'tenant_email': forwarding_email,
        }

    except Exception as e:
        current_app.logger.error(f"Error extracting sender info: {e}")
        return {
            'original_sender': envelope_from,
            'tenant_email': envelope_from
        }
@webhook.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, current_app.config['STRIPE_WEBHOOK_SECRET']
        )
        
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            
            # Log the session details
            current_app.logger.info(f"Processing checkout session: {session.id}")
            current_app.logger.info(f"Metadata: {session.metadata}")
            
            # Add this check to verify payment status
            if session.payment_status != 'paid':
                current_app.logger.error(f"Payment not completed. Status: {session.payment_status}")
                return jsonify({'error': 'Payment not completed'}), 400

            if 'company_name' in session.metadata:
                # This is a new registration
                try:
                    # Create the tenant
                    tenant = Tenant(
                        name=session.metadata['company_name'],
                        subscription_plan=session.metadata['plan'],
                        subscription_status='active',
                        subscription_starts_at=datetime.utcnow(),
                        subscription_ends_at=datetime.utcnow() + timedelta(days=30),
                        auto_renew=False  # Default to off
                    )
                    db.session.add(tenant)
                    db.session.flush()  # Get tenant ID
                    
                    # Create payment record for new registration too
                    payment = SubscriptionPayment(
                        tenant_id=tenant.id,
                        plan=session.metadata['plan'],
                        amount=get_plan_amount(session.metadata['plan']),
                        status='completed',
                        payment_id=session.subscription,
                        completed_at=datetime.utcnow()
                    )
                    db.session.add(payment)
                    
                    # Create the user
                    user = User(
                        email=session.metadata['email'],
                        first_name=session.metadata['first_name'],
                        last_name=session.metadata['last_name'],
                        role='admin',
                        tenant_id=tenant.id
                    )
                    user.set_password(session.metadata['password'])
                    
                    db.session.add(user)
                    db.session.commit()
                    
                    current_app.logger.info(f"Created new tenant {tenant.id} with plan {tenant.subscription_plan}")
                    
                except Exception as e:
                    current_app.logger.error(f"Error creating tenant: {str(e)}")
                    db.session.rollback()
                    raise
                    
            elif 'tenant_id' in session.metadata:
                # This is an upgrade
                tenant_id = session.metadata['tenant_id']
                plan = session.metadata['plan']
                
                tenant = Tenant.query.get(tenant_id)
                if tenant:
                    # Update all subscription fields
                    tenant.subscription_plan = plan
                    tenant.subscription_status = 'active'
                    tenant.subscription_starts_at = datetime.utcnow()
                    tenant.subscription_ends_at = datetime.utcnow() + timedelta(days=30)
                    # Remove auto_renew setting - keep existing value
                    
                    # Create payment record
                    payment = SubscriptionPayment(
                        tenant_id=tenant.id,
                        plan=plan,
                        amount=get_plan_amount(plan),
                        status='completed',
                        payment_id=session.subscription,
                        completed_at=datetime.utcnow()
                    )
                    
                    db.session.add(payment)
                    db.session.commit()
                    
                    current_app.logger.info(f"Successfully upgraded tenant {tenant_id} to {plan}")
                else:
                    current_app.logger.error(f"Tenant not found: {tenant_id}")
            else:
                current_app.logger.error("Invalid metadata in session")
                
        return jsonify({'status': 'success'})
        
    except Exception as e:
        current_app.logger.error(f"Webhook error: {str(e)}")
        return jsonify({'error': str(e)}), 400 

@webhook.route('/api/email/incoming', methods=['POST'])
@csrf_exempt
def email_webhook():
    try:
        # Check content type and get data accordingly
        if request.is_json:
            data = request.get_json()
        else:
            # Handle form data
            data = {
                'envelope': {
                    'from': request.form.get('envelope[from]'),
                    'to': request.form.get('envelope[to]')
                },
                'headers': {
                    'subject': request.form.get('headers[subject]', 'No Subject'),
                    'from': request.form.get('headers[from]')
                },
                'body': {
                    'html': request.form.get('html'),
                    'plain': request.form.get('plain')
                },
                'attachments': request.form.getlist('attachments[]')
            }
        
        current_app.logger.info("Received email webhook data")
        
        # Get envelope data (SMTP level information)
        envelope = data.get('envelope', {})
        envelope_from = envelope.get('from')
        envelope_to = envelope.get('to')
        
        # Get header information
        headers = data.get('headers', {})
        subject = headers.get('subject', 'No Subject')
        header_from = headers.get('from')
        
        # Get message body
        body = data.get('body', {})
        html_content = body.get('html')
        text_content = body.get('plain')
        content = html_content if html_content else text_content
        
        current_app.logger.info(f"Processing email from {envelope_from} to {envelope_to}")
        current_app.logger.info(f"Subject: {subject}")
        
        # Extract sender information
        sender_info = extract_original_sender(
            text_content,
            html_content,
            envelope_from,
            envelope_to
        )

        # Find tenant based on forwarding email
        tenant = Tenant.query.filter(
            db.or_(
                Tenant.support_email == sender_info['tenant_email'],
                Tenant.support_alias == sender_info['tenant_email'],
                Tenant.cloudmailin_address == sender_info['tenant_email']
            )
        ).first()

        if not tenant:
            current_app.logger.error(f"No tenant found for email: {sender_info['tenant_email']}")
            return jsonify({'error': 'Invalid tenant email'}), 400

        # Extract clean content
        content = extract_email_content(text_content, html_content)

        # Create ticket
        ticket = Ticket(
            title=subject,
            description=content,
            status='open',
            tenant_id=tenant.id,
            contact_email=sender_info['original_sender'],
            source='email',
            ticket_number=Ticket.generate_ticket_number(tenant.id)
        )

        db.session.add(ticket)
        db.session.commit()

        # Send confirmation email
        try:
            mailer = MailerSendService()
            mailer.send_ticket_confirmation(ticket)
        except Exception as e:
            current_app.logger.error(f"Error sending confirmation: {str(e)}")

        return jsonify({'message': 'Ticket created successfully', 'ticket_id': ticket.id}), 201

    except Exception as e:
        current_app.logger.error(f"Error processing email: {str(e)}")
        return jsonify({'error': str(e)}), 500 

@webhook.route('/api/email/test', methods=['GET'])
def test_webhook():
    return jsonify({'status': 'success', 'message': 'Webhook endpoint is accessible'}) 

@webhook.route('/api/email/addresses', methods=['GET'])
def list_addresses():
    """List all tenant email addresses (for testing)"""
    addresses = []
    tenants = Tenant.query.all()
    for tenant in tenants:
        addresses.append({
            'tenant': tenant.name,
            'email': tenant.cloudmailin_address
        })
    return jsonify(addresses) 

@webhook.route('/api/email/test-domains', methods=['GET'])
def test_email_domains():
    """Test endpoint to show domain mapping"""
    tenants = Tenant.query.all()
    results = []
    
    for tenant in tenants:
        test_email = f"test@{tenant.email_domain}" if tenant.email_domain else "No domain set"
        results.append({
            'tenant': tenant.name,
            'domain': tenant.email_domain,
            'test_email': test_email,
            'webhook_url': current_app.config['CLOUDMAILIN_WEBHOOK_URL']
        })
    
    return jsonify({
        'message': 'Use these details to test email tickets',
        'note': 'Send emails to CloudMailin address from these domains',
        'cloudmailin_address': current_app.config['CLOUDMAILIN_ADDRESS'],
        'tenants': results
    }) 

@webhook.route('/email', methods=['POST'])
@csrf_exempt
def handle_email():
    try:
        data = request.get_json()
        
        # Extract email content and headers
        html_body = data.get('html', '')
        text_body = data.get('plain', '')
        headers = data.get('headers', {})
        
        # Get sender information - try multiple possible header fields
        from_email = None
        possible_headers = ['from', 'From', 'Reply-To', 'reply-to', 'Return-Path', 'return-path']
        
        for header in possible_headers:
            if header in headers:
                from_header = headers[header]
                # Extract email from various formats:
                # "John Doe <john@example.com>" or just "john@example.com"
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', from_header)
                if email_match:
                    from_email = email_match.group(0)
                    break
        
        if not from_email:
            # Try to find email in the forwarded message
            email_pattern = r'From:.*?<([\w\.-]+@[\w\.-]+\.\w+)>'
            forwarded_match = re.search(email_pattern, html_body, re.IGNORECASE | re.DOTALL)
            if forwarded_match:
                from_email = forwarded_match.group(1)
        
        if not from_email:
            # Log the full email content for debugging
            current_app.logger.error("Could not find original sender")
            current_app.logger.error("Email headers:")
            current_app.logger.error(headers)
            current_app.logger.error("Email content:")
            current_app.logger.error(html_body)
            return jsonify({'error': 'Could not determine sender'}), 400
        
        # Extract subject
        subject = headers.get('subject', '').strip()
        if not subject:
            # Try to extract subject from forwarded message
            subject_match = re.search(r'Subject: (.*?)\n', html_body, re.IGNORECASE)
            if subject_match:
                subject = subject_match.group(1).strip()
            else:
                subject = "Email Ticket"
        
        # Get the tenant based on the support email
        to_email = headers.get('to', '').lower()
        tenant = Tenant.query.filter(
            db.or_(
                Tenant.support_email == to_email,
                Tenant.support_alias == to_email,
                Tenant.cloudmailin_address == to_email
            )
        ).first()
        
        if not tenant:
            current_app.logger.error(f"No tenant found for support email: {to_email}")
            return jsonify({'error': 'Invalid support email'}), 400
            
        # Create the ticket
        ticket = Ticket(
            title=subject,
            description=html_body or text_body,
            tenant_id=tenant.id,
            contact_email=from_email,
            source='email',
            ticket_number=Ticket.generate_ticket_number(tenant.id)
        )
        
        db.session.add(ticket)
        db.session.commit()
        
        # Send confirmation email
        try:
            mailer = MailerSendService()
            mailer.send_ticket_confirmation(ticket)
        except Exception as e:
            current_app.logger.error(f"Error sending confirmation: {str(e)}")
        
        return jsonify({'message': 'Ticket created successfully', 'ticket_id': ticket.id}), 201
        
    except Exception as e:
        current_app.logger.error(f"Error processing email: {str(e)}")
        return jsonify({'error': str(e)}), 500 