# Custom Data Export Builder - Feature Specification

**Status**: 📋 Planned (Not Yet Implemented)  
**Priority**: P2 (Future Enhancement)  
**Estimated Effort**: 4-5 days  
**Target Users**: Non-technical users (PMs, designers, analysts)

---

## 📌 Overview

### Problem Statement

Currently, users can only export single tables as CSV files. To analyze data across multiple sources (GitHub + Slack + Google Drive + Notion), they need to:

1. Download multiple CSV files
2. Manually join data in Excel/Google Sheets
3. Know SQL or rely on developers

This creates friction for non-technical users who want custom analytics.

### Proposed Solution

A **visual data builder** that allows users to:

- ✅ Select fields from multiple data sources via checkboxes
- ✅ Apply filters (date range, project, members)
- ✅ Preview results before downloading
- ✅ Export as CSV or Excel
- ✅ Save configurations as reusable templates

**Key Principle**: No SQL knowledge required. Think Google Analytics custom reports or Tableau.

---

## 🎯 User Stories

### Story 1: Project Manager

> "As a PM, I want to see each member's GitHub commits + Slack messages + Drive documents in one CSV, so I can analyze productivity without asking developers."

### Story 2: Team Lead

> "As a team lead, I want to quickly generate a report showing who worked on which project, with contribution counts from all platforms, filtered by last month."

### Story 3: Designer (Non-Developer)

> "As a designer, I want to export all Figma/Drive links I shared in Slack, along with reactions and comments, to show my collaboration impact."

### Story 4: Analyst

> "As an analyst, I want to save my custom field selection as a template so I can run the same report weekly without reconfiguring."

---

## 🎨 User Interface Design

### Main Screen Layout

```
┌────────────────────────────────────────────────────────────────┐
│  📊 Custom Data Export Builder                                 │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌────────────────┐  ┌────────────────────────────────────┐   │
│  │                │  │  Filters                           │   │
│  │  Data Sources  │  │  ┌──────────────────────────────┐ │   │
│  │  & Fields      │  │  │ 📅 Date Range                │ │   │
│  │                │  │  │   [2025-10-31] ~ [2025-11-06]│ │   │
│  │  ☑ Member Info │  │  └──────────────────────────────┘ │   │
│  │    ☑ Name      │  │  ┌──────────────────────────────┐ │   │
│  │    ☑ Email     │  │  │ 🎯 Project                   │ │   │
│  │    ☐ Role      │  │  │   [All Projects ▼]           │ │   │
│  │                │  │  └──────────────────────────────┘ │   │
│  │  ☑ GitHub      │  │  ┌──────────────────────────────┐ │   │
│  │    ☑ Commits   │  │  │ 👤 Members                   │ │   │
│  │    ☑ Lines+/-  │  │  │   [All Members ▼]            │ │   │
│  │    ☐ PRs       │  │  └──────────────────────────────┘ │   │
│  │    ☐ Reviews   │  │                                    │   │
│  │                │  │  [🔍 Preview] [💾 Export]         │   │
│  │  ☑ Slack       │  │  [💾 Save as Template]            │   │
│  │    ☑ Messages  │  └────────────────────────────────────┘   │
│  │    ☑ Links     │                                           │
│  │    ☐ Reactions │  ┌────────────────────────────────────┐   │
│  │    ☐ Threads   │  │  Preview (First 10 Rows)           │   │
│  │                │  │  ┌──────┬────────┬────────┬──────┐ │   │
│  │  ☐ Google Drive│  │  │ Name │ Email  │Commits │Msgs  │ │   │
│  │  ☐ Notion      │  │  ├──────┼────────┼────────┼──────┤ │   │
│  │                │  │  │ Jake │jake@.. │  25    │ 30   │ │   │
│  │                │  │  │Monica│monica..│   0    │ 18   │ │   │
│  │                │  │  └──────┴────────┴────────┴──────┘ │   │
│  │ Selected: 4/32 │  │  Total: 15 rows                    │   │
│  └────────────────┘  └────────────────────────────────────┘   │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Workflow Steps

```
Step 1: Select Data Sources
  └─→ Expand/collapse source groups
      └─→ Check/uncheck fields

