"""
Study Metrics and Analytics

Calculates study performance metrics like planned vs actual time,
quality ratings, and adherence statistics.
"""
from datetime import datetime, timedelta, timezone
from models.database import StudySession, SessionStatus
from sqlalchemy import and_, func


def get_week_date_range():
    """Get start and end of current week (Monday to Sunday)."""
    today = datetime.now(timezone.utc).date()
    # Monday = 0, Sunday = 6
    days_since_monday = today.weekday()
    week_start = today - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)
    
    return (
        datetime.combine(week_start, datetime.min.time()),
        datetime.combine(week_end, datetime.max.time())
    )


def get_planned_vs_actual_this_week(user_id):
    """Calculate planned vs actual study time for current week.
    
    Args:
        user_id: The user ID
    
    Returns:
        dict: {
            'planned_minutes': int,
            'actual_minutes': int,
            'adherence_rate': float (0-100),
            'completed_sessions': int,
            'planned_sessions': int,
            'week_start': date,
            'week_end': date
        }
    """
    week_start, week_end = get_week_date_range()
    
    # Get all sessions in this week
    sessions = StudySession.query.filter(
        and_(
            StudySession.user_id == user_id,
            StudySession.start_time >= week_start,
            StudySession.start_time <= week_end
        )
    ).all()
    
    planned_minutes = 0
    actual_minutes = 0
    completed_count = 0
    
    for session in sessions:
        planned_minutes += session.duration_minutes()
        
        if session.is_completed():
            completed_count += 1
            actual_minutes += session.get_actual_minutes()
    
    adherence_rate = 0
    if planned_minutes > 0:
        adherence_rate = (actual_minutes / planned_minutes) * 100
        adherence_rate = min(100, adherence_rate)  # Cap at 100%
    
    return {
        'planned_minutes': int(planned_minutes),
        'actual_minutes': int(actual_minutes),
        'adherence_rate': round(adherence_rate, 1),
        'completed_sessions': completed_count,
        'planned_sessions': len(sessions),
        'week_start': week_start.date(),
        'week_end': week_end.date()
    }


def get_average_quality_last_7_days(user_id):
    """Calculate average productivity rating for last 7 days.
    
    Args:
        user_id: The user ID
    
    Returns:
        dict: {
            'average_rating': float (0-5),
            'rated_sessions': int,
            'trend': str ('up', 'down', 'stable', 'new'),
            'trend_value': float (change from previous period)
        }
    """
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    fourteen_days_ago = now - timedelta(days=14)
    
    # Last 7 days
    recent_sessions = StudySession.query.filter(
        and_(
            StudySession.user_id == user_id,
            StudySession.completed_at >= seven_days_ago,
            StudySession.completed_at <= now,
            StudySession.status == SessionStatus.completed,
            StudySession.productivity_rating.isnot(None)
        )
    ).all()
    
    # Previous 7 days (for trend)
    previous_sessions = StudySession.query.filter(
        and_(
            StudySession.user_id == user_id,
            StudySession.completed_at >= fourteen_days_ago,
            StudySession.completed_at < seven_days_ago,
            StudySession.status == SessionStatus.completed,
            StudySession.productivity_rating.isnot(None)
        )
    ).all()
    
    # Calculate averages
    recent_avg = 0
    if recent_sessions:
        recent_avg = sum(s.productivity_rating for s in recent_sessions) / len(recent_sessions)
    
    previous_avg = 0
    if previous_sessions:
        previous_avg = sum(s.productivity_rating for s in previous_sessions) / len(previous_sessions)
    
    # Determine trend
    trend = 'new'
    trend_value = 0
    
    if previous_sessions:
        trend_value = recent_avg - previous_avg
        if abs(trend_value) < 0.2:
            trend = 'stable'
        elif trend_value > 0:
            trend = 'up'
        else:
            trend = 'down'
    elif recent_sessions:
        trend = 'stable'  # First week of data
    
    return {
        'average_rating': round(recent_avg, 1),
        'rated_sessions': len(recent_sessions),
        'trend': trend,
        'trend_value': round(trend_value, 1)
    }


def format_minutes_to_hours(minutes):
    """Format minutes as 'Xh YYm' string.
    
    Args:
        minutes: Total minutes
    
    Returns:
        str: Formatted time like '2h 30m' or '45m'
    """
    if minutes == 0:
        return '0m'
    
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    
    if hours > 0 and mins > 0:
        return f'{hours}h {mins}m'
    elif hours > 0:
        return f'{hours}h'
    else:
        return f'{mins}m'


def get_study_statistics(user_id):
    """Get comprehensive study statistics.
    
    Args:
        user_id: The user ID
    
    Returns:
        dict: Comprehensive stats for dashboard display
    """
    planned_vs_actual = get_planned_vs_actual_this_week(user_id)
    quality_stats = get_average_quality_last_7_days(user_id)
    
    return {
        'this_week': planned_vs_actual,
        'quality': quality_stats,
        'formatted': {
            'planned': format_minutes_to_hours(planned_vs_actual['planned_minutes']),
            'actual': format_minutes_to_hours(planned_vs_actual['actual_minutes']),
            'adherence': f"{planned_vs_actual['adherence_rate']}%"
        }
    }

