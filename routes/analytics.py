from flask import Blueprint, render_template, jsonify, current_app, request, send_file
from flask_login import login_required, current_user
from services.analytics_service import AnalyticsService
from models import Dashboard, ReportConfig, AnalyticsDashboard, Ticket, User, TicketComment
import csv
from io import StringIO, BytesIO
from datetime import datetime, timedelta
from extensions import db
from sqlalchemy import func, case

analytics = Blueprint('analytics', __name__)

@analytics.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """Analytics landing page"""
    return render_template('analytics/index.html')

@analytics.route('/data/<report_type>', methods=['GET'])
@login_required
def get_analytics_data(report_type):
    try:
        days = request.args.get('days', 30, type=int)
        data = None
        
        if report_type == 'summary':
            data = AnalyticsService.get_summary_metrics(current_user.tenant_id, days)
        elif report_type == 'tickets_by_status':
            data = AnalyticsService.get_tickets_by_status(current_user.tenant_id, days)
        elif report_type == 'response_times':
            data = AnalyticsService.get_response_times(current_user.tenant_id, days)
        elif report_type == 'sla_compliance':
            data = AnalyticsService.get_sla_compliance(current_user.tenant_id, days)
        elif report_type == 'agent_performance':
            data = AnalyticsService.get_agent_performance(current_user.tenant_id, days)
        
        if data is None:
            return jsonify({'error': 'Invalid report type'}), 400
            
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Error getting analytics data: {str(e)}")
        return jsonify({'error': str(e)}), 500

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
    try:
        # Get filter parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        status = request.args.getlist('status')
        priority = request.args.getlist('priority')
        assigned_to = request.args.getlist('assigned_to')
        
        # Get filtered data
        tickets = AnalyticsService.get_filtered_tickets(
            tenant_id=current_user.tenant_id,
            start_date=start_date,
            end_date=end_date,
            status=status,
            priority=priority,
            assigned_to=assigned_to
        )
        
        # Create CSV file in memory
        output = BytesIO()
        
        # Create a string buffer for CSV writing
        string_buffer = StringIO()
        writer = csv.writer(string_buffer)
        
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
        
        # Get the string value and encode it
        csv_data = string_buffer.getvalue().encode('utf-8-sig')  # utf-8-sig for Excel compatibility
        
        # Write to bytes buffer
        output.write(csv_data)
        
        # Prepare response
        output.seek(0)
        
        # Generate filename with date range
        if start_date and end_date:
            filename = f'tickets_{start_date}_to_{end_date}.csv'
        else:
            filename = f'tickets_export_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
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

@analytics.route('/dashboard-config')
@login_required
def get_dashboard_config():
    try:
        dashboard = AnalyticsDashboard.query.filter_by(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            is_default=True
        ).first()
        
        if not dashboard:
            # Return default layout if no saved configuration
            return jsonify({
                'layout': [
                    { 'x': 0, 'y': 0, 'w': 6, 'h': 4, 'id': 'ticketStatusItem' },
                    { 'x': 6, 'y': 0, 'w': 6, 'h': 4, 'id': 'responseTimeItem' },
                    { 'x': 0, 'y': 4, 'w': 6, 'h': 4, 'id': 'slaComplianceItem' },
                    { 'x': 6, 'y': 4, 'w': 6, 'h': 4, 'id': 'agentPerformanceItem' }
                ],
                'chartTypes': {
                    'ticketStatus': 'pie',
                    'responseTime': 'line',
                    'slaCompliance': 'line',
                    'agentPerformance': 'bar'
                }
            })
            
        return jsonify({
            'layout': dashboard.layout_config,
            'chartTypes': dashboard.chart_config.get('chartTypes', {}) if dashboard.chart_config else {}
        })
    except Exception as e:
        current_app.logger.error(f"Error getting dashboard config: {str(e)}")
        return jsonify({'error': str(e)}), 400

@analytics.route('/api/custom/tickets-by-category')
@login_required
def tickets_by_category():
    date_range = request.args.get('dateRange')
    start_date, end_date = parse_date_range(date_range)
    
    tickets = Ticket.query.filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date)
    ).with_entities(
        Ticket.category,
        func.count(Ticket.id)
    ).group_by(Ticket.category).all()
    
    return jsonify({
        'labels': [t[0] or 'Uncategorized' for t in tickets],
        'datasets': [{
            'data': [t[1] for t in tickets],
            'backgroundColor': ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b']
        }]
    })

