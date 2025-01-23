from flask import Flask
from extensions import db, login_manager, migrate
from routes.auth import auth
from routes.dashboard import dashboard
from routes.admin import admin
from routes.tickets import tickets
from routes.public import public
from routes.webhooks import webhooks
from datetime import datetime
from commands.recalculate_sla import recalculate_sla

def create_app():
    app = Flask(__name__)
    app.config.from_object('config')
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # Register filters FIRST
    def format_duration(minutes):
        """Format minutes into a human-readable duration."""
        if not minutes:
            return "Not set"
        if not isinstance(minutes, (int, float)):
            return "Invalid input"
        
        days = minutes // 1440
        remaining_minutes = minutes % 1440
        hours = remaining_minutes // 60
        mins = remaining_minutes % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if mins > 0:
            parts.append(f"{mins} minute{'s' if mins != 1 else ''}")
        
        return ", ".join(parts) if parts else "0 minutes"
    
    # Register both ways to be safe
    app.jinja_env.filters['format_duration'] = format_duration
    app.template_filter('format_duration')(format_duration)
    
    @app.template_filter('datetime')
    def format_datetime(value):
        if value is None:
            return ""
        return value.strftime('%Y-%m-%d %H:%M')
    
    # Then register blueprints
    app.register_blueprint(auth)
    app.register_blueprint(dashboard)
    app.register_blueprint(admin, url_prefix='/admin')
    app.register_blueprint(tickets, url_prefix='/tickets')
    app.register_blueprint(public)
    app.register_blueprint(webhooks)
    
    # Context processor for template globals
    @app.context_processor
    def utility_processor():
        return {'now': datetime.utcnow}
    
    app.cli.add_command(recalculate_sla)
    
    return app 