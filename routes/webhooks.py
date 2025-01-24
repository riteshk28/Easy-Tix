from html2text import HTML2Text
from bs4 import BeautifulSoup
import re

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

        # Handle Office 365 forwarded emails
        if '* * *' in text_content:  # Office 365 separator
            parts = text_content.split('* * *')
            if len(parts) > 1:
                for part in parts:
                    if 'From:' in part and 'Subject:' in part:
                        header_end = part.find('Subject:')
                        if header_end != -1:
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
        
        for line in lines:
            line = line.rstrip()
            
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
                'Get Outlook for',
                '+1',
                '![](cid:'  # Skip image references
            ]):
                continue

            clean_lines.append(line)

        return '\n'.join(line for line in clean_lines if line.strip())

    except Exception as e:
        current_app.logger.error(f"Error extracting email content: {e}")
        return text_content

@webhooks.route('/api/email/incoming', methods=['POST'])
def email_webhook():
    try:
        data = request.get_json()
        
        # Get envelope data
        envelope = data.get('envelope', {})
        envelope_from = envelope.get('from')
        envelope_to = envelope.get('to')
        
        # Get header information
        headers = data.get('headers', {})
        subject = headers.get('subject', 'No Subject')
        from_email = None
        
        # Try multiple possible header fields for sender
        possible_headers = ['from', 'From', 'Reply-To', 'reply-to', 'Return-Path', 'return-path']
        for header in possible_headers:
            if header in headers:
                from_header = headers[header]
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', from_header)
                if email_match:
                    from_email = email_match.group(0)
                    break
                    
        if not from_email:
            # Try to find email in forwarded message
            email_pattern = r'From:.*?<([\w\.-]+@[\w\.-]+\.\w+)>'
            forwarded_match = re.search(email_pattern, data.get('html', ''), re.IGNORECASE | re.DOTALL)
            if forwarded_match:
                from_email = forwarded_match.group(1)
                
        if not from_email:
            current_app.logger.error("Could not find original sender")
            return jsonify({'error': 'Could not determine sender'}), 400

        # Find tenant based on multiple email fields
        tenant = Tenant.query.filter(
            db.or_(
                Tenant.support_email == envelope_to,
                Tenant.support_alias == envelope_to,
                Tenant.cloudmailin_address == envelope_to
            )
        ).first()

        if not tenant:
            current_app.logger.error(f"No tenant found for email: {envelope_to}")
            return jsonify({'error': 'Invalid tenant email'}), 400

        # Extract and clean content
        html_content = data.get('html')
        text_content = data.get('plain')
        content = extract_email_content(text_content, html_content)

        # Create ticket
        ticket = Ticket(
            title=subject,
            description=content,
            status='open',
            tenant_id=tenant.id,
            contact_email=from_email,
            source='email',
            ticket_number=Ticket.generate_ticket_number(tenant.id)
        )

        db.session.add(ticket)
        db.session.commit()
        
        # Calculate SLA deadlines
        ticket.calculate_sla_deadlines()
        db.session.commit()

        return jsonify({'message': 'Ticket created successfully', 'ticket_id': ticket.id}), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing email: {str(e)}")
        return jsonify({'error': str(e)}), 500 