import os
from dotenv import load_dotenv
from app import create_app
from models.database import db

# Load environment variables
load_dotenv()

# Create Flask application
app = create_app()

# Create database tables if they don't exist
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(host=host, port=port, debug=debug) 