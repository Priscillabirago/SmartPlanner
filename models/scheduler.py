import datetime
import json
import math
import random
from collections import defaultdict
from typing import List, Dict, Tuple, Any, Optional


def _separate_capped_subjects(weights: Dict[int, float], 
                             total_hours: int, 
                             caps: Optional[Dict[int, float]]) -> Tuple[Dict[int, float], Dict[int, float], float]:
    """Separate subjects into capped and uncapped based on their caps."""
    capped_subjects = {}
    uncapped_subjects = {}
    hours_consumed_by_caps = 0
    total_weight = sum(weights.values())
    
    for subject_id, weight in weights.items():
        if caps and subject_id in caps:
            proportional = (weight / total_weight) * total_hours
            if caps[subject_id] < proportional:
                capped_subjects[subject_id] = caps[subject_id]
                hours_consumed_by_caps += caps[subject_id]
            else:
                uncapped_subjects[subject_id] = weight
        else:
            uncapped_subjects[subject_id] = weight
    
    return capped_subjects, uncapped_subjects, hours_consumed_by_caps


def _allocate_by_largest_remainder(uncapped_subjects: Dict[int, float], 
                                   remaining_hours: int) -> Dict[int, int]:
    """Allocate hours using largest remainder method."""
    if not uncapped_subjects or remaining_hours <= 0:
        return {}
    
    uncapped_total_weight = sum(uncapped_subjects.values())
    exact_allocations = {
        sid: (weight / uncapped_total_weight) * remaining_hours if uncapped_total_weight > 0 else 0
        for sid, weight in uncapped_subjects.items()
    }
    
    allocation = {sid: int(exact) for sid, exact in exact_allocations.items()}
    remainders = {sid: exact - int(exact) for sid, exact in exact_allocations.items()}
    
    allocated_so_far = sum(allocation.values())
    still_remaining = int(remaining_hours - allocated_so_far)
    
    sorted_by_remainder = sorted(
        remainders.items(),
        key=lambda x: (x[1], uncapped_subjects[x[0]]),
        reverse=True
    )
    
    for i in range(min(still_remaining, len(sorted_by_remainder))):
        subject_id = sorted_by_remainder[i][0]
        allocation[subject_id] += 1
    
    return allocation


