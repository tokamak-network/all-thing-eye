"""
Date helper functions for weekly data collection

Weekly cycle (same as github-reporter):
- Start: Friday 00:00:00 KST (last Thursday midnight transition)
- End: Thursday 23:59:59 KST (current Thursday night)

Important: When run on Friday, it collects the PREVIOUS complete week
(last Friday 00:00 ~ yesterday Thursday 23:59)
"""

from datetime import datetime, timedelta
from typing import Tuple
import pytz


# KST timezone
KST = pytz.timezone('Asia/Seoul')


def get_last_thursday_midnight() -> datetime:
    """
    Get last Thursday->Friday midnight (00:00:00) in KST
    This is the start of the weekly period
    
    This matches TypeScript's getLastThursdayMidnight()
    
    Returns:
        datetime: Last Friday 00:00:00 KST in UTC
    """
    # Current UTC time
    now = datetime.now(pytz.UTC)
    
    # Convert to KST (UTC+9)
    kst_now = now.astimezone(KST)
    
    # Current KST day of week (0: Monday, 3: Thursday, 4: Friday, 6: Sunday)
    # Convert to JavaScript style (0: Sunday, 4: Thursday, 5: Friday)
    day_of_week = (kst_now.weekday() + 1) % 7  # 0=Sunday in JS
    
    # Calculate days to subtract to get to last Thursday
    if day_of_week < 4:
        # Sunday(0) ~ Wednesday(3)
        days_to_subtract = day_of_week + 3  # Days to last week's Thursday
    else:
        # Thursday(4), Friday(5), Saturday(6)
        days_to_subtract = day_of_week - 4 + 7  # This week's Thursday(0) + 7 days
    
    # Get last Thursday
    last_thursday = kst_now - timedelta(days=days_to_subtract)
    
    # Add 1 day to get Friday, then set to midnight
    last_friday = last_thursday + timedelta(days=1)
    last_friday_midnight = last_friday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Convert to UTC
    return last_friday_midnight.astimezone(pytz.UTC)


def get_current_thursday_midnight() -> datetime:
    """
    Get current Thursday 23:59:59 in KST
    If Thursday 23:59:59 is in the future, returns current time
    
    This matches TypeScript's getCurrentThursdayMidnight()
    
    Returns:
        datetime: Thursday 23:59:59 KST in UTC, or current time if in future
    """
    # Current UTC time
    now = datetime.now(pytz.UTC)
    
    # Convert to KST (UTC+9)
    kst_now = now.astimezone(KST)
    
    # Current KST day of week (convert to JS style: 0=Sunday)
    day_of_week = (kst_now.weekday() + 1) % 7
    
    # Calculate days difference to this week's Thursday
    if day_of_week < 4:
        # Sunday(0) ~ Wednesday(3)
        days_diff = 4 - day_of_week  # Days forward to Thursday
    elif day_of_week > 4:
        # Friday(5), Saturday(6)
        days_diff = -(day_of_week - 4)  # Days backward to Thursday
    else:
        # Today is Thursday(4)
        days_diff = 0
    
    # Get this week's Thursday
    thursday_night = kst_now + timedelta(days=days_diff)
    
    # Set to 23:59:59
    thursday_night = thursday_night.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Convert to UTC
    thursday_night_utc = thursday_night.astimezone(pytz.UTC)
    
    # If Thursday 23:59:59 is in the future, return current time
    if thursday_night_utc > now:
        return now
    
    return thursday_night_utc


def get_current_week_range() -> Tuple[datetime, datetime]:
    """
    Get current week's date range (Friday 00:00:00 ~ Thursday 23:59:59 KST)
    
    Note: On Friday morning, this returns LAST WEEK's complete range
    (last Friday 00:00 ~ yesterday Thursday 23:59)
    
    Returns:
        Tuple[datetime, datetime]: (start_date, end_date) in UTC
    """
    start_date = get_last_thursday_midnight()
    end_date = get_current_thursday_midnight()
    
    return start_date, end_date


def get_last_week_range() -> Tuple[datetime, datetime]:
    """
    Get last week's complete date range (Friday 00:00:00 ~ Thursday 23:59:59 KST)
    
    This is always the week BEFORE the current week
    
    Returns:
        Tuple[datetime, datetime]: (start_date, end_date) in UTC
    """
    # Get current week start
    current_week_start = get_last_thursday_midnight()
    
    # Last week starts 7 days before
    last_week_start = current_week_start - timedelta(days=7)
    
    # Last week ends just before current week start
    # Thursday 23:59:59 = 1 second before Friday 00:00:00
    last_week_end = current_week_start - timedelta(seconds=1)
    
    return last_week_start, last_week_end


