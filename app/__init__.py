from flask import Flask
from extensions import db, login_manager, migrate
from routes.auth import auth
from routes.dashboard import dashboard
from routes.admin import admin, format_duration  # Import format_duration here
# ... other imports ...

def create_app():
    app = Flask(__name__)
    # ... other configurations ...

    # Register template filter
    app.jinja_env.filters['format_duration'] = format_duration

    # Register blueprints
    app.register_blueprint(auth)
    app.register_blueprint(dashboard)
    app.register_blueprint(admin, url_prefix='/admin')
    # ... other blueprints ...

    return app 