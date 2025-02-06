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

    @staticmethod
    def get_summary_metrics(tenant_id, days=30):
        """Get summary metrics for dashboard"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Open tickets count
        open_tickets = db.session.query(func.count(Ticket.id)).filter(
            Ticket.tenant_id == tenant_id,
            Ticket.status == 'open'
        ).scalar()
        
        # Average response time
        avg_response = db.session.query(
            func.avg(func.extract('epoch', Ticket.first_response_at - Ticket.created_at) / 3600)
        ).filter(
            Ticket.tenant_id == tenant_id,
            Ticket.created_at >= start_date,
            Ticket.first_response_at.isnot(None)
        ).scalar()
        
        # Overall SLA compliance
        sla_result = db.session.query(
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
        ).first()
        
        sla_rate = (sla_result[1] / sla_result[0] * 100) if sla_result[0] > 0 else 0
        
        # Resolution rate
        resolution_result = db.session.query(
            func.count(Ticket.id).label('total'),
            func.sum(
                case(
                    (Ticket.status == 'resolved', 1),
                    else_=0
                )
            ).label('resolved')
        ).filter(
            Ticket.tenant_id == tenant_id,
            Ticket.created_at >= start_date
        ).first()
        
        resolution_rate = (resolution_result[1] / resolution_result[0] * 100) if resolution_result[0] > 0 else 0
        
        return {
            'open_tickets': open_tickets,
            'avg_response_time': round(avg_response, 2) if avg_response else 0,
            'sla_compliance_rate': round(sla_rate, 2),
            'resolution_rate': round(resolution_rate, 2)
        }

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