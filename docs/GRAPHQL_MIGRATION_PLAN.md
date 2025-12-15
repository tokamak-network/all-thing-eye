# GraphQL Migration Plan for All-Thing-Eye

**Status**: Planning Phase  
**Created**: 2025-01-19  
**Purpose**: Analyze and plan GraphQL integration with existing MongoDB/FastAPI architecture

---

## 📋 Executive Summary

### Current State

- **Backend**: FastAPI with 82 REST endpoints across 17 files
- **Database**: MongoDB (pymongo + motor for async)
- **Models**: 35+ Pydantic models
- **Data Sources**: GitHub, Slack, Notion, Drive, Recordings (6 sources)

### Recommendation

**✅ GraphQL is highly suitable** for this project due to:

1. Complex data relationships (Members ↔ Activities ↔ Projects)
2. Multiple filtering requirements (source, member, project, date, keyword)
3. Nested data structures (messages with reactions, PRs with reviews)
4. Varied client needs (different fields for Dashboard vs Reports)

---

## 🎯 Option Analysis

### Option 1: Strawberry GraphQL (⭐ RECOMMENDED)

**Why Strawberry?**

- ✅ Native Python type hints (works seamlessly with existing Pydantic models)
- ✅ Excellent FastAPI integration
- ✅ Async/await support (compatible with motor)
- ✅ Active development and modern API
- ✅ Built-in subscriptions support
- ✅ Automatic schema generation from type hints

**Example Integration**:

```python
# backend/graphql/types.py
import strawberry
from typing import List, Optional
from datetime import datetime

@strawberry.type
class Member:
    id: str
    name: str
    email: str
    role: Optional[str]
    github_username: Optional[str]
    slack_id: Optional[str]

    @strawberry.field
    async def activities(
        self,
        info,
        source: Optional[str] = None,
        start_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List['Activity']:
        # Leverage existing MongoDB queries
        db = info.context['db']
        query = {'member_name': self.name}
        if source:
            query['source_type'] = source
        if start_date:
            query['timestamp'] = {'$gte': start_date}

        activities = []
        async for doc in db['github_commits'].find(query).limit(limit):
            activities.append(Activity.from_mongo(doc))
        return activities

@strawberry.type
class Activity:
    id: str
    member_name: str
    source_type: str
    activity_type: str
    timestamp: datetime
    metadata: strawberry.scalars.JSON

    @staticmethod
    def from_mongo(doc):
        return Activity(
            id=str(doc['_id']),
            member_name=doc['member_name'],
            source_type=doc.get('source_type', 'unknown'),
            activity_type=doc.get('activity_type', 'unknown'),
            timestamp=doc['timestamp'],
            metadata=doc.get('metadata', {})
        )

@strawberry.type
class Query:
    @strawberry.field
    async def member(self, info, name: str) -> Optional[Member]:
        db = info.context['db']
        member_doc = await db['members'].find_one({'name': name})
        if not member_doc:
            return None
        return Member(
            id=str(member_doc['_id']),
            name=member_doc['name'],
            email=member_doc['email'],
            role=member_doc.get('role'),
            github_username=member_doc.get('github_username'),
            slack_id=member_doc.get('slack_id')
        )

    @strawberry.field
    async def activities(
        self,
        info,
        source: Optional[str] = None,
        member_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Activity]:
        db = info.context['db']
        query = {}
        if source:
            query['source_type'] = source
        if member_name:
            query['member_name'] = member_name

        # Aggregate from multiple sources
        activities = []

        if not source or source == 'github':
            async for doc in db['github_commits'].find(query).limit(limit):
                activities.append(Activity.from_mongo({
                    **doc,
                    'source_type': 'github',
                    'activity_type': 'commit',
                    'timestamp': doc['date'],
                    'member_name': doc['author_name']
                }))

        return activities

schema = strawberry.Schema(query=Query)

# backend/main.py integration
from strawberry.fastapi import GraphQLRouter

graphql_app = GraphQLRouter(
    schema,
    context_getter=lambda: {'db': mongo_manager.async_db}
)

app.include_router(graphql_app, prefix="/graphql")
```

**Pros**:

- Minimal code changes required
- Reuse existing Pydantic models
- Keep REST API alongside GraphQL (gradual migration)
- Modern Python syntax (dataclasses, type hints)

**Cons**:

- Smaller community than Graphene
- Less documentation for MongoDB integration

**Installation**:

