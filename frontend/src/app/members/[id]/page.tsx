"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { api as apiClient } from "@/lib/api";
import {
  ArrowLeftIcon,
  EnvelopeIcon,
  BriefcaseIcon,
  FolderIcon,
  SparklesIcon,
} from "@heroicons/react/24/outline";
import {
  ChartBarIcon,
  ClockIcon,
  CodeBracketIcon,
  ChatBubbleLeftIcon,
  DocumentTextIcon,
  CloudIcon,
} from "@heroicons/react/24/solid";

interface MemberIdentifiers {
  email?: string;
  github?: string;
  slack?: string;
  notion?: string;
}

interface ActivityStats {
  total_activities: number;
  by_source: {
    [key: string]: {
      total: number;
      [key: string]: number;
    };
  };
  by_type: {
    [key: string]: number;
  };
  recent_activities: Array<{
    source: string;
    type: string;
    timestamp: string;
    description: string;
    repository?: string;
  }>;
}

interface MemberDetail {
  id: string;
  name: string;
  email: string;
  role?: string;
  project?: string;
  identifiers: MemberIdentifiers;
  activity_stats: ActivityStats;
  created_at?: string;
  updated_at?: string;
}

interface Activity {
  id: string;
  source_type: string;
  activity_type: string;
  timestamp: string;
  metadata: {
    [key: string]: any;
  };
}

interface ActivityGroup {
  source: string;
  activities: Activity[];
}

