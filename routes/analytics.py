from flask import Blueprint, render_template, jsonify, current_app, request, send_file
from flask_login import login_required, current_user
from services.analytics_service import AnalyticsService
from models import Dashboard, ReportConfig
import csv
from io import StringIO, BytesIO
from datetime import datetime

analytics = Blueprint('analytics', __name__)

@analytics.route('/')
@login_required
def index():
    """Analytics landing page"""
    return render_template('analytics/index.html')

@analytics.route('/data/<report_type>')
@login_required
def get_analytics_data(report_type):
    """Get data for specific report type"""
    days = request.args.get('days', 30, type=int)
    
    data_functions = {
        'tickets_by_status': AnalyticsService.get_tickets_by_status,
        'response_times': AnalyticsService.get_response_times,
        'sla_compliance': AnalyticsService.get_sla_compliance,
        'agent_performance': AnalyticsService.get_agent_performance
    }
    
    if report_type not in data_functions:
        return jsonify({'error': 'Invalid report type'}), 400
        
    data = data_functions[report_type](current_user.tenant_id, days)
    return jsonify(data)

@analytics.route('/reports/new', methods=['GET', 'POST'])
@login_required
def create_report():
    if request.method == 'POST':
        data = request.json
        report = AnalyticsService.create_report(
            tenant_id=current_user.tenant_id,
            name=data['name'],
            report_type=data['type'],
            config=data['config']
        )
        return jsonify({'id': report.id})
        
    metrics = AnalyticsService.get_available_metrics()
    return render_template('analytics/create_report.html', metrics=metrics)

@analytics.route('/dashboards/new', methods=['GET', 'POST'])
@login_required
def create_dashboard():
    if request.method == 'POST':
        data = request.json
        dashboard = AnalyticsService.create_dashboard(
            tenant_id=current_user.tenant_id,
            name=data['name'],
            layout=data.get('layout')
        )
        return jsonify({'id': dashboard.id})
        
    reports = ReportConfig.query.filter_by(tenant_id=current_user.tenant_id).all()
    return render_template('analytics/create_dashboard.html', reports=reports)

@analytics.route('/reports/<int:report_id>/data')
@login_required
def get_report_data(report_id):
    """Get data for a specific report"""
    try:
        data = AnalyticsService.get_report_data(report_id, current_user.tenant_id)
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Error getting report data: {str(e)}")
        return jsonify({'error': str(e)}), 400

@analytics.route('/dashboard/<int:dashboard_id>')
@login_required
def view_dashboard(dashboard_id):
    dashboard = Dashboard.query.filter_by(
        id=dashboard_id, 
        tenant_id=current_user.tenant_id
    ).first_or_404()
    return render_template('analytics/dashboard.html', dashboard=dashboard)

@analytics.route('/export')
@login_required
def export_data():
    """Export analytics data to CSV"""
    days = request.args.get('days', 30, type=int)
    
    # Create CSV file in binary mode
    output = BytesIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['Report Type', 'Date', 'Metric', 'Value'])
    
    # Get all data
    ticket_status = AnalyticsService.get_tickets_by_status(current_user.tenant_id, days)
    response_times = AnalyticsService.get_response_times(current_user.tenant_id, days)
    sla_compliance = AnalyticsService.get_sla_compliance(current_user.tenant_id, days)
    agent_performance = AnalyticsService.get_agent_performance(current_user.tenant_id, days)
    
    # Write data
    for label, value in zip(ticket_status['labels'], ticket_status['datasets'][0]['data']):
        writer.writerow(['Ticket Status', datetime.utcnow().strftime('%Y-%m-%d'), label, value])
    
    for date, value in zip(response_times['labels'], response_times['datasets'][0]['data']):
        writer.writerow(['Response Time', date, 'Hours', value])
    
    for date, value in zip(sla_compliance['labels'], sla_compliance['datasets'][0]['data']):
        writer.writerow(['SLA Compliance', date, 'Percentage', value])
    
    for agent, tickets, sla in zip(
        agent_performance['labels'],
        agent_performance['datasets'][0]['data'],
        agent_performance['datasets'][1]['data']
    ):
        writer.writerow(['Agent Performance', datetime.utcnow().strftime('%Y-%m-%d'), f"{agent} - Tickets", tickets])
        writer.writerow(['Agent Performance', datetime.utcnow().strftime('%Y-%m-%d'), f"{agent} - SLA", sla])
    
    # Prepare response
    output.seek(0)
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'analytics_export_{datetime.utcnow().strftime("%Y%m%d")}.csv'
    )

@analytics.route('/raw-export')
@login_required
def export_raw_data():
    """Export raw ticket data with filters"""
    # Get filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.getlist('status')
    priority = request.args.getlist('priority')
    assigned_to = request.args.getlist('assigned_to')
    
    try:
        # Get filtered data
        tickets = AnalyticsService.get_filtered_tickets(
            tenant_id=current_user.tenant_id,
            start_date=start_date,
            end_date=end_date,
            status=status,
            priority=priority,
            assigned_to=assigned_to
        )
        
        # Create CSV file
        output = BytesIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow([
            'Ticket Number',
            'Title',
            'Status',
            'Priority',
            'Created At',
            'Updated At',
            'Assigned To',
            'Contact Name',
            'Contact Email',
            'First Response At',
            'Resolved At',
            'SLA Response Met',
            'SLA Resolution Met'
        ])
        
        # Write data
        for ticket in tickets:
            writer.writerow([
                ticket.ticket_number,
                ticket.title,
                ticket.status,
                ticket.priority,
                ticket.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                ticket.updated_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.updated_at else '',
                ticket.assigned_to.email if ticket.assigned_to else '',
                ticket.contact_name,
                ticket.contact_email,
                ticket.first_response_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.first_response_at else '',
                ticket.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.resolved_at else '',
                'Yes' if ticket.sla_response_met else 'No',
                'Yes' if ticket.sla_resolution_met else 'No'
            ])
        
        # Prepare response
        output.seek(0)
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'tickets_export_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        )
    except Exception as e:
        current_app.logger.error(f"Export error: {str(e)}")
        return jsonify({'error': str(e)}), 400

@analytics.route('/data/summary')
@login_required
def get_summary_data():
    """Get summary metrics data"""
    days = request.args.get('days', 30, type=int)
    data = AnalyticsService.get_summary_metrics(current_user.tenant_id, days)
    return jsonify(data) 