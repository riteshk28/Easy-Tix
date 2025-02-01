from flask import Flask, render_template
from extensions import db, login_manager, migrate
from models import User
from config import Config
from sqlalchemy import exc
from functools import wraps
import time
from datetime import datetime

from werkzeug.serving import is_running_from_reloader
import os
from flask_wtf.csrf import CSRFProtect



def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)  # Load configuration
    app.secret_key = config_class.SECRET_KEY  # Make sure SECRET_KEY is in your Config

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf = CSRFProtect(app)

    # Register template filters
    def datetime_filter(value):
        if value is None:
            return ""
        return value.strftime('%Y-%m-%d %H:%M')
    app.jinja_env.filters['datetime'] = datetime_filter

    # Import blueprints
    from routes.auth import auth
    from routes.dashboard import dashboard
    from routes.tickets import tickets
    from routes.admin import admin
    from routes.superadmin import superadmin
    from routes.public import public
    from routes.landing import landing
    from routes.webhook import webhook

    # Exempt routes from CSRF protection
    csrf.exempt(webhook)  # Exempt webhook routes
    csrf.exempt(public)   # Exempt public portal routes

    # Register blueprints
    app.register_blueprint(landing, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(dashboard, url_prefix='/dashboard')
    app.register_blueprint(tickets, url_prefix='/tickets')
    app.register_blueprint(admin, url_prefix='/admin')
    app.register_blueprint(superadmin, url_prefix='/superadmin')
    app.register_blueprint(public, url_prefix='/public')
    app.register_blueprint(webhook)

    def retry_on_connection_error(max_retries=3, delay=1):
        def decorator(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                retries = 0
                while retries < max_retries:
                    try:
                        return f(*args, **kwargs)
                    except exc.OperationalError as e:
                        if "SSL connection has been closed unexpectedly" in str(e):
                            retries += 1
                            if retries == max_retries:
                                raise
                            time.sleep(delay)
                            continue
                        raise
                return f(*args, **kwargs)
            return wrapper
        return decorator

    @login_manager.user_loader
    @retry_on_connection_error()
    def load_user(user_id):
        return User.query.get(int(user_id))

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True) 