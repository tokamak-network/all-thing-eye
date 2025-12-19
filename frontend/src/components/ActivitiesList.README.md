# ActivitiesList Component

A reusable, feature-rich component for displaying activities from various sources (GitHub, Slack, Notion, Google Drive, Recordings).

## Features

- ✅ Display activities from multiple sources with source-specific formatting
- ✅ Expandable/collapsible activity details
- ✅ Optional translation support (EN/KR) for Slack and Notion content
- ✅ Optional daily analysis modal integration for recordings_daily
- ✅ Notion UUID to member name resolution
- ✅ Loading and error states
- ✅ Responsive design with Tailwind CSS
- ✅ Customizable through props

## Installation

The component is already created in `/frontend/src/components/ActivitiesList.tsx`.

Helper functions are available in `/frontend/src/utils/activityHelpers.ts`.

## Basic Usage

```tsx
import ActivitiesList from "@/components/ActivitiesList";

function MyPage() {
  const activities = [/* your activities data */];

  return (
    <ActivitiesList
      activities={activities}
      loading={false}
      error={null}
    />
  );
}
```

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `activities` | `Activity[]` | **required** | Array of activity objects to display |
| `loading` | `boolean` | `false` | Show loading spinner |
| `error` | `Error \| null` | `null` | Show error message |
| `expandedActivity` | `string \| null` | `null` | ID of currently expanded activity (controlled) |
| `onToggleActivity` | `(id: string) => void` | `undefined` | Handler for activity expansion (controlled) |
| `enableTranslation` | `boolean` | `false` | Enable translation buttons for text content |
| `onTranslate` | `(id: string, text: string, lang: string) => void` | `undefined` | Handler for translation requests |
| `translations` | `Record<string, {text: string, lang: string}>` | `{}` | Translation cache object |
| `translating` | `string \| null` | `null` | ID of activity currently being translated |
| `enableDailyAnalysis` | `boolean` | `false` | Enable daily analysis buttons for recordings_daily |
| `onDailyAnalysisClick` | `(activity: Activity, tab: string) => void` | `undefined` | Handler for daily analysis modal |
| `notionUuidMap` | `Record<string, string>` | `{}` | Map of Notion UUIDs to member names |
| `showEmpty` | `boolean` | `true` | Show empty state when no activities |

## Activity Object Structure

```typescript
interface Activity {
  id: string;
  activity_id?: string;
  member_name: string;
  source_type: string; // "github" | "slack" | "notion" | "drive" | "recordings" | "recordings_daily"
  activity_type: string; // "commit" | "pull_request" | "issue" | "message" | etc.
  timestamp: string; // ISO 8601 format
  metadata?: {
    title?: string;
    name?: string;
    message?: string;
    text?: string;
    repository?: string;
    channel?: string;
    url?: string;
    // ... other source-specific fields
  };
}
```

## Usage Examples

### 1. Basic List (No Extra Features)

```tsx
import ActivitiesList from "@/components/ActivitiesList";

function MemberDetailPage({ memberId }: { memberId: string }) {
  const { data, loading, error } = useActivities({ memberName: memberId });

  return (
    <ActivitiesList
      activities={data?.activities || []}
      loading={loading}
      error={error}
    />
  );
}
```

### 2. With Translation Feature

```tsx
import { useState } from "react";
import ActivitiesList from "@/components/ActivitiesList";
import { api as apiClient } from "@/lib/api";

function ActivitiesWithTranslation() {
  const [translations, setTranslations] = useState({});
  const [translating, setTranslating] = useState(null);
  const [expandedActivity, setExpandedActivity] = useState(null);
  
  const activities = [/* your data */];

  const handleTranslate = async (activityId, text, targetLang) => {
    setTranslating(activityId);
    try {
      const response = await apiClient.translateText(text, targetLang);
      setTranslations({
        ...translations,
        [activityId]: {
          text: response.translatedText,
          lang: targetLang,
        },
      });
    } catch (error) {
      console.error("Translation failed:", error);
    } finally {
      setTranslating(null);
    }
  };

  return (
    <ActivitiesList
      activities={activities}
      expandedActivity={expandedActivity}
      onToggleActivity={setExpandedActivity}
      enableTranslation={true}
      onTranslate={handleTranslate}
      translations={translations}
      translating={translating}
    />
  );
}
```

