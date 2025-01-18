from postmarker.core import PostmarkClient

class EmailService:
    def __init__(self, tenant):
        self.tenant = tenant
        self.client = PostmarkClient(server_token=tenant.email_config.postmark_api_key)
    
    def send_ticket_notification(self, ticket, comment):
        """Send email notification for ticket updates"""
        self.client.emails.send(
            From=self.tenant.email_config.email_address,
            To=ticket.contact_email,
            Subject=f"Re: [{ticket.id}] {ticket.title}",
            TextBody=comment.content,
            MessageStream="outbound",
            Headers=[
                {
                    "Name": "X-Ticket-ID",
                    "Value": str(ticket.id)
                }
            ]
        ) 