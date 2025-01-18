import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Ticket, Tenant
from sqlalchemy import text

def migrate_ticket_numbers():
    app = create_app()
    
    with app.app_context():
        print("\n=== Migrating Ticket Numbers ===\n")
        
        # Create backup of current ticket numbers
        print("Creating backup of current ticket numbers...")
        tickets_backup = {}
        tickets = Ticket.query.all()
        for ticket in tickets:
            tickets_backup[ticket.id] = ticket.ticket_number
            
        print(f"Found {len(tickets_backup)} tickets")
        
        try:
            # Update each tenant's tickets
            tenants = Tenant.query.all()
            for tenant in tenants:
                print(f"\nProcessing tenant: {tenant.name} (ID: {tenant.id})")
                
                # Get all tickets for this tenant
                tenant_tickets = Ticket.query.filter_by(tenant_id=tenant.id).order_by(Ticket.created_at).all()
                
                if not tenant_tickets:
                    print("  No tickets found")
                    continue
                
                print(f"  Found {len(tenant_tickets)} tickets")
                
                # New prefix format
                prefix = f"{tenant.name[:2].upper()}{tenant.id}"
                
                # Update each ticket
                for i, ticket in enumerate(tenant_tickets, 1):
                    old_number = ticket.ticket_number
                    new_number = f"{prefix}-{i:03d}"
                    
                    print(f"  {old_number} -> {new_number}")
                    ticket.ticket_number = new_number
                
                db.session.commit()
                print(f"  ✓ Updated {len(tenant_tickets)} tickets")
                
        except Exception as e:
            print(f"\n✗ Error during migration: {e}")
            print("\nRolling back changes...")
            
            # Restore original ticket numbers
            for ticket_id, old_number in tickets_backup.items():
                ticket = Ticket.query.get(ticket_id)
                if ticket:
                    ticket.ticket_number = old_number
            
            db.session.commit()
            print("✓ Rollback complete")
            return False
        
        print("\n✓ Migration completed successfully!")
        print("\nBackup of old ticket numbers:")
        for ticket_id, old_number in tickets_backup.items():
            ticket = Ticket.query.get(ticket_id)
            if ticket:
                print(f"ID {ticket_id}: {old_number} -> {ticket.ticket_number}")
        
        return True

if __name__ == '__main__':
    migrate_ticket_numbers() 