Step 2: Apply Filters
  └─→ Date range picker (with presets: Last Week, Last Month, etc.)
  └─→ Project dropdown (from config.yaml)
  └─→ Member multi-select

Step 3: Preview Data
  └─→ Click "Preview" button
  └─→ Show first 10 rows in table
  └─→ Display total row count

Step 4: Export
  └─→ Download CSV (quick)
  └─→ Download Excel (with formatting)
  └─→ Save as Template (for reuse)

Step 5: Load Saved Template (Optional)
  └─→ Dropdown of saved templates
  └─→ One-click to load field selection
  └─→ Adjust filters if needed
  └─→ Export
```

---

## 🏗 Technical Architecture

### Backend API Design

#### Endpoint 1: Get Export Schema

```
GET /api/v1/custom-export/schema

Response:
{
  "sources": {
    "members": {
      "display_name": "Member Info",
      "description": "Basic member information",
      "fields": [
        {
          "key": "name",
          "label": "Name",
          "type": "text",
          "description": "Member's full name"
        },
        {
          "key": "email",
          "label": "Email",
          "type": "text",
          "description": "Primary email address"
        },
        {
          "key": "role",
          "label": "Role",
          "type": "text",
          "description": "Job role (e.g., Developer, Designer)"
        }
      ]
    },
    "github": {
      "display_name": "GitHub Activity",
      "description": "Code contributions and collaboration",
      "fields": [
        {
          "key": "commit_count",
          "label": "Commits",
          "type": "number",
          "description": "Total commits in date range",
          "aggregation": "count"
        },
        {
          "key": "lines_added",
          "label": "Lines Added",
          "type": "number",
          "description": "Total lines of code added",
          "aggregation": "sum"
        },
        {
          "key": "lines_deleted",
          "label": "Lines Deleted",
          "type": "number",
          "description": "Total lines of code removed",
          "aggregation": "sum"
        },
        {
          "key": "pr_count",
          "label": "Pull Requests",
          "type": "number",
          "description": "PRs created or merged",
          "aggregation": "count"
        },
        {
          "key": "review_count",
          "label": "Code Reviews",
          "type": "number",
          "description": "PRs reviewed",
          "aggregation": "count"
        },
        {
          "key": "repositories",
          "label": "Repositories",
          "type": "text",
          "description": "Comma-separated list of repos",
          "aggregation": "group_concat"
        }
      ]
    },
    "slack": {
      "display_name": "Slack Activity",
      "description": "Communication and collaboration",
      "fields": [
        {
          "key": "message_count",
          "label": "Messages",
          "type": "number",
          "description": "Total messages sent",
          "aggregation": "count"
        },
        {
          "key": "links_shared",
          "label": "Links Shared",
          "type": "number",
          "description": "URLs shared in messages",
          "aggregation": "count"
        },
        {
          "key": "reactions_given",
          "label": "Reactions Given",
          "type": "number",
          "description": "Emoji reactions added",
          "aggregation": "count"
        },
        {
          "key": "reactions_received",
          "label": "Reactions Received",
          "type": "number",
          "description": "Reactions on own messages",
          "aggregation": "count"
        },
        {
          "key": "thread_participation",
          "label": "Thread Replies",
          "type": "number",
          "description": "Messages in threads",
          "aggregation": "count"
        },
        {
          "key": "channels",
          "label": "Active Channels",
          "type": "text",
          "description": "Comma-separated channel names",
          "aggregation": "group_concat"
        }
      ]
    },
    "google_drive": {
      "display_name": "Google Drive Activity",
      "description": "Document creation and collaboration",
      "fields": [
        {
          "key": "docs_created",
          "label": "Documents Created",
          "type": "number",
          "description": "New documents created",
          "aggregation": "count"
        },
        {
          "key": "docs_edited",
          "label": "Documents Edited",
          "type": "number",
          "description": "Documents modified",
          "aggregation": "count"
        },
        {
          "key": "files_shared",
          "label": "Files Shared",
          "type": "number",
          "description": "Documents shared with others",
          "aggregation": "count"
        },
        {
          "key": "comments_added",
          "label": "Comments Added",
          "type": "number",
          "description": "Comments on documents",
          "aggregation": "count"
        }
      ]
    },
    "notion": {
      "display_name": "Notion Activity",
      "description": "Knowledge base and documentation",
      "fields": [
        {
          "key": "pages_created",
          "label": "Pages Created",
          "type": "number",
          "description": "New Notion pages",
          "aggregation": "count"
        },
        {
          "key": "pages_edited",
          "label": "Pages Edited",
          "type": "number",
          "description": "Pages modified",
          "aggregation": "count"
        },
        {
          "key": "comments_added",
          "label": "Comments Added",
          "type": "number",
          "description": "Discussion comments",
          "aggregation": "count"
        },
        {
          "key": "databases_created",
          "label": "Databases Created",
          "type": "number",
          "description": "New Notion databases",
          "aggregation": "count"
        }
      ]
    }
  }
}
```

#### Endpoint 2: Build Custom Export (Preview)

```
POST /api/v1/custom-export/build

