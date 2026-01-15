# Frontend-Backend API Architecture

**Last Updated**: 2026-01-15  
**Purpose**: Document how the frontend communicates with the backend API

---

## 🎯 Key Architecture Decisions

### **CRITICAL: Frontend Uses GraphQL, NOT REST API**

The frontend (`frontend/src/`) communicates with the backend exclusively via **GraphQL**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js)                                                         │
│                                                                             │
│  ActivitiesView.tsx, Dashboard, Members, etc.                               │
│                                                                             │
│      │                                                                      │
│      │  POST /graphql                                                       │
│      │  (NOT /api/v1/activities)                                           │
│      ▼                                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Backend (FastAPI)                                                          │
│                                                                             │
│  GraphQL Endpoint: /graphql                                                 │
│  Resolver: backend/graphql/queries.py                                       │
│                                                                             │
│      │                                                                      │
│      ▼                                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  MongoDB Collections                                                        │
│                                                                             │
│  • github_commits, github_pull_requests                                     │
│  • slack_messages                                                           │
│  • notion_content_diffs (NOT notion_pages)                                  │
│  • drive_files                                                              │
│  • recordings_daily                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📡 API Endpoints

### GraphQL Endpoint (Primary - Used by Frontend)

| Endpoint | Method | Description |
| --- | --- | --- |
| `/graphql` | POST | Main GraphQL endpoint for all queries |
| `/graphql` | GET | GraphQL Playground (development only) |

**Resolver Location**: `backend/graphql/queries.py`

### REST Endpoints (Secondary - Used for Admin/Scripts)

| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/v1/activities` | GET | Legacy REST API (not used by frontend) |
| `/api/v1/notion/diffs` | GET | Notion diff data (REST fallback) |
| `/api/v1/members` | GET/POST | Member management |
| `/api/v1/database/collections` | GET | Database exploration |

---

## 🗄️ MongoDB Collections by Source

### GitHub
- `github_commits` - Commit activities
- `github_pull_requests` - Pull request activities

### Slack
- `slack_messages` - Messages with threads and reactions

### Notion (Important!)
| Collection | Usage | Description |
| --- | --- | --- |
| `notion_pages` | ❌ **Legacy** | 24-hour collection of page metadata |
| `notion_content_diffs` | ✅ **Current** | 1-minute granular content changes |

**Note**: The GraphQL resolver for Notion activities reads from `notion_content_diffs`, not `notion_pages`.

### Google Drive
- `drive_files` - File activities and changes

### Recordings
- `recordings` - Meeting recordings
- `recordings_daily` - Daily analysis summaries

---

## 📝 GraphQL Query: GetActivities

The frontend's `ActivitiesView.tsx` uses this query:

```graphql
query GetActivities(
  $source: SourceType
  $memberName: String
  $projectKey: String
  $keyword: String
  $startDate: DateTime
  $endDate: DateTime
  $limit: Int
  $offset: Int
) {
  activities(
    source: $source
    memberName: $memberName
    projectKey: $projectKey
    keyword: $keyword
    startDate: $startDate
    endDate: $endDate
    limit: $limit
    offset: $offset
  ) {
    id
    memberName
    sourceType
    activityType
    timestamp
    metadata
    message
    repository
    url
    additions
    deletions
  }
}
```

---

## 🔄 Data Flow Example: Notion Activities

```
1. User selects "Notion" filter in frontend
   ↓
2. Frontend sends GraphQL query:
   POST /graphql
   { query: "GetActivities", variables: { source: "NOTION", limit: 500 } }
   ↓
3. Backend resolves query in queries.py:
   - Detects source = "notion"
   - Queries db['notion_content_diffs'] collection
   - Maps document fields to Activity type
   ↓
4. Response returned to frontend:
   {
     "data": {
       "activities": [
         {
           "memberName": "Thomas Shin",
           "sourceType": "notion",
           "activityType": "notion_block",
           "metadata": {
             "additions": 5,
             "deletions": 2,
             "changes": { "added": [...], "deleted": [...] }
           }
         }
       ]
     }
   }
   ↓
5. Frontend renders activity with diff display
```

---

## ⚠️ Common Mistakes to Avoid

### 1. Don't Modify REST API When Fixing Frontend Issues

❌ **Wrong**:
```python
# Modifying backend/api/v1/activities_mongo.py
# This won't affect the frontend!
```

✅ **Correct**:
```python
# Modify backend/graphql/queries.py
# This is what the frontend actually uses
```

### 2. Remember Collection Names

❌ **Wrong**:
```python
# Looking for Notion data in notion_pages
db['notion_pages'].find(...)  # Old 24-hour collection
```

✅ **Correct**:
```python
# Use notion_content_diffs for granular changes
db['notion_content_diffs'].find(...)  # New 1-minute collection
```

### 3. Check Backend Logs for Query Source

When debugging, check backend logs:
```
🔍 [12345] ===== GraphQL Activities Query Start =====
🔍 [12345] Strawberry variable_values: {'source': <SourceType.NOTION: 'notion'>, ...}
🔍 [12345] 📝 Notion query: {}
🔍 [12345] 📝 Notion diff activities added: 16
```

This confirms GraphQL is being used (not REST).

---

## 🔧 Modifying Activity Data Display

### Step 1: Identify the Source
Check which collection provides the data in `backend/graphql/queries.py`

### Step 2: Modify the GraphQL Resolver
Update the relevant section in `queries.py`:

```python
# Example: Notion section (line ~1002)
if 'notion' in sources:
    async for doc in db['notion_content_diffs'].find(query)...
        activities.append(Activity(
            metadata=sanitize_metadata({
                'additions': ...,
                'deletions': ...,
                'changes': ...
            })
        ))
```

### Step 3: Update Frontend Component
Modify `frontend/src/components/ActivitiesView.tsx` to display new fields:

```tsx
{activity.source_type === "notion" && (
  <div>
    <span>+{activity.metadata.additions}</span>
    <span>-{activity.metadata.deletions}</span>
  </div>
)}
```

### Step 4: Restart Backend
```bash
python -m backend.main
```

---

## 📊 Source Type Mapping

| Source | GraphQL Enum | Collection(s) |
| --- | --- | --- |
| GitHub | `GITHUB` | `github_commits`, `github_pull_requests` |
| Slack | `SLACK` | `slack_messages` |
| Notion | `NOTION` | `notion_content_diffs` |
| Drive | `DRIVE` | `drive_files` |
| Recordings | `RECORDINGS` | `recordings` |
| Daily Analysis | `RECORDINGS_DAILY` | `recordings_daily` |

---

## 📚 Related Documentation

- [GraphQL Quick Start](./GRAPHQL_QUICKSTART.md) - How to use GraphQL
- [Database Schema](./DATABASE_SCHEMA.md) - MongoDB collection structures
- [Architecture](./ARCHITECTURE.md) - Overall system design
- [Data Collection Guide](./data-collection/upgrade-api.md) - Notion/Drive diff collection

---

## 🆕 Recent Changes

### 2026-01-15: Notion Diff Integration
- GraphQL resolver now uses `notion_content_diffs` instead of `notion_pages`
- New `notion_block` and `notion_comment` activity types
- Frontend displays additions/deletions with change details