def get_week_range_for_date(target_date: datetime) -> Tuple[datetime, datetime]:
    """
    Get week range that contains the target date
    
    Args:
        target_date: Target date to find week range for
        
    Returns:
        Tuple[datetime, datetime]: (start_date, end_date) in UTC
    """
    # Convert to KST if not already
    if target_date.tzinfo is None:
        target_date = pytz.UTC.localize(target_date).astimezone(KST)
    else:
        target_date = target_date.astimezone(KST)
    
    # Calculate days since last Friday
    days_since_friday = (target_date.weekday() - 4) % 7
    
    # Get Friday of that week
    week_friday = target_date - timedelta(days=days_since_friday)
    week_friday = week_friday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # End is next Friday (7 days later)
    week_end = week_friday + timedelta(days=7)
    
    # Convert to UTC
    return week_friday.astimezone(pytz.UTC), week_end.astimezone(pytz.UTC)


def format_week_title(start_date: datetime) -> str:
    """
    Format week title for display
    
    Args:
        start_date: Week start date (Friday)
        
    Returns:
        str: Formatted week title (e.g., "2025-W45" or "2025-11-07")
    """
    # Convert to KST for display
    if start_date.tzinfo is None:
        start_kst = pytz.UTC.localize(start_date).astimezone(KST)
    else:
        start_kst = start_date.astimezone(KST)
    
    # Format as YYYY-MM-DD
    return start_kst.strftime('%Y-%m-%d')


def get_week_info(start_date: datetime = None, end_date: datetime = None) -> dict:
    """
    Get comprehensive week information
    
    Args:
        start_date: Optional start date (defaults to current week)
        end_date: Optional end date (defaults to current week)
        
    Returns:
        dict: Week information including dates, title, etc.
    """
    if start_date is None or end_date is None:
        start_date, end_date = get_current_week_range()
    
    # Convert to KST for display
    start_kst = start_date.astimezone(KST)
    end_kst = end_date.astimezone(KST)
    
    # Calculate actual end (Thursday 23:59:59)
    actual_end_kst = end_kst - timedelta(seconds=1)
    
    return {
        'start_date': start_date,  # UTC
        'end_date': end_date,      # UTC
        'start_date_kst': start_kst,
        'end_date_kst': actual_end_kst,
        'week_title': format_week_title(start_date),
        'formatted_range': f"{start_kst.strftime('%Y-%m-%d')} ~ {actual_end_kst.strftime('%Y-%m-%d')}",
        'formatted_range_with_time': f"{start_kst.strftime('%Y-%m-%d %H:%M:%S')} ~ {actual_end_kst.strftime('%Y-%m-%d %H:%M:%S')} KST"
    }


if __name__ == "__main__":
    # Test the functions
    print("=" * 70)
    print("Weekly Date Range Test (KST)")
    print("=" * 70)
    
    now = datetime.now(pytz.UTC)
    now_kst = now.astimezone(KST)
    print(f"\n🕐 Current Time: {now_kst.strftime('%Y-%m-%d %H:%M:%S %Z')} ({now_kst.strftime('%A')})")
    
    print("\n📅 Current Week (get_current_week_range):")
    current_info = get_week_info()
    print(f"   Week: {current_info['week_title']}")
    print(f"   Range: {current_info['formatted_range']}")
    print(f"   Full: {current_info['formatted_range_with_time']}")
    print(f"   Note: On Friday, this is the PREVIOUS complete week")
    
    print("\n📅 Last Week (get_last_week_range):")
    last_start, last_end = get_last_week_range()
    last_info = get_week_info(last_start, last_end)
    print(f"   Week: {last_info['week_title']}")
    print(f"   Range: {last_info['formatted_range']}")
    print(f"   Full: {last_info['formatted_range_with_time']}")
    
    # Test raw functions
    print("\n🔍 Raw Function Outputs:")
    start = get_last_thursday_midnight()
    end = get_current_thursday_midnight()
    start_kst = start.astimezone(KST)
    end_kst = end.astimezone(KST)
    print(f"   get_last_thursday_midnight():    {start_kst.strftime('%Y-%m-%d %H:%M:%S %Z')} ({start_kst.strftime('%A')})")
    print(f"   get_current_thursday_midnight():  {end_kst.strftime('%Y-%m-%d %H:%M:%S %Z')} ({end_kst.strftime('%A')})")
    
    print("\n" + "=" * 70)

