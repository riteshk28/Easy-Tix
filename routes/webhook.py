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
from flask_wtf.csrf import CSRFProtect
from services.mailersend_service import MailerSendService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

webhook = Blueprint('webhook', __name__)

def extract_email_content(text_content, html_content):
    """Extract clean email content from forwarded messages with improved parsing"""
    try:
        # Initialize HTML2Text with better config
        h = HTML2Text()
        h.ignore_links = False 
        h.ignore_images = True
        h.body_width = 0  # Don't wrap lines
        h.unicode_snob = True
        h.protect_links = True
        h.single_line_break = False  # Preserve multiple line breaks
        h.ul_item_mark = '-'
        
        # Convert HTML to text if available
        if html_content:
            text_from_html = h.handle(html_content)
            main_content = text_from_html if len(text_from_html) > len(text_content) else text_content
        else:
            main_content = text_content

        # First try to find the forwarded content block
        forwarding_headers = [
            'From:',
            'Sent:',
            'To:',
            'Subject:',
            '---------- Forwarded message ---------',
            '----- Forwarded Message -----',
            'Begin forwarded message:'
        ]

        lines = main_content.split('\n')
        content_lines = []
        in_header = False
        header_count = 0
        last_line_empty = False
        
        for line in lines:
            line = line.rstrip()  # Keep leading whitespace but remove trailing
            
            # Check if this is a header line
            if any(header in line for header in forwarding_headers):
                in_header = True
                header_count += 1
                continue
                
            # After we've seen at least 3 headers, start capturing content
            if header_count >= 3 and not any(marker in line.lower() for marker in [
                'from:', 'to:', 'sent:', 'date:', 'subject:',
                'cc:', 'bcc:', 'reply-to:', '>', '|',
                'get outlook', 'thanks & regards',
                'original message', '________________________________',
                'forwarded message'
            ]):
                # Preserve paragraph breaks by not collapsing multiple empty lines
                if not line:
                    if not last_line_empty:
                        content_lines.append(line)
                        last_line_empty = True
                else:
                    content_lines.append(line)
                    last_line_empty = False
                    
        if content_lines:
            # Remove trailing empty lines but keep paragraph breaks
            while content_lines and not content_lines[-1]:
                content_lines.pop()
            return '\n'.join(content_lines)

        # If the above method didn't work, try HTML parsing with better structure preservation
        if html_content:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script, style tags etc
            for element in soup(['script', 'style', 'head', 'title', 'meta']):
                element.decompose()

            # Process paragraphs and line breaks
            content_blocks = []
            for element in soup.find_all(['p', 'div', 'br', 'ul', 'ol', 'li']):
                if element.name == 'br':
                    content_blocks.append('')
                elif element.name in ['p', 'div']:
                    text = element.get_text().strip()
                    if text:
                        content_blocks.append(text)
                        content_blocks.append('')  # Add line break after paragraphs
                elif element.name in ['ul', 'ol']:
                    for li in element.find_all('li'):
                        content_blocks.append(f"• {li.get_text().strip()}")
                    content_blocks.append('')

            # Clean up and join blocks
            while content_blocks and not content_blocks[-1]:
                content_blocks.pop()
            return '\n'.join(content_blocks)

        return main_content

    except Exception as e:
        current_app.logger.error(f"Error extracting email content: {e}")
        return text_content

