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
                            scheduled_sessions: List[Dict[str, Any]],
                            subject_time_tracking: Dict[int, Dict[int, int]] = None
                            ) -> List[Dict[str, Any]]:
        """Create a daily schedule based on subject allocation and preferences.
        
        Args:
            date: The target date to schedule
            subject_allocation: Dict mapping subject IDs to allocated hours
            scheduled_sessions: Already scheduled sessions to avoid conflicts
            subject_time_tracking: Optional tracking of which subjects have been scheduled at which hours
            
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
        
        # Build a set of booked time slots (with more granular tracking by 15-minute increments)
        # This allows for better detection of overlapping sessions
        booked_time_slots = set()
        
        # First add any existing sessions to booked_time_slots
        for session in scheduled_sessions:
            start = session['start_time']
            end = session['end_time']
            
            # Only consider sessions on the same day
            if start.date() == date.date():
                # Add all 15-minute slots covered by this session
                current = start
                while current < end:
                    # Create a unique identifier for each 15-min slot (hour and quarter)
                    slot_id = (current.hour, current.minute // 15)
                    booked_time_slots.add(slot_id)
                    current += datetime.timedelta(minutes=15)
        
        # Now properly filter out already booked hours entirely
        available_hours = [h for h in available_hours if not any(
            (h, quarter) in booked_time_slots for quarter in range(4)
        )]
        
        # Sort available hours to ensure consistent scheduling (instead of random shuffle)
        available_hours.sort()
        
        # For better subject rotation, create a queue that rotates through subjects
        # This helps ensure we don't schedule the same subject consecutively in a day
        subject_rotation_queue = []
        
        # Start with highest priority subjects that have allocation
        for subject_id, _ in subjects_by_priority:
            if remaining_allocation[subject_id] > 0:
                subject_rotation_queue.append(subject_id)
        
        # If no subjects have allocation, we're done
        if not subject_rotation_queue:
            return day_sessions
        
        # Loop through available hours and schedule sessions
        current_subject_index = 0
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
            
            # Check if this time slot is already booked (thorough check)
            time_slot_booked = False
            session_end_time = current_dt + datetime.timedelta(minutes=session_minutes)
            check_time = current_dt
            
            while check_time < session_end_time:
                slot_id = (check_time.hour, check_time.minute // 15)
                if slot_id in booked_time_slots:
                    time_slot_booked = True
                    break
                check_time += datetime.timedelta(minutes=15)
                
            if time_slot_booked:
                continue
                
            # Find a subject to schedule
            scheduled_subject = False
            attempted_subjects = set()  # Keep track of subjects we've tried
            
            # Start with the next subject in the rotation queue
            while len(attempted_subjects) < len(subject_rotation_queue):
                # Get the next subject from the rotation queue
                if current_subject_index >= len(subject_rotation_queue):
                    current_subject_index = 0
                    
                subject_id = subject_rotation_queue[current_subject_index]
                current_subject_index += 1
                
                if subject_id in attempted_subjects:
                    continue
                    
                attempted_subjects.add(subject_id)
                
                # Skip if no remaining allocation or max consecutive reached
                if remaining_allocation[subject_id] <= 0:
                    continue
                
                # Skip subjects that have reached max consecutive sessions
                if consecutive_sessions[subject_id] >= max_consecutive:
                    continue
                
                # Skip subjects that are already scheduled at this hour on multiple days
                if subject_time_tracking and subject_id in subject_time_tracking:
                    # If this subject has been scheduled at this hour too many times already
                    if subject_time_tracking[subject_id].get(hour, 0) >= 2:  # Allow max 2 occurrences
                        continue
                
                # Calculate session start and end times
                start_time = current_dt
                end_time = start_time + datetime.timedelta(minutes=session_minutes)
                
                # Create session
                session = {
                    'subject_id': subject_id,
                    'subject_name': subject_map[subject_id].name,
                    'start_time': start_time,
                    'end_time': end_time,
                    'color': subject_map[subject_id].color if hasattr(subject_map[subject_id], 'color') else "#3498db"
                }
                
                # Add session to the daily schedule
                day_sessions.append(session)
                
                # Mark these time slots as booked
                mark_time = start_time
                while mark_time < end_time:
                    slot_id = (mark_time.hour, mark_time.minute // 15)
                    booked_time_slots.add(slot_id)
                    mark_time += datetime.timedelta(minutes=15)
                
                # Update remaining allocation and consecutive sessions
                # Convert minutes to hours (e.g., 60 minutes = 1 hour allocation used)
                hours_used = session_minutes / 60
                remaining_allocation[subject_id] -= hours_used
                consecutive_sessions[subject_id] += hours_used
                
                # Update time tracking if provided
                if subject_time_tracking and subject_id in subject_time_tracking:
                    subject_time_tracking[subject_id][hour] = subject_time_tracking[subject_id].get(hour, 0) + 1
                
                scheduled_subject = True
                break
                
            if not scheduled_subject:
                continue
                
            # Add a break after this session
            if break_minutes > 0:
                break_end = end_time + datetime.timedelta(minutes=break_minutes)
                # Mark break time as booked
                mark_time = end_time
                while mark_time < break_end:
                    slot_id = (mark_time.hour, mark_time.minute // 15)
                    booked_time_slots.add(slot_id)
                    mark_time += datetime.timedelta(minutes=15)
        
        return day_sessions
    
    def generate_schedule(self) -> List[Dict[str, Any]]:
        """Generate a complete study schedule for the date range.
        
        Returns:
            List of dictionaries representing study sessions.
        """
        # Calculate how many hours to allocate to each subject
        total_subject_allocation = self.calculate_subject_allocation()
        
        # Initialize an empty schedule
        schedule = []
        
        # Calculate number of days in the date range
        date_range_days = (self.end_date.date() - self.start_date.date()).days + 1
        
        # Create a more balanced allocation across days
        # Instead of trying to schedule full allocation each day, divide it across the available days
        daily_allocation = {}
        for subject_id, total_hours in total_subject_allocation.items():
            # Get days per week from user preferences, default to 5
            days_per_week = 5
            if self.study_preference and hasattr(self.study_preference, 'days_per_week'):
                days_per_week = self.study_preference.days_per_week
            
            # Calculate how many hours per day for this subject
            # If the date range is less than a week, adjust accordingly
            if date_range_days < 7:
                effective_days = min(days_per_week, date_range_days)
            else:
                effective_days = days_per_week
            
            if effective_days > 0:
                hours_per_day = math.ceil(total_hours / effective_days)
            else:
                hours_per_day = total_hours  # Default if no effective days
                
            daily_allocation[subject_id] = hours_per_day
        
        # Create a tracking structure for allocation across the week
        # to prevent scheduling the same subject at the same time every day
        subject_time_tracking = {}  # subject_id -> {hour -> count}
        for subject_id in total_subject_allocation:
            subject_time_tracking[subject_id] = defaultdict(int)
        
        # Keep track of total hours allocated per subject
        hours_allocated = {subject_id: 0 for subject_id in total_subject_allocation}
        
        # For better distribution, we'll track subject allocations per day
        # and try to ensure each subject is studied at least once every two days
        days_since_last_studied = {subject_id: 0 for subject_id in total_subject_allocation}
        
        # Loop through each day in the date range
        current_date = self.start_date
        while current_date.date() <= self.end_date.date():
            # Increment days since last studied for tracking
            for subject_id in total_subject_allocation:
                days_since_last_studied[subject_id] += 1
            
            # For each day, create a daily allocation that considers:
            # 1. How much has already been allocated per subject
            # 2. How much should be allocated per day
            # 3. Days since last studied (to ensure variety)
            # 4. Maximum total hours across all subjects
            
            today_allocation = {}
            
            # First, prioritize subjects that haven't been studied in a while
            # (if they still have hours to allocate)
            overdue_subjects = sorted(
                [(subject_id, days) for subject_id, days in days_since_last_studied.items()
                 if days >= 2 and total_subject_allocation[subject_id] - hours_allocated[subject_id] > 0],
                key=lambda x: x[1],  # Sort by days since last studied
                reverse=True  # Highest first
            )
            
            # Allocate hours to overdue subjects first
            for subject_id, _ in overdue_subjects:
                remaining_hours = total_subject_allocation[subject_id] - hours_allocated[subject_id]
                if remaining_hours <= 0:
                    today_allocation[subject_id] = 0
                else:
                    # Don't schedule more than daily allocation or remaining hours
                    today_allocation[subject_id] = min(daily_allocation[subject_id], remaining_hours)
            
            # Then allocate to other subjects with remaining hours
            for subject_id, total_hours in total_subject_allocation.items():
                if subject_id in today_allocation:
                    continue  # Already allocated as an overdue subject
                    
                remaining_hours = total_hours - hours_allocated[subject_id]
                if remaining_hours <= 0:
                    today_allocation[subject_id] = 0
                else:
                    # Don't schedule more than daily allocation or remaining hours
                    today_allocation[subject_id] = min(daily_allocation[subject_id], remaining_hours)
            
            # Build daily schedule with this day's allocation
            daily_sessions = self.build_daily_schedule(
                current_date, 
                today_allocation,
                schedule,
                subject_time_tracking
            )
            
            # Update hours allocated for each subject and tracking info
            subjects_studied_today = set()
            for session in daily_sessions:
                subject_id = session['subject_id']
                subjects_studied_today.add(subject_id)
                
                # Calculate session duration in hours
                duration_hours = (session['end_time'] - session['start_time']).total_seconds() / 3600
                hours_allocated[subject_id] += duration_hours
                
                # Update time tracking to reduce likelihood of same subject at same time
                session_hour = session['start_time'].hour
                subject_time_tracking[subject_id][session_hour] += 1
            
            # Reset days counter for subjects studied today
            for subject_id in subjects_studied_today:
                days_since_last_studied[subject_id] = 0
            
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