# MongoDB Schema Design

**Document-Oriented Schema for All-Thing-Eye**

This document describes the MongoDB schema design for the All-Thing-Eye project, converted from the original relational database structure.

---

## 📋 **Table of Contents**

1. [Schema Design Philosophy](#schema-design-philosophy)
2. [Main Collections](#main-collections)
3. [Plugin Collections](#plugin-collections)
4. [Data Denormalization Strategy](#data-denormalization-strategy)
5. [Index Strategy](#index-strategy)
6. [Migration Notes](#migration-notes)

---

## 🎯 **Schema Design Philosophy**

### **Relational → Document Transformation**

**Original Relational Structure:**
- Multiple tables with foreign keys
- JOIN operations for cross-table queries
- Normalized data (avoid duplication)

**MongoDB Document Structure:**
- Embedded documents for 1:1 and 1:N relationships
- References for M:N relationships
- Selective denormalization for query performance

---

## 📊 **Main Collections**

### **1. `members` Collection**

**Purpose:** Store team member information with embedded identifiers

```javascript
{
  _id: ObjectId("..."),
  name: "Jake Jang",
  email: "jake@tokamak.network",
  role: "Developer",
  team: "Project OOO",
  github_username: "jake-jang",  // Denormalized for quick access
  slack_id: "U06NU86J75M",       // Denormalized for quick access
  
  // Embedded identifiers (was separate table in SQL)
  identifiers: [
    {
      source_type: "github",
      source_user_id: "jake-jang",
      source_user_name: "Jake Jang",
      metadata: {}
    },
    {
      source_type: "slack",
      source_user_id: "U06NU86J75M",
      source_user_name: "Jake Jang",
      metadata: {
        real_name: "Jake Jang",
        display_name: "Jake"
      }
    }
  ],
  
  // Metadata
  created_at: ISODate("2025-01-01T00:00:00Z"),
  updated_at: ISODate("2025-11-17T00:00:00Z")
}
```

**Indexes:**
```javascript
db.members.createIndex({ "name": 1 }, { unique: true })
db.members.createIndex({ "email": 1 })
db.members.createIndex({ "role": 1 })
db.members.createIndex({ "github_username": 1 })
db.members.createIndex({ "slack_id": 1 })
db.members.createIndex({ "identifiers.source_type": 1, "identifiers.source_user_id": 1 })
```

---

### **2. `member_activities` Collection**

**Purpose:** Unified activity log from all data sources

```javascript
{
  _id: ObjectId("..."),
  activity_id: "github_commit_ff65a28...",  // Unique activity hash
  
  // Member reference
  member_id: ObjectId("..."),  // Reference to members collection
  member_name: "Jake Jang",    // Denormalized for quick display
  
  // Activity details
  source_type: "github",       // github, slack, notion, google_drive
  activity_type: "commit",     // commit, pull_request, message, reaction, etc.
  timestamp: ISODate("2025-11-06T10:30:00Z"),
  
  // Activity metadata (flexible JSON)
  metadata: {
    repository: "Tokamak-zk-EVM",
    sha: "ff65a28",
    message: "Update L2 documentation",
    additions: 150,
    deletions: 20,
    url: "https://github.com/tokamak-network/Tokamak-zk-EVM/commit/ff65a28"
  },
  
  // Timestamps
  created_at: ISODate("2025-11-06T10:30:05Z")
}
```

**Indexes:**
```javascript
db.member_activities.createIndex({ "activity_id": 1 }, { unique: true })
db.member_activities.createIndex({ "member_id": 1 })
db.member_activities.createIndex({ "source_type": 1 })
db.member_activities.createIndex({ "activity_type": 1 })
db.member_activities.createIndex({ "timestamp": -1 })
db.member_activities.createIndex({ "member_id": 1, "timestamp": -1 })
db.member_activities.createIndex({ "source_type": 1, "activity_type": 1 })
db.member_activities.createIndex({ "member_name": 1 })  // For quick lookups
```

---

### **3. `data_collections` Collection**

**Purpose:** Track data collection runs

```javascript
{
  _id: ObjectId("..."),
  source_type: "github",
  start_time: ISODate("2025-11-06T00:00:00Z"),
  end_time: ISODate("2025-11-06T00:05:30Z"),
  status: "completed",         // pending, running, completed, failed
  records_collected: 523,
  errors: 0,
  metadata: {
    repositories_scanned: 12,
    api_calls_made: 145,
    rate_limit_remaining: 4855
  }
}
```

---

## 🔌 **Plugin Collections**

### **GitHub Collections**

#### **`github_commits`**

```javascript
{
  _id: ObjectId("..."),
  sha: "ff65a28abc123...",
  repository: "Tokamak-zk-EVM",
  author_name: "Jake Jang",
  author_email: "jake@tokamak.network",
  message: "Update L2 documentation",
  date: ISODate("2025-11-06T10:30:00Z"),
  
  // Code changes
  additions: 150,
  deletions: 20,
  total_changes: 170,
  
  // File changes (embedded array)
  files: [
    {
      filename: "docs/L2.md",
      additions: 150,
      deletions: 20,
      changes: 170,
      status: "modified"
    }
  ],
  
  // Metadata
  url: "https://github.com/tokamak-network/Tokamak-zk-EVM/commit/ff65a28",
  verified: true,
  
  collected_at: ISODate("2025-11-06T10:35:00Z")
}
```

**Indexes:**
```javascript
db.github_commits.createIndex({ "sha": 1 }, { unique: true })
db.github_commits.createIndex({ "repository": 1, "date": -1 })
db.github_commits.createIndex({ "author_name": 1 })
db.github_commits.createIndex({ "author_email": 1 })
db.github_commits.createIndex({ "date": -1 })
```

---

#### **`github_pull_requests`**

```javascript
{
  _id: ObjectId("..."),
  repository: "Tokamak-zk-EVM",
  number: 131,
  title: "WASM verifier implementation",
  state: "open",              // open, closed, merged
  author: "jake-jang",
  
  // PR details
  created_at: ISODate("2025-11-01T00:00:00Z"),
  updated_at: ISODate("2025-11-06T10:00:00Z"),
  merged_at: null,
  closed_at: null,
  
  // Code changes
  additions: 450,
  deletions: 120,
  changed_files: 8,
  commits: 12,
  
  // Review information (embedded)
  reviews: [
    {
      reviewer: "george-smith",
      state: "APPROVED",
      submitted_at: ISODate("2025-11-05T15:00:00Z"),
      body: "LGTM! Great work on the WASM implementation."
    }
  ],
  
  // Labels
  labels: ["enhancement", "wasm", "priority-high"],
  
  // Assignees
  assignees: ["jake-jang", "mehdi-beriane"],
  
  // URLs
  url: "https://github.com/tokamak-network/Tokamak-zk-EVM/pull/131",
  
  collected_at: ISODate("2025-11-06T10:35:00Z")
}
```

**Indexes:**
```javascript
db.github_pull_requests.createIndex({ "repository": 1, "number": 1 }, { unique: true })
db.github_pull_requests.createIndex({ "author": 1 })
db.github_pull_requests.createIndex({ "state": 1 })
db.github_pull_requests.createIndex({ "created_at": -1 })
db.github_pull_requests.createIndex({ "reviews.reviewer": 1 })
```

---

### **Slack Collections**

#### **`slack_messages`**

```javascript
{
  _id: ObjectId("..."),
  channel_id: "C07JN9XR570",
  channel_name: "project-ooo",      // Denormalized
  ts: "1699272248.188409",
  
  // User information
  user_id: "U06NU86J75M",
  user_name: "Jake Jang",           // Denormalized
  
  // Message content
  text: "Updated the WASM verifier documentation",
  type: "message",
  
  // Thread information
  thread_ts: null,                  // null if not a thread reply
  reply_count: 0,
  
  // Reactions (embedded)
  reactions: [
    {
      reaction: "raised_hands",
      count: 3,
      users: ["U04DNT2QS31", "U075F3T4MRB", "U092RN6PR0W"]
    }
  ],
  
  // Links shared in message
  links: [
    {
      url: "https://github.com/tokamak-network/Tokamak-zk-EVM/pull/131",
      type: "github_pr"
    }
  ],
  
  // Files attached
  files: [
    {
      id: "F123456",
      name: "architecture.pdf",
      url_private: "https://files.slack.com/...",
      size: 1024000
    }
  ],
  
  posted_at: ISODate("2025-11-06T13:24:08.188409Z"),
  collected_at: ISODate("2025-11-06T14:00:00Z")
}
```

**Indexes:**
```javascript
db.slack_messages.createIndex({ "channel_id": 1, "ts": 1 }, { unique: true })
db.slack_messages.createIndex({ "user_id": 1 })
db.slack_messages.createIndex({ "posted_at": -1 })
db.slack_messages.createIndex({ "channel_name": 1, "posted_at": -1 })
db.slack_messages.createIndex({ "thread_ts": 1 })
```

---

### **Notion Collections**

#### **`notion_pages`**

```javascript
{
  _id: ObjectId("..."),
  id: "notion-page-id-123",         // Notion's ID
  title: "Project OOO Weekly Sync Notes",
  
  // Page metadata
  created_time: ISODate("2025-10-01T00:00:00Z"),
  last_edited_time: ISODate("2025-11-06T10:00:00Z"),
  
  // Created/edited by
  created_by: {
    id: "notion-user-id-456",
    name: "Jake Jang",
    email: "jake@tokamak.network"
  },
  last_edited_by: {
    id: "notion-user-id-789",
    name: "Mehdi Beriane",
    email: "mehdi@tokamak.network"
  },
  
  // Parent information
  parent: {
    type: "database_id",
    database_id: "database-123"
  },
  
  // Properties (flexible schema)
  properties: {
    "Status": {
      select: { name: "In Progress" }
    },
    "Priority": {
      select: { name: "High" }
    },
    "Date": {
      date: { start: "2025-11-06" }
    }
  },
  
  // Content (embedded blocks)
  blocks: [
    {
      type: "heading_1",
      content: "Weekly Sync - 2025W44"
    },
    {
      type: "paragraph",
      content: "Discussed WASM verifier implementation..."
    }
  ],
  
  // Comments count
  comments_count: 5,
  
  // URL
  url: "https://www.notion.so/Project-OOO-Weekly-Sync-...",
  
  collected_at: ISODate("2025-11-06T14:00:00Z")
}
```

---

### **Google Drive Collections**

#### **`drive_activities`**

```javascript
{
  _id: ObjectId("..."),
  activity_id: "drive_activity_123",
  type: "edit",                    // create, edit, move, delete, share
  
  // Actor information
  actor_email: "jake@tokamak.network",
  actor_name: "Jake Jang",         // Denormalized
  
  // Target information
  target: {
    type: "document",              // document, spreadsheet, presentation, folder
    id: "1abc123xyz",
    name: "Project OOO Architecture.gdoc",
    url: "https://docs.google.com/document/d/..."
  },
  
  // Activity details
  details: {
    action: "edit",
    description: "Edited document",
    changed_fields: ["content"],
    moved_from: null,
    moved_to: null
  },
  
  time: ISODate("2025-11-06T10:30:00Z"),
  collected_at: ISODate("2025-11-06T14:00:00Z")
}
```

---

## 🔄 **Data Denormalization Strategy**

### **When to Embed vs Reference**

#### **✅ Embed (1:1 or 1:Few relationships)**
- `members.identifiers` - Each member has few identifiers
- `slack_messages.reactions` - Each message has limited reactions
- `github_pull_requests.reviews` - PRs have limited reviews

#### **🔗 Reference (1:Many or Many:Many)**
- `member_activities.member_id` → `members._id`
- Heavy relationships that would bloat documents

---

### **Selective Denormalization for Performance**

**Denormalized fields for quick display:**
```javascript
// In member_activities
{
  member_id: ObjectId("..."),    // Reference for joins
  member_name: "Jake Jang",       // Denormalized for display
  ...
}

// In slack_messages
{
  channel_id: "C07JN9XR570",     // Reference
  channel_name: "project-ooo",    // Denormalized for display
  user_id: "U06NU86J75M",        // Reference
  user_name: "Jake Jang",         // Denormalized for display
  ...
}
```

**Trade-off:** Faster reads, slower writes (need to update multiple places)

---

## 📊 **Index Strategy**

### **Primary Indexes (Unique)**
- `members.name`
- `member_activities.activity_id`
- `github_commits.sha`
- `github_pull_requests.[repository, number]`
- `slack_messages.[channel_id, ts]`

### **Query Optimization Indexes**
- `member_activities.[member_id, timestamp]` - Member activity timeline
- `member_activities.[source_type, activity_type]` - Filter by source/type
- `github_commits.[repository, date]` - Repository commits timeline
- `slack_messages.[channel_name, posted_at]` - Channel messages timeline

### **Text Search Indexes**
```javascript
db.slack_messages.createIndex({ "text": "text" })
db.notion_pages.createIndex({ "title": "text", "blocks.content": "text" })
```

---

## 🔄 **Migration Notes**

### **Relational → Document Transformation**

#### **1. One-to-Many → Embedding**

**SQL:**
```sql
-- members table
members (id, name, email)

-- member_identifiers table
member_identifiers (id, member_id, source_type, source_user_id)
```

**MongoDB:**
```javascript
// Embedded in members collection
{
  _id: ObjectId("..."),
  name: "Jake Jang",
  email: "jake@tokamak.network",
  identifiers: [
    { source_type: "github", source_user_id: "jake-jang" },
    { source_type: "slack", source_user_id: "U06NU86J75M" }
  ]
}
```

---

#### **2. Foreign Keys → References**

**SQL:**
```sql
member_activities (
  id,
  member_id REFERENCES members(id),
  activity_type,
  timestamp
)
```

**MongoDB:**
```javascript
{
  _id: ObjectId("..."),
  member_id: ObjectId("..."),  // Reference to members._id
  activity_type: "commit",
  timestamp: ISODate("...")
}

// Use $lookup for joins
db.member_activities.aggregate([
  {
    $lookup: {
      from: "members",
      localField: "member_id",
      foreignField: "_id",
      as: "member"
    }
  }
])
```

---

#### **3. JSON Metadata → Flexible Schema**

**SQL:**
```sql
member_activities (
  ...
  metadata TEXT  -- JSON string
)
```

**MongoDB:**
```javascript
{
  ...
  metadata: {
    repository: "Tokamak-zk-EVM",
    sha: "ff65a28",
    additions: 150,
    deletions: 20
    // Flexible structure, no schema enforcement
  }
}
```

---

## 🎯 **Query Examples**

### **1. Get member with all identifiers**

**SQL:**
```sql
SELECT m.*, mi.source_type, mi.source_user_id
FROM members m
LEFT JOIN member_identifiers mi ON m.id = mi.member_id
WHERE m.name = 'Jake Jang';
```

**MongoDB:**
```javascript
db.members.findOne({ name: "Jake Jang" })

// Returns all identifiers embedded in the document
```

---

### **2. Get member activities with member info**

**SQL:**
```sql
SELECT m.name, ma.*
FROM member_activities ma
JOIN members m ON ma.member_id = m.id
WHERE ma.source_type = 'github'
ORDER BY ma.timestamp DESC
LIMIT 10;
```

**MongoDB:**
```javascript
// Option 1: Using denormalized field (faster)
db.member_activities.find({
  source_type: "github"
}).sort({ timestamp: -1 }).limit(10)

// Option 2: Using $lookup (when need full member info)
db.member_activities.aggregate([
  { $match: { source_type: "github" } },
  { $sort: { timestamp: -1 } },
  { $limit: 10 },
  {
    $lookup: {
      from: "members",
      localField: "member_id",
      foreignField: "_id",
      as: "member"
    }
  },
  { $unwind: "$member" }
])
```

---

### **3. Complex aggregation**

**SQL:**
```sql
SELECT 
  m.name,
  COUNT(CASE WHEN ma.activity_type = 'commit' THEN 1 END) as commits,
  COUNT(CASE WHEN ma.activity_type = 'pull_request' THEN 1 END) as prs
FROM members m
JOIN member_activities ma ON m.id = ma.member_id
WHERE ma.timestamp >= '2025-11-01'
GROUP BY m.id, m.name
ORDER BY commits DESC;
```

**MongoDB:**
```javascript
db.member_activities.aggregate([
  { $match: { timestamp: { $gte: ISODate("2025-11-01") } } },
  {
    $group: {
      _id: "$member_name",  // Using denormalized field
      commits: {
        $sum: { $cond: [{ $eq: ["$activity_type", "commit"] }, 1, 0] }
      },
      prs: {
        $sum: { $cond: [{ $eq: ["$activity_type", "pull_request"] }, 1, 0] }
      }
    }
  },
  { $sort: { commits: -1 } }
])
```

---

## 🎉 **Summary**

### **Key Design Decisions:**

1. **Embedded Documents** for 1:N relationships with few children
2. **References** for 1:N with many children or M:N relationships
3. **Selective Denormalization** for frequently accessed fields
4. **Flexible Metadata** using nested documents instead of JSON strings
5. **Comprehensive Indexes** for common query patterns

### **Benefits:**
- ✅ Faster read performance (no joins needed for common queries)
- ✅ Flexible schema for metadata
- ✅ Natural JSON representation
- ✅ Easier to scale horizontally

### **Trade-offs:**
- ⚠️ More complex write operations (denormalization updates)
- ⚠️ Larger document sizes (embedded data)
- ⚠️ Learning curve for aggregation pipeline

