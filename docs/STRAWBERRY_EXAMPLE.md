# Strawberry GraphQL - Real-world Example for All-Thing-Eye

This document shows how Strawberry GraphQL would work with our existing MongoDB + FastAPI setup.

---

## 🍓 What is Strawberry GraphQL?

**Strawberry** is a modern Python GraphQL library that uses **type hints** and **decorators** to define GraphQL schemas.

**Key Features**:

- 🐍 Pythonic: Uses native Python type hints
- ⚡ Async-first: Perfect for FastAPI + motor (MongoDB async)
- 🔗 Zero migration: Works with existing Pydantic models
- 🎨 Type-safe: Auto-completion in IDEs

**Official Site**: https://strawberry.rocks/

---

## 📝 Example 1: Basic Query

### Current REST API (activities_mongo.py)

```python
# backend/api/v1/activities_mongo.py
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class ActivityResponse(BaseModel):
    id: str
    member_name: str
    source_type: str
    activity_type: str
    timestamp: datetime

@router.get("/activities")
async def get_activities(
    source: Optional[str] = None,
    member_name: Optional[str] = None,
    limit: int = 100
) -> List[ActivityResponse]:
    db = get_mongo_manager().async_db

    query = {}
    if source:
        query['source_type'] = source
    if member_name:
        query['member_name'] = member_name

    activities = []
    async for doc in db['github_commits'].find(query).limit(limit):
        activities.append(ActivityResponse(
            id=str(doc['_id']),
            member_name=doc['author_name'],
            source_type='github',
            activity_type='commit',
            timestamp=doc['date']
        ))

    return activities
```

**Frontend call**:

```typescript
// Need to make separate requests for different sources
const githubData = await api.get('/api/v1/activities?source=github&limit=100');
const slackData = await api.get('/api/v1/activities?source=slack&limit=100');
```

---

### With Strawberry GraphQL

```python
# backend/graphql/types.py
import strawberry
from typing import List, Optional
from datetime import datetime

@strawberry.type
class Activity:
    id: str
    member_name: str
    source_type: str
    activity_type: str
    timestamp: datetime

    @strawberry.field
    async def metadata(self) -> strawberry.scalars.JSON:
        """Get additional metadata (computed field)"""
        # Can add computed fields without changing database
        return {"extra": "data"}

@strawberry.enum
class SourceType:
    GITHUB = "github"
    SLACK = "slack"
    NOTION = "notion"
    DRIVE = "drive"

@strawberry.type
class Query:
    @strawberry.field
    async def activities(
        self,
        info,
        source: Optional[SourceType] = None,
        member_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Activity]:
        """Get activities with flexible filtering"""
        db = info.context['db']

        # Reuse existing MongoDB query logic
        query = {}
        if source:
            query['source_type'] = source.value
        if member_name:
            query['member_name'] = member_name

        activities = []

        # Example: GitHub commits
        if not source or source == SourceType.GITHUB:
            async for doc in db['github_commits'].find(query).limit(limit):
                activities.append(Activity(
                    id=str(doc['_id']),
                    member_name=doc['author_name'],
                    source_type='github',
                    activity_type='commit',
                    timestamp=doc['date']
                ))

        # Example: Slack messages
        if not source or source == SourceType.SLACK:
            async for doc in db['slack_messages'].find(query).limit(limit):
                activities.append(Activity(
                    id=str(doc['_id']),
                    member_name=doc['user_name'],
                    source_type='slack',
                    activity_type='message',
                    timestamp=doc['posted_at']
                ))

        return sorted(activities, key=lambda a: a.timestamp, reverse=True)

# backend/graphql/schema.py
import strawberry

schema = strawberry.Schema(query=Query)

# backend/main.py
from strawberry.fastapi import GraphQLRouter
from backend.graphql.schema import schema

graphql_app = GraphQLRouter(
    schema,
    context_getter=lambda: {'db': mongo_manager.async_db}
)
app.include_router(graphql_app, prefix="/graphql")
```

**Frontend call** (single request):

```typescript
// frontend/src/app/activities/page.tsx
import { useQuery, gql } from '@apollo/client';

const GET_ACTIVITIES = gql`
  query GetActivities {
    activities(limit: 100) {
      id
      memberName
      sourceType
      activityType
      timestamp
    }
  }
`;

// Single request gets ALL data
const { data } = useQuery(GET_ACTIVITIES);
```

**Benefits**:

- ✅ Single request instead of multiple
- ✅ Client chooses which fields to fetch
- ✅ Type-safe queries (auto-generated TypeScript types)

---

## 📝 Example 2: Nested Relationships

### Problem with Current REST API

