from datetime import datetime

from utils.timezone_utils import localize_to_utc, utc_to_local, format_for_client


def test_timezone_round_trip():
    local_naive = datetime(2025, 10, 31, 9, 30)
    tz = 'Asia/Shanghai'

    utc_value = localize_to_utc(local_naive, tz)
    back_local = utc_to_local(utc_value, tz)

    assert back_local.hour == local_naive.hour
    assert back_local.minute == local_naive.minute


def test_format_for_client():
    utc_value = datetime(2025, 10, 31, 1, 0)
    formatted = format_for_client(utc_value, 'America/New_York', '%Y-%m-%d %H:%M')
    # Eastern time should be previous day 21:00
    assert formatted == '2025-10-30 21:00'

