from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    from app.routes.auth import auth_bp
    from app.routes.landing import landing_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.api import api_bp
    from app.routes.analyzer import analyzer_bp
    from app.routes.teacher import teacher_bp
    
    app.register_blueprint(landing_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(analyzer_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    # Ensure DB schema is up-to-date even if app.db already exists.
    # (create_all does not add new columns to existing tables.)
    with app.app_context():
        db.create_all()
        try:
            from app.services.db_migrations import ensure_schema
            ensure_schema(db)
        except Exception as e:
            print(f"Schema migration warning: {e}")

    return app