Request Body:
{
  "selected_fields": [
    "members.name",
    "members.email",
    "github.commit_count",
    "github.lines_added",
    "slack.message_count",
    "slack.links_shared"
  ],
  "filters": {
    "date_start": "2025-10-31",
    "date_end": "2025-11-06",
    "project": "project-ooo",       // Optional, "all" for all projects
    "members": ["Jake", "Monica"],  // Optional, empty for all members
    "min_activity": 1               // Optional, exclude members with 0 activity
  },
  "limit": 10  // For preview
}

Response:
{
  "data": [
    {
      "members.name": "Jake",
      "members.email": "jake@tokamak.network",
      "github.commit_count": 25,
      "github.lines_added": 1240,
      "slack.message_count": 30,
      "slack.links_shared": 8
    },
    {
      "members.name": "Monica",
      "members.email": "monica@tokamak.network",
      "github.commit_count": 0,
      "github.lines_added": 0,
      "slack.message_count": 18,
      "slack.links_shared": 12
    }
  ],
  "total_rows": 15,
  "showing": 10,
  "query_time_ms": 45
}
```

#### Endpoint 3: Export Data

```
POST /api/v1/custom-export/export

Request Body: (Same as /build but without limit)
{
  "selected_fields": [...],
  "filters": {...},
  "format": "csv"  // or "excel"
}

Response:
  Content-Type: text/csv or application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
  Content-Disposition: attachment; filename="custom_export_20251112.csv"

  [File download stream]
```

#### Endpoint 4: Save Template

```
POST /api/v1/custom-export/templates

Request Body:
{
  "name": "Monthly Team Summary",
  "description": "GitHub + Slack activity for all members",
  "config": {
    "selected_fields": [...],
    "default_filters": {
      "date_range": "last_month",
      "project": "all"
    }
  }
}

Response:
{
  "template_id": "template_abc123",
  "name": "Monthly Team Summary",
  "created_at": "2025-11-12T10:30:00Z"
}
```

#### Endpoint 5: List Templates

```
GET /api/v1/custom-export/templates

Response:
{
  "templates": [
    {
      "id": "template_abc123",
      "name": "Monthly Team Summary",
      "description": "GitHub + Slack activity for all members",
      "created_at": "2025-11-12T10:30:00Z",
      "last_used_at": "2025-11-12T11:00:00Z"
    },
    {
      "id": "template_def456",
      "name": "Designer Contributions",
      "description": "Drive + Slack links for non-developers",
      "created_at": "2025-11-10T14:00:00Z",
      "last_used_at": null
    }
  ]
}
```

---

## 🔐 Security & Performance

### SQL Injection Prevention

**Problem**: User-selected fields could be exploited for SQL injection.

**Solution**: Whitelist-based field mapping

```python
# backend/services/custom_export_builder.py

# Predefined mapping: user-facing key → safe SQL expression
FIELD_MAPPING = {
    'members.name': 'm.name',
    'members.email': 'm.email',
    'members.role': 'm.role',

    'github.commit_count': '''
        (SELECT COUNT(*) FROM member_activities ma
         WHERE ma.member_id = m.id
           AND ma.source_type = 'github'
           AND ma.activity_type = 'github_commit'
           AND ma.timestamp BETWEEN :date_start AND :date_end)
    ''',

    'github.lines_added': '''
        (SELECT COALESCE(SUM(CAST(JSON_EXTRACT(ma.metadata, '$.additions') AS INTEGER)), 0)
         FROM member_activities ma
         WHERE ma.member_id = m.id
           AND ma.source_type = 'github'
           AND ma.activity_type = 'github_commit'
           AND ma.timestamp BETWEEN :date_start AND :date_end)
    ''',

    'slack.message_count': '''
        (SELECT COUNT(*) FROM member_activities ma
         WHERE ma.member_id = m.id
           AND ma.source_type = 'slack'
           AND ma.activity_type = 'message'
           AND ma.timestamp BETWEEN :date_start AND :date_end)
    ''',

    # ... more fields
}

