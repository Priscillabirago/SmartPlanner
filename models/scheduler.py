import datetime
import json
import math
import random
from collections import defaultdict
from typing import List, Dict, Tuple, Any, Optional

import pytz

# Ghana timezone
GHANA_TZ = pytz.timezone('Africa/Accra')


class StudyScheduler:
    """Advanced study scheduler that creates optimized study plans based on
    multiple factors including subject priority, workload, difficulty,
    upcoming exams, and user preferences.
    """
    
    def __init__(self, user, subjects, tasks=None, 
                 start_date=None, end_date=None):
        """Initialize the scheduler with user data and subjects."""
        self.user = user
        self.subjects = subjects
        self.tasks = tasks or []
        self.start_date = start_date or datetime.datetime.now(GHANA_TZ)
        
        # Default to 7 days scheduling period if not specified
        if end_date:
            self.end_date = end_date
        else:
            self.end_date = self.start_date + datetime.timedelta(days=7)
        
        # Get user preferences
        try:
            self.study_preference = user.study_preference
        except Exception:
            # Handle case where user doesn't have preferences set
            self.study_preference = None
        
        # Get preferred study times
        try:
            self.preferred_times = json.loads(user.preferred_study_times)
        except Exception:
            # Default preferences
            self.preferred_times = {
                "morning": False,
                "afternoon": False,
                "evening": True,
                "night": False
            }
    
    def get_time_of_day_ranges(self) -> Dict[str, Tuple[int, int]]:
        """Define the hour ranges for different times of day."""
        return {
            "morning": (5, 11),    # 5:00 AM - 11:59 AM
            "afternoon": (12, 16), # 12:00 PM - 4:59 PM
            "evening": (17, 21),   # 5:00 PM - 9:59 PM
            "night": (22, 4)       # 10:00 PM - 4:59 AM
        }
    
    def get_available_hours(self, date: datetime.datetime) -> List[int]:
        """Get the hours of the day that the user prefers to study."""
        available_hours = []
        time_ranges = self.get_time_of_day_ranges()
        
        # Check if we should include weekend study
        is_weekend = date.weekday() >= 5  # 5=Saturday, 6=Sunday
        if is_weekend and hasattr(self.study_preference, 'weekend_study'):
            if not self.study_preference.weekend_study:
                return []
        
        # Add hours based on preferred times of day
        for time_of_day, is_preferred in self.preferred_times.items():
            if is_preferred:
                start_hour, end_hour = time_ranges[time_of_day]
                if start_hour < end_hour:
                    # Normal range (e.g., 5-11)
                    available_hours.extend(range(start_hour, end_hour + 1))
                else:
                    # Overnight range (e.g., 22-4)
                    available_hours.extend(range(start_hour, 24))
                    available_hours.extend(range(0, end_hour + 1))
        
        return sorted(available_hours)
    
    def calculate_subject_weights(self) -> Dict[int, float]:
        """Calculate subject weights based on priority, workload, difficulty
        and proximity to exam date.
        """
        weights = {}
        today = datetime.datetime.now(GHANA_TZ).date()
        
        for subject in self.subjects:
            # Base weight from priority (scale 1-5)
            weight = subject.priority * 2
            
            # Add weight based on difficulty (more difficult = higher weight)
            if hasattr(subject, 'difficulty') and subject.difficulty:
                weight += subject.difficulty
            
            # Add weight based on exam proximity
            if hasattr(subject, 'exam_date') and subject.exam_date:
                days_to_exam = (subject.exam_date.date() - today).days
                if days_to_exam > 0:
                    if days_to_exam <= 7:  # Exam within a week
                        weight += 10
                    elif days_to_exam <= 14:  # Exam within two weeks
                        weight += 5
                    elif days_to_exam <= 30:  # Exam within a month
                        weight += 2
            
            weights[subject.id] = weight
        
        return weights
    
    def calculate_subject_allocation(self) -> Dict[int, int]:
        """Calculate how many hours to allocate to each subject based on
        weights and total available study hours.
        """
        weights = self.calculate_subject_weights()
        total_weight = sum(weights.values())
        total_study_hours = self.user.study_hours_per_week
        
        # Calculate proportional allocation
        allocation = {}
        for subject_id, weight in weights.items():
            # Calculate proportional hours (weight / total_weight * total_hours)
            if total_weight > 0:
                subject_hours = math.ceil((weight / total_weight) * total_study_hours)
            else:
                subject_hours = 1  # Default to 1 hour if no weights
            
            allocation[subject_id] = subject_hours
        
        # Adjust if total allocation exceeds available hours
        total_allocated = sum(allocation.values())
        if total_allocated > total_study_hours:
            excess = total_allocated - total_study_hours
            # Remove hours from lowest priority subjects
            sorted_by_weight = sorted(weights.items(), key=lambda x: x[1])
            for subject_id, _ in sorted_by_weight:
                if excess <= 0:
                    break
                if allocation[subject_id] > 1:
                    allocation[subject_id] -= 1
                    excess -= 1
        
        return allocation
    
    def get_session_length(self) -> int:
        """Get the preferred session length in minutes."""
        if (self.study_preference and 
                hasattr(self.study_preference, 'preferred_session_length')):
            return self.study_preference.preferred_session_length
        return 60  # Default to 1 hour
    
    def get_break_duration(self) -> int:
        """Get the preferred break duration in minutes."""
        if (self.study_preference and 
                hasattr(self.study_preference, 'break_duration')):
            return self.study_preference.break_duration
        return 15  # Default to 15 minutes
    
    def get_max_consecutive_hours(self) -> int:
        """Get the maximum number of consecutive study hours."""
        if (self.study_preference and 
                hasattr(self.study_preference, 'max_consecutive_hours')):
            return self.study_preference.max_consecutive_hours
        return 2  # Default to 2 hours
    
    def build_daily_schedule(self, 
                            date: datetime.datetime, 
                            subject_allocation: Dict[int, int],
                            scheduled_sessions: List[Dict[str, Any]]
                            ) -> List[Dict[str, Any]]:
        """Create a daily schedule based on subject allocation and preferences.
        
        Args:
            date: The target date to schedule
            subject_allocation: Dict mapping subject IDs to allocated hours
            scheduled_sessions: Already scheduled sessions to avoid conflicts
            
        Returns:
            List of scheduled study sessions for the day
        """
        day_sessions = []
        available_hours = self.get_available_hours(date)
        
        if not available_hours:
            return []  # No available hours for this day
        
        # Create a map of subject_id -> subject object
        subject_map = {subject.id: subject for subject in self.subjects}
        
        # Get remaining allocation for each subject
        remaining_allocation = subject_allocation.copy()
        
        # Sort subjects by priority and exam proximity
        subjects_by_priority = sorted(
            [(subject_id, subject_map[subject_id]) 
             for subject_id in remaining_allocation.keys()
             if subject_id in subject_map],
            key=lambda x: (
                -x[1].priority,  # Descending priority
                # Sort by exam date (None values last)
                x[1].exam_date if hasattr(x[1], 'exam_date') else datetime.datetime.max
            )
        )
        
        # Get session parameters
        session_minutes = self.get_session_length()
        break_minutes = self.get_break_duration()
        max_consecutive = self.get_max_consecutive_hours()
        
        # Track consecutive sessions for the same subject
        consecutive_sessions = defaultdict(int)
        
        # Check which hours are already booked in scheduled_sessions
        booked_hours = set()
        for session in scheduled_sessions:
            start = session['start_time']
            end = session['end_time']
            if start.date() == date.date():
                # Add all hours covered by this session
                current = start
                while current < end:
                    booked_hours.add(current.hour)
                    current += datetime.timedelta(hours=1)
        
        # Filter out already booked hours
        available_hours = [h for h in available_hours if h not in booked_hours]
        
        # Shuffle available hours to avoid bias to specific times
        random.shuffle(available_hours)
        
        # Loop through available hours and schedule sessions
        for hour in available_hours:
            # If no more allocation left, we're done
            if all(remaining <= 0 for remaining in remaining_allocation.values()):
                break
            
            # Create current datetime for this hour
            current_dt = date.replace(
                hour=hour, 
                minute=0, 
                second=0, 
                microsecond=0
            )
            
            # Find a subject to schedule
            for subject_id, subject in subjects_by_priority:
                if remaining_allocation[subject_id] <= 0:
                    continue
                
                # Check if we've reached max consecutive sessions for this subject
                if consecutive_sessions[subject_id] >= max_consecutive:
                    continue
                
                # Calculate session start and end times
                start_time = current_dt
                end_time = start_time + datetime.timedelta(minutes=session_minutes)
                
                # Create session
                session = {
                    'subject_id': subject_id,
                    'subject_name': subject.name,
                    'start_time': start_time,
                    'end_time': end_time,
                    'color': subject.color if hasattr(subject, 'color') else "#3498db"
                }
                
                day_sessions.append(session)
                
                # Update remaining allocation and consecutive sessions
                # Convert minutes to hours (e.g., 60 minutes = 1 hour allocation used)
                hours_used = session_minutes / 60
                remaining_allocation[subject_id] -= hours_used
                consecutive_sessions[subject_id] += hours_used
                
                # Add a break after this session (if not the last hour)
                if break_minutes > 0:
                    break_end = end_time + datetime.timedelta(minutes=break_minutes)
                    # This doesn't create an actual session, just advances the time
                    current_dt = break_end
                else:
                    current_dt = end_time
                
                # We've scheduled this hour, move to the next
                break
        
        return day_sessions
    
    def generate_schedule(self) -> List[Dict[str, Any]]:
        """Generate a complete study schedule for the date range.
        
        Returns:
            List of dictionaries representing study sessions.
        """
        # Calculate how many hours to allocate to each subject
        subject_allocation = self.calculate_subject_allocation()
        
        # Initialize an empty schedule
        schedule = []
        
        # Loop through each day in the date range
        current_date = self.start_date
        while current_date.date() <= self.end_date.date():
            # Build daily schedule
            daily_sessions = self.build_daily_schedule(
                current_date, 
                subject_allocation,
                schedule
            )
            
            # Add sessions to overall schedule
            schedule.extend(daily_sessions)
            
            # Move to next day
            current_date += datetime.timedelta(days=1)
        
        return schedule
    
    def save_schedule_to_db(self, schedule, db=None):
        """Save the generated schedule to the database.
        
        Args:
            schedule: List of session dictionaries
            db: SQLAlchemy database instance
        
        Returns:
            List of created session objects
        """
        from models.database import StudySession
        
        created_sessions = []
        for session in schedule:
            # Create a new StudySession object
            db_session = StudySession(
                user_id=self.user.id,
                subject_id=session['subject_id'],
                start_time=session['start_time'],
                end_time=session['end_time'],
                completed=False
            )
            
            if db:
                db.session.add(db_session)
                created_sessions.append(db_session)
        
        if db:
            db.session.commit()
        
        return created_sessions 