def allocate_hours(weights: Dict[int, float], 
                   total_hours: int, 
                   caps: Optional[Dict[int, float]] = None) -> Dict[int, int]:
    """
    Allocate hours using Largest Remainder (Hamilton) method.
    
    This method ensures:
    - Allocated hours sum EXACTLY to total_hours
    - Distribution is proportional to weights
    - Minimizes rounding errors fairly
    - Respects optional caps (max hours per subject)
    
    Algorithm:
    1. Calculate exact fractional allocation for each subject
    2. Take floor of each (ensuring we don't over-allocate)
    3. Distribute remaining hours to subjects with largest fractional remainders
    
    Args:
        weights: Dict mapping subject_id to weight (priority * 2 + difficulty + exam_bonus)
        total_hours: Total hours available to allocate (user's study_hours_per_week)
        caps: Optional dict of max hours per subject (e.g., from remaining task work)
    
    Returns:
        Dict mapping subject_id to allocated integer hours
        
    Example:
        weights = {1: 10, 2: 10, 3: 10}
        total_hours = 10
        # Each subject should get 3.33 hours
        result = {1: 4, 2: 3, 3: 3}  # Fair distribution, sums to 10
    """
    if not weights or total_hours <= 0:
        return {}
    
    total_weight = sum(weights.values())
    if total_weight == 0:
        hours_each = total_hours // len(weights)
        return dict.fromkeys(weights, hours_each)
    
    capped_subjects, uncapped_subjects, hours_consumed_by_caps = _separate_capped_subjects(
        weights, total_hours, caps
    )
    
    # Convert to int
    remaining_hours = int(total_hours - hours_consumed_by_caps)
    uncapped_allocation = _allocate_by_largest_remainder(uncapped_subjects, remaining_hours)
    
    allocation = {}
    for subject_id in weights:
        if subject_id in capped_subjects:
            allocation[subject_id] = int(capped_subjects[subject_id])
        elif subject_id in uncapped_allocation:
            allocation[subject_id] = uncapped_allocation[subject_id]
        else:
            allocation[subject_id] = 0
    
    return allocation


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
        self.start_date = start_date or datetime.datetime.now(datetime.timezone.utc)
        self.warnings = []  # Track scheduling warnings
        self.task_allocated_minutes = defaultdict(int)  # Track minutes allocated to each task
        
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
        
        # Track per-task allocation during this scheduling run so we don't
        # over-assign the same task beyond its estimated workload
        self._task_original_minutes: Dict[int, float] = {}
        self._task_remaining_minutes: Dict[int, float] = {}
    
    def _get_time_slot_minutes(self) -> int:
        """Derive the base granularity (in minutes) for scheduling slots."""
        session_minutes = int(self.get_session_length()) or 60
        break_pref = self.get_break_duration()
        break_minutes = int(break_pref) if break_pref else 0
        buffer_minutes = 30  # subject transition buffer

        slot_minutes = session_minutes
        if break_minutes > 0:
            slot_minutes = math.gcd(slot_minutes, break_minutes)
        slot_minutes = math.gcd(slot_minutes, buffer_minutes)
        if slot_minutes <= 0:
            slot_minutes = 5

        # Keep the slot size practical (5, 10, 15, 20, 30)
        while slot_minutes > 30:
            slot_minutes //= 2
        slot_minutes = max(5, slot_minutes)

        return slot_minutes
    
    def get_time_of_day_ranges(self) -> Dict[str, Tuple[int, int]]:
        """Define the hour ranges for different times of day."""
        return {
            "morning": (5, 11),    # 5:00 AM - 11:59 AM
            "afternoon": (12, 16), # 12:00 PM - 4:59 PM
            "evening": (17, 21),   # 5:00 PM - 9:59 PM
            "night": (22, 4)       # 10:00 PM - 4:59 AM
        }
    
    def get_available_hours(self, date: datetime.datetime) -> List[datetime.datetime]:
        """Get the start times (per slot) that the user prefers to study."""
        slot_minutes = self._get_time_slot_minutes()
        available_slots: List[datetime.datetime] = []
        time_ranges = self.get_time_of_day_ranges()
        
        # Check if we should include weekend study
        is_weekend = date.weekday() >= 5
        if is_weekend and hasattr(self.study_preference, 'weekend_study'):
            if not self.study_preference.weekend_study:
                return []
        
        def _extend_range(start_hour: int, end_hour: int):
            start_time = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            end_time = date.replace(hour=end_hour, minute=0, second=0, microsecond=0)
            current = start_time
            while current <= end_time:
                available_slots.append(current)
                current += datetime.timedelta(minutes=slot_minutes)

        for time_of_day, is_preferred in self.preferred_times.items():
            if not is_preferred:
                continue
            start_hour, end_hour = time_ranges[time_of_day]
            if start_hour <= end_hour:
                _extend_range(start_hour, end_hour)
            else:
                _extend_range(start_hour, 23)
                _extend_range(0, end_hour)

        # Remove duplicates while preserving order
        # Preserve chronological order while removing duplicates
        seen = set()
        ordered_slots = []
        for slot in sorted(available_slots):
            key = (slot.hour, slot.minute)
            if key in seen:
                continue
            seen.add(key)
            ordered_slots.append(slot)

        ordered_slots.sort()
        return ordered_slots
    
    def _is_time_blocked_by_constraints(self, check_datetime: datetime.datetime) -> bool:
        """Check if a specific time is blocked by user constraints, class blocks, or locked sessions.
        
        Args:
            check_datetime: The datetime to check
            
        Returns:
            True if time is blocked, False otherwise
        """
        from models.database import UserConstraint, ClassBlock, StudySession
        
        day_of_week = check_datetime.weekday()
        check_time = check_datetime.time()
        
        # Check user constraints (work, activities, etc)
        constraints = UserConstraint.query.filter_by(
            user_id=self.user.id,
            day_of_week=day_of_week
        ).all()
        
        for constraint in constraints:
            # Only block if it's a hard constraint
            if constraint.is_hard:
                if constraint.start_time <= check_time < constraint.end_time:
                    return True
        
        # Check class blocks (recurring classes)
        class_blocks = ClassBlock.query.filter_by(
            user_id=self.user.id,
            day_of_week=day_of_week
        ).all()
        
        for class_block in class_blocks:
            if class_block.start_time <= check_time < class_block.end_time:
                return True
        
        # Check locked sessions (user's manual edits to preserve)
        # Query locked sessions that overlap with this datetime
        locked_sessions = StudySession.query.filter(
            StudySession.user_id == self.user.id,
            StudySession.locked == True,
            StudySession.start_time <= check_datetime,
            StudySession.end_time > check_datetime
        ).all()
        
        if locked_sessions:
            return True
        
        return False
    
    def _filter_blocked_hours(self, date: datetime.datetime, available_slots: List[datetime.datetime]) -> List[datetime.datetime]:
        """Filter out start times blocked by constraints or classes."""
        if not available_slots:
            return []

        session_minutes = self.get_session_length()
        slot_minutes = self._get_time_slot_minutes()
        free_slots: List[datetime.datetime] = []

        for start_time in available_slots:
            if start_time.date() != date.date():
                continue
            if self._is_time_blocked_by_constraints(start_time):
                continue

            # Ensure the entire session fits without hitting a constraint boundary
            end_time = start_time + datetime.timedelta(minutes=session_minutes)
            check_time = start_time
            blocked = False
            while check_time < end_time:
                if self._is_time_blocked_by_constraints(check_time):
                    blocked = True
                    break
                check_time += datetime.timedelta(minutes=slot_minutes)

            if not blocked:
                free_slots.append(start_time)

        return free_slots
    
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
    
    def _get_task_urgency_weight(self, subject, today) -> float:
        """Calculate weight bonus based on task deadline proximity.
        
        This ensures subjects with urgent tasks get prioritized,
        even if they have lower base priority.
        
        Args:
            subject: Subject object
            today: Current date
            
        Returns:
            Float weight bonus (0-100), higher for urgent tasks to override subject priority
        """
        from models.database import Task
        
        # Get incomplete tasks for this subject
        tasks = Task.query.filter_by(
            subject_id=subject.id,
            completed=False
        ).all()
        
        if not tasks:
            return 0
        
        max_urgency = 0
        for task in tasks:
            if not task.deadline:
                continue
            
            days_to_deadline = (task.deadline.date() - today).days
            
            # Calculate base urgency - MUCH HIGHER values to override subject priority
            if days_to_deadline < 0:
                urgency = 100  # Overdue! CRITICAL - must be scheduled!
            elif days_to_deadline == 0:
                urgency = 90   # Due TODAY! URGENT - must be scheduled!
            elif days_to_deadline == 1:
                urgency = 50   # Due TOMORROW! HIGH
            elif days_to_deadline <= 3:
                urgency = 25   # Due very soon
            elif days_to_deadline <= 7:
                urgency = 10   # Due this week
            else:
                urgency = 0
            
            # Factor in task priority (1-5 scale)
            if hasattr(task, 'priority') and task.priority:
                urgency *= (task.priority / 3.0)
            
            # Track the most urgent task
            max_urgency = max(max_urgency, urgency)
        
        return max_urgency
    
    def calculate_subject_weights(self) -> Dict[int, float]:
        """Calculate subject weights based on priority, workload, difficulty,
        proximity to exam date, and task deadline urgency.
        """
        weights = {}
        today = datetime.datetime.now(datetime.timezone.utc).date()
        
        for subject in self.subjects:
            # Base weight from priority (scale 1-5)
            weight = subject.priority * 2
            
            # Add weight based on difficulty (more difficult = higher weight)
            if hasattr(subject, 'difficulty') and subject.difficulty:
                weight += subject.difficulty
            
            # Add weight based on exam proximity
            weight += self._get_exam_weight(subject, today)
            
            # CRITICAL: Add weight based on task deadline urgency
            weight += self._get_task_urgency_weight(subject, today)
            
            weights[subject.id] = weight
        
        return weights
    
    def calculate_subject_allocation(self) -> Dict[int, int]:
        """Calculate how many hours to allocate to each subject based on
        weights and total available study hours.
        
        Uses Largest Remainder (Hamilton) method to ensure:
        - Allocated hours sum exactly to study_hours_per_week
        - Fair proportional distribution based on weights
        - Optional workload caps from remaining task work
        """
        weights = self.calculate_subject_weights()
        total_study_hours = self.user.study_hours_per_week
        
        # Calculate workload caps based on remaining task work
        caps = self._calculate_workload_caps()
        
        # Use Largest Remainder method for accurate allocation
        allocation = allocate_hours(weights, total_study_hours, caps)
        
        # Ensure allocation covers urgent task workload due within the schedule range
        session_minutes = self.get_session_length()
        if session_minutes <= 0:
            session_minutes = 60

        urgent_minutes_total = self._get_urgent_task_minutes_by_subject(self.end_date.date())
        for subject_id, urgent_minutes in urgent_minutes_total.items():
            required_hours = math.ceil(urgent_minutes / session_minutes)
            current_hours = allocation.get(subject_id, 0)
            if required_hours > current_hours:
                allocation[subject_id] = required_hours
        
        return allocation
    
    def _calculate_workload_caps(self) -> Dict[int, float]:
        """Calculate maximum hours per subject based on remaining task work.
        
        This prevents over-scheduling when we know exactly how much work remains.
        For example, if a subject only has 2 hours of tasks left, don't allocate 5 hours.
        
        Returns:
            Dict mapping subject_id to max hours (float)
        """
        from models.database import Task
        
        caps = {}
        
        session_minutes = self.get_session_length()
        # Avoid division by zero – if preferences somehow set 0, default to 60
        if session_minutes <= 0:
            session_minutes = 60
        session_hours = session_minutes / 60.0

        for subject in self.subjects:
            # Get all incomplete tasks for this subject
            incomplete_tasks = Task.query.filter_by(
                subject_id=subject.id,
                completed=False
            ).all()
            
            # Sum estimated time for incomplete tasks
            total_minutes = 0
            for task in incomplete_tasks:
                if task.estimated_time and task.estimated_time > 0:
                    total_minutes += task.estimated_time
                else:
                    # If no estimate provided, assume one full session
                    total_minutes += session_minutes
            
            if total_minutes > 0:
                # Round up to the next full session so we never cap below 1
                sessions_needed = math.ceil(total_minutes / session_minutes)
                caps[subject.id] = sessions_needed * session_hours
            # If no tasks or no estimates, don't cap (use workload from subject)
        
        return caps
    
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
        """Build set of booked slots using the scheduler's time granularity."""
        slot_minutes = self._get_time_slot_minutes()
        booked_slots = set()
        for session in scheduled_sessions:
            if session['start_time'].date() == date.date():
                current = session['start_time']
                while current < session['end_time']:
                    booked_slots.add((current.hour, current.minute))
                    current += datetime.timedelta(minutes=slot_minutes)
        return booked_slots
    
    def _mark_time_as_booked(self, booked_slots, start_time, end_time):
        """Mark time range as booked using the scheduler's time granularity."""
        slot_minutes = self._get_time_slot_minutes()
        mark_time = start_time
        while mark_time < end_time:
            booked_slots.add((mark_time.hour, mark_time.minute))
            mark_time += datetime.timedelta(minutes=slot_minutes)
    
    def _is_slot_available(self, booked_slots, start_time, duration_minutes):
        """Check if a time slot is available."""
        slot_minutes = self._get_time_slot_minutes()
        end_time = start_time + datetime.timedelta(minutes=duration_minutes)
        check_time = start_time
        while check_time < end_time:
            if (check_time.hour, check_time.minute) in booked_slots:
                return False
            check_time += datetime.timedelta(minutes=slot_minutes)
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
    
    def _build_booked_slots(self, scheduled_sessions: List[Dict], date: datetime.datetime) -> set:
        """Build a set of booked time slots from existing sessions."""
        booked = set()
        target_date = date.date()
        
        for session in scheduled_sessions:
            start = session.get('start_time')
            end = session.get('end_time')
            
            if not start or not end:
                continue
            
            # Only consider sessions on the target date
            if start.date() != target_date:
                continue
            
            # Mark each minute as booked
            current = start
            while current < end:
                booked.add(current)
                current += datetime.timedelta(minutes=1)
        
        return booked
    
    def _get_urgent_subjects_for_date(self, target_date: datetime.date) -> List[int]:
        """Get list of subject IDs with tasks due today or tomorrow, ordered by urgency."""
        from models.database import Task
        
        tomorrow = target_date + datetime.timedelta(days=1)
        urgent_subjects = []
        
        for subject in self.subjects:
            tasks = Task.query.filter_by(subject_id=subject.id, completed=False).all()
            for task in tasks:
                if task.deadline and task.deadline.date() <= tomorrow:
                    if subject.id not in urgent_subjects:
                        urgent_subjects.append(subject.id)
                    break
        
        return urgent_subjects
    
    def _schedule_subject_block(self, subject_id: int, subject_map: Dict, 
                                remaining_allocation: Dict, available_slots: List,
                                booked_slots: set, session_minutes: int, 
                                break_minutes: int, max_consecutive_hours: int) -> List[Dict]:
        """Schedule a block of sessions for one subject, keeping them together."""
        if subject_id not in subject_map:
            return []
        
        subject = subject_map[subject_id]
        sessions_to_add = []
        hours_to_schedule = remaining_allocation.get(subject_id, 0)
        
        if hours_to_schedule <= 0:
            return []
        
        # Convert hours to number of sessions
        sessions_needed = math.ceil(hours_to_schedule * 60 / session_minutes)
        max_sessions = int(max_consecutive_hours * 60 / session_minutes)
        sessions_to_schedule = min(sessions_needed, max_sessions)
        
        # Track initial allocation to check if we meet it
        initial_hours = hours_to_schedule
        
        # Find consecutive available slots
        for i, slot_start in enumerate(available_slots):
            if len(sessions_to_add) >= sessions_to_schedule:
                break
            
            # Check if this slot is available
            if not self._is_slot_available(booked_slots, slot_start, session_minutes):
                continue
            
            # Create session
            session_end = slot_start + datetime.timedelta(minutes=session_minutes)
            session = {
                'subject_id': subject_id,
                'subject_name': subject.name,
                'start_time': slot_start,
                'end_time': session_end,
                'color': subject.color if hasattr(subject, 'color') else "#3498db"
            }
            
            sessions_to_add.append(session)
            
            # Mark time as booked (session + break)
            self._mark_time_as_booked(booked_slots, slot_start, session_end)
            if break_minutes > 0 and len(sessions_to_add) < sessions_to_schedule:
                break_end = session_end + datetime.timedelta(minutes=break_minutes)
                self._mark_time_as_booked(booked_slots, session_end, break_end)
            
            # Update remaining allocation
            hours_used = session_minutes / 60
            remaining_allocation[subject_id] -= hours_used
        
        # Check if we couldn't schedule enough time for urgent tasks
        hours_scheduled = len(sessions_to_add) * (session_minutes / 60)
        if hours_scheduled < initial_hours * 0.5:  # Less than 50% of needed time
            self.warnings.append({
                'type': 'insufficient_time',
                'subject': subject.name,
                'needed_hours': initial_hours,
                'scheduled_hours': hours_scheduled,
                'message': f"Could only schedule {hours_scheduled:.1f} of {initial_hours:.1f} hours needed for {subject.name}"
            })
        
        return sessions_to_add
    
    def _try_schedule_subject(self, current_dt, subject_rotation_queue, current_subject_index,
                              remaining_allocation, consecutive_sessions, max_consecutive,
                              subject_time_tracking, subject_map, session_minutes, booked_time_slots,
                              existing_schedule):
        """Try to schedule a subject at the given hour, respecting transition buffers."""
        attempted_subjects = set()
        slot_hour = current_dt.hour
        
        # Check if we need a buffer for subject transitions
        needs_buffer, prev_subject_id = self._needs_subject_transition_buffer(
            existing_schedule, current_dt, buffer_minutes=30
        )
        
        while len(attempted_subjects) < len(subject_rotation_queue):
            if current_subject_index >= len(subject_rotation_queue):
                current_subject_index = 0
            
            subject_id = subject_rotation_queue[current_subject_index]
            current_subject_index += 1
            
            if subject_id in attempted_subjects:
                continue
            
            attempted_subjects.add(subject_id)
            
            # Skip if buffer is needed and this is a different subject
            if needs_buffer and prev_subject_id is not None and subject_id != prev_subject_id:
                continue
            
            if not self._can_schedule_subject(subject_id, slot_hour, remaining_allocation,
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
                subject_time_tracking[subject_id][slot_hour] = subject_time_tracking[subject_id].get(slot_hour, 0) + 1
            
            return session, current_subject_index
        
        return None, current_subject_index
    
    def _initialize_schedule_data(self, date, subject_allocation, scheduled_sessions):
        """Initialize data structures for daily scheduling."""
        available_slots = self.get_available_hours(date)
        if not available_slots:
            return None, None, None, None, None
        
        # Filter out hours blocked by constraints and classes
        available_slots = self._filter_blocked_hours(date, available_slots)
        if not available_slots:
            return None, None, None, None, None
        
        subject_map = {subject.id: subject for subject in self.subjects}
        remaining_allocation = subject_allocation.copy()
        
        urgent_hours = getattr(self, '_current_day_urgent_hours', {})
        subjects_by_priority = sorted(
            [(subject_id, subject_map[subject_id])
             for subject_id in remaining_allocation.keys()
             if subject_id in subject_map],
            key=lambda x: (
                -urgent_hours.get(x[0], 0),
                -subject_allocation.get(x[0], 0),
                -x[1].priority,
                x[1].exam_date if hasattr(x[1], 'exam_date') else datetime.datetime.max
            )
        )
        
        session_minutes = self.get_session_length()
        booked_time_slots = self._build_booked_slots(scheduled_sessions, date)
        available_slots = [slot for slot in available_slots if self._is_slot_available(
            booked_time_slots, slot, session_minutes
        )]
        available_slots.sort()
        
        urgent_hours = getattr(self, '_current_day_urgent_hours', {})
        urgent_queue: List[int] = []
        normal_queue: List[int] = []

        for sid, _ in subjects_by_priority:
            remaining = remaining_allocation.get(sid, 0)
            if remaining <= 0:
                continue

            repeats = max(1, math.ceil(remaining))
            urgent_required = urgent_hours.get(sid, 0)

            if urgent_required and urgent_required > 0:
                urgent_repeats = min(repeats, math.ceil(urgent_required))
                urgent_queue.extend([sid] * urgent_repeats)
                leftover = repeats - urgent_repeats
                if leftover > 0:
                    normal_queue.extend([sid] * leftover)
            else:
                normal_queue.extend([sid] * repeats)

        subject_rotation_queue = urgent_queue + normal_queue
        
        return subject_map, remaining_allocation, available_slots, subject_rotation_queue, booked_time_slots
    
    def build_daily_schedule(self, 
                            date: datetime.datetime, 
                            subject_allocation: Dict[int, int],
                            scheduled_sessions: List[Dict[str, Any]]
                            ) -> List[Dict[str, Any]]:
        """TASK-BASED: Schedule using actual tasks with variable lengths, smart distribution, and subject interleaving."""
        from models.database import Task
        
        # Get available time slots
        available_slots = self.get_available_hours(date)
        if not available_slots:
            return []
        
        available_slots = self._filter_blocked_hours(date, available_slots)
        if not available_slots:
            return []
        
        base_session_minutes = self.get_session_length()
        break_minutes = self.get_break_duration() or 0
        max_task_chunk = 120  # Split tasks >200 min into chunks of max 120 min
        
        # Build booked slots from existing schedule
        booked_slots = self._build_booked_slots(scheduled_sessions, date)
        
        subject_map = {s.id: s for s in self.subjects}
        remaining_allocation = subject_allocation.copy()
        day_sessions = []
        target_date = date.date()
        tomorrow = target_date + datetime.timedelta(days=1)
        
        # PHASE 1: Get and prepare urgent tasks (due today or tomorrow, NOT past due date)
        urgent_tasks = []
        for subject in self.subjects:
            tasks = Task.query.filter_by(
                subject_id=subject.id, 
                completed=False,
                user_id=self.user.id
            ).all()
            
            for task in tasks:
                if not task.deadline:
                    continue
                    
                task_deadline_date = task.deadline.date()
                
                # Only include tasks due today or tomorrow
                # If task is past its due date (more than yesterday), don't schedule it
                if task_deadline_date > tomorrow:
                    continue  # Not due yet, skip
                
                # If task's deadline is in the past (before today), don't schedule it
                # Tasks past their due date should not be scheduled in subsequent days
                if task_deadline_date < target_date:
                    continue  # Task is past due date, don't schedule in future days
                
                # Check if task is already fully scheduled
                task_estimated = task.estimated_time if task.estimated_time and task.estimated_time > 0 else base_session_minutes
                task_allocated = self.task_allocated_minutes.get(task.id, 0)
                
                # Skip if already fully allocated
                if task_allocated >= task_estimated:
                    continue  # Task already fully scheduled
                
                # Calculate priority score (deadline + task priority)
                days_until_due = (task_deadline_date - target_date).days
                urgency_score = 100 - (days_until_due * 10)  # Overdue gets 100+, today gets 100
                if task.priority:
                    urgency_score += task.priority * 5
                
                # Calculate remaining minutes needed
                remaining_minutes = task_estimated - task_allocated
                
                urgent_tasks.append({
                    'task': task,
                    'subject_id': subject.id,
                    'estimated_minutes': remaining_minutes,  # Use remaining minutes, not total
                    'urgency_score': urgency_score
                })
        
        # Sort urgent tasks by urgency (highest first)
        urgent_tasks.sort(key=lambda x: x['urgency_score'], reverse=True)
        
        # PHASE 2: Schedule urgent tasks with smart distribution
        task_sessions_per_subject = defaultdict(int)  # Track how many sessions per subject to interleave
        urgent_task_index = 0
        max_urgent_iterations = len(urgent_tasks) * 10  # Safety limit to prevent infinite loops
        urgent_iterations = 0
        
        while urgent_task_index < len(urgent_tasks) and urgent_iterations < max_urgent_iterations:
            urgent_iterations += 1
            task_info = urgent_tasks[urgent_task_index]
            task = task_info['task']
            subject_id = task_info['subject_id']
            estimated = task_info['estimated_minutes']
            
            # For urgent tasks (due today or tomorrow), allow scheduling even if allocation is 0
            # Deadlines should override allocation limits
            task_deadline_date = task.deadline.date() if task.deadline else None
            is_urgent = task_deadline_date and task_deadline_date <= tomorrow
            
            if subject_id not in remaining_allocation:
                urgent_task_index += 1
                continue
            
            # Only skip if allocation is exhausted AND task is not urgent
            # Urgent tasks should be scheduled regardless of allocation
            if remaining_allocation[subject_id] <= 0 and not is_urgent:
                urgent_task_index += 1
                continue
            
            # Re-filter available slots
            available_slots = [s for s in available_slots if self._is_slot_available(booked_slots, s, 30)]  # Min 30 min check
            if not available_slots:
                urgent_task_index += 1
                continue
            
            # If task is >200 minutes, split into chunks
            if estimated > 200:
                chunk_size = min(estimated // 2, max_task_chunk)  # Split into 2-3 chunks
                chunks = []
                remaining = estimated
                while remaining > 0:
                    chunk = min(chunk_size, remaining)
                    chunks.append(chunk)
                    remaining -= chunk
            else:
                chunks = [estimated]
            
            # Schedule each chunk
            task_allocated = self.task_allocated_minutes.get(task.id, 0)
            task_estimated = task.estimated_time if task.estimated_time and task.estimated_time > 0 else base_session_minutes
            
            # Track whether we've already moved to the next task
            task_completed = False
            switched_subject = False
            
            for chunk_idx, chunk_minutes in enumerate(chunks):
                # Check if task is already fully allocated (double-check)
                if task_allocated >= task_estimated:
                    task_completed = True
                    break  # Task already fully scheduled
                
                # Don't schedule more than what's remaining
                remaining_for_task = task_estimated - task_allocated
                if chunk_minutes > remaining_for_task:
                    chunk_minutes = remaining_for_task
                    if chunk_minutes <= 0:
                        task_completed = True
                        break
                
                # Re-filter available slots
                available_slots = [s for s in available_slots if self._is_slot_available(booked_slots, s, chunk_minutes)]
                if not available_slots:
                    break  # No more available time, will retry this task later
                
                # Find next available slot
                slot_index = -1
                for i, slot_start in enumerate(available_slots):
                    if self._is_slot_available(booked_slots, slot_start, chunk_minutes):
                        slot_index = i
                        break
                
                if slot_index == -1:
                    break  # No more available time, will retry this task later
                
                slot_start = available_slots[slot_index]
                slot_end = slot_start + datetime.timedelta(minutes=chunk_minutes)
                
                # Create session
                session = {
                    'subject_id': subject_id,
                    'subject_name': subject_map[subject_id].name,
                    'start_time': slot_start,
                    'end_time': slot_end,
                    'task_id': task.id,
                    'task_title': task.title,
                    'color': subject_map[subject_id].color if hasattr(subject_map[subject_id], 'color') else "#3498db"
                }
                
                day_sessions.append(session)
                
                # Mark time as booked (session + break)
                self._mark_time_as_booked(booked_slots, slot_start, slot_end)
                if break_minutes > 0:
                    break_end = slot_end + datetime.timedelta(minutes=break_minutes)
                    self._mark_time_as_booked(booked_slots, slot_end, break_end)
                
                # Update remaining allocation
                hours_used = chunk_minutes / 60
                remaining_allocation[subject_id] -= hours_used
                
                # Track task allocation (prevent duplicate scheduling)
                self.task_allocated_minutes[task.id] += chunk_minutes
                task_allocated += chunk_minutes  # Update local counter
                
                # Check if task is now fully scheduled
                if task_allocated >= task_estimated:
                    task_completed = True
                    break  
                # Remove used slot
                available_slots.pop(slot_index)
                
                # Interleave: After 2 sessions of same subject, switch to another if available
                task_sessions_per_subject[subject_id] += 1
                
                # If we've scheduled 2 sessions for this subject AND there are more chunks or other tasks
                if task_sessions_per_subject[subject_id] >= 2:
                    # Check if there are other urgent tasks from different subjects
                    for i in range(urgent_task_index + 1, len(urgent_tasks)):
                        next_info = urgent_tasks[i]
                        if (next_info['subject_id'] != subject_id and 
                            next_info['subject_id'] in remaining_allocation and
                            remaining_allocation[next_info['subject_id']] > 0):
                            # Switch to this different subject task
                            urgent_task_index = i - 1  # Will be incremented at end of outer loop
                            switched_subject = True
                            task_sessions_per_subject[subject_id] = 0  # Reset counter for this subject
                            break  # Break out of inner loop
                    
                    if switched_subject:
                        break  
            
            # Move to next task only if task is completed or we switched subjects
            # If we ran out of slots, keep current task_index to retry later
            if task_completed or switched_subject:
                urgent_task_index += 1
            # Otherwise, if no slots available, the loop will exit and we'll move on
        
        # PHASE 3: Schedule regular work by subject (interleaved after 1-2 sessions)
        regular_subjects = sorted(
            [sid for sid in remaining_allocation.keys() if sid not in [t['subject_id'] for t in urgent_tasks]],
            key=lambda sid: -subject_map[sid].priority if sid in subject_map else 0
        )
        
        current_subject_index = 0
        max_regular_iterations = len(regular_subjects) * 50  # Safety limit
        regular_iterations = 0
        
        while current_subject_index < len(regular_subjects) and available_slots and regular_iterations < max_regular_iterations:
            regular_iterations += 1
            subject_id = regular_subjects[current_subject_index]
            
            if remaining_allocation.get(subject_id, 0) <= 0:
                current_subject_index = (current_subject_index + 1) % len(regular_subjects) if regular_subjects else 0
                continue
            
            # Re-filter available slots
            available_slots = [s for s in available_slots if self._is_slot_available(booked_slots, s, base_session_minutes)]
            if not available_slots:
                break
            
            # Schedule 1-2 sessions for this subject, then switch
            sessions_to_schedule = min(2, math.ceil(remaining_allocation[subject_id] / (base_session_minutes / 60)))
            sessions_scheduled_this_round = 0
            
            for _ in range(sessions_to_schedule):
                if not available_slots:
                    break
                
                slot_index = -1
                for i, slot_start in enumerate(available_slots):
                    if self._is_slot_available(booked_slots, slot_start, base_session_minutes):
                        slot_index = i
                        break
                
                if slot_index == -1:
                    break  # No available slots for this subject
                
                slot_start = available_slots[slot_index]
                slot_end = slot_start + datetime.timedelta(minutes=base_session_minutes)
                
                session = {
                    'subject_id': subject_id,
                    'subject_name': subject_map[subject_id].name,
                    'start_time': slot_start,
                    'end_time': slot_end,
                    'color': subject_map[subject_id].color if hasattr(subject_map[subject_id], 'color') else "#3498db"
                }
                
                day_sessions.append(session)
                self._mark_time_as_booked(booked_slots, slot_start, slot_end)
                
                if break_minutes > 0:
                    break_end = slot_end + datetime.timedelta(minutes=break_minutes)
                    self._mark_time_as_booked(booked_slots, slot_end, break_end)
                
                hours_used = base_session_minutes / 60
                remaining_allocation[subject_id] -= hours_used
                available_slots.pop(slot_index)
                sessions_scheduled_this_round += 1
            
            # If we couldn't schedule any sessions for this subject, move to next
            if sessions_scheduled_this_round == 0:
                current_subject_index = (current_subject_index + 1) % len(regular_subjects) if regular_subjects else 0
            else:
                # Switch to next subject (round-robin) after scheduling 1-2 sessions
                current_subject_index = (current_subject_index + 1) % len(regular_subjects) if regular_subjects else 0
        
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
    
    def _get_urgent_task_minutes_by_subject(self, due_date: datetime.date) -> Dict[int, int]:
        """Return total minutes of work due on/before the given date for each subject."""
        from models.database import Task

        session_minutes = self.get_session_length()
        if session_minutes <= 0:
            session_minutes = 60

        urgent_minutes = {}
        for subject in self.subjects:
            tasks = Task.query.filter_by(subject_id=subject.id, completed=False).all()
            total = 0
            for task in tasks:
                if not task.deadline:
                    continue
                if task.deadline.date() <= due_date:
                    estimate = task.estimated_time if task.estimated_time and task.estimated_time > 0 else session_minutes
                    total += estimate
            if total > 0:
                urgent_minutes[subject.id] = total
        return urgent_minutes

    def _calculate_today_allocation(self, total_subject_allocation, hours_allocated, 
                                    days_since_last_studied, daily_allocation, current_date):
        """Calculate allocation for today based on priorities and remaining hours."""
        today_allocation = {}
        session_minutes = self.get_session_length()
        if session_minutes <= 0:
            session_minutes = 60
        urgent_minutes_due = self._get_urgent_task_minutes_by_subject(current_date.date())
        urgent_hours_allocation = {}
        
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

        # Boost allocation for tasks whose deadlines are today or already overdue
        for subject_id, urgent_minutes in urgent_minutes_due.items():
            if subject_id not in total_subject_allocation:
                continue
            allocated_minutes = hours_allocated[subject_id] * 60
            urgent_minutes_remaining = max(0, urgent_minutes - allocated_minutes)
            if urgent_minutes_remaining <= 0:
                continue
            urgent_hours_needed = math.ceil(urgent_minutes_remaining / session_minutes)
            if urgent_hours_needed <= 0:
                continue
            today_allocation[subject_id] = max(today_allocation.get(subject_id, 0), urgent_hours_needed)
            urgent_hours_allocation[subject_id] = urgent_hours_needed
        
        self._current_day_urgent_hours = urgent_hours_allocation
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
    
    def check_urgent_task_coverage(self) -> Dict[str, Any]:
        """Check if urgent tasks can be covered with current study hours.
        
        Returns:
            Dict with 'warnings' list and 'urgent_tasks' info
        """
        from models.database import Task
        
        warnings = []
        urgent_tasks = []
        today = datetime.datetime.now(datetime.timezone.utc).date()
        
        # Find all urgent tasks (due today or tomorrow)
        for subject in self.subjects:
            tasks = Task.query.filter_by(
                subject_id=subject.id,
                completed=False
            ).all()
            
            for task in tasks:
                if not task.deadline:
                    continue
                
                days_to_deadline = (task.deadline.date() - today).days
                
                if days_to_deadline <= 1:  # Due today or tomorrow
                    urgent_tasks.append({
                        'subject': subject.name,
                        'task': task.title,
                        'deadline': task.deadline,
                        'estimated_time': task.estimated_time or 60,
                        'days_to_deadline': days_to_deadline
                    })
        
        if urgent_tasks:
            total_urgent_minutes = sum(t['estimated_time'] for t in urgent_tasks)
            total_urgent_hours = total_urgent_minutes / 60
            
            # Calculate available hours per day
            hours_per_day = self.user.study_hours_per_week / 7
            
            # Check if we have enough time
            if total_urgent_hours > hours_per_day * 2:  # More than 2 days worth
                warnings.append({
                    'type': 'insufficient_hours',
                    'message': f'You have {len(urgent_tasks)} urgent task(s) requiring {total_urgent_hours:.1f} hours, but only {hours_per_day:.1f} hours/day scheduled.',
                    'suggestion': f'Consider increasing your study hours to at least {math.ceil(total_urgent_hours/2)} hours/day.'
                })
        
        return {
            'warnings': warnings,
            'urgent_tasks': urgent_tasks
        }
    
    def generate_schedule(self) -> List[Dict[str, Any]]:
        """Generate a complete study schedule for the date range.
        
        Returns:
            List of dictionaries representing study sessions.
        """
        # Reset task allocation tracking for fresh schedule generation
        self.task_allocated_minutes = defaultdict(int)
        
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
                total_subject_allocation, hours_allocated, days_since_last_studied,
                daily_allocation, current_date
            )
            
            daily_sessions = self.build_daily_schedule(
                current_date, today_allocation, schedule
            )
            
            self._update_tracking(daily_sessions, hours_allocated, days_since_last_studied, subject_time_tracking)
            schedule.extend(daily_sessions)
            current_date += datetime.timedelta(days=1)
        
        return schedule
    
    def _suggest_task_for_session(self, subject_id: int, session_duration_minutes: float, 
                                  session_start: datetime.datetime) -> Optional[Tuple[int, str]]:
        """Intelligently suggest the best task for a study session.
        
        Scoring algorithm considers:
        - Deadline urgency (most important)
        - Task priority
        - Time match (session length vs task estimated time)
        - Task completion status
        
        Args:
            subject_id: Subject ID for this session
            session_duration_minutes: Length of the session in minutes
            session_start: When the session starts
            
        Returns:
            Tuple of (task_id, suggested_session_type) or None if no suitable task
        """
        from models.database import Task
        
        # Get all incomplete tasks for this subject
        tasks = Task.query.filter_by(
            subject_id=subject_id,
            completed=False
        ).all()
        
        if not tasks:
            return None
        
        today = session_start.date()
        best_task = None
        best_score = -1
        best_remaining = 0
        
        for task in tasks:
            # IMPORTANT: Skip tasks past their due date for this session's date
            if task.deadline:
                task_deadline_date = task.deadline.date()
                # Don't suggest tasks that are past their due date
                if task_deadline_date < today:
                    continue  # Task is past due date, don't suggest it
            
            # Check if task is already fully scheduled using our tracking system
            task_estimated = task.estimated_time if task.estimated_time and task.estimated_time > 0 else session_duration_minutes
            task_allocated = self.task_allocated_minutes.get(task.id, 0)
            if task_allocated >= task_estimated:
                continue  # Task already fully scheduled, don't suggest it
            
            # Calculate remaining minutes needed
            remaining_minutes = task_estimated - task_allocated
            
            score = 0
            
            # 1. Deadline urgency (0-50 points) - but only for tasks due today or future
            if task.deadline:
                days_to_deadline = (task.deadline.date() - today).days
                if days_to_deadline == 0:
                    score += 50  # Due TODAY - highest priority
                elif days_to_deadline == 1:
                    score += 45  # Due TOMORROW
                elif days_to_deadline <= 3:
                    score += 35  # Due very soon
                elif days_to_deadline <= 7:
                    score += 25  # Due this week
                elif days_to_deadline <= 14:
                    score += 15  # Due in 2 weeks
                else:
                    score += 5  # Future deadline
            
            # 2. Task priority (0-15 points)
            if hasattr(task, 'priority') and task.priority:
                score += task.priority * 3  # 1-5 priority → 3-15 points
            
            # 3. Time match bonus (0-20 points)
            # Prefer tasks that fit well in the session length
            if remaining_minutes:
                time_ratio = remaining_minutes / session_duration_minutes
                if 0.5 <= time_ratio <= 1.5:
                    # Task fits well in session
                    score += 20
                elif 0.3 <= time_ratio <= 2.0:
                    # Decent fit
                    score += 10
                elif time_ratio > 2.0:
                    # Task too long, might want to break it up
                    score += 5
            
            # 4. Recently created tasks get slight boost (0-5 points)
            if hasattr(task, 'created_at') and task.created_at:
                days_old = (today - task.created_at.date()).days
                if days_old <= 2:
                    score += 5
            
            # Slightly prefer tasks we haven't allocated much time to yet
            if task_allocated == 0:
                score += 2
            
            if score > best_score:
                best_score = score
                best_task = task
                best_remaining = remaining_minutes
        
        if best_task:
            # Suggest session type based on task characteristics
            suggested_type = 'assignment'  # Default for tasks
            
            # If task mentions certain keywords, adjust type
            if best_task.title and best_task.description:
                combined_text = (best_task.title + ' ' + best_task.description).lower()
                if any(word in combined_text for word in ['practice', 'exercise', 'problem set', 'drill']):
                    suggested_type = 'practice'
                elif any(word in combined_text for word in ['review', 'study', 'prepare', 'exam', 'test', 'quiz']):
                    suggested_type = 'review'
                elif any(word in combined_text for word in ['learn', 'read', 'chapter', 'lecture']):
                    suggested_type = 'learn'
            
            # Track that we've allocated time to this task (prevents duplicate suggestions)
            # Update allocation - but only allocate what's remaining, not more
            # Use best_remaining which we tracked earlier
            allocation_to_add = min(session_duration_minutes, best_remaining)
            self.task_allocated_minutes[best_task.id] = self.task_allocated_minutes.get(best_task.id, 0) + allocation_to_add
            
            return (best_task.id, suggested_type)
        
        return None
    
    def save_schedule_to_db(self, schedule, db=None):
        """Save the generated schedule to the database with intelligent task linking.
        
        Args:
            schedule: List of session dictionaries
            db: SQLAlchemy database instance
        
        Returns:
            List of created session objects
        """
        from models.database import StudySession, SessionStatus, SessionType
        
        created_sessions = []
        for session in schedule:
            session_duration = (session['end_time'] - session['start_time']).total_seconds() / 60
            
            # If task_id is already set in session (from task-based scheduling), validate it
            task_id = session.get('task_id')
            session_type = SessionType.learn  # Default
            
            if task_id:
                # Task already linked, validate it's still valid
                from models.database import Task
                task = Task.query.get(task_id)
                
                # If task doesn't exist or is completed, clear the link
                if not task or (hasattr(task, 'completed') and task.completed):
                    task_id = None
                    task = None
                
                # Validate task is not past due date for this session's date
                if task and task_id:
                    session_date = session['start_time'].date()
                    if task.deadline:
                        task_deadline_date = task.deadline.date()
                        # If task's deadline is before the session date, don't link it
                        if task_deadline_date < session_date:
                            task_id = None  # Clear invalid task link
                            task = None  # Don't use this task
                
                # Note: We don't validate "fully allocated" here because:
                # 1. Allocation is already tracked during schedule creation in build_daily_schedule
                # 2. If a session was created with task_id, it means the task needed that time
                # 3. Multiple sessions can be linked to the same task if it needs more time
                
                if task and task.title and task.description:
                    combined_text = (task.title + ' ' + (task.description or '')).lower()
                    if any(word in combined_text for word in ['practice', 'exercise', 'problem set', 'drill']):
                        suggested_type = 'practice'
                    elif any(word in combined_text for word in ['review', 'study', 'prepare', 'exam', 'test', 'quiz']):
                        suggested_type = 'review'
                    elif any(word in combined_text for word in ['learn', 'read', 'chapter', 'lecture']):
                        suggested_type = 'learn'
                    else:
                        suggested_type = 'assignment'
                    
                    try:
                        session_type = SessionType[suggested_type]
                    except (KeyError, AttributeError):
                        session_type = SessionType.assignment
            else:
                # No task linked, suggest one using old method
                task_suggestion = self._suggest_task_for_session(
                    session['subject_id'], 
                    session_duration,
                    session['start_time']
                )
                
                if task_suggestion:
                    task_id, suggested_type = task_suggestion
                    try:
                        session_type = SessionType[suggested_type]
                    except (KeyError, AttributeError):
                        session_type = SessionType.assignment  # Fallback to assignment if invalid
            
            # Create a new StudySession object
            db_session = StudySession(
                user_id=self.user.id,
                subject_id=session['subject_id'],
                start_time=session['start_time'],
                end_time=session['end_time'],
                status=SessionStatus.planned,
                session_type=session_type,
                task_id=task_id,  # NOW LINKED!
                completed=False
            )
            
            # Track task allocation if task is linked (to prevent duplicate scheduling across days)
            if task_id and task:
                # Update allocation tracking (in case we're saving sessions from multiple days)
                # This ensures tasks aren't duplicated across days
                if task_id not in self.task_allocated_minutes:
                    # First time we see this task, check if it was already allocated in build_daily_schedule
                    pass  # Already tracked in build_daily_schedule
                # Note: We don't double-count here because allocation was already tracked
                # during build_daily_schedule. This is just for validation.
            
            if db:
                db.session.add(db_session)
                created_sessions.append(db_session)
        
        if db:
            db.session.commit()
            
        # Log warnings if any
        if self.warnings:
            print(f"\n⚠️  SCHEDULING WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   - {warning['message']}")
        
        return created_sessions 