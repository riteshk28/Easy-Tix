from flask import current_app
from models import db, Ticket, User, TicketActivity
from sqlalchemy import func, case
from datetime import datetime, timedelta

class AnalyticsService:
    @staticmethod
    def get_tickets_by_status(tenant_id, days=30):
        """Get ticket distribution by status"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        result = db.session.query(
            Ticket.status,
            func.count(Ticket.id)
        ).filter(
            Ticket.tenant_id == tenant_id,
            Ticket.created_at >= start_date
        ).group_by(Ticket.status).all()
        
        return {
            'labels': [r[0] for r in result],
            'datasets': [{
                'data': [r[1] for r in result],
                'backgroundColor': [
                    '#FF6384',  # red for open
                    '#36A2EB',  # blue for in_progress
                    '#FFCE56',  # yellow for pending
                    '#4BC0C0'   # green for resolved
                ]
            }]
        }

    @staticmethod
    def get_response_times(tenant_id, days=30):
        """Get average response times by day"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        result = db.session.query(
            func.date(Ticket.created_at),
            func.avg(
                func.extract('epoch', Ticket.first_response_at - Ticket.created_at) / 3600
            )
        ).filter(
            Ticket.tenant_id == tenant_id,
            Ticket.created_at >= start_date,
            Ticket.first_response_at.isnot(None)
        ).group_by(
            func.date(Ticket.created_at)
        ).order_by(
            func.date(Ticket.created_at)
        ).all()
        
        return {
            'labels': [r[0].strftime('%Y-%m-%d') for r in result],
            'datasets': [{
                'label': 'Average Response Time (hours)',
                'data': [float(r[1]) if r[1] else 0 for r in result],
                'borderColor': '#36A2EB',
                'fill': False
            }]
        }

    @staticmethod
    def get_sla_compliance(tenant_id, days=30):
        """Get SLA compliance rate by day"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        result = db.session.query(
            func.date(Ticket.created_at),
            func.count(Ticket.id).label('total'),
            func.sum(
                case(
                    (Ticket.sla_response_met.is_(True), 1),
                    else_=0
                )
            ).label('met')
        ).filter(
            Ticket.tenant_id == tenant_id,
            Ticket.created_at >= start_date,
            Ticket.sla_response_met.isnot(None)
        ).group_by(
            func.date(Ticket.created_at)
        ).order_by(
            func.date(Ticket.created_at)
        ).all()
        
        return {
            'labels': [r[0].strftime('%Y-%m-%d') for r in result],
            'datasets': [{
                'label': 'SLA Compliance Rate (%)',
                'data': [round((r[2] / r[1] * 100), 2) if r[1] > 0 else 0 for r in result],
                'borderColor': '#4BC0C0',
                'fill': False
            }]
        }

    @staticmethod
    def get_agent_performance(tenant_id, days=30):
        """Get agent performance metrics"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        result = db.session.query(
            User.email,
            func.count(Ticket.id).label('total_tickets'),
            func.avg(
                case(
                    (Ticket.sla_response_met.is_(True), 1),
                    else_=0
                )
            ).label('sla_rate')
        ).join(
            Ticket, Ticket.assigned_to_id == User.id
        ).filter(
            Ticket.tenant_id == tenant_id,
            Ticket.created_at >= start_date
        ).group_by(
            User.id, User.email
        ).all()
        
        return {
            'labels': [r[0] for r in result],
            'datasets': [{
                'label': 'Tickets Handled',
                'data': [r[1] for r in result],
                'backgroundColor': '#36A2EB'
            }, {
                'label': 'SLA Compliance Rate (%)',
                'data': [round(float(r[2] * 100), 2) if r[2] else 0 for r in result],
                'backgroundColor': '#4BC0C0'
            }]
        }

    @classmethod
    def get_summary_metrics(cls, tenant_id, days=30):
        """Get summary metrics for the dashboard"""
        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get tickets in date range
            tickets = Ticket.query.filter(
                Ticket.tenant_id == tenant_id,
                Ticket.created_at >= start_date,
                Ticket.created_at <= end_date
            ).all()
            
            if not tickets:
                return {
                    'open_tickets': 0,
                    'avg_response_time': 0,
                    'sla_compliance': 0,
                    'resolution_rate': 0
                }
            
            # Calculate open tickets
            open_tickets = len([t for t in tickets if t.status == 'open'])
            
            # Calculate average response time (in hours)
            response_times = []
            for ticket in tickets:
                if ticket.first_response_at:
                    response_time = (ticket.first_response_at - ticket.created_at).total_seconds() / 3600
                    response_times.append(response_time)
            avg_response_time = round(sum(response_times) / len(response_times)) if response_times else 0
            
            # Calculate SLA compliance
            total_sla_tickets = len([t for t in tickets if t.sla_response_due_at is not None])
            sla_met_tickets = len([t for t in tickets if t.sla_response_met and t.sla_resolution_met])
            sla_compliance = round((sla_met_tickets / total_sla_tickets * 100) if total_sla_tickets > 0 else 0)
            
            # Calculate resolution rate
            total_tickets = len(tickets)
            resolved_tickets = len([t for t in tickets if t.status == 'resolved'])
            resolution_rate = round((resolved_tickets / total_tickets * 100) if total_tickets > 0 else 0)
            
            return {
                'open_tickets': open_tickets,
                'avg_response_time': avg_response_time,
                'sla_compliance': sla_compliance,
                'resolution_rate': resolution_rate
            }
        except Exception as e:
            current_app.logger.error(f"Error getting summary metrics: {str(e)}")
            return None

    @staticmethod
    def get_filtered_tickets(tenant_id, start_date=None, end_date=None, status=None, priority=None, assigned_to=None):
        """Get filtered ticket data"""
        if not start_date or not end_date:
            raise ValueError("Date range is required")
        
        query = Ticket.query.filter(Ticket.tenant_id == tenant_id)
        
        # Date range is required
        query = query.filter(Ticket.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
        query = query.filter(Ticket.created_at <= datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
        
        # Status and priority are required
        if not status:
            raise ValueError("At least one status must be selected")
        if not priority:
            raise ValueError("At least one priority must be selected")
        
        query = query.filter(Ticket.status.in_(status))
        query = query.filter(Ticket.priority.in_(priority))
        
        if assigned_to:
            query = query.filter(Ticket.assigned_to_id.in_(assigned_to))
        
        return query.order_by(Ticket.created_at.desc()).all() 