```typescript
// frontend/src/app/members/[id]/page.tsx

// Need 4 separate requests!
const member = await api.get(`/api/v1/members/${id}`);
const activities = await api.get(`/api/v1/activities?member_name=${member.name}`);
const projects = await api.get(`/api/v1/projects?member_id=${id}`);
const stats = await api.get(`/api/v1/stats/member/${id}`);
```

### Solution with Strawberry

```python
# backend/graphql/types.py
import strawberry
from typing import List

@strawberry.type
class Member:
    id: str
    name: str
    email: str
    role: Optional[str]

    @strawberry.field
    async def activities(
        self,
        info,
        limit: int = 10
    ) -> List[Activity]:
        """Get activities for this member (field resolver)"""
        db = info.context['db']

        activities = []

        # GitHub commits
        async for doc in db['github_commits'].find(
            {'author_name': self.name}
        ).limit(limit):
            activities.append(Activity.from_mongo(doc, 'github'))

        # Slack messages
        async for doc in db['slack_messages'].find(
            {'user_name': self.name}
        ).limit(limit):
            activities.append(Activity.from_mongo(doc, 'slack'))

        return sorted(activities, key=lambda a: a.timestamp, reverse=True)

    @strawberry.field
    async def projects(self, info) -> List['Project']:
        """Get projects this member belongs to"""
        db = info.context['db']

        projects = []
        async for doc in db['projects'].find({'member_ids': self.id}):
            projects.append(Project(
                id=str(doc['_id']),
                name=doc['name'],
                key=doc['key']
            ))

        return projects

    @strawberry.field
    async def activity_count(self, info) -> int:
        """Get total activity count (computed field)"""
        db = info.context['db']

        count = 0
        count += await db['github_commits'].count_documents({'author_name': self.name})
        count += await db['slack_messages'].count_documents({'user_name': self.name})

        return count

@strawberry.type
class Project:
    id: str
    name: str
    key: str

    @strawberry.field
    async def members(self, info) -> List[Member]:
        """Get all members in this project"""
        db = info.context['db']

        # Convert member_ids to ObjectId list
        from bson import ObjectId
        member_ids = [ObjectId(mid) for mid in self.member_ids]

        members = []
        async for doc in db['members'].find({'_id': {'$in': member_ids}}):
            members.append(Member(
                id=str(doc['_id']),
                name=doc['name'],
                email=doc['email'],
                role=doc.get('role')
            ))

        return members

@strawberry.type
class Query:
    @strawberry.field
    async def member(self, info, name: str) -> Optional[Member]:
        """Get member by name with nested data"""
        db = info.context['db']

        doc = await db['members'].find_one({'name': name})
        if not doc:
            return None

        return Member(
            id=str(doc['_id']),
            name=doc['name'],
            email=doc['email'],
            role=doc.get('role')
        )
```

**Frontend usage**:

```typescript
// Single GraphQL query replaces 4 REST calls!
const GET_MEMBER_DETAIL = gql`
  query GetMemberDetail($name: String!) {
    member(name: $name) {
      id
      name
      email
      role

      # Nested data fetched automatically
      activities(limit: 20) {
        sourceType
        activityType
        timestamp
      }

      projects {
        name
        key
      }

      # Computed fields
      activityCount
    }
  }
`;

const { data } = useQuery(GET_MEMBER_DETAIL, {
  variables: { name: "Monica" }
});

// data.member now has everything!
console.log(data.member.activities);  // ✅ Loaded
console.log(data.member.projects);    // ✅ Loaded
console.log(data.member.activityCount); // ✅ Computed
```

---

## 📝 Example 3: Flexible Field Selection

### Problem: Over-fetching with REST

```python
# REST API always returns ALL fields
@router.get("/activities")
async def get_activities() -> List[ActivityResponse]:
    return [
        ActivityResponse(
            id="...",
            member_name="Monica",
            source_type="github",
            activity_type="commit",
            timestamp="...",
            metadata={...},  # Large nested object
            repository="...",
            message="...",
            additions=100,
            deletions=50,
            # ... 10+ more fields
        )
    ]

# Frontend only needs 3 fields, but gets 15+ fields!
```

### Solution: Client controls fields

```graphql
# Query 1: Dashboard (only needs summary)
query Dashboard {
  activities(limit: 100) {
    memberName
    activityType
    timestamp
  }
}

# Query 2: Detail page (needs everything)
query ActivityDetail {
  activities(limit: 10) {
    id
    memberName
    sourceType
    activityType
    timestamp
    metadata
    repository
    message
    additions
    deletions
  }
}

# Query 3: Export (custom fields)
query Export {
  activities(source: GITHUB, startDate: "2025-01-01") {
    memberName
    timestamp
    metadata
  }
}
```

**Benefits**:

