"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { format } from "date-fns";
import { api as apiClient } from "@/lib/api";
import {
  ArrowLeftIcon,
  EnvelopeIcon,
  BriefcaseIcon,
  FolderIcon,
  SparklesIcon,
  ChartBarIcon,
} from "@heroicons/react/24/outline";
import {
  Area,
  AreaChart,
  BarChart,
  Bar,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Legend,
} from "recharts";
import DateRangePicker from "@/components/DateRangePicker";
import { CollaborationNetwork } from "@/components/CollaborationNetwork";
import ActivitiesView from "@/components/ActivitiesView";
import { useProjects } from "@/graphql/hooks";
// TODO: Fix issues with new GraphQL components before re-enabling
// import { useMemberDetail } from "@/graphql/hooks";
// import MemberCollaboration from "@/components/MemberCollaboration";
// import MemberActivityStats from "@/components/MemberActivityStats";

// Helper function to safely format timestamps
function formatTimestamp(timestamp: string, formatStr: string): string {
  if (!timestamp) return "N/A";
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return "N/A";
  return format(date, formatStr);
}

// Helper to check if string is UUID format
function isUUID(str: string): boolean {
  const uuidRegex =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  return uuidRegex.test(str);
}

// Helper to check if string is Notion-prefixed
function isNotionPrefix(str: string): boolean {
  return str.startsWith("Notion-");
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
  daily_trends?: Array<{
    date: string;
    github: number;
    slack: number;
    notion: number;
    drive: number;
  }>;
  code_changes?: {
    total: {
      additions: number;
      deletions: number;
    };
    daily: Array<{
      date: string;
      additions: number;
      deletions: number;
    }>;
    weekly: Array<{
      week: string;
      additions: number;
      deletions: number;
    }>;
  };
}

interface MemberDetail {
  id: string;
  name: string;
  email: string;
  role?: string;
  project?: string; // Backward compatibility: single project
  projects?: string[]; // New: array of project keys
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

  // GraphQL query for projects (to get project names)
  const { data: projectsData } = useProjects({ isActive: true });
  const projects = projectsData?.projects || [];

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

  // TODO: Fix issues with new GraphQL components before re-enabling
  // GraphQL: Fetch member detail with collaboration and repository data
  // const {
  //   data: memberDetailData,
  //   loading: graphqlLoading,
  //   error: graphqlError,
  // } = useMemberDetail({ name: memberId });

  // // Debug GraphQL data
  // useEffect(() => {
  //   console.log("🔍 GraphQL Debug:", {
  //     memberId,
  //     loading: graphqlLoading,
  //     error: graphqlError,
  //     hasData: !!memberDetailData,
  //     member: memberDetailData?.member,
  //     topCollaborators: memberDetailData?.member?.topCollaborators,
  //     activeRepositories: memberDetailData?.member?.activeRepositories,
  //     activityStats: memberDetailData?.member?.activityStats,
  //   });
  // }, [memberId, graphqlLoading, graphqlError, memberDetailData]);

  // Translation states
  const [summaryTranslation, setSummaryTranslation] = useState<{
    text: string;
    lang: string;
  } | null>(null);
  const [translatingSummary, setTranslatingSummary] = useState(false);

