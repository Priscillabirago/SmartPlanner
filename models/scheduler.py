import datetime
import json
import math
import random
from collections import defaultdict
from typing import List, Dict, Tuple, Any, Optional


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
        self.start_date = start_date or datetime.datetime.now()
        
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
        is_weekend = date.weekday() >= 5
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
    
    def _get_exam_weight(self, subject, today) -> float:
        """Calculate weight bonus based on exam proximity."""
        if not hasattr(subject, 'exam_date') or not subject.exam_date:
            return 0
        
        days_to_exam = (subject.exam_date.date() - today).days
        if days_to_exam <= 0:
            return 0
        if days_to_exam <= 7:
            return 10
        if days_to_exam <= 14:
            return 5
        if days_to_exam <= 30:
            return 2
        return 0
    
    def calculate_subject_weights(self) -> Dict[int, float]:
        """Calculate subject weights based on priority, workload, difficulty
        and proximity to exam date.
        """
        weights = {}
        today = datetime.datetime.now().date()
        
        for subject in self.subjects:
            # Base weight from priority (scale 1-5)
            weight = subject.priority * 2
            
            # Add weight based on difficulty (more difficult = higher weight)
            if hasattr(subject, 'difficulty') and subject.difficulty:
                weight += subject.difficulty
            
            # Add weight based on exam proximity
            weight += self._get_exam_weight(subject, today)
            
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
    
    def _build_booked_slots(self, scheduled_sessions, date):
        """Build set of booked 15-minute time slots."""
        booked_slots = set()
        for session in scheduled_sessions:
            if session['start_time'].date() == date.date():
                current = session['start_time']
                while current < session['end_time']:
                    booked_slots.add((current.hour, current.minute // 15))
                    current += datetime.timedelta(minutes=15)
        return booked_slots
    
    def _mark_time_as_booked(self, booked_slots, start_time, end_time):
        """Mark time range as booked in 15-minute slots."""
        mark_time = start_time
        while mark_time < end_time:
            booked_slots.add((mark_time.hour, mark_time.minute // 15))
            mark_time += datetime.timedelta(minutes=15)
    
    def _is_slot_available(self, booked_slots, start_time, duration_minutes):
        """Check if a time slot is available."""
        end_time = start_time + datetime.timedelta(minutes=duration_minutes)
        check_time = start_time
        while check_time < end_time:
            if (check_time.hour, check_time.minute // 15) in booked_slots:
                return False
            check_time += datetime.timedelta(minutes=15)
        return True
    
    def _can_schedule_subject(self, subject_id, hour, remaining_allocation, 
                             consecutive_sessions, max_consecutive, subject_time_tracking):
        """Check if a subject can be scheduled at this time."""
        if remaining_allocation[subject_id] <= 0:
            return False
        if consecutive_sessions[subject_id] >= max_consecutive:
            return False
        if subject_time_tracking and subject_id in subject_time_tracking:
            if subject_time_tracking[subject_id].get(hour, 0) >= 2:
                return False
        return True
    
    def _create_session_dict(self, subject_id, subject_map, start_time, end_time):
        """Create a session dictionary."""
        subject = subject_map[subject_id]
        return {
            'subject_id': subject_id,
            'subject_name': subject.name,
            'start_time': start_time,
            'end_time': end_time,
            'color': subject.color if hasattr(subject, 'color') else "#3498db"
        }
    
    def _try_schedule_subject(self, hour, current_dt, subject_rotation_queue, current_subject_index,
                              remaining_allocation, consecutive_sessions, max_consecutive,
                              subject_time_tracking, subject_map, session_minutes, booked_time_slots):
        """Try to schedule a subject at the given hour."""
        attempted_subjects = set()
        
        while len(attempted_subjects) < len(subject_rotation_queue):
            if current_subject_index >= len(subject_rotation_queue):
                current_subject_index = 0
            
            subject_id = subject_rotation_queue[current_subject_index]
            current_subject_index += 1
            
            if subject_id in attempted_subjects:
                continue
            
            attempted_subjects.add(subject_id)
            
            if not self._can_schedule_subject(subject_id, hour, remaining_allocation,
                                             consecutive_sessions, max_consecutive, subject_time_tracking):
                continue
            
            start_time = current_dt
            end_time = start_time + datetime.timedelta(minutes=session_minutes)
            
            session = self._create_session_dict(subject_id, subject_map, start_time, end_time)
            self._mark_time_as_booked(booked_time_slots, start_time, end_time)
            
            hours_used = session_minutes / 60
            remaining_allocation[subject_id] -= hours_used
            consecutive_sessions[subject_id] += hours_used
            
            if subject_time_tracking and subject_id in subject_time_tracking:
                subject_time_tracking[subject_id][hour] = subject_time_tracking[subject_id].get(hour, 0) + 1
            
            return session, current_subject_index
        
        return None, current_subject_index
    
    def _initialize_schedule_data(self, date, subject_allocation, scheduled_sessions):
        """Initialize data structures for daily scheduling."""
        available_hours = self.get_available_hours(date)
        if not available_hours:
            return None, None, None, None
        
        subject_map = {subject.id: subject for subject in self.subjects}
        remaining_allocation = subject_allocation.copy()
        
        subjects_by_priority = sorted(
            [(subject_id, subject_map[subject_id]) 
             for subject_id in remaining_allocation.keys()
             if subject_id in subject_map],
            key=lambda x: (
                -x[1].priority,
                x[1].exam_date if hasattr(x[1], 'exam_date') else datetime.datetime.max
            )
        )
        
        booked_time_slots = self._build_booked_slots(scheduled_sessions, date)
        available_hours = [h for h in available_hours if not any(
            (h, quarter) in booked_time_slots for quarter in range(4)
        )]
        available_hours.sort()
        
        subject_rotation_queue = [sid for sid, _ in subjects_by_priority if remaining_allocation[sid] > 0]
        
        return subject_map, remaining_allocation, available_hours, subject_rotation_queue, booked_time_slots
    
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
        result = self._initialize_schedule_data(date, subject_allocation, scheduled_sessions)
        if result[0] is None:
            return []
        
        subject_map, remaining_allocation, available_hours, subject_rotation_queue, booked_time_slots = result
        
        if not subject_rotation_queue:
            return []
        
        day_sessions = []
        session_minutes = self.get_session_length()
        break_minutes = self.get_break_duration()
        max_consecutive = self.get_max_consecutive_hours()
        consecutive_sessions = defaultdict(int)
        
        # Loop through available hours and schedule sessions
        current_subject_index = 0
        for hour in available_hours:
            # If no more allocation left, we're done
            if all(remaining <= 0 for remaining in remaining_allocation.values()):
                break
            
            current_dt = date.replace(hour=hour, minute=0, second=0, microsecond=0)
            
            if not self._is_slot_available(booked_time_slots, current_dt, session_minutes):
                continue
            
            session, current_subject_index = self._try_schedule_subject(
                hour, current_dt, subject_rotation_queue, current_subject_index,
                remaining_allocation, consecutive_sessions, max_consecutive,
                subject_time_tracking, subject_map, session_minutes, booked_time_slots
            )
            
            if session:
                day_sessions.append(session)
                if break_minutes > 0:
                    break_end = session['end_time'] + datetime.timedelta(minutes=break_minutes)
                    self._mark_time_as_booked(booked_time_slots, session['end_time'], break_end)
        
        return day_sessions
    
    def _calculate_daily_allocation(self, total_subject_allocation, date_range_days):
        """Calculate hours per day for each subject."""
        daily_allocation = {}
        days_per_week = 5
        if self.study_preference and hasattr(self.study_preference, 'days_per_week'):
            days_per_week = self.study_preference.days_per_week
        
        for subject_id, total_hours in total_subject_allocation.items():
            effective_days = min(days_per_week, date_range_days) if date_range_days < 7 else days_per_week
            hours_per_day = math.ceil(total_hours / effective_days) if effective_days > 0 else total_hours
            daily_allocation[subject_id] = hours_per_day
        
        return daily_allocation
    
    def _calculate_today_allocation(self, total_subject_allocation, hours_allocated, 
                                    days_since_last_studied, daily_allocation):
        """Calculate allocation for today based on priorities and remaining hours."""
        today_allocation = {}
        
        overdue_subjects = sorted(
            [(sid, days) for sid, days in days_since_last_studied.items()
             if days >= 2 and total_subject_allocation[sid] - hours_allocated[sid] > 0],
            key=lambda x: x[1], reverse=True
        )
        
        for subject_id, _ in overdue_subjects:
            remaining = total_subject_allocation[subject_id] - hours_allocated[subject_id]
            today_allocation[subject_id] = min(daily_allocation[subject_id], remaining) if remaining > 0 else 0
        
        for subject_id, total_hours in total_subject_allocation.items():
            if subject_id not in today_allocation:
                remaining = total_hours - hours_allocated[subject_id]
                today_allocation[subject_id] = min(daily_allocation[subject_id], remaining) if remaining > 0 else 0
        
        return today_allocation
    
    def _update_tracking(self, daily_sessions, hours_allocated, days_since_last_studied, subject_time_tracking):
        """Update tracking data after scheduling daily sessions."""
        subjects_studied_today = set()
        for session in daily_sessions:
            subject_id = session['subject_id']
            subjects_studied_today.add(subject_id)
            
            duration_hours = (session['end_time'] - session['start_time']).total_seconds() / 3600
            hours_allocated[subject_id] += duration_hours
            
            session_hour = session['start_time'].hour
            subject_time_tracking[subject_id][session_hour] += 1
        
        for subject_id in subjects_studied_today:
            days_since_last_studied[subject_id] = 0
    
    def generate_schedule(self) -> List[Dict[str, Any]]:
        """Generate a complete study schedule for the date range.
        
        Returns:
            List of dictionaries representing study sessions.
        """
        total_subject_allocation = self.calculate_subject_allocation()
        schedule = []
        date_range_days = (self.end_date.date() - self.start_date.date()).days + 1
        
        daily_allocation = self._calculate_daily_allocation(total_subject_allocation, date_range_days)
        
        subject_time_tracking = {sid: defaultdict(int) for sid in total_subject_allocation}
        hours_allocated = dict.fromkeys(total_subject_allocation, 0)
        days_since_last_studied = dict.fromkeys(total_subject_allocation, 0)
        
        current_date = self.start_date
        while current_date.date() <= self.end_date.date():
            for subject_id in total_subject_allocation:
                days_since_last_studied[subject_id] += 1
            
            today_allocation = self._calculate_today_allocation(
                total_subject_allocation, hours_allocated, days_since_last_studied, daily_allocation
            )
            
            daily_sessions = self.build_daily_schedule(
                current_date, today_allocation, schedule, subject_time_tracking
            )
            
            self._update_tracking(daily_sessions, hours_allocated, days_since_last_studied, subject_time_tracking)
            schedule.extend(daily_sessions)
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