### 3. With Daily Analysis Modal

```tsx
import { useState } from "react";
import ActivitiesList from "@/components/ActivitiesList";
import { api as apiClient } from "@/lib/api";

function ActivitiesWithDailyAnalysis() {
  const [expandedActivity, setExpandedActivity] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [selectedAnalysis, setSelectedAnalysis] = useState(null);
  
  const activities = [/* your data */];

  const handleDailyAnalysisClick = async (activity, tab) => {
    setShowModal(true);
    try {
      const response = await apiClient.getRecordingsDailyByDate(
        activity.metadata?.target_date
      );
      setSelectedAnalysis(response);
    } catch (error) {
      console.error("Failed to load analysis:", error);
    }
  };

  return (
    <>
      <ActivitiesList
        activities={activities}
        expandedActivity={expandedActivity}
        onToggleActivity={setExpandedActivity}
        enableDailyAnalysis={true}
        onDailyAnalysisClick={handleDailyAnalysisClick}
      />
      
      {/* Your modal component here */}
      {showModal && <DailyAnalysisModal data={selectedAnalysis} />}
    </>
  );
}
```

### 4. With Notion UUID Resolution

```tsx
import ActivitiesList from "@/components/ActivitiesList";

function ActivitiesWithNotionMapping() {
  const activities = [/* your data */];
  
  // Map Notion UUIDs to real member names
  const notionUuidMap = {
    "123e4567-e89b-12d3-a456-426614174000": "John Doe",
    "987fcdeb-51a2-43f7-8b6d-9c8e7d6f5e4d": "Jane Smith",
  };

  return (
    <ActivitiesList
      activities={activities}
      notionUuidMap={notionUuidMap}
    />
  );
}
```

### 5. Full-Featured (All Options)

```tsx
import { useState } from "react";
import ActivitiesList from "@/components/ActivitiesList";
import { api as apiClient } from "@/lib/api";

function FullFeaturedActivities() {
  const [translations, setTranslations] = useState({});
  const [translating, setTranslating] = useState(null);
  const [expandedActivity, setExpandedActivity] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [selectedAnalysis, setSelectedAnalysis] = useState(null);
  
  const activities = [/* your data */];
  const notionUuidMap = {/* your mapping */};

  const handleTranslate = async (activityId, text, targetLang) => {
    setTranslating(activityId);
    try {
      const response = await apiClient.translateText(text, targetLang);
      setTranslations({
        ...translations,
        [activityId]: { text: response.translatedText, lang: targetLang },
      });
    } finally {
      setTranslating(null);
    }
  };

  const handleDailyAnalysisClick = async (activity, tab) => {
    setShowModal(true);
    const response = await apiClient.getRecordingsDailyByDate(
      activity.metadata?.target_date
    );
    setSelectedAnalysis(response);
  };

  return (
    <>
      <ActivitiesList
        activities={activities}
        loading={false}
        error={null}
        expandedActivity={expandedActivity}
        onToggleActivity={setExpandedActivity}
        enableTranslation={true}
        onTranslate={handleTranslate}
        translations={translations}
        translating={translating}
        enableDailyAnalysis={true}
        onDailyAnalysisClick={handleDailyAnalysisClick}
        notionUuidMap={notionUuidMap}
      />
      
      {showModal && <DailyAnalysisModal data={selectedAnalysis} />}
    </>
  );
}
```

## Helper Functions

The component uses helper functions from `@/utils/activityHelpers`:

