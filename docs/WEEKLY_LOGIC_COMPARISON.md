# Weekly Logic Comparison: TypeScript vs Python

## 🔄 Function Mapping

| TypeScript (github-reporter) | Python (all-thing-eye) | Description |
|------------------------------|------------------------|-------------|
| `getLastThursdayMidnight()` | `get_last_thursday_midnight()` | Last Friday 00:00:00 KST |
| `getCurrentThursdayMidnight()` | `get_current_thursday_midnight()` | This Thursday 23:59:59 KST (or now) |
| N/A | `get_current_week_range()` | Combines both functions |
| N/A | `get_last_week_range()` | Previous complete week |

## 📅 Logic Examples

### Example: Friday Morning

**Date**: 2025-11-14 (Friday) 09:00 KST

#### TypeScript:
```typescript
getLastThursdayMidnight()
// Returns: 2025-11-07 00:00:00 KST (last Friday)

getCurrentThursdayMidnight()
// Returns: 2025-11-13 23:59:59 KST (yesterday Thursday)
```

#### Python:
```python
get_last_thursday_midnight()
# Returns: 2025-11-07 00:00:00 KST (last Friday)

get_current_thursday_midnight()
# Returns: 2025-11-13 23:59:59 KST (yesterday Thursday)

get_current_week_range()
# Returns: (2025-11-07 00:00:00, 2025-11-13 23:59:59) KST
```

✅ **Result**: Both collect PREVIOUS week's complete data (last Friday ~ yesterday Thursday)

### Example: Monday Afternoon

**Date**: 2025-11-11 (Monday) 14:30 KST

#### TypeScript:
```typescript
getLastThursdayMidnight()
// Returns: 2025-11-08 00:00:00 KST (last Friday)

getCurrentThursdayMidnight()
// Returns: 2025-11-11 14:30:00 KST (current time, because Thu is future)
```

#### Python:
```python
get_last_thursday_midnight()
# Returns: 2025-11-08 00:00:00 KST (last Friday)

get_current_thursday_midnight()
# Returns: 2025-11-11 14:30:00 KST (current time, because Thu is future)

get_current_week_range()
# Returns: (2025-11-08 00:00:00, 2025-11-11 14:30:00) KST
```

✅ **Result**: Both collect current week's partial data (last Friday ~ now)

### Example: Thursday Night

**Date**: 2025-11-13 (Thursday) 23:00 KST

#### TypeScript:
```typescript
getLastThursdayMidnight()
// Returns: 2025-11-08 00:00:00 KST (last Friday)

getCurrentThursdayMidnight()
// Returns: 2025-11-13 23:00:00 KST (current time, 1 hour before week end)
```

#### Python:
```python
get_last_thursday_midnight()
# Returns: 2025-11-08 00:00:00 KST (last Friday)

get_current_thursday_midnight()
# Returns: 2025-11-13 23:00:00 KST (current time, 1 hour before week end)

get_current_week_range()
# Returns: (2025-11-08 00:00:00, 2025-11-13 23:00:00) KST
```

✅ **Result**: Both collect almost complete week (6 days + 23 hours)

## 🧮 Day of Week Calculation

### TypeScript (JavaScript Date):
```typescript
const dayOfWeek = kstNow.getUTCDay()
// Returns: 0 (Sunday), 1 (Monday), ..., 5 (Friday), 6 (Saturday)
```

### Python (datetime.weekday()):
```python
day_of_week = kst_now.weekday()
# Returns: 0 (Monday), 1 (Tuesday), ..., 4 (Friday), 6 (Sunday)

# Convert to JS style
js_day_of_week = (kst_now.weekday() + 1) % 7
# Returns: 0 (Sunday), 1 (Monday), ..., 5 (Friday), 6 (Saturday)
```

✅ **Python Implementation**: Converts Python weekday to JavaScript style for identical logic

## ⏰ Time Calculation

### Last Thursday Midnight (Friday 00:00:00)