def build_query(selected_fields: List[str], filters: dict) -> str:
    # Step 1: Validate all fields are in whitelist
    for field in selected_fields:
        if field not in FIELD_MAPPING:
            raise ValueError(f"Invalid field: {field}")

    # Step 2: Build SELECT clause from whitelist
    select_parts = []
    for field in selected_fields:
        sql_expr = FIELD_MAPPING[field]
        # Add AS clause for column naming
        select_parts.append(f"{sql_expr} AS \"{field}\"")

    select_clause = ",\n".join(select_parts)

    # Step 3: Build WHERE clause (with parameter binding)
    where_conditions = ["1=1"]  # Always true base condition
    params = {}

    if filters.get('date_start'):
        params['date_start'] = filters['date_start']
    if filters.get('date_end'):
        params['date_end'] = filters['date_end']

    if filters.get('project') and filters['project'] != 'all':
        # Project filtering requires JOIN to project mapping
        where_conditions.append("m.project = :project")
        params['project'] = filters['project']

    if filters.get('members'):
        # Use parameter binding for member names
        placeholders = ", ".join([f":member_{i}" for i in range(len(filters['members']))])
        where_conditions.append(f"m.name IN ({placeholders})")
        for i, member in enumerate(filters['members']):
            params[f'member_{i}'] = member

    where_clause = " AND ".join(where_conditions)

    # Step 4: Construct final query
    query = text(f"""
        SELECT {select_clause}
        FROM members m
        WHERE {where_clause}
        ORDER BY m.name
    """)

    return query, params
```

### Performance Optimization

**Problem**: Complex subqueries for each field can be slow.

**Solutions**:

1. **Materialized CTEs**: Pre-aggregate activity counts
2. **Indexing**: Ensure indexes on `member_activities(member_id, source_type, timestamp)`
3. **Caching**: Cache schema definitions and common queries
4. **Pagination**: Limit preview to 10 rows
5. **Background Jobs**: For large exports (>1000 rows), queue async job

```python
# Optimized query using CTEs
def build_optimized_query(selected_fields, filters):
    query = text("""
        -- Pre-aggregate GitHub activities
        WITH github_stats AS (
            SELECT
                member_id,
                COUNT(CASE WHEN activity_type = 'github_commit' THEN 1 END) as commit_count,
                SUM(CAST(JSON_EXTRACT(metadata, '$.additions') AS INTEGER)) as lines_added,
                SUM(CAST(JSON_EXTRACT(metadata, '$.deletions') AS INTEGER)) as lines_deleted
            FROM member_activities
            WHERE source_type = 'github'
              AND timestamp BETWEEN :date_start AND :date_end
            GROUP BY member_id
        ),
        -- Pre-aggregate Slack activities
        slack_stats AS (
            SELECT
                member_id,
                COUNT(CASE WHEN activity_type = 'message' THEN 1 END) as message_count,
                COUNT(CASE WHEN JSON_EXTRACT(metadata, '$.has_links') = 1 THEN 1 END) as links_shared
            FROM member_activities
            WHERE source_type = 'slack'
              AND timestamp BETWEEN :date_start AND :date_end
            GROUP BY member_id
        )
        -- Main query joining pre-aggregated data
        SELECT
            m.name,
            m.email,
            COALESCE(g.commit_count, 0) as "github.commit_count",
            COALESCE(g.lines_added, 0) as "github.lines_added",
            COALESCE(s.message_count, 0) as "slack.message_count",
            COALESCE(s.links_shared, 0) as "slack.links_shared"
        FROM members m
        LEFT JOIN github_stats g ON m.id = g.member_id
        LEFT JOIN slack_stats s ON m.id = s.member_id
        WHERE 1=1  -- Additional filters added dynamically
        ORDER BY m.name
    """)

    return query