```bash
pip install strawberry-graphql[fastapi]
```

---

### Option 2: Graphene + Graphene-Mongo

**Why Graphene?**

- ✅ Mature and battle-tested
- ✅ Large community and extensive documentation
- ✅ Direct MongoDB integration via graphene-mongo
- ✅ Compatible with mongoengine ODM

**Example Integration**:

```python
# First, convert Pydantic models to MongoEngine
# backend/models/mongoengine_models.py
from mongoengine import Document, StringField, DateTimeField, ListField, DictField

class Member(Document):
    meta = {'collection': 'members'}
    name = StringField(required=True, unique=True)
    email = StringField(required=True)
    role = StringField()
    github_username = StringField()
    slack_id = StringField()
    created_at = DateTimeField(default=datetime.utcnow)

class Activity(Document):
    meta = {'collection': 'activities'}
    member_name = StringField(required=True)
    source_type = StringField(required=True)
    activity_type = StringField(required=True)
    timestamp = DateTimeField(required=True)
    metadata = DictField()

# backend/graphql/schema.py
import graphene
from graphene_mongo import MongoengineObjectType

class MemberType(MongoengineObjectType):
    class Meta:
        model = Member
        interfaces = (graphene.relay.Node,)

    activities = graphene.List(lambda: ActivityType)

    def resolve_activities(self, info):
        return Activity.objects(member_name=self.name)

class ActivityType(MongoengineObjectType):
    class Meta:
        model = Activity
        interfaces = (graphene.relay.Node,)

class Query(graphene.ObjectType):
    member = graphene.Field(MemberType, name=graphene.String(required=True))
    activities = graphene.List(
        ActivityType,
        source=graphene.String(),
        member_name=graphene.String(),
        limit=graphene.Int(default_value=100)
    )

    def resolve_member(self, info, name):
        return Member.objects(name=name).first()

    def resolve_activities(self, info, source=None, member_name=None, limit=100):
        query = {}
        if source:
            query['source_type'] = source
        if member_name:
            query['member_name'] = member_name
        return Activity.objects(**query).limit(limit)

schema = graphene.Schema(query=Query)

# backend/main.py integration
from starlette_graphene3 import GraphQLApp, make_graphiql_handler

app.mount("/graphql", GraphQLApp(
    schema=schema,
    on_get=make_graphiql_handler()
))
```

**Pros**:

- Mature ecosystem
- Direct mongoengine integration
- Extensive documentation
- Relay-compliant (cursor pagination)

**Cons**:

- Requires converting ALL Pydantic models to MongoEngine (significant refactoring)
- MongoEngine has performance overhead
- Less Pythonic (older API design)

**Installation**:

```bash
pip install graphene==3.3
pip install graphene-mongo==0.2.15
pip install starlette-graphene3==0.6.0
```

---

### Option 3: Ariadne (Code-First GraphQL)

**Why Ariadne?**

- ✅ Schema-first approach (write .graphql files)
- ✅ Flexible resolver system
- ✅ Good FastAPI integration
- ✅ Async-first design

**Example**:

```python
# backend/graphql/schema.graphql
type Member {
  id: ID!
  name: String!
  email: String!
  role: String
  activities(source: String, limit: Int = 100): [Activity!]!
}

type Activity {
  id: ID!
  memberName: String!
  sourceType: String!
  activityType: String!
  timestamp: DateTime!
  metadata: JSON
}

type Query {
  member(name: String!): Member
  activities(source: String, memberName: String, limit: Int = 100): [Activity!]!
}

# backend/graphql/resolvers.py
from ariadne import QueryType, ObjectType, make_executable_schema
from ariadne.asgi import GraphQL

query = QueryType()
member_type = ObjectType("Member")

@query.field("member")
async def resolve_member(_, info, name):
    db = info.context['db']
    member = await db['members'].find_one({'name': name})
    return member

@member_type.field("activities")
async def resolve_member_activities(member, info, source=None, limit=100):
    db = info.context['db']
    query = {'member_name': member['name']}
    if source:
        query['source_type'] = source

    activities = []
    async for doc in db['github_commits'].find(query).limit(limit):
        activities.append({
            'id': str(doc['_id']),
            'memberName': doc['author_name'],
            'sourceType': 'github',
            'activityType': 'commit',
            'timestamp': doc['date'],
            'metadata': doc
        })
    return activities

schema = make_executable_schema(type_defs, [query, member_type])
graphql_app = GraphQL(schema, context_value={'db': mongo_manager.async_db})

# backend/main.py
app.mount("/graphql", graphql_app)
```

