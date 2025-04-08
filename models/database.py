from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import json

db = SQLAlchemy()

class User(db.Model, UserMixin):
    """User model that represents students using the study planner."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    name = db.Column(db.String(64))
    school = db.Column(db.String(128))
    grade_level = db.Column(db.String(32))
    study_hours_per_week = db.Column(db.Integer, default=10)
    preferred_study_times = db.Column(db.String(256), default=json.dumps({
        "morning": False,
        "afternoon": False,
        "evening": True,
        "night": False
    }))
    academic_goals = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    subjects = db.relationship('Subject', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    study_sessions = db.relationship('StudySession', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_preferred_times(self):
        return json.loads(self.preferred_study_times)
    
    def set_preferred_times(self, preferences_dict):
        self.preferred_study_times = json.dumps(preferences_dict)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Subject(db.Model):
    """Subject model that represents academic subjects a student is studying."""
    __tablename__ = 'subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    workload = db.Column(db.Integer)  # Hours per week
    priority = db.Column(db.Integer)  # 1-5 scale
    difficulty = db.Column(db.Integer)  # 1-5 scale
    exam_date = db.Column(db.DateTime, nullable=True)
    color = db.Column(db.String(7), default="#3498db")  # Hex color code
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    study_sessions = db.relationship('StudySession', backref='subject', lazy='dynamic', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Subject {self.name}>'


class StudySession(db.Model):
    """Study session model that represents scheduled study blocks."""
    __tablename__ = 'study_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    completed = db.Column(db.Boolean, default=False)
    productivity_rating = db.Column(db.Integer, nullable=True)  # 1-5 scale
    notes = db.Column(db.Text)
    location = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def duration_minutes(self):
        """Calculate session duration in minutes."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 60
        return 0
    
    def __repr__(self):
        return f'<StudySession {self.subject.name if self.subject else "Unknown"} {self.start_time}>'


class Task(db.Model):
    """Task model that represents specific assignments or study goals."""
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    deadline = db.Column(db.DateTime, nullable=True)
    estimated_time = db.Column(db.Integer)  # Minutes
    completed = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer)  # 1-5 scale
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    subject = db.relationship('Subject', backref='tasks')
    
    def __repr__(self):
        return f'<Task {self.title}>'


class StudyPreference(db.Model):
    """Study preferences model that stores user's study habits and preferences."""
    __tablename__ = 'study_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    max_consecutive_hours = db.Column(db.Integer, default=2)
    break_duration = db.Column(db.Integer, default=15)  # Minutes
    preferred_session_length = db.Column(db.Integer, default=60)  # Minutes
    weekend_study = db.Column(db.Boolean, default=True)
    notification_preferences = db.Column(db.String(256), default=json.dumps({
        "email": True, 
        "browser": True,
        "reminder_time": 30  # Minutes before session
    }))
    
    # Relationships
    user = db.relationship('User', backref=db.backref('study_preference', uselist=False))
    
    def get_notification_prefs(self):
        return json.loads(self.notification_preferences)
    
    def set_notification_prefs(self, prefs_dict):
        self.notification_preferences = json.dumps(prefs_dict)
    
    def __repr__(self):
        return f'<StudyPreference for {self.user.username if self.user else "Unknown"}>' 