```typescript
import {
  formatTimestamp,
  resolveMemberName,
  getSourceColor,
  getSourceIcon,
  parseRawAnalysis,
  formatSize,
  getTimezoneString,
} from "@/utils/activityHelpers";
```

### Available Helpers

- `formatTimestamp(timestamp: string, formatStr: string): string` - Format dates using date-fns
- `resolveMemberName(name: string, sourceType: string, uuidMap: Record<string, string>): string` - Resolve Notion UUIDs to names
- `getSourceColor(source: string): string` - Get Tailwind color classes for source badges
- `getSourceIcon(source: string): string` - Get emoji icon for source type
- `parseRawAnalysis(data: any): any` - Parse _raw field in daily analysis
- `formatSize(bytes: number): string` - Format file sizes
- `getTimezoneString(): string` - Get current timezone offset

## Styling

The component uses Tailwind CSS classes. Make sure your project has Tailwind configured.

Key classes used:
- `bg-white shadow rounded-lg` - Container styling
- `hover:bg-gray-50` - Interactive states
- `divide-y divide-gray-200` - List dividers
- Source-specific colors (e.g., `bg-purple-100 text-purple-800`)

## Extending the Component

To add support for a new source type:

1. Add the source icon and color in `activityHelpers.ts`:

```typescript
// In getSourceIcon()
const icons: Record<string, string> = {
  // ... existing
  my_new_source: "🆕",
};

// In getSourceColor()
const colors: Record<string, string> = {
  // ... existing
  my_new_source: "bg-teal-100 text-teal-800",
};
```

2. Add a new detail section in `ActivitiesList.tsx`:

```tsx
{/* My New Source Details */}
{activity.source_type === "my_new_source" && (
  <div className="space-y-3">
    {/* Your custom fields here */}
  </div>
)}
```

## Migration Guide

If you're migrating from the old activities page implementation:

### Before (in page.tsx):
```tsx
// 1000+ lines of activity rendering code mixed with page logic
```

### After (in page.tsx):
```tsx
import ActivitiesList from "@/components/ActivitiesList";

// Just pass the data and handlers
<ActivitiesList
  activities={data?.activities || []}
  loading={loading}
  error={error}
  enableTranslation={true}
  onTranslate={handleTranslate}
  // ... other props
/>
```

## Testing

Example test setup:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import ActivitiesList from "./ActivitiesList";

test("renders activities list", () => {
  const activities = [
    {
      id: "1",
      member_name: "John Doe",
      source_type: "github",
      activity_type: "commit",
      timestamp: "2024-01-01T00:00:00Z",
      metadata: { title: "Test commit" },
    },
  ];

  render(<ActivitiesList activities={activities} />);
  
  expect(screen.getByText("John Doe")).toBeInTheDocument();
  expect(screen.getByText("Test commit")).toBeInTheDocument();
});
```

## Troubleshooting

### Activities not expanding
- Make sure you're passing `onToggleActivity` handler
- Or let the component manage state internally (don't pass `expandedActivity`)

### Translation not working
- Ensure `enableTranslation={true}`
- Provide `onTranslate` handler
- Check API endpoint is working

### Notion names showing as UUIDs
- Pass `notionUuidMap` prop with UUID → name mapping
- Ensure UUIDs are lowercase in the map

## Performance Tips

- Use pagination or virtualization for large lists (500+ items)
- Memoize the `activities` array to prevent unnecessary re-renders
- Consider lazy-loading expanded content for complex metadata

## Related Files

- Component: `/frontend/src/components/ActivitiesList.tsx`
- Helpers: `/frontend/src/utils/activityHelpers.ts`
- Examples: `/frontend/src/components/ActivitiesList.example.tsx`
- Types: `/frontend/src/types/index.ts`

## Support

For issues or questions, refer to:
- Project documentation in `/docs`
- GraphQL schema in `/frontend/src/graphql`
- API client in `/frontend/src/lib/api.ts`