- ✅ Dashboard loads faster (3 fields instead of 15)
- ✅ Reduced bandwidth (30-50% savings)
- ✅ No need to create separate REST endpoints

---

## 📝 Example 4: Real-world Query (Activities Page)

### Current Implementation (REST)

```typescript
// frontend/src/app/activities/page.tsx
export default function ActivitiesPage() {
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);

      // Multiple requests needed
      const sources = ['github', 'slack', 'notion', 'drive'];
      const allActivities = [];

      for (const source of sources) {
        const response = await api.get('/api/v1/activities', {
          params: { source, limit: 500 }
        });
        allActivities.push(...response.data.activities);
      }

      // Manual sorting and filtering
      allActivities.sort((a, b) =>
        new Date(b.timestamp) - new Date(a.timestamp)
      );

      setActivities(allActivities);
      setLoading(false);
    };

    fetchData();
  }, []);

  return <div>...</div>;
}
```

### With Strawberry GraphQL

```typescript
// frontend/src/app/activities/page.tsx
import { useQuery, gql } from '@apollo/client';

const GET_ACTIVITIES = gql`
  query GetActivities(
    $source: SourceType
    $memberName: String
    $startDate: DateTime
    $endDate: DateTime
    $limit: Int = 500
  ) {
    activities(
      source: $source
      memberName: $memberName
      startDate: $startDate
      endDate: $endDate
      limit: $limit
    ) {
      id
      memberName
      sourceType
      activityType
      timestamp
      metadata
    }
  }
`;

export default function ActivitiesPage() {
  // Single request, automatic caching, loading state
  const { data, loading, error } = useQuery(GET_ACTIVITIES, {
    variables: {
      limit: 500
    }
  });

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div>
      {data.activities.map(activity => (
        <ActivityCard key={activity.id} activity={activity} />
      ))}
    </div>
  );
}
```

**Improvements**:

- ✅ 4 requests → 1 request
- ✅ Automatic loading states
- ✅ Built-in caching (Apollo Client)
- ✅ Type-safe (auto-generated types)
- ✅ Easier to maintain

---

## 🎯 Installation & Setup

### 1. Install Strawberry

```bash
cd /Users/son-yeongseong/Desktop/dev/all-thing-eye

# Install with FastAPI integration
pip install strawberry-graphql[fastapi]

# Update requirements.txt
echo "strawberry-graphql[fastapi]==0.235.0" >> requirements.txt
```

### 2. Create GraphQL Structure

```bash
mkdir -p backend/graphql
touch backend/graphql/__init__.py
touch backend/graphql/types.py
touch backend/graphql/queries.py
touch backend/graphql/schema.py
```

### 3. Add to FastAPI

```python
# backend/main.py
from strawberry.fastapi import GraphQLRouter
from backend.graphql.schema import schema

# Create GraphQL endpoint
graphql_app = GraphQLRouter(
    schema,
    context_getter=lambda: {
        'db': mongo_manager.async_db,
        'config': app.state.config
    }
)

# Mount GraphQL endpoint
app.include_router(graphql_app, prefix="/graphql", tags=["graphql"])
```

### 4. Test

```bash
# Start server
python3 -m uvicorn backend.main:app --reload --port 8000

# Open browser to GraphQL Playground
open http://localhost:8000/graphql
```

---

## 🚀 Why Strawberry for This Project?

### ✅ Pros

1. **Minimal code changes**

   - Works with existing Pydantic models
   - No need to rewrite 35+ models
   - Can reuse MongoDB query logic

2. **Modern Python**

   - Uses type hints (Python 3.10+)
   - Async-first (perfect for motor)
   - IDE auto-completion

3. **FastAPI native**

   - Built-in integration
   - No additional middleware
   - Same request/response flow

4. **Gradual migration**
   - Keep REST API running
   - Add GraphQL in parallel
   - Migrate frontend page-by-page

### ⚠️ Cons

1. **Learning curve**

   - Team needs to learn GraphQL concepts
   - Different from REST API thinking

2. **Query complexity**

   - Need to add query depth limiters
   - Monitor for expensive queries

3. **Smaller ecosystem**
   - Less mature than Graphene
   - Fewer MongoDB examples

---

## 📚 Resources

- **Official Docs**: https://strawberry.rocks/docs
- **FastAPI Integration**: https://strawberry.rocks/docs/integrations/fastapi
- **GitHub**: https://github.com/strawberry-graphql/strawberry
- **Discord Community**: https://discord.gg/strawberry

---

## 🎓 Next Steps

1. **Read documentation** (`docs/GRAPHQL_MIGRATION_PLAN.md`)
2. **Start Phase 1** (1 week proof of concept)
3. **Test with real data**
4. **Evaluate before full migration**

Would you like me to implement Phase 1 now?