@analytics.route('/api/custom/tickets-by-priority')
@login_required
def tickets_by_priority():
    date_range = request.args.get('dateRange')
    start_date, end_date = parse_date_range(date_range)
    
    tickets = Ticket.query.filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date)
    ).with_entities(
        Ticket.priority,
        func.count(Ticket.id)
    ).group_by(Ticket.priority).all()
    
    return jsonify({
        'labels': [t[0].capitalize() for t in tickets],
        'datasets': [{
            'data': [t[1] for t in tickets],
            'backgroundColor': ['#4e73df', '#1cc88a', '#36b9cc']
        }]
    })

@analytics.route('/api/custom/response-time-trend')
@login_required
def response_time_trend():
    date_range = request.args.get('dateRange')
    start_date, end_date = parse_date_range(date_range)
    
    response_times = db.session.query(
        func.date(Ticket.created_at).label('date'),
        func.avg(TicketComment.created_at - Ticket.created_at).label('avg_response')
    ).join(
        TicketComment,
        Ticket.id == TicketComment.ticket_id
    ).filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date),
        TicketComment.is_response == True
    ).group_by(
        func.date(Ticket.created_at)
    ).order_by(
        func.date(Ticket.created_at)
    ).all()
    
    return jsonify({
        'labels': [rt.date.strftime('%Y-%m-%d') for rt in response_times],
        'datasets': [{
            'label': 'Average Response Time (hours)',
            'data': [float(rt.avg_response.total_seconds() / 3600) if rt.avg_response else 0 
                    for rt in response_times],
            'borderColor': '#4e73df',
            'fill': False
        }]
    })

@analytics.route('/api/custom/tickets-by-status')
@login_required
def tickets_by_status():
    date_range = request.args.get('dateRange')
    start_date, end_date = parse_date_range(date_range)
    
    tickets = Ticket.query.filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date)
    ).with_entities(
        Ticket.status,
        func.count(Ticket.id)
    ).group_by(Ticket.status).all()
    
    return jsonify({
        'labels': [t[0].capitalize() for t in tickets],
        'datasets': [{
            'data': [t[1] for t in tickets],
            'backgroundColor': ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e']
        }]
    })

@analytics.route('/api/custom/agent-performance')
@login_required
def agent_performance():
    date_range = request.args.get('dateRange')
    start_date, end_date = parse_date_range(date_range)
    
    # Get agent performance metrics
    performance = db.session.query(
        User.name,
        func.count(Ticket.id).label('tickets_handled'),
        func.avg(case([(Ticket.status == 'closed', 1)], else_=0)).label('resolution_rate')
    ).join(
        Ticket, User.id == Ticket.assigned_to
    ).filter(
        User.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date)
    ).group_by(User.id, User.name).all()
    
    return jsonify({
        'labels': [p.name for p in performance],
        'datasets': [{
            'label': 'Tickets Handled',
            'data': [p.tickets_handled for p in performance],
            'backgroundColor': '#4e73df'
        }, {
            'label': 'Resolution Rate (%)',
            'data': [float(p.resolution_rate * 100) if p.resolution_rate else 0 for p in performance],
            'backgroundColor': '#1cc88a'
        }]
    })

@analytics.route('/api/custom/tickets-by-source')
@login_required
def tickets_by_source():
    date_range = request.args.get('dateRange')
    start_date, end_date = parse_date_range(date_range)
    
    tickets = Ticket.query.filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date)
    ).with_entities(
        Ticket.source,
        func.count(Ticket.id)
    ).group_by(Ticket.source).all()
    
    return jsonify({
        'labels': [t[0].capitalize() for t in tickets],
        'datasets': [{
            'data': [t[1] for t in tickets],
            'backgroundColor': ['#4e73df', '#1cc88a', '#36b9cc']
        }]
    })

@analytics.route('/api/custom/resolution-time-by-priority')
@login_required
def resolution_time_by_priority():
    date_range = request.args.get('dateRange')
    start_date, end_date = parse_date_range(date_range)
    
    resolution_times = db.session.query(
        Ticket.priority,
        func.avg(Ticket.resolved_at - Ticket.created_at).label('avg_resolution_time')
    ).filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date),
        Ticket.resolved_at.isnot(None)
    ).group_by(Ticket.priority).all()
    
    return jsonify({
        'labels': [rt.priority.capitalize() for rt in resolution_times],
        'datasets': [{
            'label': 'Average Resolution Time (hours)',
            'data': [float(rt.avg_resolution_time.total_seconds() / 3600) if rt.avg_resolution_time else 0 
                    for rt in resolution_times],
            'backgroundColor': ['#4e73df', '#1cc88a', '#36b9cc']
        }]
    })

