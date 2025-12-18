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
  const [searchInput, setSearchInput] = useState(""); // User input
  const [searchKeyword, setSearchKeyword] = useState(""); // Actual search query
  const [localMemberFilter, setLocalMemberFilter] = useState(memberName || "");
  const [expandedActivity, setExpandedActivity] = useState<string | null>(null);

  // Handle search
  const handleSearch = () => {
    setSearchKeyword(searchInput);
  };

  // Handle Enter key in search input
  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSearch();
    }
  };

  // Toggle activity expansion
  const toggleActivity = (activityId: string) => {
    setExpandedActivity(expandedActivity === activityId ? null : activityId);
  };

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
      projectKey: projectKey || undefined,
      limit,
      offset: 0,
    };

    console.log("🔍 ActivitiesList GraphQL Variables:", JSON.stringify(vars, null, 2));

    return vars;
  }, [sourceFilter, memberName, localMemberFilter, searchKeyword, projectKey, limit]);

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
          <div className="flex gap-4 items-center">
            {/* Search Input with Button */}
            <div className="flex-1 flex gap-2">
              <input
                type="text"
                placeholder="Search by keyword..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <button
                onClick={handleSearch}
                className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors font-medium"
              >
                🔍 Search
              </button>
            </div>

            {/* Source Filter */}
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent min-w-[200px]"
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
                className="px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent min-w-[200px]"
              />
            )}
          </div>

          {/* Active Filters Display */}
          {(memberName || sourceFilter || searchKeyword) && (
            <div className="mt-3 flex flex-wrap gap-2">
              {memberName && (
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                  👤 {memberName}
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
                <div key={activity.id} className="hover:bg-gray-50">
                  {/* Activity Header */}
                  <div
                    className="px-4 py-4 sm:px-6 cursor-pointer"
                    onClick={() => toggleActivity(activity.id)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3">
                          <span className="text-2xl">{sourceConfig.icon}</span>
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${activityConfig.bgColor}`}
                          >
                            {activityConfig.icon} {activityConfig.label}
                          </span>
                          <p className="text-sm font-medium text-gray-900">
                            {activity.memberName}
                          </p>
                        </div>
                        <div className="mt-2 text-sm text-gray-600">
                          {activity.metadata?.title && (
                            <p className="line-clamp-1 font-medium">
                              {activity.metadata.title}
                            </p>
                          )}
                          {activity.metadata?.name && (
                            <p className="line-clamp-1 font-medium">
                              {activity.metadata.name}
                            </p>
                          )}
                          {activity.metadata?.message && (
                            <p className="line-clamp-1">
                              {activity.metadata.message}
                            </p>
                          )}
                          {activity.metadata?.text && (
                            <p className="line-clamp-1">
                              {activity.metadata.text}
                            </p>
                          )}
                          {activity.metadata?.repository && (
                            <p className="line-clamp-1 font-mono text-xs mt-1">
                              📦 {activity.metadata.repository}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center space-x-4">
                        <div className="text-right min-w-[160px]">
                          <p className="text-sm font-medium text-gray-900">
                            {new Date(activity.timestamp).toLocaleDateString(
                              "en-US",
                              {
                                month: "short",
                                day: "numeric",
                                year: "numeric",
                              }
                            )}
                          </p>
                          <p className="text-xs text-gray-600">
                            {new Date(activity.timestamp).toLocaleTimeString(
                              "en-US",
                              {
                                hour: "2-digit",
                                minute: "2-digit",
                                second: "2-digit",
                              }
                            )}
                          </p>
                        </div>
                        <svg
                          className={`h-5 w-5 text-gray-400 transition-transform ${
                            expandedActivity === activity.id
                              ? "transform rotate-180"
                              : ""
                          }`}
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M19 9l-7 7-7-7"
                          />
                        </svg>
                      </div>
                    </div>
                  </div>

                  {/* Expanded Details */}
                  {expandedActivity === activity.id && (
                    <div className="px-4 py-4 sm:px-6 bg-gray-50 border-t border-gray-200">
                      {/* GitHub Details */}
                      {activity.sourceType === "github" && (
                        <div className="space-y-3">
                          <div className="flex items-center space-x-2">
                            {activity.activityType === "commit" && (
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                💾 Commit
                              </span>
                            )}
                            {activity.activityType === "pull_request" && (
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                                🔀 Pull Request
                              </span>
                            )}
                            {activity.activityType === "issue" && (
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                                ⚠️ Issue
                              </span>
                            )}
                            {activity.metadata?.state && (
                              <span
                                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                                  activity.metadata.state === "open"
                                    ? "bg-green-100 text-green-800"
                                    : "bg-gray-100 text-gray-800"
                                }`}
                              >
                                {activity.metadata.state}
                              </span>
                            )}
                          </div>

                          <div>
                            <span className="text-xs font-medium text-gray-500">
                              Time:
                            </span>
                            <p className="text-sm text-gray-900">
                              {new Date(activity.timestamp).toLocaleString(
                                "en-US",
                                {
                                  year: "numeric",
                                  month: "2-digit",
                                  day: "2-digit",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                  second: "2-digit",
                                }
                              )}
                            </p>
                          </div>

                          {activity.metadata?.repository && (
                            <div>
                              <span className="text-xs font-medium text-gray-500">
                                Repository:
                              </span>
                              <p className="text-sm text-gray-900">
                                tokamak-network/{activity.metadata.repository}
                              </p>
                            </div>
                          )}

                          {activity.metadata?.sha && (
                            <div>
                              <span className="text-xs font-medium text-gray-500">
                                Commit SHA:
                              </span>
                              <p className="text-sm font-mono text-gray-900">
                                {activity.metadata.sha.substring(0, 7)}
                              </p>
                            </div>
                          )}

                          {activity.metadata?.number && (
                            <div>
                              <span className="text-xs font-medium text-gray-500">
                                {activity.activityType === "pull_request"
                                  ? "PR Number:"
                                  : "Issue Number:"}
                              </span>
                              <p className="text-sm text-gray-900">
                                #{activity.metadata.number}
                              </p>
                            </div>
                          )}

                          {(activity.metadata?.additions !== undefined ||
                            activity.metadata?.deletions !== undefined) && (
                            <div className="flex items-center space-x-4">
                              <div className="flex items-center space-x-1">
                                <span className="text-xs font-medium text-gray-500">
                                  Changes:
                                </span>
                                <span className="text-xs font-medium text-green-600">
                                  +{activity.metadata.additions || 0}
                                </span>
                                <span className="text-xs font-medium text-red-600">
                                  -{activity.metadata.deletions || 0}
                                </span>
                              </div>
                            </div>
                          )}

                          {activity.metadata?.url && (
                            <div className="mt-3">
                              <a
                                href={activity.metadata.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center px-3 py-1.5 bg-gray-800 text-white text-sm rounded hover:bg-gray-700 transition-colors"
                              >
                                🔗 View on GitHub →
                              </a>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Slack Details */}
                      {activity.sourceType === "slack" && (
                        <div className="space-y-3">
                          <div className="flex items-center space-x-2">
                            {activity.activityType === "message" && (
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                                💬 Message
                              </span>
                            )}
                          </div>

                          <div>
                            <span className="text-xs font-medium text-gray-500">
                              Time:
                            </span>
                            <p className="text-sm text-gray-900">
                              {new Date(activity.timestamp).toLocaleString(
                                "en-US",
                                {
                                  year: "numeric",
                                  month: "2-digit",
                                  day: "2-digit",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                  second: "2-digit",
                                }
                              )}
                            </p>
                          </div>

                          {activity.metadata?.channel_name && (
                            <div>
                              <span className="text-xs font-medium text-gray-500">
                                Channel:
                              </span>
                              <p className="text-sm text-gray-900">
                                #{activity.metadata.channel_name}
                              </p>
                            </div>
                          )}

                          {activity.metadata?.text && (
                            <div>
                              <span className="text-xs font-medium text-gray-500">
                                Message:
                              </span>
                              <p className="text-sm text-gray-700 whitespace-pre-wrap bg-white p-3 rounded border border-gray-200 mt-1">
                                {activity.metadata.text}
                              </p>
                            </div>
                          )}

                          {activity.metadata?.url && (
                            <div className="mt-3">
                              <a
                                href={activity.metadata.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center px-3 py-1.5 bg-purple-600 text-white text-sm rounded hover:bg-purple-700 transition-colors"
                              >
                                🔗 View on Slack →
                              </a>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Notion Details */}
                      {activity.sourceType === "notion" && (
                        <div className="space-y-3">
                          <div>
                            <span className="text-xs font-medium text-gray-500">
                              Time:
                            </span>
                            <p className="text-sm text-gray-900">
                              {new Date(activity.timestamp).toLocaleString(
                                "en-US",
                                {
                                  year: "numeric",
                                  month: "2-digit",
                                  day: "2-digit",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                  second: "2-digit",
                                }
                              )}
                            </p>
                          </div>

                          {activity.metadata?.title && (
                            <div>
                              <span className="text-xs font-medium text-gray-500">
                                Title:
                              </span>
                              <p className="text-sm text-gray-900">
                                {activity.metadata.title}
                              </p>
                            </div>
                          )}

                          {activity.metadata?.url && (
                            <div className="mt-3">
                              <a
                                href={activity.metadata.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
                              >
                                🔗 View on Notion →
                              </a>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Google Drive Details */}
                      {(activity.sourceType === "drive" ||
                        activity.sourceType === "google_drive") && (
                        <div className="space-y-3">
                          <div>
                            <span className="text-xs font-medium text-gray-500">
                              Time:
                            </span>
                            <p className="text-sm text-gray-900">
                              {new Date(activity.timestamp).toLocaleString(
                                "en-US",
                                {
                                  year: "numeric",
                                  month: "2-digit",
                                  day: "2-digit",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                  second: "2-digit",
                                }
                              )}
                            </p>
                          </div>

                          {activity.metadata?.primary_action && (
                            <div>
                              <span className="text-xs font-medium text-gray-500">
                                Action:
                              </span>
                              <p className="text-sm text-gray-900">
                                {activity.metadata.primary_action}
                              </p>
                            </div>
                          )}

                          {activity.metadata?.target_name && (
                            <div>
                              <span className="text-xs font-medium text-gray-500">
                                File:
                              </span>
                              <p className="text-sm text-gray-900">
                                {activity.metadata.target_name}
                              </p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Recordings Details */}
                      {activity.sourceType === "recordings" && (
                        <div className="space-y-3">
                          <div>
                            <span className="text-xs font-medium text-gray-500">
                              Time:
                            </span>
                            <p className="text-sm text-gray-900">
                              {new Date(activity.timestamp).toLocaleString(
                                "en-US",
                                {
                                  year: "numeric",
                                  month: "2-digit",
                                  day: "2-digit",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                  second: "2-digit",
                                }
                              )}
                            </p>
                          </div>

                          {activity.metadata?.name && (
                            <div>
                              <span className="text-xs font-medium text-gray-500">
                                Recording:
                              </span>
                              <p className="text-sm text-gray-900">
                                {activity.metadata.name}
                              </p>
                            </div>
                          )}

                          {activity.metadata?.participants && (
                            <div>
                              <span className="text-xs font-medium text-gray-500">
                                Participants:
                              </span>
                              <p className="text-sm text-gray-900">
                                {Array.isArray(activity.metadata.participants)
                                  ? activity.metadata.participants.join(", ")
                                  : activity.metadata.participants}
                              </p>
                            </div>
                          )}

                          {activity.metadata?.size && (
                            <div>
                              <span className="text-xs font-medium text-gray-500">
                                Size:
                              </span>
                              <p className="text-sm text-gray-900">
                                {(
                                  activity.metadata.size /
                                  (1024 * 1024)
                                ).toFixed(2)}{" "}
                                MB
                              </p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Recordings Daily (Analysis) Details */}
                      {activity.sourceType === "recordings_daily" && (
                        <div className="space-y-3">
                          <div>
                            <span className="text-xs font-medium text-gray-500">
                              Date:
                            </span>
                            <p className="text-sm text-gray-900">
                              {activity.metadata?.target_date ||
                                new Date(activity.timestamp).toLocaleDateString()}
                            </p>
                          </div>

                          {activity.metadata?.summary && (
                            <div>
                              <span className="text-xs font-medium text-gray-500">
                                Summary:
                              </span>
                              <div className="text-sm text-gray-700 bg-white p-3 rounded border border-gray-200 mt-1">
                                {typeof activity.metadata.summary === "string"
                                  ? activity.metadata.summary
                                  : JSON.stringify(activity.metadata.summary)}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
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

