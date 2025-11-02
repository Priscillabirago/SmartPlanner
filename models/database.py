from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone, time
import json
import enum

# Constants
CASCADE_DELETE = "all, delete-orphan"
FK_USERS_ID = "users.id"
SUBJECTS_ID = "subjects.id"

# Create timezone-aware now function for defaults (using UTC)
def utc_now():
    return datetime.now(timezone.utc)

db = SQLAlchemy()


# Enums for session tracking
class SessionStatus(enum.Enum):
    """Status of a study session."""
    planned = "planned"
    completed = "completed"
    missed = "missed"
    canceled = "canceled"


class SessionType(enum.Enum):
    """Type of study session."""
    learn = "learn"            # Learning new material
    practice = "practice"      # Practicing problems/exercises
    review = "review"          # Reviewing for exams/spaced repetition
    assignment = "assignment"  # Working on homework/assignments


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
    timezone = db.Column(db.String(50), default='UTC', nullable=False)  # User's timezone (e.g., 'America/New_York')
    study_hours_per_week = db.Column(db.Integer, default=10)
    preferred_study_times = db.Column(db.String(256), default=json.dumps({
        "morning": False,
        "afternoon": False,
        "evening": True,
        "night": False
    }))
    academic_goals = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationships
    subjects = db.relationship('Subject', backref='user', lazy='dynamic', cascade=CASCADE_DELETE)
    study_sessions = db.relationship('StudySession', backref='user', lazy='dynamic', cascade=CASCADE_DELETE)
    constraints = db.relationship('UserConstraint', backref='user', lazy='dynamic', cascade=CASCADE_DELETE)
    class_blocks = db.relationship('ClassBlock', backref='user', lazy='dynamic', cascade=CASCADE_DELETE)
    
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
    __table_args__ = (
        db.CheckConstraint('priority >= 1 AND priority <= 5', name='check_priority_range'),
        db.CheckConstraint('difficulty >= 1 AND difficulty <= 5', name='check_difficulty_range'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(FK_USERS_ID), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    workload = db.Column(db.Integer)  # Hours per week
    priority = db.Column(db.Integer)  # 1-5 scale
    difficulty = db.Column(db.Integer)  # 1-5 scale
    exam_date = db.Column(db.DateTime, nullable=True)
    color = db.Column(db.String(7), default="#3498db")  
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationships
    study_sessions = db.relationship('StudySession', backref='subject', lazy='dynamic', cascade=CASCADE_DELETE)
    
    def __repr__(self):
        return f'<Subject {self.name}>'


class StudySession(db.Model):
    """Study session model that represents scheduled study blocks."""
    __tablename__ = 'study_sessions'
    __table_args__ = (
        db.Index('idx_user_start_time', 'user_id', 'start_time'),
        db.Index('idx_subject_id', 'subject_id'),
        db.Index('idx_status', 'status'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(FK_USERS_ID), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey(SUBJECTS_ID), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)  # Optional link to specific task
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    
    # Session categorization
    status = db.Column(db.Enum(SessionStatus), default=SessionStatus.planned, nullable=False)
    session_type = db.Column(db.Enum(SessionType), default=SessionType.learn, nullable=False)
    locked = db.Column(db.Boolean, default=False, nullable=False)  # Protect from regeneration
    
    # DEPRECATED: Keep completed for backward compatibility during migration
    # NOTE: Use `status` field as the source of truth (planned/completed/missed/canceled)
    # This boolean field is maintained for backward compatibility only
    # TODO: Remove this field in a future migration after confirming all code uses `status`
    completed = db.Column(db.Boolean, default=False)
    
    # Actual tracking (planned vs actual)
    actual_minutes = db.Column(db.Integer, nullable=True)  # How long they actually studied
    completed_at = db.Column(db.DateTime, nullable=True)   # When they marked it complete
    
    productivity_rating = db.Column(db.Integer, nullable=True)  # 1-5 scale
    notes = db.Column(db.Text)
    location = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationships
    task = db.relationship('Task', backref='study_sessions', foreign_keys=[task_id])
    
    def duration_minutes(self):
        """Calculate planned session duration in minutes."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 60
        return 0
    
    def get_actual_minutes(self):
        """Get actual study time, falling back to planned if not recorded."""
        if self.actual_minutes is not None:
            return self.actual_minutes
        # If completed but no actual time recorded, assume they did the full planned time
        if self.is_completed():
            return self.duration_minutes()
        return 0
    
    def get_adherence_percentage(self):
        """Calculate adherence: actual / planned * 100."""
        planned = self.duration_minutes()
        if planned == 0:
            return 0
        actual = self.get_actual_minutes()
        return min(100, (actual / planned) * 100)  # Cap at 100%
    
    def is_completed(self):
        """Check if session is completed (for backward compatibility)."""
        return self.status == SessionStatus.completed or self.completed
    
    def __repr__(self):
        return f'<StudySession {self.subject.name if self.subject else "Unknown"} {self.start_time} [{self.status.value if self.status else "planned"}]>'


class Task(db.Model):
    """Task model that represents specific assignments or study goals."""
    __tablename__ = 'tasks'
    __table_args__ = (
        db.Index('idx_user_subject', 'user_id', 'subject_id'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(FK_USERS_ID), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey(SUBJECTS_ID), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    deadline = db.Column(db.DateTime, nullable=True)
    estimated_time = db.Column(db.Integer)  # Minutes
    completed = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer)  # 1-5 scale
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationships
    subject = db.relationship('Subject', backref='tasks')
    
    def __repr__(self):
        return f'<Task {self.title}>'


class StudyPreference(db.Model):
    """Study preferences model that stores user's study habits and preferences."""
    __tablename__ = 'study_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(FK_USERS_ID), unique=True, nullable=False)
    max_consecutive_hours = db.Column(db.Integer, default=2)
    break_duration = db.Column(db.Integer, default=15)  # Minutes
    preferred_session_length = db.Column(db.Integer, default=60)  # Minutes
    weekend_study = db.Column(db.Boolean, default=True)
    grace_minutes = db.Column(db.Integer, default=30)  # Grace period before marking session as missed
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


class MakeupQueue(db.Model):
    """Queue for tracking missed session time that needs to be rescheduled."""
    __tablename__ = 'makeup_queue'
    __table_args__ = (
        db.Index('idx_makeup_user_subject', 'user_id', 'subject_id'),
        db.Index('idx_makeup_expires', 'expires_at'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(FK_USERS_ID), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey(SUBJECTS_ID), nullable=False)
    minutes = db.Column(db.Integer, nullable=False)  # Minutes of makeup time needed
    expires_at = db.Column(db.Date, nullable=False)  # Stop trying to reschedule after this date
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationships
    user = db.relationship('User', backref='makeup_queue')
    subject = db.relationship('Subject', backref='makeup_queue')
    
    def is_expired(self):
        """Check if this makeup queue entry has expired."""
        from datetime import date
        return date.today() > self.expires_at
    
    def __repr__(self):
        return f'<MakeupQueue {self.subject.name if self.subject else "Unknown"}: {self.minutes}min expires {self.expires_at}>'


class UserConstraint(db.Model):
    """User constraint model for blocking out busy times (work, activities, etc)."""
    __tablename__ = 'user_constraints'
    __table_args__ = (
        db.Index('idx_user_day', 'user_id', 'day_of_week'),
        db.CheckConstraint('day_of_week >= 0 AND day_of_week <= 6', name='check_day_range'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(FK_USERS_ID), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_hard = db.Column(db.Boolean, default=True, nullable=False)  # True = cannot schedule over
    created_at = db.Column(db.DateTime, default=utc_now)
    
    def __repr__(self):
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        day_name = days[self.day_of_week] if 0 <= self.day_of_week <= 6 else '?'
        return f'<UserConstraint {self.title} {day_name} {self.start_time}-{self.end_time}>'


class ClassBlock(db.Model):
    """Class block model for recurring weekly class schedules."""
    __tablename__ = 'class_blocks'
    __table_args__ = (
        db.Index('idx_class_user_day', 'user_id', 'day_of_week'),
        db.CheckConstraint('day_of_week >= 0 AND day_of_week <= 6', name='check_class_day_range'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(FK_USERS_ID), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    location = db.Column(db.String(128))
    color = db.Column(db.String(7), default="#6c757d")  # Gray by default
    created_at = db.Column(db.DateTime, default=utc_now)
    
    def __repr__(self):
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        day_name = days[self.day_of_week] if 0 <= self.day_of_week <= 6 else '?'
        return f'<ClassBlock {self.title} {day_name} {self.start_time}-{self.end_time}>' 