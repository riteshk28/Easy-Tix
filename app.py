from flask import Flask
from extensions import db, login_manager, migrate
from models import User
from config import Config
from sqlalchemy import exc
from functools import wraps
import time

from werkzeug.serving import is_running_from_reloader
import os



def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)  # Load configuration

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # Import blueprints
    from routes.auth import auth
    from routes.dashboard import dashboard
    from routes.tickets import tickets
    from routes.admin import admin
    from routes.superadmin import superadmin
    from routes.public import public
    from routes.landing import landing
    from routes.webhook import webhook

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