@analytics.route('/api/custom/first-response-trend')
@login_required
def first_response_trend():
    date_range = request.args.get('dateRange')
    start_date, end_date = parse_date_range(date_range)
    
    response_times = db.session.query(
        func.date(Ticket.created_at).label('date'),
        func.avg(TicketComment.created_at - Ticket.created_at).label('avg_first_response')
    ).join(
        TicketComment,
        Ticket.id == TicketComment.ticket_id
    ).filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date),
        TicketComment.is_first_response == True
    ).group_by(
        func.date(Ticket.created_at)
    ).order_by(
        func.date(Ticket.created_at)
    ).all()
    
    return jsonify({
        'labels': [rt.date.strftime('%Y-%m-%d') for rt in response_times],
        'datasets': [{
            'label': 'First Response Time (hours)',
            'data': [float(rt.avg_first_response.total_seconds() / 3600) if rt.avg_first_response else 0 
                    for rt in response_times],
            'borderColor': '#4e73df',
            'fill': false
        }]
    })

@analytics.route('/api/custom/open-tickets-age')
@login_required
def open_tickets_age():
    date_range = request.args.get('dateRange')
    start_date, end_date = parse_date_range(date_range)
    
    now = datetime.now()
    tickets = db.session.query(
        case(
            (now - Ticket.created_at < timedelta(days=1), '<1 day'),
            (now - Ticket.created_at < timedelta(days=7), '1-7 days'),
            (now - Ticket.created_at < timedelta(days=30), '8-30 days'),
            else_='>30 days'
        ).label('age_group'),
        func.count(Ticket.id).label('count')
    ).filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.status != 'closed',
        Ticket.created_at.between(start_date, end_date)
    ).group_by('age_group').all()
    
    return jsonify({
        'labels': [t.age_group for t in tickets],
        'datasets': [{
            'data': [t.count for t in tickets],
            'backgroundColor': ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e']
        }]
    })

@analytics.route('/data/dashboard')
@login_required
@handle_analytics_errors
def get_dashboard_data():
    """Get all dashboard data in a single request"""
    try:
        days = request.args.get('days', 30, type=int)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Get summary metrics
        summary = get_summary_metrics(start_date, end_date)
        
        # Get chart data
        charts = {
            'ticketTrend': get_ticket_trend_data(start_date, end_date),
            'agentPerformance': get_agent_performance_data(start_date, end_date),
            'statusDistribution': get_status_distribution_data(start_date, end_date),
            'priorityAnalysis': get_priority_analysis_data(start_date, end_date),
            'responseTime': get_response_time_data(start_date, end_date),
            'categoryDistribution': get_category_distribution_data(start_date, end_date)
        }

        return jsonify({
            'summary': summary,
            'charts': charts
        })

    except Exception as e:
        current_app.logger.error(f"Error getting dashboard data: {str(e)}")
        return jsonify({'error': str(e)}), 500

def get_summary_metrics(start_date, end_date):
    """Get summary metrics for dashboard"""
    return {
        'openTickets': db.session.query(func.count(Ticket.id)).filter(
            Ticket.tenant_id == current_user.tenant_id,
            Ticket.status == 'open'
        ).scalar() or 0,
        
        'avgResponseTime': db.session.query(
            func.avg(
                func.extract('epoch', 
                    func.min(TicketComment.created_at) - Ticket.created_at
                ) / 3600
            )
        ).select_from(Ticket).join(
            TicketComment,
            (Ticket.id == TicketComment.ticket_id) & 
            (TicketComment.is_response == True)
        ).filter(
            Ticket.tenant_id == current_user.tenant_id,
            Ticket.created_at.between(start_date, end_date)
        ).scalar() or 0,
        
        'resolutionRate': calculate_resolution_rate(start_date, end_date),
        'slaCompliance': calculate_sla_compliance(start_date, end_date)
    }

def get_ticket_trend_data(start_date, end_date):
    """Get ticket trend data for line chart"""
    daily_tickets = db.session.query(
        func.date(Ticket.created_at).label('date'),
        func.count(Ticket.id).label('count')
    ).filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date)
    ).group_by(
        func.date(Ticket.created_at)
    ).order_by('date').all()

    return {
        'x': [dt.date.strftime('%Y-%m-%d') for dt in daily_tickets],
        'y': [dt.count for dt in daily_tickets],
        'type': 'scatter',
        'mode': 'lines+markers',
        'name': 'Daily Tickets'
    }

