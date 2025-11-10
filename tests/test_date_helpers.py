#!/usr/bin/env python
"""
Test script for date helper functions

This script tests the weekly date range calculation (Friday ~ Thursday KST)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.date_helpers import (
    get_current_week_range,
    get_last_week_range,
    get_week_info,
    get_last_friday_midnight_kst,
    get_current_thursday_midnight_kst
)
from datetime import datetime
import pytz


def main():
    print("=" * 70)
    print("📅 Weekly Date Range Test (KST)")
    print("=" * 70)
    
    # Current time
    now_utc = datetime.now(pytz.UTC)
    now_kst = now_utc.astimezone(pytz.timezone('Asia/Seoul'))
    print(f"\n🕐 Current Time:")
    print(f"   UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   KST: {now_kst.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   Day of Week: {now_kst.strftime('%A')}")
    
    # Current week
    print(f"\n📅 Current Week (This Week):")
    current_start, current_end = get_current_week_range()
    current_info = get_week_info(current_start, current_end)
    
    print(f"   Week ID: {current_info['week_title']}")
    print(f"   Range: {current_info['formatted_range']}")
    print(f"   Full: {current_info['formatted_range_with_time']}")
    print(f"\n   Start (UTC): {current_start.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   End (UTC):   {current_end.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Last week (complete)
    print(f"\n📅 Last Week (Complete):")
    last_start, last_end = get_last_week_range()
    last_info = get_week_info(last_start, last_end)
    
    print(f"   Week ID: {last_info['week_title']}")
    print(f"   Range: {last_info['formatted_range']}")
    print(f"   Full: {last_info['formatted_range_with_time']}")
    print(f"\n   Start (UTC): {last_start.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   End (UTC):   {last_end.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Verify logic
    print(f"\n✅ Verification:")
    
    # Check that current week starts on Friday
    current_start_kst = current_start.astimezone(pytz.timezone('Asia/Seoul'))
    print(f"   Current week starts on: {current_start_kst.strftime('%A')} (should be Friday)")
    assert current_start_kst.strftime('%A') == 'Friday', "Current week should start on Friday!"
    
    # Check that it's midnight
    print(f"   Current week starts at: {current_start_kst.strftime('%H:%M:%S')} (should be 00:00:00)")
    assert current_start_kst.hour == 0 and current_start_kst.minute == 0, "Should start at midnight!"
    
    # Check that last week also starts on Friday
    last_start_kst = last_start.astimezone(pytz.timezone('Asia/Seoul'))
    print(f"   Last week starts on: {last_start_kst.strftime('%A')} (should be Friday)")
    assert last_start_kst.strftime('%A') == 'Friday', "Last week should start on Friday!"
    
    # Check that weeks are 7 days apart
    days_diff = (current_start - last_start).days
    print(f"   Weeks are {days_diff} days apart (should be 7)")
    assert days_diff == 7, "Weeks should be exactly 7 days apart!"
    
    print("\n✅ All checks passed!")
    
    print("\n" + "=" * 70)
    print("📌 Usage Example:")
    print("=" * 70)
    print("""
# In your collection script:
from src.utils.date_helpers import get_current_week_range, get_week_info

# Get current week range
start_date, end_date = get_current_week_range()

# Collect data
data = github_plugin.collect_data(start_date, end_date)

# Get week info for display
week_info = get_week_info(start_date, end_date)
print(f"Collected data for week: {week_info['week_title']}")
print(f"Range: {week_info['formatted_range']}")
""")
    print("=" * 70)


if __name__ == "__main__":
    main()