export default function MemberDetailPage() {
  const params = useParams();
  const router = useRouter();
  const memberId = params.id as string;
  
  const [member, setMember] = useState<MemberDetail | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [groupedActivities, setGroupedActivities] = useState<ActivityGroup[]>([]);
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activitiesLoading, setActivitiesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [showSummary, setShowSummary] = useState(false);

  useEffect(() => {
    loadMemberDetail();
    loadActivities();
  }, [memberId]);

  useEffect(() => {
    if (activities.length > 0) {
      groupActivitiesBySource();
    }
  }, [activities, selectedSource]);

  const loadMemberDetail = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.getMemberDetailById(memberId);
      setMember(data);
    } catch (err: any) {
      console.error("Error loading member detail:", err);
      setError(err.response?.data?.detail || err.message || "Failed to load member details");
    } finally {
      setLoading(false);
    }
  };

  const loadActivities = async (source?: string) => {
    try {
      setActivitiesLoading(true);
      // Map frontend source names to backend source_type
      let backendSourceType = source;
      if (source === "drive") {
        backendSourceType = "google_drive";
      }
      
      const data = await apiClient.getMemberActivities(memberId, {
        source_type: backendSourceType || undefined,
        limit: 200,
      });
      setActivities(data.activities || []);
    } catch (err: any) {
      console.error("Error loading activities:", err);
      setActivities([]);
    } finally {
      setActivitiesLoading(false);
    }
  };

  const groupActivitiesBySource = () => {
    const filtered = selectedSource
      ? activities.filter((a) => a.source_type === selectedSource)
      : activities;

    const grouped: { [key: string]: Activity[] } = {};
    filtered.forEach((activity) => {
      const source = activity.source_type;
      if (!grouped[source]) {
        grouped[source] = [];
      }
      grouped[source].push(activity);
    });

    const result: ActivityGroup[] = Object.entries(grouped).map(([source, activities]) => ({
      source,
      activities: activities.sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      ),
    }));

    setGroupedActivities(result);
  };

  const handleGenerateSummary = async () => {
    try {
      setSummaryLoading(true);
      setShowSummary(true);
      const data = await apiClient.generateMemberSummary(memberId);
      setSummary(data.summary || "No summary available.");
    } catch (err: any) {
      console.error("Error generating summary:", err);
      setSummary("Error generating summary. Please try again.");
    } finally {
      setSummaryLoading(false);
    }
  };

  const getSourceIcon = (source: string) => {
    switch (source) {
      case "github":
        return <CodeBracketIcon className="h-5 w-5" />;
      case "slack":
        return <ChatBubbleLeftIcon className="h-5 w-5" />;
      case "notion":
        return <DocumentTextIcon className="h-5 w-5" />;
      case "google_drive":
      case "drive":
        return <CloudIcon className="h-5 w-5" />;
      default:
        return <ChartBarIcon className="h-5 w-5" />;
    }
  };

  const getSourceColor = (source: string) => {
    switch (source) {
      case "github":
        return "bg-gray-100 text-gray-800 border-gray-300";
      case "slack":
        return "bg-purple-100 text-purple-800 border-purple-300";
      case "notion":
        return "bg-blue-100 text-blue-800 border-blue-300";
      case "google_drive":
      case "drive":
        return "bg-green-100 text-green-800 border-green-300";
      default:
        return "bg-gray-100 text-gray-800 border-gray-300";
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return "N/A";
    const date = new Date(dateString);
    return date.toLocaleString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatActivityDescription = (activity: Activity): string => {
    const { source_type, activity_type, metadata } = activity;
    
    if (source_type === "github") {
      if (activity_type === "commit") {
        return metadata.message || "Commit";
      } else if (activity_type === "pull_request") {
        return `PR #${metadata.number}: ${metadata.title || "Pull Request"}`;
      } else if (activity_type === "issue") {
        return `Issue #${metadata.number}: ${metadata.title || "Issue"}`;
      }
    } else if (source_type === "slack") {
      return metadata.text || "Message";
    } else if (source_type === "notion") {
      return metadata.title || "Page";
    } else if (source_type === "google_drive" || source_type === "drive") {
      return `${metadata.primary_action || "Activity"} on ${metadata.target_name || "file"}`;
    }
    
    return `${activity_type} activity`;
  };

  const getActivityUrl = (activity: Activity): string | null => {
    const { source_type, metadata } = activity;
    
    if (source_type === "github") {
      return metadata.url || null;
    } else if (source_type === "slack") {
      return metadata.permalink || null;
    } else if (source_type === "notion") {
      return metadata.url || null;
    }
    
    return null;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading member details...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !member) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-8">
            <h2 className="text-xl font-bold text-red-800 mb-2">Error</h2>
            <p className="text-red-600">{error || "Member not found"}</p>
            <button
              onClick={() => router.push("/members")}
              className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
            >
              Back to Members
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => router.push("/members")}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeftIcon className="h-5 w-5" />
            Back to Members
          </button>
          <h1 className="text-3xl font-bold text-gray-900">{member.name}</h1>
        </div>

        {/* Member Info Card */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Profile Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex items-center gap-3">
              <EnvelopeIcon className="h-5 w-5 text-gray-400" />
              <div>
                <p className="text-sm text-gray-500">Email</p>
                <p className="text-gray-900">{member.email}</p>
              </div>
            </div>

            {member.role && (
              <div className="flex items-center gap-3">
                <BriefcaseIcon className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Role</p>
                  <p className="text-gray-900">{member.role}</p>
                </div>
              </div>
            )}

            {member.project && (
              <div className="flex items-center gap-3">
                <FolderIcon className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Project</p>
                  <p className="text-gray-900">{member.project}</p>
                </div>
              </div>
            )}

            {member.identifiers.github && (
              <div className="flex items-center gap-3">
                <CodeBracketIcon className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">GitHub</p>
                  <a
                    href={`https://github.com/${member.identifiers.github}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800"
                  >
                    {member.identifiers.github}
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* AI Summary Section */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              <SparklesIcon className="h-6 w-6 text-yellow-500" />
              Activity Summary
            </h2>
            <button
              onClick={handleGenerateSummary}
              disabled={summaryLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {summaryLoading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  Generating...
                </>
              ) : (
                <>
                  <SparklesIcon className="h-4 w-4" />
                  Generate Summary
                </>
              )}
            </button>
          </div>
          {showSummary && (
            <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
              {summaryLoading ? (
                <div className="flex items-center gap-2 text-gray-600">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                  <span>Generating summary with AI...</span>
                </div>
              ) : summary ? (
                <div className="prose max-w-none">
                  <p className="text-gray-700 whitespace-pre-wrap">{summary}</p>
                </div>
              ) : (
                <p className="text-gray-500">Click "Generate Summary" to analyze activities with AI.</p>
              )}
            </div>
          )}
        </div>

        {/* Activity Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
          {/* Total Activities */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Total Activities</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">
                  {member.activity_stats.total_activities}
                </p>
              </div>
              <ChartBarIcon className="h-10 w-10 text-blue-500" />
            </div>
          </div>

          {/* GitHub Activities */}
          {member.activity_stats.by_source.github && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">GitHub</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {member.activity_stats.by_source.github.total}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {member.activity_stats.by_source.github.commits || 0} commits,{" "}
                    {member.activity_stats.by_source.github.pull_requests || 0} PRs
                  </p>
                </div>
                <CodeBracketIcon className="h-10 w-10 text-gray-500" />
              </div>
            </div>
          )}

          {/* Slack Activities */}
          {member.activity_stats.by_source.slack && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Slack</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {member.activity_stats.by_source.slack.total}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {member.activity_stats.by_source.slack.messages || 0} messages
                  </p>
                </div>
                <ChatBubbleLeftIcon className="h-10 w-10 text-purple-500" />
              </div>
            </div>
          )}

          {/* Other Sources */}
          {(member.activity_stats.by_source.notion || member.activity_stats.by_source.drive) && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Other Sources</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {(member.activity_stats.by_source.notion?.total || 0) +
                      (member.activity_stats.by_source.drive?.total || 0)}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">Notion, Drive</p>
                </div>
                <DocumentTextIcon className="h-10 w-10 text-blue-500" />
              </div>
            </div>
          )}
        </div>

        {/* Source Filter */}
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-gray-700">Filter by source:</span>
            <button
              onClick={() => {
                setSelectedSource(null);
                loadActivities();
              }}
              className={`px-3 py-1 rounded-lg text-sm ${
                selectedSource === null
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              All
            </button>
            {Object.keys(member.activity_stats.by_source).map((source) => {
              // Map backend source names to display names
              const displayName = source === "google_drive" ? "drive" : source;
              return (
                <button
                  key={source}
                  onClick={() => {
                    setSelectedSource(source);
                    loadActivities(source);
                  }}
                  className={`px-3 py-1 rounded-lg text-sm capitalize ${
                    selectedSource === source
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}
                >
                  {displayName}
                </button>
              );
            })}
          </div>
        </div>

        {/* Activities by Source */}
        {activitiesLoading ? (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading activities...</p>
          </div>
        ) : groupedActivities.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <p className="text-gray-500">No activities found for this member.</p>
          </div>
        ) : (
          <div className="space-y-6">
            {groupedActivities.map((group) => (
              <div key={group.source} className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                  <div className={`p-2 rounded-lg ${getSourceColor(group.source)}`}>
                    {getSourceIcon(group.source)}
                  </div>
                  <span className="capitalize">{group.source}</span>
                  <span className="text-sm font-normal text-gray-500">
                    ({group.activities.length} activities)
                  </span>
                </h3>
                <div className="space-y-3">
                  {group.activities.map((activity) => {
                    const url = getActivityUrl(activity);
                    const description = formatActivityDescription(activity);
                    return (
                      <div
                        key={activity.id}
                        className="border-l-4 border-gray-200 pl-4 py-2 hover:border-blue-500 transition-colors"
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-3 flex-1">
                            <div className={`p-2 rounded-lg ${getSourceColor(activity.source_type)}`}>
                              {getSourceIcon(activity.source_type)}
                            </div>
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-sm font-medium text-gray-700 capitalize">
                                  {activity.activity_type.replace("_", " ")}
                                </span>
                                {activity.metadata.repository && (
                                  <>
                                    <span className="text-sm text-gray-500">•</span>
                                    <span className="text-sm text-gray-600 font-mono">
                                      {activity.metadata.repository}
                                    </span>
                                  </>
                                )}
                                {activity.source_type === "github" &&
                                  activity.activity_type === "commit" &&
                                  activity.metadata.sha && (
                                    <>
                                      <span className="text-sm text-gray-500">•</span>
                                      <span className="text-sm text-gray-600 font-mono">
                                        {activity.metadata.sha.substring(0, 7)}
                                      </span>
                                    </>
                                  )}
                                {activity.source_type === "github" &&
                                  (activity.activity_type === "pull_request" ||
                                    activity.activity_type === "issue") &&
                                  activity.metadata.number && (
                                    <>
                                      <span className="text-sm text-gray-500">•</span>
                                      <span className="text-sm text-gray-600 font-mono">
                                        #{activity.metadata.number}
                                      </span>
                                    </>
                                  )}
                              </div>
                              {url ? (
                                <a
                                  href={url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
                                >
                                  {description}
                                </a>
                              ) : (
                                <p className="text-sm text-gray-600">{description}</p>
                              )}
                              {activity.source_type === "github" &&
                                activity.activity_type === "commit" &&
                                (activity.metadata.additions > 0 || activity.metadata.deletions > 0) && (
                                  <p className="text-xs text-gray-500 mt-1">
                                    +{activity.metadata.additions} / -{activity.metadata.deletions} lines
                                  </p>
                                )}
                              {activity.source_type === "slack" &&
                                activity.metadata.channel_name && (
                                  <p className="text-xs text-gray-500 mt-1">
                                    Channel: {activity.metadata.channel_name}
                                  </p>
                                )}
                            </div>
                          </div>
                          <div className="text-right ml-4">
                            <p className="text-xs text-gray-500">{formatDate(activity.timestamp)}</p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Activity Breakdown by Source */}
        <div className="bg-white rounded-lg shadow p-6 mt-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Activity Breakdown</h2>
          <div className="space-y-4">
            {Object.entries(member.activity_stats.by_source).map(([source, stats]) => {
              const percentage =
                member.activity_stats.total_activities > 0
                  ? (stats.total / member.activity_stats.total_activities) * 100
                  : 0;
              return (
                <div key={source}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-700 capitalize flex items-center gap-2">
                      {getSourceIcon(source)}
                      {source}
                    </span>
                    <span className="text-sm text-gray-600">
                      {stats.total} activities ({percentage.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${
                        source === "github"
                          ? "bg-gray-600"
                          : source === "slack"
                          ? "bg-purple-600"
                          : source === "notion"
                          ? "bg-blue-600"
                          : "bg-green-600"
                      }`}
                      style={{ width: `${percentage}%` }}
                    ></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