**Pros**:

- Schema-first = better for frontend collaboration
- Very flexible resolver system
- Clean separation of schema and logic

**Cons**:

- More boilerplate (manual resolver bindings)
- No automatic schema generation

**Installation**:

```bash
pip install ariadne==0.22.0
```

---

## 🏆 Recommendation: Strawberry GraphQL

### Why Strawberry?

1. **Minimal Migration Effort**

   - Works directly with existing Pydantic models
   - No need to rewrite 35+ models
   - Can reuse existing MongoDB query logic

2. **Modern Python**

   ```python
   # Your existing code
   class ActivityResponse(BaseModel):
       id: str
       member_name: str
       source_type: str

   # Convert to Strawberry (minimal change)
   @strawberry.type
   class Activity:
       id: str
       member_name: str
       source_type: str
   ```

3. **Hybrid Approach**

   - Keep REST API for simple CRUD operations
   - Add GraphQL for complex queries
   - Gradual migration without breaking existing frontend

4. **MongoDB Compatibility**
   - Works great with motor (async MongoDB driver)
   - No ORM/ODM required
   - Direct query control (important for performance)

---

## 📝 Migration Strategy

### Phase 1: Setup & Proof of Concept (1-2 days)

```bash
# 1. Install Strawberry
pip install strawberry-graphql[fastapi]

# 2. Create GraphQL structure
mkdir -p backend/graphql
touch backend/graphql/__init__.py
touch backend/graphql/types.py
touch backend/graphql/queries.py
touch backend/graphql/mutations.py
touch backend/graphql/schema.py
```

**Files to create**:

```python
# backend/graphql/types.py
import strawberry
from typing import List, Optional
from datetime import datetime

@strawberry.type
class Member:
    id: str
    name: str
    email: str
    role: Optional[str] = None
    github_username: Optional[str] = None
    slack_id: Optional[str] = None

@strawberry.type
class Activity:
    id: str
    member_name: str
    source_type: str
    activity_type: str
    timestamp: datetime
    metadata: strawberry.scalars.JSON

@strawberry.enum
class SourceType:
    GITHUB = "github"
    SLACK = "slack"
    NOTION = "notion"
    DRIVE = "drive"
    RECORDINGS = "recordings"

# backend/graphql/queries.py
import strawberry
from typing import List, Optional
from .types import Member, Activity, SourceType

@strawberry.type
class Query:
    @strawberry.field
    async def members(self, info, limit: int = 100) -> List[Member]:
        """Get all members"""
        db = info.context['db']
        members = []
        async for doc in db['members'].find().limit(limit):
            members.append(Member(
                id=str(doc['_id']),
                name=doc['name'],
                email=doc['email'],
                role=doc.get('role'),
                github_username=doc.get('github_username'),
                slack_id=doc.get('slack_id')
            ))
        return members

    @strawberry.field
    async def member(self, info, name: str) -> Optional[Member]:
        """Get member by name"""
        db = info.context['db']
        doc = await db['members'].find_one({'name': name})
        if not doc:
            return None
        return Member(
            id=str(doc['_id']),
            name=doc['name'],
            email=doc['email'],
            role=doc.get('role'),
            github_username=doc.get('github_username'),
            slack_id=doc.get('slack_id')
        )

    @strawberry.field
    async def activities(
        self,
        info,
        source: Optional[SourceType] = None,
        member_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        keyword: Optional[str] = None,
        limit: int = 100
    ) -> List[Activity]:
        """
        Query activities with flexible filtering

        This resolver can leverage existing query logic from activities_mongo.py
        """
        db = info.context['db']

        # Build query (reuse existing logic)
        sources = [source.value] if source else ['github', 'slack', 'notion', 'drive', 'recordings']
        activities = []

        for src in sources:
            if src == 'github':
                collection = db['github_commits']
                query = {}
                if member_name:
                    query['author_name'] = member_name
                if start_date:
                    query['date'] = {'$gte': start_date}
                if end_date:
                    query['date'] = query.get('date', {})
                    query['date']['$lte'] = end_date
                if keyword:
                    query['message'] = {'$regex': keyword, '$options': 'i'}

                async for doc in collection.find(query).limit(limit):
                    activities.append(Activity(
                        id=str(doc['_id']),
                        member_name=doc['author_name'],
                        source_type='github',
                        activity_type='commit',
                        timestamp=doc['date'],
                        metadata={
                            'sha': doc['sha'],
                            'message': doc['message'],
                            'repository': doc['repository'],
                            'additions': doc.get('additions', 0),
                            'deletions': doc.get('deletions', 0)
                        }
                    ))

        # Sort by timestamp
        activities.sort(key=lambda a: a.timestamp, reverse=True)
        return activities[:limit]

# backend/graphql/schema.py
import strawberry
from .queries import Query
from .types import Member, Activity

schema = strawberry.Schema(query=Query)

# backend/main.py (add GraphQL endpoint)
from backend.graphql.schema import schema
from strawberry.fastapi import GraphQLRouter

# Add GraphQL endpoint
graphql_app = GraphQLRouter(
    schema,
    context_getter=lambda: {
        'db': mongo_manager.async_db,
        'config': app.state.config
    }
)
app.include_router(graphql_app, prefix="/graphql", tags=["graphql"])
```