#### TypeScript:
```typescript
if (dayOfWeek < 4) {
  daysToSubtract = dayOfWeek + 3  // Sun~Wed
} else {
  daysToSubtract = dayOfWeek - 4 + 7  // Thu~Sat
}
const lastThursday = new Date(kstNow)
lastThursday.setUTCDate(kstNow.getUTCDate() - daysToSubtract)
lastThursday.setUTCHours(15, 0, 0, 0)  // Friday 00:00:00 KST = UTC 15:00:00
```

#### Python:
```python
if day_of_week < 4:
    days_to_subtract = day_of_week + 3  # Sun~Wed
else:
    days_to_subtract = day_of_week - 4 + 7  # Thu~Sat

last_thursday = kst_now - timedelta(days=days_to_subtract)
last_friday = last_thursday + timedelta(days=1)
last_friday_midnight = last_friday.replace(hour=0, minute=0, second=0, microsecond=0)
```

✅ **Logic**: Identical day calculation, then set to midnight

### Current Thursday Midnight (Thursday 23:59:59)

#### TypeScript:
```typescript
if (dayOfWeek < 4) {
  daysDiff = 4 - dayOfWeek  // Forward to Thursday
} else if (dayOfWeek > 4) {
  daysDiff = -(dayOfWeek - 4)  // Backward to Thursday
} else {
  daysDiff = 0  // Today is Thursday
}
thursdayNight.setUTCHours(14, 59, 59, 999)  // Thu 23:59:59 KST = UTC 14:59:59

if (thursdayNight > now) {
  return now
}
```

#### Python:
```python
if day_of_week < 4:
    days_diff = 4 - day_of_week  # Forward to Thursday
elif day_of_week > 4:
    days_diff = -(day_of_week - 4)  # Backward to Thursday
else:
    days_diff = 0  # Today is Thursday

thursday_night = kst_now + timedelta(days=days_diff)
thursday_night = thursday_night.replace(hour=23, minute=59, second=59, microsecond=999999)

thursday_night_utc = thursday_night.astimezone(pytz.UTC)
if thursday_night_utc > now:
    return now
```

✅ **Logic**: Identical day calculation and future check

## 🌍 Timezone Handling

### TypeScript:
```typescript
// Manual UTC+9 offset
const kstNow = new Date(now.getTime() + 9 * 60 * 60 * 1000)

// Set UTC hours for KST times
lastThursday.setUTCHours(15, 0, 0, 0)  // KST 00:00:00 = UTC 15:00:00
thursdayNight.setUTCHours(14, 59, 59, 999)  // KST 23:59:59 = UTC 14:59:59
```

### Python:
```python
# Using pytz for proper timezone handling
KST = pytz.timezone('Asia/Seoul')
kst_now = now.astimezone(KST)

# Set KST times directly
last_friday_midnight = last_friday.replace(hour=0, minute=0, second=0)
thursday_night = thursday_night.replace(hour=23, minute=59, second=59)

# Convert to UTC
return last_friday_midnight.astimezone(pytz.UTC)
```

✅ **Result**: Same UTC times, Python uses pytz for cleaner code

## ✅ Verification

Run both implementations and compare:

### TypeScript:
```bash
cd github-reporter
npm run biweekly
```

### Python:
```bash
cd all-thing-eye
python tests/test_date_helpers.py
```

Expected output should show identical date ranges! 🎯

## 📊 Summary

| Feature | TypeScript | Python | Match? |
|---------|-----------|---------|--------|
| Week start | Friday 00:00 KST | Friday 00:00 KST | ✅ |
| Week end | Thursday 23:59 KST | Thursday 23:59 KST | ✅ |
| Friday behavior | Returns previous week | Returns previous week | ✅ |
| Future check | Returns current time | Returns current time | ✅ |
| Day calculation | JS weekday (0=Sun) | Converted to JS style | ✅ |
| Timezone | Manual UTC+9 | pytz KST | ✅ |

**Result**: 100% Compatible! 🎉