```

---

## 📱 Frontend Implementation

### Key Components

#### 1. FieldSelector Component

```typescript
// frontend/src/components/custom-export/FieldSelector.tsx

interface Field {
  key: string;
  label: string;
  type: 'text' | 'number';
  description: string;
}

interface Source {
  display_name: string;
  description: string;
  fields: Field[];
}

interface FieldSelectorProps {
  schema: Record<string, Source>;
  selectedFields: string[];
  onFieldToggle: (fieldKey: string) => void;
}

export function FieldSelector({ schema, selectedFields, onFieldToggle }: FieldSelectorProps) {
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set());

  const toggleSource = (sourceKey: string) => {
    setExpandedSources(prev => {
      const next = new Set(prev);
      if (next.has(sourceKey)) {
        next.delete(sourceKey);
      } else {
        next.add(sourceKey);
      }
      return next;
    });
  };

  const selectAllInSource = (sourceKey: string) => {
    const source = schema[sourceKey];
    source.fields.forEach(field => {
      const fullKey = `${sourceKey}.${field.key}`;
      if (!selectedFields.includes(fullKey)) {
        onFieldToggle(fullKey);
      }
    });
  };

  return (
    <div className="field-selector">
      <div className="selector-header">
        <h3>Data Sources & Fields</h3>
        <span className="selected-count">
          {selectedFields.length} selected
        </span>
      </div>

      {Object.entries(schema).map(([sourceKey, source]) => (
        <div key={sourceKey} className="source-group">
          <div className="source-header" onClick={() => toggleSource(sourceKey)}>
            <span className="expand-icon">
              {expandedSources.has(sourceKey) ? '▼' : '▶'}
            </span>
            <label>
              <input
                type="checkbox"
                checked={source.fields.every(f =>
                  selectedFields.includes(`${sourceKey}.${f.key}`)
                )}
                onChange={() => selectAllInSource(sourceKey)}
                onClick={(e) => e.stopPropagation()}
              />
              {source.display_name}
            </label>
          </div>

          {expandedSources.has(sourceKey) && (
            <div className="field-list">
              {source.fields.map(field => {
                const fullKey = `${sourceKey}.${field.key}`;
                return (
                  <label key={fullKey} className="field-item">
                    <input
                      type="checkbox"
                      checked={selectedFields.includes(fullKey)}
                      onChange={() => onFieldToggle(fullKey)}
                    />
                    <span className="field-label">{field.label}</span>
                    <span className="field-type">{field.type}</span>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
```

#### 2. FilterPanel Component

```typescript
// frontend/src/components/custom-export/FilterPanel.tsx

interface FilterPanelProps {
  filters: ExportFilters;
  onChange: (filters: ExportFilters) => void;
  projects: string[];
  members: string[];
}

export function FilterPanel({ filters, onChange, projects, members }: FilterPanelProps) {
  return (
    <div className="filter-panel">
      <h3>Filters</h3>

      <div className="filter-group">
        <label>📅 Date Range</label>
        <div className="date-range-picker">
          <input
            type="date"
            value={filters.date_start}
            onChange={(e) => onChange({ ...filters, date_start: e.target.value })}
          />
          <span>to</span>
          <input
            type="date"
            value={filters.date_end}
            onChange={(e) => onChange({ ...filters, date_end: e.target.value })}
          />
        </div>
        <div className="date-presets">
          <button onClick={() => setLastWeek()}>Last Week</button>
          <button onClick={() => setLastMonth()}>Last Month</button>
          <button onClick={() => setLast3Months()}>Last 3 Months</button>
        </div>
      </div>

      <div className="filter-group">
        <label>🎯 Project</label>
        <select
          value={filters.project}
          onChange={(e) => onChange({ ...filters, project: e.target.value })}
        >
          <option value="all">All Projects</option>
          {projects.map(p => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label>👤 Members</label>
        <MultiSelect
          options={members}
          selected={filters.members}
          onChange={(selected) => onChange({ ...filters, members: selected })}
          placeholder="All Members"
        />
      </div>

      <div className="filter-group">
        <label>
          <input
            type="checkbox"
            checked={filters.exclude_inactive}
            onChange={(e) => onChange({ ...filters, exclude_inactive: e.target.checked })}
          />
          Exclude members with 0 activity
        </label>
      </div>
    </div>
  );
}
```

#### 3. PreviewTable Component

```typescript
// frontend/src/components/custom-export/PreviewTable.tsx

interface PreviewTableProps {
  data: any[];
  fields: string[];
  totalRows: number;
  loading: boolean;
}

export function PreviewTable({ data, fields, totalRows, loading }: PreviewTableProps) {
  if (loading) {
    return <div className="loading">Loading preview...</div>;
  }

  if (!data || data.length === 0) {
    return <div className="empty-state">No data to display. Adjust filters or select more fields.</div>;
  }

  return (
    <div className="preview-table">
      <div className="table-info">
        <span>Showing {data.length} of {totalRows} rows</span>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              {fields.map(field => (
                <th key={field}>{field.split('.').pop()}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i}>
                {fields.map(field => (
                  <td key={field}>{row[field]}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

---

## 🧪 Testing Strategy

### Unit Tests

- [ ] Field validation (whitelist check)
- [ ] SQL query builder (safe construction)
- [ ] Filter parameter binding
- [ ] Aggregation functions

### Integration Tests

- [ ] End-to-end export flow (select → preview → download)
- [ ] Template save/load
- [ ] CSV vs Excel output

### User Acceptance Tests

- [ ] Non-technical user can export custom data without help
- [ ] Preview matches downloaded file
- [ ] Templates work correctly
- [ ] Error messages are clear

---

## 📅 Implementation Roadmap

### Phase 1: Backend Foundation (2 days)

- [ ] Create `/custom-export/schema` endpoint
- [ ] Implement field mapping whitelist
- [ ] Build dynamic SQL query generator
- [ ] Add parameter binding for filters
- [ ] Create `/custom-export/build` (preview) endpoint

### Phase 2: Export Functionality (1 day)

- [ ] Create `/custom-export/export` endpoint
- [ ] CSV output generator
- [ ] Excel output generator (with openpyxl)
- [ ] Stream large files for download

### Phase 3: Frontend UI (2-3 days)

- [ ] FieldSelector component
- [ ] FilterPanel component
- [ ] PreviewTable component
- [ ] Download buttons
- [ ] Loading states and error handling

### Phase 4: Template System (1 day)

- [ ] Backend: Save/load/delete templates
- [ ] Frontend: Template dropdown
- [ ] Frontend: "Save as Template" dialog

### Phase 5: Polish & Optimization (1 day)

- [ ] Performance optimization (CTEs, indexes)
- [ ] UI/UX improvements
- [ ] Documentation
- [ ] User testing

**Total Estimated Time**: 4-5 working days

---

## 💡 Future Enhancements

### Phase 2 Features (Post-MVP)

- [ ] **Advanced Aggregations**: Group by project/member, calculate averages
- [ ] **Sorting Options**: Order by specific fields (ASC/DESC)
- [ ] **Visualization**: Generate charts from selected data
- [ ] **Scheduled Exports**: Auto-generate weekly reports
- [ ] **Email Delivery**: Send exports to email
- [ ] **API Access**: Allow external tools to trigger exports
- [ ] **Excel Advanced**: Conditional formatting, charts, pivot tables

### Phase 3 Features (Long-term)

- [ ] **Query Builder Mode**: Visual SQL builder for power users
- [ ] **Data Transformations**: Calculated fields (e.g., commits per day)
- [ ] **Collaboration**: Share templates with team
- [ ] **Version History**: Track template changes
- [ ] **Permissions**: Restrict certain fields based on user role

---

## 📚 Related Documents

- [DATA_GUIDE_FOR_AI.md](./DATA_GUIDE_FOR_AI.md) - Data structure reference
- [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) - Database schema documentation
- [API_DEVELOPMENT.md](./API_DEVELOPMENT.md) - API development guide
- [REPORT_GUIDELINES.md](./REPORT_GUIDELINES.md) - Report generation standards

---

## 📞 Questions & Feedback

If you have questions or suggestions for this feature:

1. Review this specification document
2. Check related documentation
3. Discuss with product team
4. Update this document with decisions

---

**Document Version**: 1.0.0  
**Last Updated**: 2025-11-12  
**Status**: 📋 Planned - Ready for implementation when prioritized
