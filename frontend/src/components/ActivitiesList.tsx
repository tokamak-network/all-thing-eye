"use client";

/**
 * ActivitiesList - Reusable Activities Component
 * 
 * Displays filtered activities from various sources (GitHub, Slack, Notion, Drive, Recordings).
 * Can be used in:
 * - /activities page (all activities with full filters)
 * - /members/[id] page (activities for specific member)
 * - /projects/[key] page (activities for specific project)
 * 
 * Props:
 * - memberName?: Filter by specific member
 * - projectKey?: Filter by specific project
 * - initialSource?: Initial source filter
 * - showFilters?: Show filter controls (default: true)
 * - limit?: Number of items to load (default: 500)
 */

import { useState, useMemo } from "react";
import { useActivities } from "@/graphql/hooks";
import { Activity } from "@/graphql/types";

// Activity type display configuration
const activityTypeConfig: Record<
  string,
  { icon: string; bgColor: string; label: string }
> = {
  commit: { icon: "💾", bgColor: "bg-blue-100", label: "Commit" },
  pull_request: { icon: "🔀", bgColor: "bg-purple-100", label: "Pull Request" },
  issue: { icon: "🐛", bgColor: "bg-red-100", label: "Issue" },
  slack_message: { icon: "💬", bgColor: "bg-green-100", label: "Message" },
  slack_reaction: { icon: "👍", bgColor: "bg-yellow-100", label: "Reaction" },
  notion_page: { icon: "📄", bgColor: "bg-gray-100", label: "Page" },
  drive_activity: { icon: "📁", bgColor: "bg-indigo-100", label: "Drive" },
  meeting_recording: { icon: "🎥", bgColor: "bg-pink-100", label: "Recording" },
  daily_analysis: { icon: "📊", bgColor: "bg-orange-100", label: "Analysis" },
};

// Source type configuration
const sourceTypeConfig: Record<
  string,
  { icon: string; color: string; label: string }
> = {
  github: { icon: "🐙", color: "text-gray-900", label: "GitHub" },
  slack: { icon: "💬", color: "text-green-600", label: "Slack" },
  notion: { icon: "📝", color: "text-blue-600", label: "Notion" },
  drive: { icon: "📁", color: "text-yellow-600", label: "Drive" },
  recordings: { icon: "🎥", color: "text-pink-600", label: "Recordings" },
  recordings_daily: {
    icon: "📊",
    color: "text-orange-600",
    label: "Analysis",
  },
};

interface ActivitiesListProps {
  memberName?: string;
  projectKey?: string;
  initialSource?: string;
  showFilters?: boolean;
  limit?: number;
}

