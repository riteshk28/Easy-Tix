import jwt
import time
from flask import current_app
import requests
from models import Tenant, ReportConfig, Dashboard, DashboardReport
from sqlalchemy import text
from extensions import db

class MetabaseService:
    @staticmethod
    def generate_embed_url(tenant_id, dashboard_id):
        """Generate signed URL for Metabase dashboard embedding"""
        metabase_url = current_app.config['METABASE_URL']
        secret_key = current_app.config['METABASE_SECRET_KEY']

        payload = {
            "resource": {"dashboard": dashboard_id},
            "params": {
                "tenant_id": tenant_id
            },
            "exp": round(time.time()) + (60 * 60 * 24)
        }

        token = jwt.encode(
            payload,
            secret_key,
            algorithm="HS256"
        )

        return f"{metabase_url}/embed/dashboard/{token}#bordered=true&titled=true"

    @staticmethod
    def create_report(tenant_id, name, report_type, config):
        """Create a new report"""
        report = ReportConfig(
            tenant_id=tenant_id,
            name=name,
            type=report_type,
            query_config=config
        )
        db.session.add(report)
        db.session.commit()
        return report

    @staticmethod
    def get_report_data(report_id, tenant_id):
        """Get data for a specific report"""
        report = ReportConfig.query.filter_by(
            id=report_id,
            tenant_id=tenant_id
        ).first_or_404()

        # Execute the report query with tenant isolation
        query = report.query_config.get('query', '')
        params = {'tenant_id': tenant_id}
        
        result = db.session.execute(text(query), params)
        return [dict(row) for row in result]

    @staticmethod
    def create_dashboard(tenant_id, name, layout=None):
        """Create a new dashboard"""
        dashboard = Dashboard(
            tenant_id=tenant_id,
            name=name,
            layout_config=layout or {}
        )
        db.session.add(dashboard)
        db.session.commit()
        return dashboard

    @staticmethod
    def add_report_to_dashboard(dashboard_id, report_id, position):
        """Add a report to a dashboard"""
        dashboard_report = DashboardReport(
            dashboard_id=dashboard_id,
            report_id=report_id,
            position_config=position
        )
        db.session.add(dashboard_report)
        db.session.commit()
        return dashboard_report

    @staticmethod
    def get_available_metrics():
        """Get list of available metrics for report creation"""
        return {
            'ticket_volume': {
                'name': 'Ticket Volume',
                'query': """
                    SELECT DATE(created_at) as date, COUNT(*) as count 
                    FROM ticket 
                    WHERE tenant_id = :tenant_id 
                    GROUP BY DATE(created_at)
                    ORDER BY date
                """
            },
            'response_time': {
                'name': 'Response Time',
                'query': """
                    SELECT 
                        DATE(created_at) as date,
                        AVG(EXTRACT(EPOCH FROM (first_response_at - created_at))) as avg_response_time
                    FROM ticket 
                    WHERE tenant_id = :tenant_id 
                    AND first_response_at IS NOT NULL
                    GROUP BY DATE(created_at)
                    ORDER BY date
                """
            },
            'sla_compliance': {
                'name': 'SLA Compliance',
                'query': """
                    SELECT 
                        DATE(created_at) as date,
                        COUNT(CASE WHEN sla_response_met THEN 1 END) * 100.0 / COUNT(*) as compliance_rate
                    FROM ticket 
                    WHERE tenant_id = :tenant_id 
                    GROUP BY DATE(created_at)
                    ORDER BY date
                """
            }
        } 