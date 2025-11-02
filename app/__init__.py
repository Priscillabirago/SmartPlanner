import os
from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate

from models.database import db, User

def create_app(test_config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True,
                template_folder='../templates',
                static_folder='../static')
    
    # Load default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-key-for-testing'),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            'DATABASE_URL', 'sqlite:///study_planner.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False
    )
    if test_config:
        app.config.update(test_config)
    
    # Initialize database
    db.init_app(app)
    
    # Initialize migrations
    migrate = Migrate(app, db)
    
    # Initialize login manager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login."""
        return User.query.get(int(user_id))
    
    # Register Jinja2 template filters for timezone handling
    from utils.timezone_utils import utc_to_local, format_for_client
    from flask_login import current_user
    
    @app.template_filter('user_time')
    def user_time_filter(dt, format_str='%Y-%m-%d %H:%M'):
        """Convert UTC datetime to user's local time for display."""
        if dt is None:
            return ''
        try:
            if hasattr(current_user, 'timezone') and current_user.is_authenticated:
                return format_for_client(dt, current_user.timezone, format_str)
            else:
                return dt.strftime(format_str)
        except Exception:
            return dt.strftime(format_str) if dt else ''
    
    @app.template_filter('user_date')
    def user_date_filter(dt):
        """Convert UTC datetime to user's local date for display."""
        return user_time_filter(dt, '%Y-%m-%d')
    
    @app.template_filter('user_time_only')
    def user_time_only_filter(dt):
        """Convert UTC datetime to user's local time (time only) for display."""
        return user_time_filter(dt, '%H:%M')
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # Register blueprints
    from app.routes.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)
    
    from app.routes.main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    from app.routes.subjects import subjects as subjects_blueprint
    app.register_blueprint(subjects_blueprint)
    
    from app.routes.scheduler import scheduler as scheduler_blueprint
    app.register_blueprint(scheduler_blueprint)
    
    from app.routes.constraints import constraints as constraints_blueprint
    app.register_blueprint(constraints_blueprint)
    
    from app.routes.jobs import jobs as jobs_blueprint
    app.register_blueprint(jobs_blueprint)
    
    return app 