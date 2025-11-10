# Weekly Data Collection Guide

## 📅 Weekly Cycle Definition

The system uses a **Friday-to-Thursday** weekly cycle based on **KST (Korea Standard Time)**:

- **Week Start**: Friday 00:00:00 KST
- **Week End**: Thursday 23:59:59 KST

This matches the workflow used in the original TypeScript github-reporter project.

## 🕐 Why Friday to Thursday?

1. **Team Workflow**: Aligns with weekly planning and review cycles
2. **Reporting**: Weekly reports are typically generated on Fridays
3. **Consistency**: Matches existing reporting infrastructure

## 📊 Date Range Examples

### Example 1: Collection on Monday

```
Current Date: Monday, 2025-11-11 14:30 KST

Current Week (get_current_week_range):
  Start: Friday, 2025-11-08 00:00:00 KST
  End:   Monday, 2025-11-11 14:30:00 KST (current time)
  Status: ⏳ In progress (3.5 days so far)

Last Week (get_last_week_range):
  Start: Friday, 2025-11-01 00:00:00 KST
  End:   Thursday, 2025-11-07 23:59:59 KST
  Status: Complete
```

**Note**: End time is current time because Thursday 23:59:59 is in the future.

### Example 2: Collection on Friday ⭐ (Most Common)

```
Current Date: Friday, 2025-11-14 09:00 KST

Current Week (get_current_week_range):
  Start: Friday, 2025-11-07 00:00:00 KST (last week)
  End:   Thursday, 2025-11-13 23:59:59 KST (yesterday)
  Status: ✅ Complete (collects PREVIOUS week's complete data)

Last Week (get_last_week_range):
  Start: Friday, 2025-10-31 00:00:00 KST
  End:   Thursday, 2025-11-06 23:59:59 KST
  Status: Complete (week before previous)
```

**Important**: On Friday, `get_current_week_range()` returns the PREVIOUS complete week, not the current ongoing week!

### Example 3: Collection on Thursday (Last Day of Week)

```
Current Date: Thursday, 2025-11-13 22:00 KST

Current Week (get_current_week_range):
  Start: Friday, 2025-11-08 00:00:00 KST
  End:   Thursday, 2025-11-13 22:00:00 KST (current time)
  Status: ⏳ Almost complete (2 hours until Friday)

Last Week (get_last_week_range):
  Start: Friday, 2025-11-01 00:00:00 KST
  End:   Thursday, 2025-11-07 23:59:59 KST
  Status: Complete
```

**Note**: Running at Thursday 22:00 gives you 6 days + 22 hours of data.

## 🔧 Usage in Code

### Get Current Week Range

```python
from src.utils.date_helpers import get_current_week_range, get_week_info

# Get date range for current week
start_date, end_date = get_current_week_range()

# Get detailed week information
week_info = get_week_info(start_date, end_date)

print(f"Week: {week_info['week_title']}")           # "2025-11-07"
print(f"Range: {week_info['formatted_range']}")     # "2025-11-07 ~ 2025-11-13"
```

### Get Last Week Range (Complete)

```python
from src.utils.date_helpers import get_last_week_range

# Get complete last week
start_date, end_date = get_last_week_range()

# Collect data for complete week
data = github_plugin.collect_data(start_date, end_date)
```

### Get Week for Specific Date

```python
from src.utils.date_helpers import get_week_range_for_date
from datetime import datetime

# Find which week contains a specific date
target_date = datetime(2025, 11, 10)  # Monday
start, end = get_week_range_for_date(target_date)

# Returns: Friday 2025-11-07 ~ Friday 2025-11-14
```

## 🤖 Automated Collection Strategy

### Daily Collection (Recommended)

Run every day at midnight KST to collect yesterday's data:

```python
from src.utils.date_helpers import get_current_week_range

# Runs daily at 00:05 KST
start_date, end_date = get_current_week_range()
collect_data(start_date, end_date)

# Data is accumulated throughout the week
# No duplicates due to UNIQUE constraints in DB
```

**Benefits**:
- ✅ Fresh data every day
- ✅ Catches late commits/PRs
- ✅ Spreads API calls across the week
- ✅ No duplicates (INSERT OR IGNORE)

### Weekly Collection

Run once per week on Friday morning:

```python
from src.utils.date_helpers import get_last_week_range

# Runs Friday at 01:00 KST
start_date, end_date = get_last_week_range()
collect_data(start_date, end_date)

# Collects complete week all at once
```

**Benefits**:
- ✅ Complete week data in one go
- ✅ Fewer runs needed
- ❌ More API calls at once
- ❌ Misses this week's early data

## 📅 Week Identification

Weeks are identified by their start date (Friday):

```
Week ID Format: YYYY-MM-DD

Examples:
- 2025-11-07  (Week starting Friday, Nov 7)
- 2025-11-14  (Week starting Friday, Nov 14)
- 2025-11-21  (Week starting Friday, Nov 21)
```

This makes it easy to:
- Store data by week
- Query specific weeks
- Compare weeks
- Generate reports