def parse_date_range(date_range):
    """Parse date range string into start and end dates"""
    if not date_range:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        return start_date, end_date
    
    start_str, end_str = date_range.split(' - ')
    start_date = datetime.strptime(start_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_str, '%Y-%m-%d') + timedelta(days=1)  # Include the end date
    return start_date, end_date 

def get_agent_performance_data(start_date, end_date):
    """Get agent performance data for bar chart"""
    performance = db.session.query(
        User.name,
        func.count(Ticket.id).label('tickets_handled'),
        func.avg(case([(Ticket.status == 'closed', 1)], else_=0)).label('resolution_rate')
    ).join(
        Ticket, User.id == Ticket.assigned_to
    ).filter(
        User.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date)
    ).group_by(User.id, User.name).all()

    return {
        'type': 'bar',
        'x': [p.name for p in performance],
        'y': [p.tickets_handled for p in performance],
        'name': 'Tickets Handled',
        'marker': {
            'color': '#4e73df'
        }
    }

def get_status_distribution_data(start_date, end_date):
    """Get status distribution data for pie chart"""
    status_counts = db.session.query(
        Ticket.status,
        func.count(Ticket.id).label('count')
    ).filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date)
    ).group_by(Ticket.status).all()

    return {
        'type': 'pie',
        'labels': [s.status.capitalize() for s in status_counts],
        'values': [s.count for s in status_counts],
        'marker': {
            'colors': ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e']
        }
    }

def get_priority_analysis_data(start_date, end_date):
    """Get priority analysis data for bar chart"""
    priority_data = db.session.query(
        Ticket.priority,
        func.count(Ticket.id).label('count')
    ).filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date)
    ).group_by(Ticket.priority).all()

    return {
        'type': 'bar',
        'x': [p.priority.capitalize() for p in priority_data],
        'y': [p.count for p in priority_data],
        'marker': {
            'color': ['#e74a3b', '#f6c23e', '#1cc88a']  # High, Medium, Low
        }
    }

def get_response_time_data(start_date, end_date):
    """Get response time analysis data for box plot"""
    response_times = db.session.query(
        Ticket.priority,
        func.extract('epoch', 
            func.min(TicketComment.created_at) - Ticket.created_at
        ).label('response_time')
    ).join(
        TicketComment,
        (Ticket.id == TicketComment.ticket_id) & 
        (TicketComment.is_response == True)
    ).filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date)
    ).group_by(
        Ticket.id,
        Ticket.priority
    ).all()

    # Organize data by priority
    data_by_priority = {}
    for rt in response_times:
        if rt.priority not in data_by_priority:
            data_by_priority[rt.priority] = []
        data_by_priority[rt.priority].append(rt.response_time / 3600)  # Convert to hours

    return {
        'type': 'box',
        'x': list(data_by_priority.keys()),
        'y': list(data_by_priority.values()),
        'marker': {
            'color': '#4e73df'
        }
    }

def get_category_distribution_data(start_date, end_date):
    """Get category distribution data for treemap"""
    categories = db.session.query(
        Ticket.category,
        Ticket.priority,
        func.count(Ticket.id).label('count')
    ).filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date)
    ).group_by(
        Ticket.category,
        Ticket.priority
    ).all()

    return {
        'type': 'treemap',
        'labels': [f"{c.category or 'Uncategorized'} - {c.priority}" for c in categories],
        'parents': [c.category or 'Uncategorized' for c in categories],
        'values': [c.count for c in categories],
        'marker': {
            'colors': ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b']
        }
    }

def calculate_resolution_rate(start_date, end_date):
    """Calculate ticket resolution rate"""
    total = db.session.query(func.count(Ticket.id)).filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date)
    ).scalar() or 0
    
    resolved = db.session.query(func.count(Ticket.id)).filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.status == 'closed',
        Ticket.created_at.between(start_date, end_date)
    ).scalar() or 0
    
    return resolved / total if total > 0 else 0

def calculate_sla_compliance(start_date, end_date):
    """Calculate SLA compliance rate"""
    total = db.session.query(func.count(Ticket.id)).filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date)
    ).scalar() or 0
    
    compliant = db.session.query(func.count(Ticket.id)).filter(
        Ticket.tenant_id == current_user.tenant_id,
        Ticket.created_at.between(start_date, end_date),
        Ticket.sla_breach.is_(False)
    ).scalar() or 0
    
    return compliant / total if total > 0 else 0 