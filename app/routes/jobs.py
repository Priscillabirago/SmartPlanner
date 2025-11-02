"""
Job endpoints for background/maintenance tasks.
"""
from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from models.missed_sessions import mark_missed_sessions, cleanup_expired_makeup_queue

jobs = Blueprint('jobs', __name__, url_prefix='/jobs')


@jobs.route('/mark_missed', methods=['POST'])
@login_required
def mark_missed():
    """
    Mark sessions as missed if they've passed their grace period.
    Can be called manually or via cron.
    """
    # Get user's grace period preference
    grace_minutes = 30  # Default
    if current_user.study_preference and current_user.study_preference.grace_minutes:
        grace_minutes = current_user.study_preference.grace_minutes
    
    count = mark_missed_sessions(current_user.id, grace_minutes)
    
    return jsonify({
        'success': True,
        'marked_as_missed': count,
        'message': f'{count} session(s) marked as missed'
    })


@jobs.route('/cleanup_expired', methods=['POST'])
@login_required
def cleanup_expired():
    """
    Clean up expired makeup queue entries.
    Admin/maintenance endpoint.
    """
    count = cleanup_expired_makeup_queue()
    
    return jsonify({
        'success': True,
        'removed': count,
        'message': f'{count} expired makeup queue entries removed'
    })

