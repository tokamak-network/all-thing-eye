# GraphQL Phase 3 - Frontend Integration

**Phase 3 Complete** ✅

---

## 🎯 What's New in Phase 3

### 1. Apollo Client Setup

- **Apollo Client** installed and configured
- **Error handling** with onError link
- **Cache management** with InMemoryCache
- **Automatic retry** for failed queries

### 2. GraphQL Provider

- **ApolloProvider** component wraps entire app
- Integrated into root layout (`layout.tsx`)
- Available in all pages and components

### 3. GraphQL Schema

- **Fragments**: Reusable field selections
- **Queries**: Pre-defined GraphQL queries
- **Types**: TypeScript types for type safety
- **Hooks**: Custom React hooks for easy data fetching

### 4. Demo Page

- **GraphQL Demo** page at `/graphql-demo`
- Interactive filters (member, source)
- Real-time data fetching
- Activity summary statistics

---

## 📦 New Files

### Configuration

- `frontend/src/lib/apollo-client.ts` - Apollo Client setup
- `frontend/src/components/ApolloProvider.tsx` - Provider component

### GraphQL Schema

- `frontend/src/graphql/fragments.ts` - GraphQL fragments
- `frontend/src/graphql/queries.ts` - GraphQL queries
- `frontend/src/graphql/types.ts` - TypeScript types
- `frontend/src/graphql/hooks.ts` - Custom hooks
- `frontend/src/graphql/index.ts` - Module exports

### Demo Page

- `frontend/src/app/graphql-demo/page.tsx` - Demo page

### Modified Files

- `frontend/package.json` - Added Apollo Client dependencies
- `frontend/src/app/layout.tsx` - Added ApolloProvider

---

## 🚀 Installation

### 1. Install Dependencies

```bash
cd frontend
npm install
```

This will install:

- `@apollo/client@^3.8.8` - Apollo Client for React
- `graphql@^16.8.1` - GraphQL core library

### 2. Environment Variables

Add to `frontend/.env.local` (if not already set):

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Start Development Server

```bash
npm run dev
```

Frontend will be available at: http://localhost:3000

---

## 🧪 Testing

### 1. Open Demo Page

Navigate to: **http://localhost:3000/graphql-demo**

### 2. Test Features

**Members Section:**

- Should display first 10 members
- Each member card shows name, email, role, activity count
- Data fetched via GraphQL `useMembers` hook

**Filters:**

- **Member dropdown**: Filter activities by member
- **Source dropdown**: Filter activities by data source (GitHub, Slack, etc.)
- Filters update instantly

**Activity Summary:**

- Total activity count
- Breakdown by source (GitHub, Slack, Notion, Drive)
- Updates when filters change

**Recent Activities:**

- Shows latest 20 activities
- Filters by selected member and source
- Displays: member name, source type, activity type, message, timestamp
- Click "View →" to open activity URL

### 3. Check Browser Console

Open browser DevTools (F12) and check:

**No GraphQL errors:**

```
✅ No [GraphQL error] messages
✅ No [Network error] messages
```

**Successful queries:**

```
Apollo Client: Loaded cache
Query completed in Xms
```

### 4. Check Backend Logs

In backend terminal, you should see:

```
🔍 GraphQL query started: GetMembers
📦 DataLoader: Batch loading activity counts for 10 members
✅ DataLoader: Loaded 10 activity counts
✅ GraphQL query completed: GetMembers in XXXms

🔍 GraphQL query started: GetActivities
✅ GraphQL query completed: GetActivities in XXXms
```

---

## 📚 Usage Examples

### Example 1: Fetch Members

```typescript
import { useMembers } from '@/graphql/hooks';

function MyComponent() {
  const { data, loading, error } = useMembers({ limit: 10 });

  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error: {error.message}</p>;

  return (
    <ul>
      {data?.members.map(member => (
        <li key={member.name}>
          {member.name} - {member.activityCount} activities
        </li>
      ))}
    </ul>
  );
}
```

### Example 2: Fetch Activities with Filters

```typescript
import { useActivities } from '@/graphql/hooks';
import { SourceType } from '@/graphql/types';

function ActivitiesList() {
  const { data, loading } = useActivities({
    memberName: 'Jason',
    source: SourceType.GITHUB,
    limit: 20,
  });

  return (
    <div>
      {data?.activities.map(activity => (
        <div key={activity.id}>
          <p>{activity.activityType}: {activity.message}</p>
          <span>{activity.timestamp}</span>
        </div>
      ))}
    </div>
  );
}
```

### Example 3: Fetch Single Member

```typescript
import { useMember } from '@/graphql/hooks';

function MemberProfile({ name }: { name: string }) {
  const { data, loading } = useMember({ name });

  if (loading) return <p>Loading...</p>;
  if (!data?.member) return <p>Member not found</p>;

  const member = data.member;

  return (
    <div>
      <h2>{member.name}</h2>
      <p>Email: {member.email}</p>
      <p>Total Activities: {member.activityCount}</p>

      <h3>Recent Activities:</h3>
      <ul>
        {member.recentActivities?.map(activity => (
          <li key={activity.id}>{activity.message}</li>
        ))}
      </ul>
    </div>
  );
}
```

