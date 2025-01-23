from flask.cli import with_appcontext
import click
from models import db, Ticket

@click.command('recalculate-sla')
@with_appcontext
def recalculate_sla():
    """Recalculate SLA for all tickets."""
    tickets = Ticket.query.all()
    for ticket in tickets:
        ticket.calculate_sla_deadlines()
    db.session.commit()
    click.echo(f"Recalculated SLA for {len(tickets)} tickets") 