def format_email_content(text_content):
    """Format the content with improved structure preservation and signature handling"""
    try:
        if '<html' in text_content:
            soup = BeautifulSoup(text_content, 'html.parser')
            
            # Extract all text content while preserving structure
            content_blocks = []
            signature_blocks = []
            in_signature = False
            
            for element in soup.find_all(['p', 'div', 'br', 'ul', 'ol', 'li']):
                text = element.get_text().strip()
                
                # Check if this is likely the start of a signature
                if not in_signature and text and any(sig_marker in text.lower() for sig_marker in [
                    'thanks & regards',
                    'best regards',
                    'regards',
                    'thank you',
                    'thanks,',
                    'sincerely',
                    'cheers',
                ]):
                    in_signature = True
                
                if element.name == 'br':
                    if in_signature:
                        signature_blocks.append('')
                    else:
                        content_blocks.append('')
                elif element.name in ['ul', 'ol']:
                    items = []
                    for li in element.find_all('li'):
                        items.append(f"• {li.get_text().strip()}")
                    if in_signature:
                        signature_blocks.extend(items)
                    else:
                        content_blocks.extend(items)
                elif text:
                    if in_signature:
                        signature_blocks.append(text)
                    else:
                        content_blocks.append(text)
            
            # Join blocks with appropriate spacing
            formatted_content = []
            prev_block = ''
            
            # Add main content
            for block in content_blocks:
                if block != prev_block:  # Skip duplicates
                    if block and prev_block:
                        formatted_content.append('')
                    if block:
                        formatted_content.append(block)
                        prev_block = block
            
            # Add signature if present
            if signature_blocks:
                if formatted_content:
                    formatted_content.extend(['', '---'])  # Add separator before signature
                formatted_content.extend(signature_blocks)
            
            return '\n'.join(formatted_content)
            
        return text_content
        
    except Exception as e:
        current_app.logger.error(f"Error formatting email content: {e}")
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

@webhook.route('/webhook/test/email', methods=['GET'])
def test_email():
    """Test endpoint for email notifications"""
    try:
        test_email = request.args.get('email')
        if not test_email:
            return jsonify({'error': 'Please provide an email parameter'}), 400

        # Create a dummy ticket for testing
        test_tenant = Tenant.query.first()
        if not test_tenant:
            return jsonify({'error': 'No tenant found for testing'}), 400

        # Test all three channels
        results = []
        
        # 1. Test Manual Creation Channel
        manual_ticket = Ticket(
            title="Test Manual Ticket",
            description="Test ticket created via manual channel",
            status='open',
            priority='medium',
            tenant_id=test_tenant.id,
            contact_email=test_email,
            ticket_number=Ticket.generate_ticket_number(test_tenant.id),
            source='manual'
        )
        
        # 2. Test Portal Channel
        portal_ticket = Ticket(
            title="Test Portal Ticket",
            description="Test ticket created via portal",
            status='open',
            priority='medium',
            tenant_id=test_tenant.id,
            contact_email=test_email,
            ticket_number=Ticket.generate_ticket_number(test_tenant.id),
            source='portal'
        )
        
        # 3. Test Email Channel
        email_ticket = Ticket(
            title="Test Email Ticket",
            description="Test ticket created via email",
            status='open',
            priority='medium',
            tenant_id=test_tenant.id,
            contact_email=test_email,
            ticket_number=Ticket.generate_ticket_number(test_tenant.id),
            source='email'
        )

        # Test email sending for all channels
        mailer = MailerSendService()
        try:
            mailer.send_ticket_confirmation(manual_ticket)
            results.append({"channel": "manual", "status": "success"})
        except Exception as e:
            results.append({"channel": "manual", "status": "failed", "error": str(e)})

        try:
            mailer.send_ticket_confirmation(portal_ticket)
            results.append({"channel": "portal", "status": "success"})
        except Exception as e:
            results.append({"channel": "portal", "status": "failed", "error": str(e)})

        try:
            mailer.send_ticket_confirmation(email_ticket)
            results.append({"channel": "email", "status": "success"})
        except Exception as e:
            results.append({"channel": "email", "status": "failed", "error": str(e)})

        current_app.logger.info(f"Test emails sent to {test_email}")
        current_app.logger.info(f"Using tenant: {test_tenant.name}")

        return jsonify({
            'message': 'Test completed',
            'to': test_email,
            'tenant': test_tenant.name,
            'results': results,
            'mailersend_config': {
                'api_key_exists': bool(current_app.config.get('MAILERSEND_API_KEY')),
                'from_email': current_app.config.get('MAILERSEND_FROM_EMAIL'),
                'from_name': current_app.config.get('MAILERSEND_FROM_NAME')
            }
        })
    except Exception as e:
        current_app.logger.error(f"Test email error: {str(e)}")
        return jsonify({
            'error': str(e),
            'mailersend_config': {
                'api_key_exists': bool(current_app.config.get('MAILERSEND_API_KEY')),
                'from_email': current_app.config.get('MAILERSEND_FROM_EMAIL'),
                'from_name': current_app.config.get('MAILERSEND_FROM_NAME')
            }
        }), 500 