  // Pagination states
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  const loadMemberDetail = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.getMemberDetailById(memberId);
      setMember(data);
    } catch (err: any) {
      console.error("Error loading member detail:", err);
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Failed to load member details"
      );
    } finally {
      setLoading(false);
    }
  }, [memberId]);

  const loadActivities = useCallback(async () => {
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
  }, [memberId, selectedSource, startDate, endDate, itemsPerPage]);

  useEffect(() => {
    loadMemberDetail();
  }, [loadMemberDetail]);

  useEffect(() => {
    loadActivities();
  }, [loadActivities]);

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

  // Filter activities by source
  const filteredActivities = selectedSource
    ? activities.filter((a) => {
        const source =
          a.source_type === "google_drive" ? "drive" : a.source_type;
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
    new Set(
      activities.map((a) =>
        a.source_type === "google_drive" ? "drive" : a.source_type
      )
    )
  ).sort();

  // Helper functions for activity display
  const getSourceColor = (source: string) => {
    const colors: Record<string, string> = {
      github: "bg-gray-100 text-gray-800",
      slack: "bg-purple-100 text-purple-800",
      notion: "bg-blue-100 text-blue-800",
      drive: "bg-green-100 text-green-800",
      google_drive: "bg-green-100 text-green-800",
      recordings: "bg-red-100 text-red-800",
      recordings_daily: "bg-orange-100 text-orange-800",
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
      recordings_daily: "📊",
    };
    return icons[source] || "📋";
  };

  const resolveMemberName = (
    memberName: string,
    sourceType: string
  ): string => {
    // Only apply conversion for Notion source
    if (sourceType !== "notion") return memberName;

    // Check if it's a full UUID
    if (isUUID(memberName)) {
      // For now, just return the memberName as-is
      // TODO: Add notion UUID map if needed
      return memberName;
    }

    // Check if it's "Notion-xxx" format
    if (isNotionPrefix(memberName)) {
      // For now, just return the memberName as-is
      // TODO: Add notion UUID map if needed
      return memberName;
    }

    return memberName;
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
            {member.activity_stats?.total_activities?.toLocaleString() || 0}{" "}
            activities recorded across all sources
          </p>
        </div>

        {/* Member Info Card */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">
            Profile Information
          </h2>
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

            {(() => {
              // Get all project keys from member
              const memberProjectKeys =
                member.projects && member.projects.length > 0
                  ? member.projects
                  : member.project
                  ? [member.project]
                  : [];

              // Filter to only show active projects
              const activeProjectKeys = memberProjectKeys.filter((pk) =>
                projects.some((p) => p.key === pk)
              );

              if (activeProjectKeys.length === 0) return null;

              return (
                <div className="flex items-center gap-3">
                  <FolderIcon className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-sm text-gray-500">Projects</p>
                    <div className="flex flex-wrap gap-2 mt-1">
                      {activeProjectKeys.map((projectKey, idx) => {
                        const project = projects.find(
                          (p) => p.key === projectKey
                        );
                        return (
                          <span
                            key={idx}
                            className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                          >
                            {project ? project.name : projectKey}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                </div>
              );
            })()}

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
                      } ${translatingSummary ? "opacity-50 cursor-wait" : ""}`}
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
                      } ${translatingSummary ? "opacity-50 cursor-wait" : ""}`}
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
                      {summaryTranslation.lang === "ko" ? "Korean" : "English"}
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-gray-500">
                  Click &quot;Generate Summary&quot; to analyze activities with
                  AI.
                </p>
              )}
            </div>
          )}
        </div>

        {/* Analytics Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Stacked Area Chart - Activity Trends */}
          <div className="bg-white rounded-lg shadow p-6 lg:col-span-2">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                <ChartBarIcon className="h-5 w-5 text-indigo-500" />
                Activity Trends (Last 90 Days)
              </h2>
            </div>
            <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex items-start gap-3">
              <span className="text-xl">⚠️</span>
              <div>
                <h3 className="text-sm font-medium text-yellow-800">
                  Drive Data Temporarily Disabled
                </h3>
                <p className="text-sm text-yellow-700 mt-1">
                  Google Drive activity data is currently excluded from
                  visualizations due to high volume noise causing skewness. We
                  are optimizing the filtering logic.
                </p>
              </div>
            </div>

            <div className="h-[300px] w-full">
              {member.activity_stats.daily_trends &&
              member.activity_stats.daily_trends.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart
                    data={member.activity_stats.daily_trends}
                    margin={{
                      top: 10,
                      right: 10,
                      left: 0,
                      bottom: 0,
                    }}
                  >
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 12 }}
                      tickFormatter={(value) =>
                        format(new Date(value), "MM/dd")
                      }
                      interval="preserveStartEnd"
                    />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip
                      contentStyle={{
                        borderRadius: "8px",
                        border: "none",
                        boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                      }}
                      labelFormatter={(value) =>
                        format(new Date(value), "MMM dd, yyyy")
                      }
                    />
                    <Legend />
                    <Area
                      type="monotone"
                      dataKey="github"
                      name="GitHub"
                      stackId="1"
                      stroke="#3B82F6"
                      fill="#3B82F6"
                    />
                    <Area
                      type="monotone"
                      dataKey="slack"
                      name="Slack"
                      stackId="1"
                      stroke="#8B5CF6"
                      fill="#8B5CF6"
                    />
                    <Area
                      type="monotone"
                      dataKey="notion"
                      name="Notion"
                      stackId="1"
                      stroke="#14B8A6"
                      fill="#14B8A6"
                    />
                    {/* Drive area hidden due to noise */}
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500">
                  No trend data available
                </div>
              )}
            </div>
          </div>

          {/* Radar Chart - Activity Distribution */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-6 flex items-center gap-2">
              <span className="text-xl">🎯</span>
              Focus Areas
            </h2>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart
                  cx="50%"
                  cy="50%"
                  outerRadius="80%"
                  data={[
                    {
                      subject: "GitHub",
                      A: member.activity_stats.by_source.github?.total || 0,
                      fullMark: 100,
                    },
                    {
                      subject: "Slack",
                      A: member.activity_stats.by_source.slack?.total || 0,
                      fullMark: 100,
                    },
                    {
                      subject: "Notion",
                      A: member.activity_stats.by_source.notion?.total || 0,
                      fullMark: 100,
                    },
                    // Drive excluded due to noise
                  ]}
                >
                  <PolarGrid />
                  <PolarAngleAxis
                    dataKey="subject"
                    tick={{ fill: "#4B5563", fontSize: 12 }}
                  />

                  <Radar
                    name="Activities"
                    dataKey="A"
                    stroke="#4F46E5"
                    fill="#4F46E5"
                    fillOpacity={0.6}
                  />
                  <Tooltip />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Code Changes Section */}
        {member.activity_stats.code_changes && (
          <div className="space-y-6">
            {/* Code Changes Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-gradient-to-br from-emerald-500 to-emerald-600 rounded-xl shadow-lg p-6 text-white">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-emerald-100 text-sm font-medium mb-1">
                      Lines Added (90d)
                    </p>
                    <p className="text-3xl font-bold">
                      +
                      {member.activity_stats.code_changes.total.additions.toLocaleString()}
                    </p>
                  </div>
                  <span className="text-5xl opacity-20">➕</span>
                </div>
              </div>

              <div className="bg-gradient-to-br from-rose-500 to-rose-600 rounded-xl shadow-lg p-6 text-white">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-rose-100 text-sm font-medium mb-1">
                      Lines Deleted (90d)
                    </p>
                    <p className="text-3xl font-bold">
                      -
                      {member.activity_stats.code_changes.total.deletions.toLocaleString()}
                    </p>
                  </div>
                  <span className="text-5xl opacity-20">➖</span>
                </div>
              </div>

              <div className="bg-gradient-to-br from-indigo-500 to-indigo-600 rounded-xl shadow-lg p-6 text-white">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-indigo-100 text-sm font-medium mb-1">
                      Net Change (90d)
                    </p>
                    <p className="text-3xl font-bold">
                      {member.activity_stats.code_changes.total.additions -
                        member.activity_stats.code_changes.total.deletions >=
                      0
                        ? "+"
                        : ""}
                      {(
                        member.activity_stats.code_changes.total.additions -
                        member.activity_stats.code_changes.total.deletions
                      ).toLocaleString()}
                    </p>
                  </div>
                  <span className="text-5xl opacity-20">📊</span>
                </div>
              </div>
            </div>

            {/* Code Changes Chart */}
            {member.activity_stats.code_changes.daily.length > 0 && (
              <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-lg font-bold text-gray-900 mb-6 flex items-center gap-2">
                  <span className="text-xl">💻</span>
                  Code Changes (Last 30 Days)
                </h2>
                <div className="h-[300px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={member.activity_stats.code_changes.daily.map(
                        (d) => ({
                          ...d,
                          changes: d.additions + d.deletions,
                        })
                      )}
                      margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient
                          id="colorMemberChanges"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="5%"
                            stopColor="#6366f1"
                            stopOpacity={0.8}
                          />
                          <stop
                            offset="95%"
                            stopColor="#6366f1"
                            stopOpacity={0.1}
                          />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: 12 }}
                        tickFormatter={(value) =>
                          format(new Date(value), "MM/dd")
                        }
                        interval="preserveStartEnd"
                      />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{
                          borderRadius: "8px",
                          border: "none",
                          boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                        }}
                        labelFormatter={(value) =>
                          format(new Date(value), "MMM dd, yyyy")
                        }
                        formatter={(value: number, name: string, props: any) => {
                          const item = props.payload;
                          return [
                            `${value.toLocaleString()} lines (+${item.additions.toLocaleString()} / -${item.deletions.toLocaleString()})`,
                            "Code Changes",
                          ];
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="changes"
                        name="Code Changes"
                        stroke="#6366f1"
                        fill="url(#colorMemberChanges)"
                        strokeWidth={2}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Collaboration Network */}
        <CollaborationNetwork memberName={member.name} days={90} limit={10} />

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
                    {member.activity_stats.by_source.github.commits || 0}{" "}
                    commits,{" "}
                    {member.activity_stats.by_source.github.pull_requests || 0}{" "}
                    PRs
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
                    {member.activity_stats.by_source.slack.messages || 0}{" "}
                    messages
                  </p>
                </div>
                <span className="text-4xl">💬</span>
              </div>
            </div>
          )}

          {/* Other Sources */}
          {(member.activity_stats.by_source.notion ||
            member.activity_stats.by_source.drive) && (
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

        {/* Activities Section */}
        {member && (
          <div className="mt-8">
            <ActivitiesView
              initialMemberFilter={member.name}
              showProjectFilter={false}
            />
          </div>
        )}

        {/* TODO: Fix issues with new GraphQL components before re-enabling */}
        {/* GraphQL-Powered Collaboration and Repository Analysis */}
        {/* {!graphqlLoading && memberDetailData?.member && (
              <div className="mt-8 space-y-8">
                {memberDetailData.member.activityStats && (
                  <div>
                    <h2 className="text-2xl font-bold mb-4 flex items-center">
                      📊 Activity Statistics
                    </h2>
                    <MemberActivityStats
                      stats={memberDetailData.member.activityStats}
                    />
                  </div>
                )}

                {(memberDetailData.member.topCollaborators ||
                  memberDetailData.member.activeRepositories) && (
                  <div>
                    <h2 className="text-2xl font-bold mb-4 flex items-center">
                      🤝 Collaboration Network
                    </h2>
                    <MemberCollaboration
                      collaborators={
                        memberDetailData.member.topCollaborators || []
                      }
                      repositories={
                        memberDetailData.member.activeRepositories || []
                      }
                    />
                  </div>
                )}
              </div>
            )} */}
      </div>
    </div>
  );
}