**Access GraphQL Playground**:

```
http://localhost:8000/graphql
```

---

### Phase 2: Add Field Resolvers (2-3 days)

Add computed fields and nested relationships:

```python
@strawberry.type
class Member:
    id: str
    name: str
    email: str

    @strawberry.field
    async def activity_count(self, info, source: Optional[SourceType] = None) -> int:
        """Get total activity count for this member"""
        db = info.context['db']
        query = {'member_name': self.name}

        count = 0
        if not source or source == SourceType.GITHUB:
            count += await db['github_commits'].count_documents(query)
            count += await db['github_pull_requests'].count_documents({'author': self.name})

        if not source or source == SourceType.SLACK:
            count += await db['slack_messages'].count_documents({'user_name': self.name})

        return count

    @strawberry.field
    async def recent_activities(
        self,
        info,
        limit: int = 10
    ) -> List[Activity]:
        """Get recent activities for this member"""
        # Reuse activities resolver with member_name filter
        return await Query().activities(
            info,
            member_name=self.name,
            limit=limit
        )

    @strawberry.field
    async def projects(self, info) -> List['Project']:
        """Get projects this member is involved in"""
        db = info.context['db']
        projects = []
        async for doc in db['projects'].find({'member_ids': self.id}):
            projects.append(Project.from_mongo(doc))
        return projects

@strawberry.type
class Project:
    id: str
    key: str
    name: str
    slack_channel: Optional[str]
    repositories: List[str]

    @strawberry.field
    async def members(self, info) -> List[Member]:
        """Get all members in this project"""
        db = info.context['db']
        members = []
        async for doc in db['members'].find({'_id': {'$in': self.member_ids}}):
            members.append(Member.from_mongo(doc))
        return members

    @strawberry.field
    async def activity_summary(
        self,
        info,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> 'ActivitySummary':
        """Get activity statistics for this project"""
        db = info.context['db']

        # Count activities by source
        github_count = await db['github_commits'].count_documents({
            'repository': {'$in': self.repositories}
        })

        return ActivitySummary(
            total=github_count,
            by_source={'github': github_count}
        )

@strawberry.type
class ActivitySummary:
    total: int
    by_source: strawberry.scalars.JSON
```

---

### Phase 3: Add Subscriptions (Optional, 1 day)

Real-time updates via WebSocket:

```python
import asyncio
from typing import AsyncGenerator

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def activity_feed(
        self,
        info,
        source: Optional[SourceType] = None
    ) -> AsyncGenerator[Activity, None]:
        """Real-time activity stream"""
        db = info.context['db']

        while True:
            # Poll database for new activities
            # (In production, use MongoDB Change Streams)
            query = {}
            if source:
                query['source_type'] = source.value

            async for doc in db['github_commits'].find(query).sort('date', -1).limit(1):
                yield Activity.from_mongo(doc)

            await asyncio.sleep(5)  # Poll every 5 seconds

schema = strawberry.Schema(
    query=Query,
    subscription=Subscription
)
```

**Frontend usage**:

```typescript
// Using urql or Apollo Client
const subscription = `
  subscription {
    activityFeed(source: GITHUB) {
      id
      memberName
      activityType
      timestamp
    }
  }
`;
```

---

### Phase 4: Frontend Integration (2-3 days)

**Option A: Apollo Client** (Most popular)

