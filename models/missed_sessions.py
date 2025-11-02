"""
Missed Sessions Management

Handles automatic marking of missed sessions and rescheduling logic.
"""
from datetime import datetime, timedelta, timezone
from models.database import db, StudySession, SessionStatus, MakeupQueue
from sqlalchemy import and_


def mark_missed_sessions(user_id, grace_minutes=30):
    """
    Mark sessions as 'missed' if end_time + grace period has passed.
    
    Args:
        user_id: The user ID to check sessions for
        grace_minutes: Minutes of grace period after session end (default: 30)
    
    Returns:
        int: Number of sessions marked as missed
    """
    now = datetime.now(timezone.utc)
    grace_period = timedelta(minutes=grace_minutes)
    cutoff_time = now - grace_period
    
    # Find planned sessions that have passed their grace period
    # Status precedence: completed > missed > planned
    # Note: If locked field exists, we should exclude locked sessions
    filters = [
        StudySession.user_id == user_id,
        StudySession.status == SessionStatus.planned,
        StudySession.end_time <= cutoff_time
    ]
    
    # Check if locked field exists (from previous feature)
    if hasattr(StudySession, 'locked'):
        filters.append(StudySession.locked == False)
    
    missed_sessions = StudySession.query.filter(and_(*filters)).all()
    
    count = 0
    for session in missed_sessions:
        session.status = SessionStatus.missed
        count += 1
    
    if count > 0:
        db.session.commit()
    
    return count


def get_missed_sessions_summary(user_id):
    """
    Get summary of missed sessions for a user.
    
    Args:
        user_id: The user ID
    
    Returns:
        dict: {
            'count': int,
            'total_minutes': float,
            'by_subject': {subject_id: {'name': str, 'minutes': float, 'count': int}}
        }
    """
    missed_sessions = StudySession.query.filter(
        and_(
            StudySession.user_id == user_id,
            StudySession.status == SessionStatus.missed
        )
    ).all()
    
    summary = {
        'count': len(missed_sessions),
        'total_minutes': 0,
        'by_subject': {}
    }
    
    for session in missed_sessions:
        minutes = session.duration_minutes()
        summary['total_minutes'] += minutes
        
        subject_id = session.subject_id
        if subject_id not in summary['by_subject']:
            summary['by_subject'][subject_id] = {
                'name': session.subject.name if session.subject else 'Unknown',
                'minutes': 0,
                'count': 0
            }
        
        summary['by_subject'][subject_id]['minutes'] += minutes
        summary['by_subject'][subject_id]['count'] += 1
    
    return summary


def queue_missed_sessions_for_makeup(user_id, days_to_expire=7):
    """
    Add missed session time to the makeup queue for rescheduling.
    
    Args:
        user_id: The user ID
        days_to_expire: Number of days before makeup expires (default: 7)
    
    Returns:
        dict: Summary of queued makeup time by subject
    """
    from datetime import date
    
    # Get all missed sessions
    missed_sessions = StudySession.query.filter(
        and_(
            StudySession.user_id == user_id,
            StudySession.status == SessionStatus.missed
        )
    ).all()
    
    if not missed_sessions:
        return {}
    
    # Aggregate by subject
    subject_minutes = {}
    for session in missed_sessions:
        subject_id = session.subject_id
        minutes = session.duration_minutes()
        
        if subject_id not in subject_minutes:
            subject_minutes[subject_id] = {
                'minutes': 0,
                'subject_name': session.subject.name if session.subject else 'Unknown'
            }
        subject_minutes[subject_id]['minutes'] += minutes
    
    # Create or update makeup queue entries
    expires_at = date.today() + timedelta(days=days_to_expire)
    queued = {}
    
    for subject_id, data in subject_minutes.items():
        minutes = int(data['minutes'])  # Round to int
        
        # Check if entry already exists
        existing = MakeupQueue.query.filter_by(
            user_id=user_id,
            subject_id=subject_id
        ).filter(
            MakeupQueue.expires_at >= date.today()  # Not expired
        ).first()
        
        if existing:
            # Add to existing queue
            existing.minutes += minutes
            existing.expires_at = max(existing.expires_at, expires_at)  # Extend expiry if needed
        else:
            # Create new entry
            new_queue = MakeupQueue(
                user_id=user_id,
                subject_id=subject_id,
                minutes=minutes,
                expires_at=expires_at
            )
            db.session.add(new_queue)
        
        queued[subject_id] = {
            'subject_name': data['subject_name'],
            'minutes': minutes
        }
    
    # Mark missed sessions as "queued" by changing status to canceled
    # (Alternative: add a "queued_for_makeup" boolean field)
    # For now, we'll leave them as missed but could track this differently
    
    db.session.commit()
    
    return queued


def cleanup_expired_makeup_queue():
    """
    Remove expired makeup queue entries.
    
    Returns:
        int: Number of expired entries removed
    """
    from datetime import date
    
    expired = MakeupQueue.query.filter(
        MakeupQueue.expires_at < date.today()
    ).all()
    
    count = len(expired)
    
    for entry in expired:
        db.session.delete(entry)
    
    if count > 0:
        db.session.commit()
    
    return count


def get_makeup_queue_summary(user_id):
    """
    Get summary of makeup queue for a user.
    
    Args:
        user_id: The user ID
    
    Returns:
        dict: {
            'total_minutes': int,
            'by_subject': {subject_id: {'name': str, 'minutes': int, 'expires_at': date}}
        }
    """
    from datetime import date
    
    queue_entries = MakeupQueue.query.filter(
        and_(
            MakeupQueue.user_id == user_id,
            MakeupQueue.expires_at >= date.today()  # Only active entries
        )
    ).all()
    
    summary = {
        'total_minutes': 0,
        'by_subject': {}
    }
    
    for entry in queue_entries:
        summary['total_minutes'] += entry.minutes
        summary['by_subject'][entry.subject_id] = {
            'name': entry.subject.name if entry.subject else 'Unknown',
            'minutes': entry.minutes,
            'expires_at': entry.expires_at
        }
    
    return summary

