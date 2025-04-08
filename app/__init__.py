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
    
    return app 