```typescript
// frontend/src/lib/apolloClient.ts
import { ApolloClient, InMemoryCache, HttpLink } from '@apollo/client';

const client = new ApolloClient({
  link: new HttpLink({
    uri: 'http://localhost:8000/graphql',
  }),
  cache: new InMemoryCache(),
});

export default client;

// frontend/src/app/activities/page.tsx
import { useQuery, gql } from '@apollo/client';

const GET_ACTIVITIES = gql`
  query GetActivities($source: SourceType, $memberName: String, $limit: Int) {
    activities(source: $source, memberName: $memberName, limit: $limit) {
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
  const { data, loading, error } = useQuery(GET_ACTIVITIES, {
    variables: {
      source: 'GITHUB',
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

**Option B: urql** (Lighter alternative)

```typescript
import { createClient, Provider, useQuery } from 'urql';

const client = createClient({
  url: 'http://localhost:8000/graphql',
});

// Wrap app
<Provider value={client}>
  <App />
</Provider>
```

---

## 🔄 Migration Path

### Hybrid Approach (Recommended)

**Keep REST for**:

- Simple CRUD operations (`GET /members`, `POST /members`)
- File uploads/downloads
- Authentication endpoints
- Health checks

**Use GraphQL for**:

- Complex queries with filters (`activities` with multiple sources)
- Nested data fetching (member + activities + projects in one query)
- Dashboard aggregations
- Reports with custom field selection

**Example**:

```
REST Endpoints (Keep):
├── POST   /api/v1/auth/login
├── GET    /api/v1/health
├── POST   /api/v1/members
├── GET    /api/v1/custom-export/export  (binary download)

GraphQL Endpoint (New):
└── POST   /graphql
    ├── Query: members, activities, projects, stats
    ├── Mutation: updateMember, createProject
    └── Subscription: activityFeed (optional)
```

---

## 🚀 Implementation Plan

### Week 1: Setup + Core Types

- [ ] Install Strawberry (`pip install strawberry-graphql[fastapi]`)
- [ ] Create `backend/graphql/` structure
- [ ] Define core types: `Member`, `Activity`, `Project`
- [ ] Implement basic Query: `members`, `activities`
- [ ] Add `/graphql` endpoint to `main.py`
- [ ] Test with GraphQL Playground

### Week 2: Field Resolvers + Complex Queries

- [ ] Add computed fields (`Member.activity_count`, `Member.recent_activities`)
- [ ] Add nested resolvers (`Member.projects`, `Project.members`)
- [ ] Implement filtering enums and input types
- [ ] Add pagination (cursor-based or offset-based)
- [ ] Performance optimization (DataLoader for N+1 prevention)

### Week 3: Frontend Integration

- [ ] Install Apollo Client or urql
- [ ] Create GraphQL queries for Activities page
- [ ] Migrate Dashboard to use GraphQL
- [ ] Add query caching
- [ ] Performance testing

### Week 4: Advanced Features (Optional)

- [ ] Add mutations (`createMember`, `updateProject`)
- [ ] Implement subscriptions for real-time updates
- [ ] Add GraphQL query cost analysis
- [ ] Setup monitoring (query complexity, execution time)

---

## 🎨 Example Use Cases

### Use Case 1: Dashboard Overview

**Current REST** (3 requests):

```javascript
const members = await fetch('/api/v1/members?limit=100');
const activities = await fetch('/api/v1/activities?limit=500');
const stats = await fetch('/api/v1/stats/summary');
```

**With GraphQL** (1 request):

```graphql
query DashboardOverview {
  members(limit: 10) {
    name
    activityCount(source: GITHUB)
    recentActivities(limit: 5) {
      activityType
      timestamp
    }
  }
  activitySummary {
    total
    bySource
    byType
  }
}
```

### Use Case 2: Member Detail Page

**Current REST** (5+ requests):

```javascript
const member = await fetch(`/api/v1/members/${id}`);
const githubActivities = await fetch(`/api/v1/activities?source=github&member=${name}`);
const slackActivities = await fetch(`/api/v1/activities?source=slack&member=${name}`);
const projects = await fetch(`/api/v1/projects?member=${name}`);
const stats = await fetch(`/api/v1/stats/member/${id}`);
```

**With GraphQL** (1 request):

```graphql
query MemberDetail($name: String!) {
  member(name: $name) {
    id
    name
    email
    role

    activities(limit: 100) {
      sourceType
      activityType
      timestamp
      metadata
    }

    activityCount(source: GITHUB)
    activityCount(source: SLACK)

    projects {
      name
      slack_channel
    }

    collaborations {
      withMember
      sharedActivities
    }
  }
}
```

### Use Case 3: Custom Export with Field Selection

```graphql
query CustomExport($filters: ActivityFilters!) {
  activities(
    source: GITHUB,
    memberName: "Monica",
    startDate: "2025-01-01",
    endDate: "2025-01-31"
  ) {
    # Client selects only needed fields
    memberName
    timestamp
    metadata
  }
}
```

---

## ⚠️ Considerations

### 1. **ORM/ODM Decision**

**Current**: Raw pymongo queries (no ORM)

**Options**:

#### A. Keep Raw Queries (✅ Recommended)

```python
# Pros:
✅ Maximum performance control
✅ No learning curve (team already familiar)
✅ Direct MongoDB feature access ($lookup, aggregation pipeline)
✅ No schema migration needed

# Cons:
❌ More boilerplate in resolvers
❌ Manual data validation
```

#### B. Adopt Beanie ODM

```python
# backend/models/beanie_models.py
from beanie import Document
from pydantic import Field

class Member(Document):
    name: str
    email: str
    role: Optional[str] = None

    class Settings:
        name = "members"  # Collection name

# Pros:
✅ Pydantic-based (minimal refactoring)
✅ Async-first (motor under the hood)
✅ Better type safety
✅ Query builder syntax

# Cons:
❌ Requires rewriting all models (~10-15 models)
❌ Learning curve for team
❌ Some MongoDB features not exposed
```

**Recommendation**: **Keep raw queries** for now. Add Beanie later if needed.

### 2. **Performance Concerns**

**N+1 Query Problem**:

```graphql
query {
  members {
    name
    activities {  # ❌ Queries DB once per member!
      activityType
    }
  }
}
```

**Solution: DataLoader**:

```python
from strawberry.dataloader import DataLoader

async def load_activities_batch(keys: List[str]) -> List[List[Activity]]:
    """Batch load activities for multiple members"""
    db = get_db()

    # Single query for all members
    pipeline = [
        {'$match': {'member_name': {'$in': keys}}},
        {'$group': {'_id': '$member_name', 'activities': {'$push': '$$ROOT'}}}
    ]

    results = {}
    async for doc in db['github_commits'].aggregate(pipeline):
        results[doc['_id']] = doc['activities']

    return [results.get(key, []) for key in keys]

activities_loader = DataLoader(load_fn=load_activities_batch)

@strawberry.type
class Member:
    @strawberry.field
    async def activities(self, info) -> List[Activity]:
        loader = info.context['activities_loader']
        return await loader.load(self.name)
```

### 3. **Query Complexity**

Add query cost analysis to prevent expensive queries:

```python
from strawberry.extensions import QueryDepthLimiter

schema = strawberry.Schema(
    query=Query,
    extensions=[
        QueryDepthLimiter(max_depth=10),  # Prevent deeply nested queries
    ]
)
```

### 4. **Backward Compatibility**

**Strategy**: Gradual migration

- Keep ALL REST endpoints functional
- Add GraphQL endpoint `/graphql` in parallel
- Migrate frontend pages one by one
- Monitor GraphQL adoption metrics
- Deprecate REST endpoints only after 100% migration

---

## 📊 Comparison Table

| Feature              | REST API (Current)            | GraphQL (Proposed)         |
| -------------------- | ----------------------------- | -------------------------- |
| **Endpoints**        | 82 endpoints                  | 1 endpoint                 |
| **Over-fetching**    | ❌ Common                     | ✅ Client controls fields  |
| **Under-fetching**   | ❌ Requires multiple requests | ✅ Single request          |
| **Type Safety**      | ⚠️ Manual (Pydantic)          | ✅ Auto-generated          |
| **Documentation**    | ⚠️ Swagger/OpenAPI            | ✅ Self-documenting schema |
| **Caching**          | ⚠️ URL-based                  | ✅ Field-level caching     |
| **Real-time**        | ❌ Polling only               | ✅ Subscriptions           |
| **Learning Curve**   | ✅ Simple                     | ⚠️ Medium                  |
| **Migration Effort** | -                             | ⚠️ 2-4 weeks               |

---

## 🎯 Quick Start (Proof of Concept)

**1. Install Strawberry**

```bash
cd /Users/son-yeongseong/Desktop/dev/all-thing-eye
pip install strawberry-graphql[fastapi]
```

**2. Create minimal GraphQL endpoint**

```bash
mkdir -p backend/graphql
```

**3. Create `backend/graphql/schema.py`** (see Phase 1 code above)

**4. Update `backend/main.py`**:

```python
from backend.graphql.schema import schema
from strawberry.fastapi import GraphQLRouter

graphql_app = GraphQLRouter(
    schema,
    context_getter=lambda: {'db': mongo_manager.async_db}
)
app.include_router(graphql_app, prefix="/graphql", tags=["graphql"])
```

**5. Test**:

```bash
# Start server
python3 -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Open browser
open http://localhost:8000/graphql

# Run test query
query {
  members(limit: 5) {
    name
    email
  }
}
```

---

## 🔧 Technical Decisions

### Decision 1: ORM/ODM

**Choice**: ❌ No ORM (keep raw pymongo queries)
**Rationale**:

- Existing code uses raw queries efficiently
- MongoDB aggregation pipelines need direct access
- No migration needed
- Can add Beanie later if team wants

### Decision 2: GraphQL Library

**Choice**: ✅ Strawberry GraphQL
**Rationale**:

- Best FastAPI integration
- Works with existing Pydantic models
- Modern Python syntax (type hints)
- Async-first design

### Decision 3: Migration Strategy

**Choice**: ✅ Hybrid (REST + GraphQL)
**Rationale**:

- Zero downtime migration
- Gradual frontend migration
- Keep REST for simple operations
- GraphQL for complex queries only

### Decision 4: Schema Generation

**Choice**: ✅ Code-first (Strawberry decorators)
**Rationale**:

- Type safety with Python type hints
- Auto-sync with backend code
- Less boilerplate than schema-first

---

## 📈 Expected Benefits

### Performance

- **Reduced API calls**: 3-5 requests → 1 request (60-80% reduction)
- **Smaller payload**: Client requests only needed fields (30-50% bandwidth savings)
- **Better caching**: Field-level granularity

### Developer Experience

- **Self-documenting API**: GraphQL Playground with inline docs
- **Type safety**: Auto-generated TypeScript types from schema
- **Faster development**: Frontend can add fields without backend changes

### User Experience

- **Faster page loads**: Fewer round trips
- **Real-time updates**: Subscriptions (optional)
- **Better mobile experience**: Less data transfer

---

## ⚠️ Risks & Mitigation

| Risk                       | Impact | Mitigation                                       |
| -------------------------- | ------ | ------------------------------------------------ |
| **Learning curve**         | Medium | Training session, documentation                  |
| **Query complexity**       | High   | Add QueryDepthLimiter, cost analysis             |
| **N+1 queries**            | High   | Use DataLoader for batch loading                 |
| **Breaking changes**       | Low    | Keep REST API during migration                   |
| **Performance regression** | Medium | Monitor query execution time, optimize resolvers |

---

## 🎓 Resources

### Learning

- [Strawberry Documentation](https://strawberry.rocks/)
- [GraphQL Best Practices](https://graphql.org/learn/best-practices/)
- [FastAPI + Strawberry Tutorial](https://strawberry.rocks/docs/integrations/fastapi)

### Tools

- **GraphQL Playground**: Built-in at `/graphql`
- **GraphQL Codegen**: Generate TypeScript types
- **Apollo Studio**: GraphQL monitoring and analytics

---

## 🚦 Go/No-Go Decision

### ✅ Proceed with GraphQL if:

1. Team is willing to invest 2-4 weeks for migration
2. Frontend complexity is growing (many API calls per page)
3. Mobile app is planned (bandwidth optimization critical)
4. Real-time features are desired

### ❌ Stick with REST if:

1. Current API performance is satisfactory
2. Team bandwidth is limited
3. No complex nested queries needed
4. Simple CRUD operations dominate

---

## 💡 Recommendation

**Start with Phase 1 (1 week proof of concept)**:

1. Install Strawberry
2. Create GraphQL endpoint
3. Implement `members` and `activities` queries
4. Test with existing data
5. Evaluate before full migration

**Success Metrics**:

- GraphQL query executes in <500ms
- Frontend code reduced by 30%+
- Team comfortable with GraphQL concepts

If successful → proceed to Phase 2-4.
If not → stick with REST, revisit in 6 months.

---

**Next Steps**: Would you like me to implement Phase 1 (proof of concept) now?