### Example 4: Direct Apollo Client Usage

```typescript
import { apolloClient } from '@/lib/apollo-client';
import { GET_MEMBERS } from '@/graphql/queries';

async function fetchMembers() {
  const { data } = await apolloClient.query({
    query: GET_MEMBERS,
    variables: { limit: 10 },
  });

  return data.members;
}
```

---

## 🎨 Available Hooks

### Member Hooks

- `useMembers(variables?)` - Fetch all members
- `useMember(variables)` - Fetch single member
- `useMembersWithActivities(variables?)` - Fetch members with recent activities

### Activity Hooks

- `useActivities(variables?)` - Fetch activities
- `useActivitySummary(variables?)` - Fetch activity summary

### Project Hooks

- `useProjects(variables?)` - Fetch all projects
- `useProject(variables)` - Fetch single project

---

## 🔧 Customization

### Modify Cache Behavior

Edit `frontend/src/lib/apollo-client.ts`:

```typescript
cache: new InMemoryCache({
  typePolicies: {
    Query: {
      fields: {
        activities: {
          // Custom merge logic
          merge(existing = [], incoming) {
            return [...existing, ...incoming];
          },
        },
      },
    },
  },
}),
```

### Add New Queries

1. **Add query in `frontend/src/graphql/queries.ts`:**

```typescript
export const GET_MY_DATA = gql`
  query GetMyData($param: String!) {
    myData(param: $param) {
      field1
      field2
    }
  }
`;
```

2. **Add types in `frontend/src/graphql/types.ts`:**

```typescript
export interface GetMyDataVariables {
  param: string;
}

export interface GetMyDataResponse {
  myData: MyData;
}
```

3. **Add hook in `frontend/src/graphql/hooks.ts`:**

```typescript
export function useMyData(variables: GetMyDataVariables) {
  return useQuery<GetMyDataResponse, GetMyDataVariables>(GET_MY_DATA, {
    variables,
  });
}
```

---

## 🐛 Troubleshooting

### Issue: "Cannot find module '@apollo/client'"

**Solution**: Install dependencies

```bash
cd frontend
npm install
```

### Issue: GraphQL queries fail with network error

**Check**:

1. Backend is running on port 8000
2. GraphQL endpoint is accessible: http://localhost:8000/graphql
3. CORS is configured correctly

**Solution**: Verify `NEXT_PUBLIC_API_URL` in `.env.local`

### Issue: "Variable is not defined" error

**Check**: Make sure variable types match GraphQL schema

**Solution**: Use correct types from `@/graphql/types`

### Issue: Data not updating after changes

**Solution**: Use `refetch()` or set `fetchPolicy: 'network-only'`

```typescript
const { data, refetch } = useActivities();

// Later...
await refetch();
```

---

## 📊 Performance

### Before GraphQL (REST API)

- Multiple API calls for related data
- Over-fetching (receiving unused fields)
- No automatic caching
- Manual state management

### After GraphQL (Apollo Client)

- **Single query** for complex data requirements
- **Precise data fetching** (only requested fields)
- **Automatic caching** (reduces API calls)
- **DataLoader** prevents N+1 queries on backend
- **Optimistic UI** updates possible

**Example**: Fetching members with activities

**REST API** (old):

```
GET /api/members → 50ms
GET /api/activities?member=Jason → 150ms
GET /api/activities?member=Monica → 150ms
...
Total: 50 + (150 × N members) = 1550ms for 10 members
```

**GraphQL** (new):

```
POST /graphql (members with recentActivities) → 200ms
Total: 200ms (87% faster!)
```

---

## 🎯 Next Steps

### Migrate Existing Pages

1. **Members Page** (`/members`)

   - Replace REST API calls with `useMembers()`
   - Use `useMember()` for member details

2. **Projects Page** (`/projects`)

   - Replace REST API calls with `useProjects()`
   - Use `useProject()` for project details

3. **Activities Page** (`/activities`)
   - Replace REST API calls with `useActivities()`
   - Add real-time filters with Apollo Client

### Add GraphQL Mutations

Create mutations for:

- Creating/updating members
- Creating projects
- Bulk operations

### Add GraphQL Subscriptions

For real-time updates:

- New activities notifications
- Live activity feed
- Real-time collaboration

---

## 📝 Summary

**Phase 3 delivers:**

✅ **Apollo Client** fully integrated
✅ **GraphQL Provider** in root layout
✅ **Type-safe queries** with TypeScript
✅ **Custom hooks** for easy data fetching
✅ **Demo page** showcasing GraphQL features
✅ **Error handling** and caching configured
✅ **Documentation** and usage examples

**Ready to use GraphQL in:**

- Any page component
- Any client component
- Server components (with direct Apollo Client usage)

---

**Test it now:** Open http://localhost:3000/graphql-demo 🚀

