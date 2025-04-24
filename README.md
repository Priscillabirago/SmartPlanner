# Ghana Smart Study Planner

![Ghana Smart Study Planner Logo](/static/img/logo.png)

A powerful study scheduling tool designed specifically for Ghanaian students to optimize their study time and improve academic performance.

## Features

- **Smart Schedule Generation**: Creates personalized study schedules based on subject priority, workload, difficulty, and upcoming exams
- **Dynamic Scheduling Algorithm**: Adapts to each student's study habits, preferences, and academic goals
- **User-Friendly Interface**: Modern, responsive web interface accessible on various devices
- **Visual Analytics**: Track your study progress with intuitive charts and statistics
- **Task Management**: Organize assignments and study goals for each subject
- **Calendar Integration**: View your study schedule in a familiar calendar interface
- **Ghana-Specific Design**: Tailored for the Ghanaian educational system and student needs

## Technology Stack

- **Backend**: Python with Flask framework
- **Database**: SQLite (SQLAlchemy ORM)
- **Frontend**: HTML, CSS, JavaScript, Bootstrap
- **Charts**: Chart.js
- **Calendar**: FullCalendar

## 🚀 Installation

### Prerequisites
- Python 3.7 or higher
- pip (Python package manager)
- Git

### Setup Instructions

1. Clone the repository or download:
   ```bash
   git clone https://github.com/yourusername/SmartPlanner.git
   cd SmartPlanner
   ```

2. Create and activate a virtual environment (optional but recommended):
   ```bash
   # On macOS/Linux
   python -m venv venv
   source venv/bin/activate
   
   # On Windows
   python -m venv venv
   venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   # Copy the example environment file
   cp .env.example .env
   
   # Edit the .env file and replace the placeholder values
   # Make sure to set a strong SECRET_KEY for security
   ```

5. Initialize the database:
   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

6. Run the application:
   ```bash
   python app.py
   ```

7. Access the application in your browser:
   ```
   http://127.0.0.1:5000/
   ```

## 📱 Usage

### Registration and Login
1. Create a new account with your email, name, and academic details
2. Log in to access your personalized dashboard

### Setting Up Your Subjects
1. Navigate to the Subjects section
2. Add new subjects with details like name, workload, priority, and exam dates
3. Use the color picker to assign unique colors to each subject for easy identification
4. Make other relevant changes in your user profile

### Generating Your Study Schedule
1. Go to the Schedule section
2. Click "Generate Schedule" to create your personalized study plan
3. View and manage your study sessions
4. 'Regenerate schedule whenever you update your information. For example, after adding a new subject, or even after editing anything in previous subjects'

### Tracking Progress
1. Mark study sessions as completed as you finish them
2. View statistics on your dashboard for completion rates and study distribution
3. Add notes to study sessions to track your productivity

## Environment Variables
The application uses the following environment variables:

- `FLASK_APP`: The entry point of the application (default: app.py)
- `FLASK_ENV`: The environment mode (development/production)
- `SECRET_KEY`: Secret key for session security (IMPORTANT: use a strong random key)
- `DATABASE_URL`: The database connection URL

## Project Structure

```
SmartPlanner/
├── app/                  # Application package
│   ├── __init__.py       # Application factory
│   └── routes/           # Blueprint routes
│       ├── auth.py       # Authentication routes
│       ├── main.py       # Main routes
│       ├── scheduler.py  # Scheduler routes
│       └── subjects.py   # Subject management routes
├── models/               # Database models
│   ├── database.py       # SQLAlchemy models
│   └── scheduler.py      # Scheduling algorithm
├── static/               # Static files
│   ├── css/              # CSS files
│   ├── js/               # JavaScript files
│   └── img/              # Images
├── templates/            # Jinja2 templates
│   ├── auth/             # Authentication templates
│   ├── main/             # Main page templates
│   ├── scheduler/        # Scheduler templates
│   ├── subjects/         # Subject management templates
│   └── base.html         # Base template
├── app.py                # Application entry point
├── requirements.txt      # Dependencies
├── .env                  # Environment variables (not committed to version control)
├── .env.example          # Example environment variables template
├── .gitignore            # Git ignore file
└── README.md             # Project documentation
```

