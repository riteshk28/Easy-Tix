from flask import Flask
from extensions import db, login_manager, migrate
from routes.auth import auth
from routes.dashboard import dashboard
from routes.admin import admin
from routes.tickets import tickets
from routes.public import public
from routes.webhooks import webhooks
from datetime import datetime
from template_filters import format_duration  # Import the filter

def create_app():
    app = Flask(__name__)
    app.config.from_object('config')
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # Register template filters BEFORE blueprints
    app.template_filter('format_duration')(format_duration)
    
    @app.template_filter('datetime')
    def format_datetime(value):
        if value is None:
            return ""
        return value.strftime('%Y-%m-%d %H:%M')
    
    # Register blueprints
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
    
    return app 