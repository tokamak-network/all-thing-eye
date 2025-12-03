"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { format } from "date-fns";
import { api as apiClient } from "@/lib/api";
import {
  ArrowLeftIcon,
  EnvelopeIcon,
  BriefcaseIcon,
  FolderIcon,
  SparklesIcon,
} from "@heroicons/react/24/outline";
import DateRangePicker from "@/components/DateRangePicker";

// Helper function to safely format timestamps
function formatTimestamp(timestamp: string, formatStr: string): string {
  if (!timestamp) return "N/A";
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return "N/A";
  return format(date, formatStr);
}

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

export default function MemberDetailPage() {
  const params = useParams();
  const router = useRouter();
  const memberId = params.id as string;
  
  const [member, setMember] = useState<MemberDetail | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [selectedSource, setSelectedSource] = useState<string>("");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [activitiesLoading, setActivitiesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [showSummary, setShowSummary] = useState(false);
  const [expandedActivity, setExpandedActivity] = useState<string | null>(null);
  
  // Translation states
  const [summaryTranslation, setSummaryTranslation] = useState<{
    text: string;
    lang: string;
  } | null>(null);
  const [translatingSummary, setTranslatingSummary] = useState(false);
  
  // Pagination states
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  useEffect(() => {
    loadMemberDetail();
  }, [memberId]);

  useEffect(() => {
    loadActivities();
  }, [memberId, selectedSource, startDate, endDate]);

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

  const loadActivities = async () => {
    try {
      setActivitiesLoading(true);
      // Map frontend source names to backend source_type
      let backendSourceType = selectedSource || undefined;
      if (selectedSource === "drive") {
        backendSourceType = "google_drive";
      }
      
      // Load enough data for pagination
      const loadLimit = Math.max(itemsPerPage * 10, 500);
      
      const data = await apiClient.getMemberActivities(memberId, {
        source_type: backendSourceType,
        limit: loadLimit,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      });
      setActivities(data.activities || []);
      setCurrentPage(1); // Reset to first page when filter changes
    } catch (err: any) {
      console.error("Error loading activities:", err);
      setActivities([]);
    } finally {
      setActivitiesLoading(false);
    }
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

  const toggleActivity = (activityId: string) => {
    setExpandedActivity(expandedActivity === activityId ? null : activityId);
  };

  // Translate summary text
  const handleTranslateSummary = async (targetLang: string) => {
    if (!summary || translatingSummary) return;

    // If already translated to this language, toggle back to original
    if (summaryTranslation?.lang === targetLang) {
      setSummaryTranslation(null);
      return;
    }

    setTranslatingSummary(true);
    try {
      const result = await apiClient.translateText(summary, targetLang);
      setSummaryTranslation({
        text: result.translated_text,
        lang: targetLang,
      });
    } catch (err: any) {
      console.error("Translation error:", err);
      alert("Translation failed. Please try again.");
    } finally {
      setTranslatingSummary(false);
    }
  };

  const getSourceColor = (source: string) => {
    const colors: Record<string, string> = {
      github: "bg-gray-100 text-gray-800",
      slack: "bg-purple-100 text-purple-800",
      notion: "bg-blue-100 text-blue-800",
      drive: "bg-green-100 text-green-800",
      google_drive: "bg-green-100 text-green-800",
      recordings: "bg-red-100 text-red-800",
    };
    return colors[source] || "bg-gray-100 text-gray-800";
  };

  const getSourceIcon = (source: string) => {
    const icons: Record<string, string> = {
      github: "🐙",
      slack: "💬",
      notion: "📝",
      drive: "📁",
      google_drive: "📁",
      recordings: "📹",
    };
    return icons[source] || "📋";
  };

  // Filter activities by source
  const filteredActivities = selectedSource
    ? activities.filter((a) => {
        const source = a.source_type === "google_drive" ? "drive" : a.source_type;
        return source === selectedSource;
      })
    : activities;

  // Paginate filtered activities
  const totalItems = filteredActivities.length;
  const totalPages = Math.ceil(totalItems / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedActivities = filteredActivities.slice(startIndex, endIndex);

  // Get all available sources from activities
  const availableSources = Array.from(
    new Set(activities.map((a) => a.source_type === "google_drive" ? "drive" : a.source_type))
  ).sort();

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
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <button
            onClick={() => router.push("/members")}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeftIcon className="h-5 w-5" />
            Back to Members
          </button>
          <h1 className="text-3xl font-bold text-gray-900">{member.name}</h1>
          <p className="mt-2 text-gray-600">
            {totalItems.toLocaleString()} activities recorded across all sources
          </p>
        </div>

        {/* Member Info Card */}
        <div className="bg-white rounded-lg shadow p-6">
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
                <span className="text-2xl">🐙</span>
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
        <div className="bg-white rounded-lg shadow p-6">
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
                  {/* Translation buttons */}
                  <div className="flex items-center gap-2 mb-3 pb-3 border-b border-gray-200">
                    <span className="text-xs text-gray-500">Translate:</span>
                    <button
                      onClick={() => handleTranslateSummary("en")}
                      disabled={translatingSummary}
                      className={`text-xs px-2 py-0.5 rounded transition-colors ${
                        summaryTranslation?.lang === "en"
                          ? "bg-blue-600 text-white"
                          : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                      } ${
                        translatingSummary
                          ? "opacity-50 cursor-wait"
                          : ""
                      }`}
                    >
                      EN
                    </button>
                    <button
                      onClick={() => handleTranslateSummary("ko")}
                      disabled={translatingSummary}
                      className={`text-xs px-2 py-0.5 rounded transition-colors ${
                        summaryTranslation?.lang === "ko"
                          ? "bg-blue-600 text-white"
                          : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                      } ${
                        translatingSummary
                          ? "opacity-50 cursor-wait"
                          : ""
                      }`}
                    >
                      KR
                    </button>
                    {translatingSummary && (
                      <div className="flex items-center gap-1 text-xs text-gray-500">
                        <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-gray-400"></div>
                        <span>Translating...</span>
                      </div>
                    )}
                  </div>
                  {/* Summary content */}
                  <p className="text-gray-700 whitespace-pre-wrap">
                    {summaryTranslation?.text || summary}
                  </p>
                  {summaryTranslation && (
                    <p className="text-xs text-gray-400 mt-2">
                      🌐 Translated to{" "}
                      {summaryTranslation.lang === "ko"
                        ? "Korean"
                        : "English"}
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-gray-500">Click "Generate Summary" to analyze activities with AI.</p>
              )}
            </div>
          )}
        </div>

        {/* Activity Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {/* Total Activities */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Total Activities</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">
                  {member.activity_stats.total_activities}
                </p>
              </div>
              <span className="text-4xl">📊</span>
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
                <span className="text-4xl">🐙</span>
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
                <span className="text-4xl">💬</span>
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
                <span className="text-4xl">📝</span>
              </div>
            </div>
          )}
        </div>

        {/* Date Range Filter */}
        <DateRangePicker
          startDate={startDate}
          endDate={endDate}
          onDateChange={(start, end) => {
            setStartDate(start);
            setEndDate(end);
            setCurrentPage(1); // Reset to first page when date changes
          }}
          className="mb-4"
        />

        {/* Filters and Pagination Controls */}
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-medium text-gray-700">Filter by source:</span>
              <select
                value={selectedSource}
                onChange={(e) => {
                  setSelectedSource(e.target.value);
                  setCurrentPage(1);
                }}
                className="block rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              >
                <option value="">All Sources</option>
                <option value="github">🐙 GitHub</option>
                <option value="slack">💬 Slack</option>
                <option value="notion">📝 Notion</option>
                <option value="drive">📁 Google Drive</option>
                <option value="recordings">📹 Recordings</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-700">Items per page:</label>
              <select
                value={itemsPerPage}
                onChange={(e) => {
                  setItemsPerPage(Number(e.target.value));
                  setCurrentPage(1);
                }}
                className="block rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>
          </div>
        </div>

        {/* Activities List */}
        {activitiesLoading ? (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading activities...</p>
          </div>
        ) : (
          <>
            <div className="bg-white shadow overflow-hidden sm:rounded-lg">
              <ul className="divide-y divide-gray-200">
                {paginatedActivities.length === 0 ? (
                  <li className="px-4 py-12 text-center">
                    <p className="text-gray-500">No activities found for this member.</p>
                  </li>
                ) : (
                  paginatedActivities.map((activity) => {
                    const displaySource = activity.source_type === "google_drive" ? "drive" : activity.source_type;
                    return (
                      <li key={activity.id} className="hover:bg-gray-50">
                        {/* Activity Header */}
                        <div
                          className="px-4 py-4 sm:px-6 cursor-pointer"
                          onClick={() => toggleActivity(activity.id)}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex-1">
                              <div className="flex items-center space-x-3">
                                <span className="text-2xl">
                                  {getSourceIcon(displaySource)}
                                </span>
                                <span
                                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getSourceColor(
                                    displaySource
                                  )}`}
                                >
                                  {displaySource}
                                </span>

                                {/* Activity Type Badge for GitHub */}
                                {activity.source_type === "github" && (
                                  <>
                                    {activity.activity_type === "commit" && (
                                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                        💾 commit
                                      </span>
                                    )}
                                    {activity.activity_type === "pull_request" && (
                                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                                        🔀 pull request
                                      </span>
                                    )}
                                    {activity.activity_type === "issue" && (
                                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                                        ⚠️ issue
                                      </span>
                                    )}
                                  </>
                                )}

                                {/* Activity Type Badge for Slack */}
                                {activity.source_type === "slack" && (
                                  <>
                                    {activity.activity_type === "message" && (
                                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                        💬 message
                                      </span>
                                    )}
                                    {activity.metadata?.channel && (
                                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                                        #{activity.metadata.channel}
                                      </span>
                                    )}
                                  </>
                                )}
                              </div>
                              <div className="mt-2 text-sm text-gray-600">
                                {activity.metadata?.title && (
                                  <p className="line-clamp-1 font-medium">
                                    {activity.metadata.title}
                                  </p>
                                )}
                                {activity.metadata?.message && (
                                  <p className="line-clamp-1">
                                    {activity.metadata.message}
                                  </p>
                                )}
                                {activity.metadata?.text && (
                                  <p className="line-clamp-1">{activity.metadata.text}</p>
                                )}
                                {activity.metadata?.target_name && (
                                  <p className="line-clamp-1">{activity.metadata.target_name}</p>
                                )}
                                {activity.metadata?.repository && (
                                  <p className="line-clamp-1 font-mono text-xs">
                                    {activity.metadata.repository}
                                  </p>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center space-x-4">
                              <div className="text-right min-w-[160px]">
                                <p className="text-sm font-medium text-gray-900">
                                  {formatTimestamp(activity.timestamp, "MMM dd, yyyy")}
                                </p>
                                <p className="text-xs text-gray-600">
                                  {formatTimestamp(activity.timestamp, "HH:mm:ss")}
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
                            {activity.source_type === "github" && (
                              <div className="space-y-3">
                                <div className="flex items-center space-x-2">
                                  {activity.activity_type === "commit" && (
                                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                      💾 Commit
                                    </span>
                                  )}
                                  {activity.activity_type === "pull_request" && (
                                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                                      🔀 Pull Request
                                    </span>
                                  )}
                                  {activity.activity_type === "issue" && (
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
                                  <span className="text-xs font-medium text-gray-500">Time:</span>
                                  <p className="text-sm text-gray-900">
                                    {formatTimestamp(activity.timestamp, "yyyy-MM-dd HH:mm:ss")}
                                  </p>
                                </div>

                                {activity.metadata?.repository && (
                                  <div>
                                    <span className="text-xs font-medium text-gray-500">Repository:</span>
                                    <p className="text-sm text-gray-900">
                                      tokamak-network/{activity.metadata.repository}
                                    </p>
                                  </div>
                                )}

                                {activity.metadata?.sha && (
                                  <div>
                                    <span className="text-xs font-medium text-gray-500">Commit SHA:</span>
                                    <p className="text-sm font-mono text-gray-900">
                                      {activity.metadata.sha.substring(0, 7)}
                                    </p>
                                  </div>
                                )}

                                {activity.metadata?.number && (
                                  <div>
                                    <span className="text-xs font-medium text-gray-500">
                                      {activity.activity_type === "pull_request"
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
                                      <span className="text-xs font-medium text-gray-500">Changes:</span>
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
                            {activity.source_type === "slack" && (
                              <div className="space-y-3">
                                <div className="flex items-center space-x-2">
                                  {activity.activity_type === "message" && (
                                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                                      💬 Message
                                    </span>
                                  )}
                                </div>

                                <div>
                                  <span className="text-xs font-medium text-gray-500">Time:</span>
                                  <p className="text-sm text-gray-900">
                                    {formatTimestamp(activity.timestamp, "yyyy-MM-dd HH:mm:ss")}
                                  </p>
                                </div>

                                {activity.metadata?.channel && (
                                  <div>
                                    <span className="text-xs font-medium text-gray-500">Channel:</span>
                                    <p className="text-sm text-gray-900">
                                      #{activity.metadata.channel}
                                    </p>
                                  </div>
                                )}

                                {activity.metadata?.text && (
                                  <div>
                                    <span className="text-xs font-medium text-gray-500">Message:</span>
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
                            {activity.source_type === "notion" && (
                              <div className="space-y-3">
                                <div>
                                  <span className="text-xs font-medium text-gray-500">Time:</span>
                                  <p className="text-sm text-gray-900">
                                    {formatTimestamp(activity.timestamp, "yyyy-MM-dd HH:mm:ss")}
                                  </p>
                                </div>

                                {activity.metadata?.title && (
                                  <div>
                                    <span className="text-xs font-medium text-gray-500">Title:</span>
                                    <p className="text-sm text-gray-900">{activity.metadata.title}</p>
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
                            {(activity.source_type === "google_drive" || activity.source_type === "drive") && (
                              <div className="space-y-3">
                                <div>
                                  <span className="text-xs font-medium text-gray-500">Time:</span>
                                  <p className="text-sm text-gray-900">
                                    {formatTimestamp(activity.timestamp, "yyyy-MM-dd HH:mm:ss")}
                                  </p>
                                </div>

                                {activity.metadata?.primary_action && (
                                  <div>
                                    <span className="text-xs font-medium text-gray-500">Action:</span>
                                    <p className="text-sm text-gray-900">{activity.metadata.primary_action}</p>
                                  </div>
                                )}

                                {activity.metadata?.target_name && (
                                  <div>
                                    <span className="text-xs font-medium text-gray-500">File:</span>
                                    <p className="text-sm text-gray-900">{activity.metadata.target_name}</p>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                      </li>
                    );
                  })
                )}
              </ul>
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between bg-white px-4 py-3 sm:px-6 rounded-lg shadow">
                <div className="flex flex-1 justify-between sm:hidden">
                  <button
                    onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                    disabled={currentPage === 1}
                    className="relative inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                    disabled={currentPage === totalPages}
                    className="relative ml-3 inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
                <div className="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm text-gray-700">
                      Showing <span className="font-medium">{startIndex + 1}</span> to{" "}
                      <span className="font-medium">{Math.min(endIndex, totalItems)}</span> of{" "}
                      <span className="font-medium">{totalItems}</span> results
                    </p>
                  </div>
                  <div>
                    <nav
                      className="isolate inline-flex -space-x-px rounded-md shadow-sm"
                      aria-label="Pagination"
                    >
                      <button
                        onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                        disabled={currentPage === 1}
                        className="relative inline-flex items-center rounded-l-md px-2 py-2 text-gray-400 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:z-20 focus:outline-offset-0 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <span className="sr-only">Previous</span>
                        <svg
                          className="h-5 w-5"
                          viewBox="0 0 20 20"
                          fill="currentColor"
                          aria-hidden="true"
                        >
                          <path
                            fillRule="evenodd"
                            d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </button>
                      {Array.from({ length: totalPages }, (_, i) => i + 1)
                        .filter((page) => {
                          return (
                            page === 1 ||
                            page === totalPages ||
                            (page >= currentPage - 1 && page <= currentPage + 1)
                          );
                        })
                        .map((page, index, array) => {
                          const prevPage = array[index - 1];
                          const showEllipsis = prevPage && page - prevPage > 1;

                          return (
                            <div key={page} className="inline-flex">
                              {showEllipsis && (
                                <span className="relative inline-flex items-center px-4 py-2 text-sm font-semibold text-gray-700 ring-1 ring-inset ring-gray-300">
                                  ...
                                </span>
                              )}
                              <button
                                onClick={() => setCurrentPage(page)}
                                className={`relative inline-flex items-center px-4 py-2 text-sm font-semibold ${
                                  page === currentPage
                                    ? "z-10 bg-primary-600 text-white focus:z-20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
                                    : "text-gray-900 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:z-20 focus:outline-offset-0"
                                }`}
                              >
                                {page}
                              </button>
                            </div>
                          );
                        })}
                      <button
                        onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                        disabled={currentPage === totalPages}
                        className="relative inline-flex items-center rounded-r-md px-2 py-2 text-gray-400 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:z-20 focus:outline-offset-0 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <span className="sr-only">Next</span>
                        <svg
                          className="h-5 w-5"
                          viewBox="0 0 20 20"
                          fill="currentColor"
                          aria-hidden="true"
                        >
                          <path
                            fillRule="evenodd"
                            d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </button>
                    </nav>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
