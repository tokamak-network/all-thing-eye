# Data Collector Status Tracking

## Overview

This document explains the data collector status tracking system implemented to accurately show when data collectors last ran, regardless of whether they collected data.

## Problem

Previously, the Data Freshness indicator showed when the **most recent data was created** (e.g., when a Slack message was posted), not when the **collector last ran**. This caused issues:

- If the collector ran but found no new data, it would show as "Stale"
- Users couldn't tell if the collector was actually running
- The indicator didn't reflect the actual data sync status

## Solution

### New Collection: `collection_status`

A new MongoDB collection tracks every collection run:

```javascript
{
  source: "slack",                        // github, slack, notion, drive
  started_at: ISODate("2025-12-17T00:00:00Z"),
  completed_at: ISODate("2025-12-17T00:10:00Z"),
  duration_seconds: 600,
  status: "success",                       // success, failed, disabled
  items_collected: 132,
  error_message: null
}
```

### Changes Made

#### 1. Data Collection Script (`daily_data_collection_mongo.py`)

Each `collect_*()` function now:
- Records start time
- Tracks items collected
- Records status (success/failed/disabled)
- Captures error messages
- Saves to `collection_status` collection in `finally` block

```python
async def collect_slack(...):
    start_time = datetime.utcnow()
    status = "failed"
    items_collected = 0
    error_message = None
    
    try:
        # ... collection logic ...
        items_collected = len(messages)
        status = "success"
    except Exception as e:
        error_message = str(e)
    finally:
        await record_collection_status(
            mongo_manager, "slack", start_time, status, items_collected, error_message
        )
```

#### 2. API Endpoint (`stats_mongo.py`)

The `/api/v1/stats/summary` endpoint now reads from `collection_status`:

```python
# Find most recent collection status for each source
status_doc = await collection_status_coll.find_one(
    {'source': source},
    sort=[('completed_at', -1)]
)
last_collected[source] = status_doc['completed_at'].isoformat() + 'Z'
```

#### 3. Frontend (No Changes Needed)

The frontend continues to use the same `last_collected` field, but now it reflects when the collector last ran.

## Benefits

### ✅ Accurate Freshness Indicator

- Shows when collector **last ran**, not when data was created
- "Fresh" = collector ran within 24 hours
- "1d old" = collector ran 24-48 hours ago
- "Stale" = collector hasn't run in 48+ hours

### 📊 Additional Insights Available

The `collection_status` collection provides:
- Success/failure tracking
- Items collected per run
- Collection duration
- Error messages for debugging
- Historical trend data

### 🔍 Better Debugging

Admins can query collection history:

```javascript
// Find failed collections
db.collection_status.find({ status: "failed" })

// Check recent Slack collections
db.collection_status.find({ source: "slack" }).sort({ completed_at: -1 }).limit(10)

// Average items collected
db.collection_status.aggregate([
  { $match: { source: "slack", status: "success" } },
  { $group: { _id: null, avg: { $avg: "$items_collected" } } }
])
```

## Deployment

### 1. Commit and Push Changes

```bash
git add scripts/daily_data_collection_mongo.py backend/api/v1/stats_mongo.py
git commit -m "feat: add collection status tracking for accurate data freshness"
git push origin main
```

### 2. Deploy to AWS

```bash
# SSH to AWS server
ssh ubuntu@your-server

# Pull latest changes
cd ~/all-thing-eye
git pull origin main

# Rebuild and restart services
docker-compose -f docker-compose.prod.yml up -d --build backend data-collector

# Verify collection_status is being populated
docker-compose -f docker-compose.prod.yml exec backend python -c "
from backend.main import mongo_manager
db = mongo_manager.sync_db
print(list(db.collection_status.find().sort('completed_at', -1).limit(5)))
"
```

### 3. Wait for Next Collection

The next collection (midnight KST) will populate `collection_status`. After that, the Data Freshness indicator will accurately reflect collector status.

### 4. Verify in Dashboard

After the next collection runs:
1. Open dashboard: https://your-domain.com
2. Check "Data Freshness" section
3. All sources should show "✓ Fresh" if collection succeeded

## Future Enhancements

### Possible Additions

1. **Collection Analytics Dashboard**
   - Success rate over time
   - Average collection duration
   - Items collected trends
   
2. **Alerting System**
   - Email/Slack notifications on collection failures
   - Alert if no collection in 48 hours
   
3. **Retry Logic**
   - Automatic retry on failure
   - Exponential backoff
   
4. **Health Endpoint**
   - `/api/v1/health/collectors` showing real-time status
   - Integration with monitoring systems (DataDog, New Relic)

## Schema

### `collection_status` Collection

| Field | Type | Description |
|-------|------|-------------|
| `source` | string | Data source (github, slack, notion, drive) |
| `started_at` | datetime | When collection started (UTC) |
| `completed_at` | datetime | When collection finished (UTC) |
| `duration_seconds` | float | How long collection took |
| `status` | string | success, failed, disabled |
| `items_collected` | int | Number of items collected |
| `error_message` | string? | Error details if failed |

### Index Recommendations

```javascript
// For fast lookup of recent status
db.collection_status.createIndex({ source: 1, completed_at: -1 })

// For status filtering
db.collection_status.createIndex({ status: 1, completed_at: -1 })
```

## Maintenance

### Data Retention

Consider implementing retention policy to prevent collection from growing indefinitely:

```python
# Keep only last 90 days of collection status
retention_date = datetime.utcnow() - timedelta(days=90)
db.collection_status.delete_many({ 'completed_at': { '$lt': retention_date } })
```

### Monitoring Queries

```javascript
// Collections in last 24 hours
db.collection_status.find({
  completed_at: { $gte: new Date(Date.now() - 24*60*60*1000) }
})

// Failed collections
db.collection_status.find({ status: "failed" }).sort({ completed_at: -1 })

// Average duration by source
db.collection_status.aggregate([
  { $group: {
    _id: "$source",
    avg_duration: { $avg: "$duration_seconds" },
    total_items: { $sum: "$items_collected" }
  }}
])
```

## Summary

The collection status tracking system provides:
- ✅ Accurate data freshness indicators
- ✅ Collector health monitoring
- ✅ Historical tracking
- ✅ Better debugging capabilities
- ✅ Foundation for alerting and analytics

This ensures users always know if the data sync is working, regardless of whether new data was found.