## 🔄 Data Update Strategy

### Option 1: Incremental Daily Updates (Recommended)

```bash
# Cron job: Daily at 00:05 KST
5 0 * * * cd /path/to/project && python scripts/daily_collect.py
```

```python
# scripts/daily_collect.py
from src.utils.date_helpers import get_current_week_range
from src.core.plugin_loader import PluginLoader

# Collect current week data
start, end = get_current_week_range()
data = collect_github_data(start, end)

# Database automatically handles duplicates
save_to_database(data)
```

### Option 2: Weekly Batch Collection (Recommended for Complete Weeks)

```bash
# Cron job: Every Friday at 01:00 KST
0 1 * * 5 cd /path/to/project && python scripts/weekly_collect.py
```

```python
# scripts/weekly_collect.py
from src.utils.date_helpers import get_current_week_range

# On Friday morning, this gets the PREVIOUS complete week!
start, end = get_current_week_range()
data = collect_github_data(start, end)
save_to_database(data)

# Result: Last Friday 00:00 ~ Yesterday Thursday 23:59
```

**Perfect for**:
- ✅ Complete weekly reports
- ✅ Friday morning collection gets yesterday's complete week
- ✅ Clean 7-day periods

### Option 3: Hybrid Approach

```bash
# Daily updates for current week
5 0 * * * cd /path/to/project && python scripts/daily_collect.py

# Weekly finalization for last week
0 1 * * 5 cd /path/to/project && python scripts/weekly_finalize.py
```

## 🌍 Timezone Handling

The system handles timezones automatically:

1. **Input**: Dates are in KST for human readability
2. **Storage**: Converted to UTC for API calls and database
3. **Display**: Converted back to KST for reports

```python
# Internal handling (automatic)
start_kst = datetime(2025, 11, 7, 0, 0, 0, tzinfo=KST)
start_utc = start_kst.astimezone(UTC)  # Used for GitHub API

# Database stores UTC
# Reports show KST
```

## 📊 Testing Date Functions

```bash
# Test the date helper functions
python tests/test_date_helpers.py
```

Output:
```
======================================================================
📅 Weekly Date Range Test (KST)
======================================================================

🕐 Current Time:
   UTC: 2025-11-10 05:30:00 UTC
   KST: 2025-11-10 14:30:00 KST
   Day of Week: Monday

📅 Current Week (This Week):
   Week ID: 2025-11-07
   Range: 2025-11-07 ~ 2025-11-13
   Full: 2025-11-07 00:00:00 ~ 2025-11-13 23:59:59 KST

📅 Last Week (Complete):
   Week ID: 2025-10-31
   Range: 2025-10-31 ~ 2025-11-06
   Full: 2025-10-31 00:00:00 ~ 2025-11-06 23:59:59 KST

✅ All checks passed!
```

## 🚀 Quick Start

### Test Current Week Collection

```bash
# Collect current week data (Friday ~ now)
python tests/test_github_plugin.py
```

### Test Date Calculations

```bash
# Verify date ranges are correct
python tests/test_date_helpers.py
```

### Manual Collection for Specific Week

```python
from src.utils.date_helpers import get_week_range_for_date
from datetime import datetime

# Get week containing October 15, 2025
target = datetime(2025, 10, 15)
start, end = get_week_range_for_date(target)

# Collect that week's data
data = github_plugin.collect_data(start, end)
```

## 📚 API Reference

### Functions

| Function | Description | Returns |
|----------|-------------|---------|
| `get_current_week_range()` | Current week: Friday ~ now | `(start, end)` in UTC |
| `get_last_week_range()` | Last complete week | `(start, end)` in UTC |
| `get_week_range_for_date(date)` | Week containing date | `(start, end)` in UTC |
| `get_week_info(start, end)` | Detailed week info | `dict` with formatted dates |
| `format_week_title(start)` | Week ID string | `"YYYY-MM-DD"` |

### Week Info Dictionary

```python
{
    'start_date': datetime,           # UTC
    'end_date': datetime,             # UTC
    'start_date_kst': datetime,       # KST
    'end_date_kst': datetime,         # KST (actual end: Thursday 23:59:59)
    'week_title': '2025-11-07',
    'formatted_range': '2025-11-07 ~ 2025-11-13',
    'formatted_range_with_time': '2025-11-07 00:00:00 ~ 2025-11-13 23:59:59 KST'
}
```

## 🔍 Comparison with github-reporter

| Feature | github-reporter (TS) | all-thing-eye (Python) |
|---------|---------------------|------------------------|
| Week Start | Friday 00:00 KST | Friday 00:00 KST ✅ |
| Week End | Thursday 23:59 KST | Thursday 23:59 KST ✅ |
| Function | `getLastThursdayMidnight()` | `get_last_friday_midnight_kst()` |
| Function | `getCurrentThursdayMidnight()` | `get_current_thursday_midnight_kst()` |
| Timezone | pytz (Asia/Seoul) | pytz (Asia/Seoul) ✅ |

The Python implementation is **fully compatible** with the TypeScript version! 🎉