export default function ActivitiesList({
  memberName,
  projectKey,
  initialSource = "",
  showFilters = true,
  limit = 500,
}: ActivitiesListProps) {
  // Filter states
  const [sourceFilter, setSourceFilter] = useState(initialSource);
  const [searchKeyword, setSearchKeyword] = useState("");
  const [localMemberFilter, setLocalMemberFilter] = useState(memberName || "");
  const [localProjectFilter, setLocalProjectFilter] = useState(projectKey || "");

  // Normalize source type for GraphQL
  const normalizeSourceType = (source: string) => {
    const mapping: Record<string, string> = {
      github: "GITHUB",
      slack: "SLACK",
      notion: "NOTION",
      drive: "DRIVE",
      recordings: "RECORDINGS",
      recordings_daily: "RECORDINGS_DAILY",
      analysis: "RECORDINGS_DAILY",
    };
    return source ? mapping[source.toLowerCase()] || source.toUpperCase() : undefined;
  };

  // Build GraphQL variables
  const activitiesVariables = useMemo(() => {
    const vars: any = {
      source: normalizeSourceType(sourceFilter),
      memberName: memberName || (localMemberFilter !== "" ? localMemberFilter : undefined),
      keyword: searchKeyword !== "" ? searchKeyword : undefined,
      projectKey: projectKey || (localProjectFilter !== "" ? localProjectFilter : undefined),
      limit,
      offset: 0,
    };

    console.log("🔍 ActivitiesList GraphQL Variables:", JSON.stringify(vars, null, 2));

    return vars;
  }, [sourceFilter, memberName, localMemberFilter, searchKeyword, projectKey, localProjectFilter, limit]);

  // Fetch activities
  const { data, loading, error } = useActivities(activitiesVariables);

  const activities = data?.activities || [];

  // Format timestamp
  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  };

  // Get activity config
  const getActivityConfig = (activity: Activity) => {
    return (
      activityTypeConfig[activity.activityType] || {
        icon: "📌",
        bgColor: "bg-gray-100",
        label: activity.activityType,
      }
    );
  };

  // Get source config
  const getSourceConfig = (sourceType: string) => {
    const normalized = sourceType.toLowerCase();
    return (
      sourceTypeConfig[normalized] || {
        icon: "📌",
        color: "text-gray-600",
        label: sourceType,
      }
    );
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      {showFilters && (
        <div className="bg-white rounded-lg shadow p-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Search */}
            <div className="md:col-span-2">
              <input
                type="text"
                placeholder="Search by keyword..."
                value={searchKeyword}
                onChange={(e) => setSearchKeyword(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* Source Filter */}
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">📂 All Sources</option>
              <option value="github">🐙 GitHub</option>
              <option value="slack">💬 Slack</option>
              <option value="notion">📝 Notion</option>
              <option value="drive">📁 Drive</option>
              <option value="recordings">🎥 Recordings</option>
              <option value="analysis">📊 Analysis</option>
            </select>

            {/* Member Filter (only if not fixed by props) */}
            {!memberName && (
              <input
                type="text"
                placeholder="Filter by member..."
                value={localMemberFilter}
                onChange={(e) => setLocalMemberFilter(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            )}

            {/* Project Filter (only if not fixed by props) */}
            {!projectKey && (
              <input
                type="text"
                placeholder="Filter by project..."
                value={localProjectFilter}
                onChange={(e) => setLocalProjectFilter(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            )}
          </div>

          {/* Active Filters Display */}
          {(memberName || projectKey || sourceFilter || searchKeyword) && (
            <div className="mt-3 flex flex-wrap gap-2">
              {memberName && (
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                  👤 {memberName}
                </span>
              )}
              {projectKey && (
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-sm">
                  📁 {projectKey}
                </span>
              )}
              {sourceFilter && (
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm">
                  {getSourceConfig(sourceFilter).icon} {getSourceConfig(sourceFilter).label}
                </span>
              )}
              {searchKeyword && (
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full text-sm">
                  🔍 "{searchKeyword}"
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Activities List */}
      <div className="bg-white rounded-lg shadow">
        {loading ? (
          <div className="p-8 text-center text-gray-500">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
            <p className="mt-4">Loading activities...</p>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-red-600">
            <p>Error loading activities: {error.message}</p>
          </div>
        ) : activities.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <p className="text-lg">📭 No activities found</p>
            <p className="text-sm mt-2">Try adjusting your filters</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {activities.map((activity) => {
              const activityConfig = getActivityConfig(activity);
              const sourceConfig = getSourceConfig(activity.sourceType);

              return (
                <div
                  key={activity.id}
                  className="p-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      {/* Header */}
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`text-2xl ${sourceConfig.color}`}>
                          {sourceConfig.icon}
                        </span>
                        <span
                          className={`px-2 py-1 rounded text-xs font-medium ${activityConfig.bgColor}`}
                        >
                          {activityConfig.icon} {activityConfig.label}
                        </span>
                        <span className="text-sm font-medium text-gray-900">
                          {activity.memberName}
                        </span>
                      </div>

                      {/* Content */}
                      <div className="text-sm text-gray-700">
                        {activity.metadata?.title ||
                          activity.metadata?.name ||
                          activity.metadata?.message ||
                          activity.metadata?.text ||
                          activity.metadata?.file_name ||
                          "No title"}
                      </div>

                      {/* Metadata */}
                      {activity.metadata && (
                        <div className="mt-2 text-xs text-gray-500 space-y-1">
                          {activity.metadata.repository && (
                            <div>📦 {activity.metadata.repository}</div>
                          )}
                          {activity.metadata.channel_name && (
                            <div>💬 #{activity.metadata.channel_name}</div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Timestamp */}
                    <div className="ml-4 text-xs text-gray-500 text-right whitespace-nowrap">
                      {formatTimestamp(activity.timestamp)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Results count */}
      {!loading && !error && activities.length > 0 && (
        <div className="text-center text-sm text-gray-500">
          Showing {activities.length} {activities.length === 1 ? "activity" : "activities"}
        </div>
      )}
    </div>
  );
}

