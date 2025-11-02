"""
Timezone Utilities

Handles conversion between user's local timezone and UTC for proper datetime storage.
All datetimes are stored in UTC in the database and converted to user's timezone for display.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytz


def get_user_timezone(user):
    """Get user's timezone object.
    
    Args:
        user: User object with timezone field
    
    Returns:
        ZoneInfo: User's timezone
    """
    try:
        return ZoneInfo(user.timezone)
    except Exception:
        # Fallback to UTC if invalid timezone
        return ZoneInfo('UTC')


def localize_to_utc(dt_naive, user_tz_str='UTC'):
    """Convert naive datetime in user's timezone to UTC.
    
    Args:
        dt_naive: Naive datetime object (no timezone info)
        user_tz_str: User's timezone string (e.g., 'America/New_York')
    
    Returns:
        datetime: Timezone-aware datetime in UTC
    
    Example:
        >>> dt = datetime(2024, 10, 29, 14, 0)  # 2 PM in user's timezone
        >>> utc_dt = localize_to_utc(dt, 'America/Los_Angeles')
        >>> # Returns 2024-10-29 21:00:00+00:00 (9 PM UTC)
    """
    try:
        local_tz = ZoneInfo(user_tz_str)
        # Add timezone info to naive datetime
        local_dt = dt_naive.replace(tzinfo=local_tz)
        # Convert to UTC
        return local_dt.astimezone(timezone.utc)
    except Exception:
        # If conversion fails, assume it's already UTC
        if dt_naive.tzinfo is None:
            return dt_naive.replace(tzinfo=timezone.utc)
        return dt_naive


def utc_to_local(dt_utc, user_tz_str='UTC'):
    """Convert UTC datetime to user's local timezone.
    
    Args:
        dt_utc: UTC datetime (may be naive or aware)
        user_tz_str: User's timezone string (e.g., 'America/New_York')
    
    Returns:
        datetime: Timezone-aware datetime in user's timezone
    
    Example:
        >>> dt = datetime(2024, 10, 29, 21, 0, tzinfo=timezone.utc)  # 9 PM UTC
        >>> local_dt = utc_to_local(dt, 'America/Los_Angeles')
        >>> # Returns 2024-10-29 14:00:00-07:00 (2 PM PDT)
    """
    try:
        # Ensure UTC timezone info
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        
        # Convert to user's timezone
        local_tz = ZoneInfo(user_tz_str)
        return dt_utc.astimezone(local_tz)
    except Exception:
        # Fallback: return as-is
        return dt_utc


def parse_client_datetime(iso_string, user_tz_str='UTC'):
    """Parse ISO datetime string from client and convert to UTC.
    
    Client should send: '2024-10-29T14:00:00' (local time) or '2024-10-29T14:00:00-07:00' (with offset)
    
    Args:
        iso_string: ISO 8601 datetime string from client
        user_tz_str: User's timezone (used if client doesn't send offset)
    
    Returns:
        datetime: Timezone-aware datetime in UTC
    """
    from dateutil import parser
    
    try:
        dt = parser.isoparse(iso_string)
        
        # If naive (no timezone), assume it's in user's timezone
        if dt.tzinfo is None:
            return localize_to_utc(dt, user_tz_str)
        
        # If already has timezone, convert to UTC
        return dt.astimezone(timezone.utc)
    except Exception:
        # Fallback: return current time in UTC
        return datetime.now(timezone.utc)


def format_for_client(dt_utc, user_tz_str='UTC', format_str='%Y-%m-%dT%H:%M:%S'):
    """Format UTC datetime for sending to client.
    
    Args:
        dt_utc: UTC datetime
        user_tz_str: User's timezone
        format_str: strftime format string
    
    Returns:
        str: Formatted datetime string in user's timezone
    """
    local_dt = utc_to_local(dt_utc, user_tz_str)
    return local_dt.strftime(format_str)


def get_common_timezones():
    """Get list of common timezones for dropdown.
    
    Returns:
        list: List of (timezone_name, display_name) tuples
    """
    common_tzs = [
        'UTC',
        'America/New_York',
        'America/Chicago',
        'America/Denver',
        'America/Los_Angeles',
        'America/Anchorage',
        'Pacific/Honolulu',
        'Europe/London',
        'Europe/Paris',
        'Europe/Berlin',
        'Asia/Tokyo',
        'Asia/Shanghai',
        'Asia/Dubai',
        'Australia/Sydney',
        'America/Toronto',
        'America/Mexico_City',
        'America/Sao_Paulo',
    ]
    
    # Generate display names with current offset
    result = []
    now = datetime.now(timezone.utc)
    
    for tz_name in common_tzs:
        try:
            tz = ZoneInfo(tz_name)
            local_time = now.astimezone(tz)
            offset = local_time.strftime('%z')
            # Format offset as UTC+/-X:XX
            offset_formatted = f"UTC{offset[:3]}:{offset[3:]}"
            display = f"{tz_name.replace('_', ' ')} ({offset_formatted})"
            result.append((tz_name, display))
        except Exception:
            continue
    
    return result


def get_all_timezones():
    """Get all available timezones.
    
    Returns:
        list: List of timezone names
    """
    return sorted(pytz.all_timezones)

