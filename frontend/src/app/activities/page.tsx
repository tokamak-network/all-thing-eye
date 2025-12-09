"use client";

import { useEffect, useState } from "react";
import { format } from "date-fns";
import { api as apiClient } from "@/lib/api";
import type { ActivityListResponse } from "@/types";

// Helper function to safely format timestamps (converts to browser's local timezone)
function formatTimestamp(timestamp: string, formatStr: string): string {
  if (!timestamp) return "N/A";
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return "N/A";
  return format(date, formatStr);
}

// Helper function to get timezone offset string (e.g., "UTC+9", "UTC-5")
function getTimezoneString(): string {
  const offset = -new Date().getTimezoneOffset() / 60;
  const sign = offset >= 0 ? "+" : "";
  return `UTC${sign}${offset}`;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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

export default function ActivitiesPage() {
  const [allActivities, setAllActivities] =
    useState<ActivityListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const [memberFilter, setMemberFilter] = useState<string>("");
  const [participantFilter, setParticipantFilter] = useState<string>("");
  const [expandedActivity, setExpandedActivity] = useState<string | null>(null);
  const [recordingDetail, setRecordingDetail] = useState<any>(null);
  const [showTranscript, setShowTranscript] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  // Daily Analysis Detail states
  const [selectedDailyAnalysis, setSelectedDailyAnalysis] = useState<any>(null);
  const [showDailyAnalysisDetail, setShowDailyAnalysisDetail] = useState(false);
  const [dailyAnalysisLoading, setDailyAnalysisLoading] = useState(false);
  const [dailyAnalysisTab, setDailyAnalysisTab] = useState<string>("overview");
  const [allMembers, setAllMembers] = useState<string[]>([]);
  // Notion UUID to member name mapping
  const [notionUuidMap, setNotionUuidMap] = useState<Record<string, string>>(
    {}
  );

  // Pagination states
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  // Translation states
  const [translations, setTranslations] = useState<
    Record<string, { text: string; lang: string }>
  >({});
  const [translating, setTranslating] = useState<string | null>(null);
  const [translatingSet, setTranslatingSet] = useState<Set<string>>(new Set());

  // AI Meeting Analysis states
  const [meetingAnalysis, setMeetingAnalysis] = useState<any>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<string>("default");
  const [analysisLoading, setAnalysisLoading] = useState(false);

  // Fetch all members and Notion UUID mappings from DB (runs once on mount)
  useEffect(() => {
    async function fetchMembersAndMappings() {
      try {
        const response = await apiClient.getMembers({ limit: 100 });
        // Response is directly an array of members
        const memberNames = response
          .map((m: any) => m.name)
          .filter((name: string) => name)
          .sort();
        setAllMembers(memberNames);

        // Fetch member_identifiers for Notion UUID mapping
        try {
          const identifiersResponse = await apiClient.get(
            "/database/collections/member_identifiers/documents",
            {
              limit: 100,
            }
          );
          const documents = identifiersResponse.documents || [];

          // Build UUID -> member_name mapping for Notion
          const uuidMap: Record<string, string> = {};
          documents.forEach((doc: any) => {
            if (
              doc.source === "notion" &&
              doc.identifier_value &&
              doc.member_name
            ) {
              // Map full UUID
              uuidMap[doc.identifier_value.toLowerCase()] = doc.member_name;
              // Also map short UUID (first 8 chars) for "Notion-xxx" format
              const shortUuid = doc.identifier_value
                .split("-")[0]
                .toLowerCase();
              uuidMap[shortUuid] = doc.member_name;
            }
          });
          setNotionUuidMap(uuidMap);
        } catch (err) {
          console.error("Error fetching member identifiers:", err);
        }
      } catch (err: any) {
        console.error("Error fetching members:", err);
      }
    }

    fetchMembersAndMappings();
  }, []);

  // Fetch activities with filters (including member filter from backend)
  useEffect(() => {
    async function fetchActivities() {
      try {
        setLoading(true);
        // Always fetch enough data for current page settings
        const loadLimit = Math.max(itemsPerPage * 10, 500);
        const response = await apiClient.getActivities({
          limit: loadLimit,
          source_type: sourceFilter || undefined,
          member_name: memberFilter || undefined, // Filter by member on backend
          participant_name: participantFilter || undefined, // Filter by participant on backend (for recordings and daily analysis)
        });
        setAllActivities(response);
        setCurrentPage(1); // Reset to first page when filter changes
      } catch (err: any) {
        console.error("Error fetching activities:", err);
        setError(err.message || "Failed to fetch activities");
      } finally {
        setLoading(false);
      }
    }

    fetchActivities();
  }, [sourceFilter, memberFilter, participantFilter, itemsPerPage]); // Reload when any filter changes

  // Activities are already filtered by backend, but we need to filter out Kevin's Google Drive activities (noise)
  const filteredActivities = allActivities
    ? allActivities.activities.filter(
        (activity) =>
          !(
            activity.source_type === "drive" &&
            activity.member_name &&
            activity.member_name.toLowerCase() === "kevin"
          )
      )
    : [];

  // Paginate filtered activities
  const totalItems = filteredActivities.length;
  const totalPages = Math.ceil(totalItems / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedActivities = filteredActivities.slice(startIndex, endIndex);

  const data = allActivities
    ? {
        ...allActivities,
        activities: paginatedActivities,
        total: totalItems,
      }
    : null;

  const toggleActivity = (activityId: string) => {
    setExpandedActivity(expandedActivity === activityId ? null : activityId);
  };

  // Translate text using Google Translate API
  const handleTranslate = async (
    activityId: string,
    text: string,
    targetLang: string,
    sourceLang?: string
  ): Promise<void> => {
    if (!text) return Promise.resolve();

    // If already translated to this language, toggle back to original
    if (translations[activityId]?.lang === targetLang) {
      setTranslations((prev) => {
        const newTranslations = { ...prev };
        delete newTranslations[activityId];
        return newTranslations;
      });
      return Promise.resolve();
    }

    // Check if this specific translation is already in progress
    setTranslatingSet((prev) => {
      if (prev.has(activityId)) {
        return prev; // Already translating, skip
      }
      const newSet = new Set(prev);
      newSet.add(activityId);
      return newSet;
    });

    // Also set the main translating state for backward compatibility
    setTranslating(activityId);
    
    try {
      const result = await apiClient.translateText(text, targetLang, sourceLang);
      setTranslations((prev) => ({
        ...prev,
        [activityId]: { text: result.translated_text, lang: targetLang },
      }));
    } catch (err: any) {
      console.error("Translation error:", err);
      // Show error but don't block UI - don't alert for individual translations in batch
    } finally {
      setTranslatingSet((prev) => {
        const newSet = new Set(prev);
        newSet.delete(activityId);
        return newSet;
      });
      // Only clear main translating if this was the last one
      setTranslating((prev) => (prev === activityId ? null : prev));
    }
  };

  // Convert Notion UUID or "Notion-xxx" format to member name
  const resolveMemberName = (
    memberName: string,
    sourceType: string
  ): string => {
    // Only apply conversion for Notion source
    if (sourceType !== "notion") return memberName;

    // Check if it's a full UUID
    if (isUUID(memberName)) {
      const resolved = notionUuidMap[memberName.toLowerCase()];
      return resolved || memberName;
    }

    // Check if it's "Notion-xxx" format
    if (isNotionPrefix(memberName)) {
      const shortUuid = memberName.replace("Notion-", "").toLowerCase();
      const resolved = notionUuidMap[shortUuid];
      return resolved || memberName;
    }

    return memberName;
  };

  const handleViewRecordingDetail = async (recordingId: string) => {
    setDetailLoading(true);
    setAnalysisLoading(true);
    setShowTranscript(true);
    // Note: selectedTemplate is set by the button before calling this function

    try {
      // Fetch meeting details and AI analysis from /ai/meetings/ API
      const response = await apiClient.getMeetingDetail(recordingId);

      // Set both recordingDetail and meetingAnalysis from the same response
      setRecordingDetail(response);
      setMeetingAnalysis(response);

      // Keep the selected template - UI will show "No AI Analysis" message if not available
      // Only switch if the specific template doesn't exist but others do
      if (
        selectedTemplate !== "transcript" &&
        response?.analyses &&
        Object.keys(response.analyses).length > 0 &&
        !response.analyses[selectedTemplate]
      ) {
        // Requested template doesn't exist, switch to first available
        const firstAnalysis = Object.keys(response.analyses)[0];
        setSelectedTemplate(firstAnalysis);
      }
    } catch (err: any) {
      console.error("Failed to load recording details:", err);
      alert("Failed to load recording details");
    } finally {
      setDetailLoading(false);
      setAnalysisLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">Error: {error}</p>
      </div>
    );
  }

  const getSourceColor = (source: string) => {
    const colors: Record<string, string> = {
      github: "bg-gray-100 text-gray-800",
      slack: "bg-purple-100 text-purple-800",
      notion: "bg-blue-100 text-blue-800",
      drive: "bg-green-100 text-green-800",
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
      recordings: "📹",
      recordings_daily: "📊",
    };
    return icons[source] || "📋";
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">📋 Activities</h1>
          <p className="mt-2 text-gray-600">
            {data?.total?.toLocaleString() || 0} activities recorded across all
            sources
          </p>
        </div>
        <div className="flex space-x-2">
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="block rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
          >
            <option value="">All Sources</option>
            <option value="github">🐙 GitHub</option>
            <option value="slack">💬 Slack</option>
            <option value="notion">📝 Notion</option>
            <option value="drive">📁 Google Drive</option>
            <option value="recordings">📹 Recordings</option>
            <option value="recordings_daily">📊 Daily Analysis</option>
          </select>
          <select
            value={memberFilter}
            onChange={(e) => setMemberFilter(e.target.value)}
            className="block rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
          >
            <option value="">All Members</option>
            {allMembers.map((member) => (
              <option key={member} value={member}>
                {member}
              </option>
            ))}
          </select>
          <select
            value={participantFilter}
            onChange={(e) => setParticipantFilter(e.target.value)}
            className="block rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            title="Filter by participant (for recordings and daily analysis)"
          >
            <option value="">All Participants</option>
            {allMembers.map((member) => (
              <option key={member} value={member}>
                👥 {member}
              </option>
            ))}
          </select>
          <select
            value={itemsPerPage}
            onChange={(e) => {
              setItemsPerPage(Number(e.target.value));
              setCurrentPage(1);
            }}
            className="block rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
          >
            <option value="10">10 per page</option>
            <option value="30">30 per page</option>
            <option value="50">50 per page</option>
          </select>
          <a
            href={apiClient.getExportActivitiesUrl("csv", {
              limit: 10000,
              source_type: sourceFilter || undefined,
            })}
            download
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
          >
            <svg
              className="mr-2 h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
            Export CSV
          </a>
        </div>
      </div>

      {/* Pagination Controls */}
      {data && totalPages > 1 && (
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
              onClick={() =>
                setCurrentPage(Math.min(totalPages, currentPage + 1))
              }
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
                <span className="font-medium">
                  {Math.min(endIndex, totalItems)}
                </span>{" "}
                of <span className="font-medium">{totalItems}</span> results
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
                    // Show first page, last page, current page, and pages around current
                    return (
                      page === 1 ||
                      page === totalPages ||
                      (page >= currentPage - 1 && page <= currentPage + 1)
                    );
                  })
                  .map((page, index, array) => {
                    // Add ellipsis if there's a gap
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
                  onClick={() =>
                    setCurrentPage(Math.min(totalPages, currentPage + 1))
                  }
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

      {/* Activities List */}
      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <ul className="divide-y divide-gray-200">
          {data?.activities.map((activity) => (
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
                        {getSourceIcon(activity.source_type)}
                      </span>
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getSourceColor(
                          activity.source_type
                        )}`}
                      >
                        {activity.source_type}
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
                          {activity.activity_type === "thread_reply" && (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
                              💭 thread reply
                            </span>
                          )}
                          {activity.activity_type === "file_share" && (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                              📎 file share
                            </span>
                          )}
                          {activity.metadata?.channel && (
                            <>
                              {activity.metadata?.url ? (
                                <a
                                  href={activity.metadata.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  onClick={(e) => e.stopPropagation()}
                                  className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
                                >
                                  #{activity.metadata.channel}
                                </a>
                              ) : (
                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                                  #{activity.metadata.channel}
                                </span>
                              )}
                            </>
                          )}
                        </>
                      )}

                      <p className="text-sm font-medium text-gray-900">
                        {activity.source_type === "recordings_daily"
                          ? activity.metadata?.target_date || "Daily Analysis"
                          : resolveMemberName(
                          activity.member_name,
                          activity.source_type
                        )}
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
                        <p className="line-clamp-1">{activity.metadata.text}</p>
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
                      {/* Activity Type Badge */}
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

                      {/* Timestamp */}
                      <div>
                        <span className="text-xs font-medium text-gray-500">
                          Time:
                        </span>
                        <p className="text-sm text-gray-900">
                          {formatTimestamp(
                            activity.timestamp,
                            "yyyy-MM-dd HH:mm:ss"
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

                      {activity.metadata?.github_username && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">
                            GitHub:
                          </span>
                          <p className="text-sm text-gray-600">
                            @{activity.metadata.github_username}
                          </p>
                        </div>
                      )}

                      {/* Link Button */}
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
                      {/* Activity Type Badge */}
                      <div className="flex items-center space-x-2">
                        {activity.activity_type === "message" && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                            💬 Message
                          </span>
                        )}
                        {activity.activity_type === "thread_reply" && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
                            💭 Thread Reply
                          </span>
                        )}
                        {activity.activity_type === "file_share" && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            📎 File Share
                          </span>
                        )}
                      </div>

                      {/* Timestamp */}
                      <div>
                        <span className="text-xs font-medium text-gray-500">
                          Time:
                        </span>
                        <p className="text-sm text-gray-900">
                          {formatTimestamp(
                            activity.timestamp,
                            "yyyy-MM-dd HH:mm:ss"
                          )}
                        </p>
                      </div>

                      {activity.metadata?.channel && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">
                            Channel:
                          </span>
                          <p className="text-sm text-gray-900">
                            #{activity.metadata.channel}
                          </p>
                        </div>
                      )}

                      {activity.metadata?.text && (
                        <div>
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-gray-500">
                              Message:
                            </span>
                            <div className="flex gap-1">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  const actId =
                                    activity.activity_id || activity.id;
                                  if (actId)
                                    handleTranslate(
                                      actId,
                                      activity.metadata.text,
                                      "en"
                                    );
                                }}
                                disabled={
                                  translating ===
                                  (activity.activity_id || activity.id)
                                }
                                className={`text-xs px-2 py-0.5 rounded transition-colors ${
                                  translations[
                                    activity.activity_id || activity.id
                                  ]?.lang === "en"
                                    ? "bg-blue-600 text-white"
                                    : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                                } ${
                                  translating ===
                                  (activity.activity_id || activity.id)
                                    ? "opacity-50 cursor-wait"
                                    : ""
                                }`}
                              >
                                EN
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  const actId =
                                    activity.activity_id || activity.id;
                                  if (actId)
                                    handleTranslate(
                                      actId,
                                      activity.metadata.text,
                                      "ko"
                                    );
                                }}
                                disabled={
                                  translating ===
                                  (activity.activity_id || activity.id)
                                }
                                className={`text-xs px-2 py-0.5 rounded transition-colors ${
                                  translations[
                                    activity.activity_id || activity.id
                                  ]?.lang === "ko"
                                    ? "bg-blue-600 text-white"
                                    : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                                } ${
                                  translating ===
                                  (activity.activity_id || activity.id)
                                    ? "opacity-50 cursor-wait"
                                    : ""
                                }`}
                              >
                                KR
                              </button>
                            </div>
                          </div>
                          <p className="text-sm text-gray-700 whitespace-pre-wrap bg-white p-3 rounded border border-gray-200 mt-1">
                            {translations[activity.activity_id || activity.id]
                              ?.text || activity.metadata.text}
                          </p>
                          {translations[
                            activity.activity_id || activity.id
                          ] && (
                            <p className="text-xs text-gray-400 mt-1">
                              🌐 Translated to{" "}
                              {translations[activity.activity_id || activity.id]
                                ?.lang === "ko"
                                ? "Korean"
                                : "English"}
                            </p>
                          )}
                        </div>
                      )}

                      {/* Stats */}
                      <div className="flex flex-wrap gap-3 text-sm">
                        {activity.metadata?.reactions > 0 && (
                          <div className="flex items-center space-x-1">
                            <span className="text-gray-500">👍 Reactions:</span>
                            <span className="font-medium text-gray-900">
                              {activity.metadata.reactions}
                            </span>
                          </div>
                        )}
                        {activity.metadata?.reply_count > 0 && (
                          <div className="flex items-center space-x-1">
                            <span className="text-gray-500">💬 Replies:</span>
                            <span className="font-medium text-gray-900">
                              {activity.metadata.reply_count}
                            </span>
                          </div>
                        )}
                        {activity.metadata?.links > 0 && (
                          <div className="flex items-center space-x-1">
                            <span className="text-gray-500">🔗 Links:</span>
                            <span className="font-medium text-gray-900">
                              {activity.metadata.links}
                            </span>
                          </div>
                        )}
                        {activity.metadata?.files > 0 && (
                          <div className="flex items-center space-x-1">
                            <span className="text-gray-500">📎 Files:</span>
                            <span className="font-medium text-gray-900">
                              {activity.metadata.files}
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Link Button */}
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
                      {/* Timestamp */}
                      <div>
                        <span className="text-xs font-medium text-gray-500">
                          Time:
                        </span>
                        <p className="text-sm text-gray-900">
                          {formatTimestamp(
                            activity.timestamp,
                            "yyyy-MM-dd HH:mm:ss"
                          )}
                        </p>
                      </div>

                      {activity.metadata?.title && (
                        <div>
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-gray-500">
                              Page Title:
                            </span>
                            <div className="flex gap-1">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleTranslate(
                                    activity.id,
                                    activity.metadata.title,
                                    "en"
                                  );
                                }}
                                disabled={translating === activity.id}
                                className={`text-xs px-2 py-0.5 rounded transition-colors ${
                                  translations[activity.id]?.lang === "en"
                                    ? "bg-blue-600 text-white"
                                    : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                                } ${
                                  translating === activity.id
                                    ? "opacity-50 cursor-wait"
                                    : ""
                                }`}
                              >
                                EN
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleTranslate(
                                    activity.id,
                                    activity.metadata.title,
                                    "ko"
                                  );
                                }}
                                disabled={translating === activity.id}
                                className={`text-xs px-2 py-0.5 rounded transition-colors ${
                                  translations[activity.id]?.lang === "ko"
                                    ? "bg-blue-600 text-white"
                                    : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                                } ${
                                  translating === activity.id
                                    ? "opacity-50 cursor-wait"
                                    : ""
                                }`}
                              >
                                KR
                              </button>
                            </div>
                          </div>
                          <p className="text-sm text-gray-900 mt-1">
                            {translations[activity.id]?.text ||
                              activity.metadata.title}
                          </p>
                          {translations[activity.id] && (
                            <p className="text-xs text-gray-400 mt-1">
                              🌐 Translated to{" "}
                              {translations[activity.id].lang === "ko"
                                ? "Korean"
                                : "English"}
                            </p>
                          )}
                        </div>
                      )}
                      {activity.metadata?.comments && (
                        <div>
                          <span className="text-sm text-gray-500">
                            💬 {activity.metadata.comments} comments
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Google Drive Details */}
                  {activity.source_type === "drive" && (
                    <div className="space-y-3">
                      {/* Timestamp */}
                      <div>
                        <span className="text-xs font-medium text-gray-500">
                          Time:
                        </span>
                        <p className="text-sm text-gray-900">
                          {formatTimestamp(
                            activity.timestamp,
                            "yyyy-MM-dd HH:mm:ss"
                          )}
                        </p>
                      </div>

                      {activity.metadata?.action && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">
                            Action:
                          </span>
                          <p className="text-sm text-gray-900">
                            {activity.metadata.action}
                          </p>
                        </div>
                      )}
                      {activity.metadata?.doc_title && (
                        <div>
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-gray-500">
                              Document:
                            </span>
                            <div className="flex gap-1">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleTranslate(
                                    activity.id,
                                    activity.metadata.doc_title,
                                    "en"
                                  );
                                }}
                                disabled={translating === activity.id}
                                className={`text-xs px-2 py-0.5 rounded transition-colors ${
                                  translations[activity.id]?.lang === "en"
                                    ? "bg-blue-600 text-white"
                                    : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                                } ${
                                  translating === activity.id
                                    ? "opacity-50 cursor-wait"
                                    : ""
                                }`}
                              >
                                EN
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleTranslate(
                                    activity.id,
                                    activity.metadata.doc_title,
                                    "ko"
                                  );
                                }}
                                disabled={translating === activity.id}
                                className={`text-xs px-2 py-0.5 rounded transition-colors ${
                                  translations[activity.id]?.lang === "ko"
                                    ? "bg-blue-600 text-white"
                                    : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                                } ${
                                  translating === activity.id
                                    ? "opacity-50 cursor-wait"
                                    : ""
                                }`}
                              >
                                KR
                              </button>
                            </div>
                          </div>
                          <p className="text-sm text-gray-900 mt-1">
                            {translations[activity.id]?.text ||
                              activity.metadata.doc_title}
                          </p>
                          {translations[activity.id] && (
                            <p className="text-xs text-gray-400 mt-1">
                              🌐 Translated to{" "}
                              {translations[activity.id].lang === "ko"
                                ? "Korean"
                                : "English"}
                            </p>
                          )}
                        </div>
                      )}
                      {activity.metadata?.doc_type && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">
                            Type:
                          </span>
                          <p className="text-sm text-gray-900">
                            {activity.metadata.doc_type}
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Recordings Daily Analysis Details */}
                  {activity.source_type === "recordings_daily" && (
                    <div className="space-y-3">
                      <div>
                        <span className="text-xs font-medium text-gray-500">
                          Target Date:
                        </span>
                        <p className="text-sm text-gray-900">
                          {activity.metadata?.target_date}
                        </p>
                      </div>
                      <div>
                        <span className="text-xs font-medium text-gray-500">
                          Meetings Analyzed:
                        </span>
                        <p className="text-sm text-gray-900">
                          {activity.metadata?.meeting_count || 0}
                        </p>
                      </div>
                      <div>
                        <span className="text-xs font-medium text-gray-500">
                          Total Time:
                        </span>
                        <p className="text-sm text-gray-900">
                          {activity.metadata?.total_meeting_time || "N/A"}
                        </p>
                      </div>
                      <div>
                        <span className="text-xs font-medium text-gray-500">
                          Status:
                        </span>
                        <span
                          className={`ml-2 px-2 py-1 text-xs rounded-full ${
                            activity.metadata?.status === "success"
                              ? "bg-green-100 text-green-800"
                              : "bg-yellow-100 text-yellow-800"
                          }`}
                        >
                          {activity.metadata?.status || "unknown"}
                        </span>
                      </div>
                      {activity.metadata?.meeting_titles &&
                        activity.metadata.meeting_titles.length > 0 && (
                          <div>
                            <span className="text-xs font-medium text-gray-500">
                              Meeting Titles:
                            </span>
                            <div className="mt-1 flex flex-wrap gap-1">
                              {activity.metadata.meeting_titles
                                .slice(0, 3)
                                .map((title: string, idx: number) => (
                                  <span
                                    key={idx}
                                    className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded"
                                  >
                                    {title}
                                  </span>
                                ))}
                              {activity.metadata.meeting_titles.length > 3 && (
                                <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded">
                                  +{activity.metadata.meeting_titles.length - 3} more
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                      {/* Action Buttons */}
                      <div className="flex flex-wrap gap-2 mt-3">
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            setDailyAnalysisLoading(true);
                            setShowDailyAnalysisDetail(true);
                            setDailyAnalysisTab("overview");
                            try {
                              const targetDate = activity.metadata?.target_date;
                              if (targetDate) {
                                const response = await apiClient.getRecordingsDailyByDate(targetDate);
                                setSelectedDailyAnalysis(response);
                              }
                            } catch (err: any) {
                              console.error("Failed to load daily analysis details:", err);
                              alert("Failed to load daily analysis details");
                            } finally {
                              setDailyAnalysisLoading(false);
                            }
                          }}
                          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
                        >
                          📊 Overview
                        </button>
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            setDailyAnalysisLoading(true);
                            setShowDailyAnalysisDetail(true);
                            setDailyAnalysisTab("topics");
                            try {
                              const targetDate = activity.metadata?.target_date;
                              if (targetDate) {
                                const response = await apiClient.getRecordingsDailyByDate(targetDate);
                                setSelectedDailyAnalysis(response);
                              }
                            } catch (err: any) {
                              console.error("Failed to load daily analysis details:", err);
                              alert("Failed to load daily analysis details");
                            } finally {
                              setDailyAnalysisLoading(false);
                            }
                          }}
                          className="px-3 py-1.5 bg-purple-600 text-white text-sm rounded hover:bg-purple-700 transition-colors"
                        >
                          💬 Topics
                        </button>
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            setDailyAnalysisLoading(true);
                            setShowDailyAnalysisDetail(true);
                            setDailyAnalysisTab("decisions");
                            try {
                              const targetDate = activity.metadata?.target_date;
                              if (targetDate) {
                                const response = await apiClient.getRecordingsDailyByDate(targetDate);
                                setSelectedDailyAnalysis(response);
                              }
                            } catch (err: any) {
                              console.error("Failed to load daily analysis details:", err);
                              alert("Failed to load daily analysis details");
                            } finally {
                              setDailyAnalysisLoading(false);
                            }
                          }}
                          className="px-3 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700 transition-colors"
                        >
                          📋 Decisions
                        </button>
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            setDailyAnalysisLoading(true);
                            setShowDailyAnalysisDetail(true);
                            setDailyAnalysisTab("participants");
                            try {
                              const targetDate = activity.metadata?.target_date;
                              if (targetDate) {
                                const response = await apiClient.getRecordingsDailyByDate(targetDate);
                                setSelectedDailyAnalysis(response);
                              }
                            } catch (err: any) {
                              console.error("Failed to load daily analysis details:", err);
                              alert("Failed to load daily analysis details");
                            } finally {
                              setDailyAnalysisLoading(false);
                            }
                          }}
                          className="px-3 py-1.5 bg-orange-600 text-white text-sm rounded hover:bg-orange-700 transition-colors"
                        >
                          👥 Participants
                        </button>
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            setDailyAnalysisLoading(true);
                            setShowDailyAnalysisDetail(true);
                            setDailyAnalysisTab("full");
                            try {
                              const targetDate = activity.metadata?.target_date;
                              if (targetDate) {
                                const response = await apiClient.getRecordingsDailyByDate(targetDate);
                                setSelectedDailyAnalysis(response);
                              }
                            } catch (err: any) {
                              console.error("Failed to load daily analysis details:", err);
                              alert("Failed to load daily analysis details");
                            } finally {
                              setDailyAnalysisLoading(false);
                            }
                          }}
                          className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 transition-colors"
                        >
                          📄 Full Analysis
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Recordings Details */}
                  {activity.source_type === "recordings" && (
                    <div className="space-y-3">
                      {/* Timestamp */}
                      <div>
                        <span className="text-xs font-medium text-gray-500">
                          Time:
                        </span>
                        <p className="text-sm text-gray-900">
                          {formatTimestamp(
                            activity.timestamp,
                            "yyyy-MM-dd HH:mm:ss"
                          )}
                        </p>
                      </div>

                      {activity.metadata?.name && (
                        <div>
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-gray-500">
                              Recording Name:
                            </span>
                            <div className="flex gap-1">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleTranslate(
                                    activity.id,
                                    activity.metadata.name,
                                    "en"
                                  );
                                }}
                                disabled={translating === activity.id}
                                className={`text-xs px-2 py-0.5 rounded transition-colors ${
                                  translations[activity.id]?.lang === "en"
                                    ? "bg-blue-600 text-white"
                                    : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                                } ${
                                  translating === activity.id
                                    ? "opacity-50 cursor-wait"
                                    : ""
                                }`}
                              >
                                EN
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleTranslate(
                                    activity.id,
                                    activity.metadata.name,
                                    "ko"
                                  );
                                }}
                                disabled={translating === activity.id}
                                className={`text-xs px-2 py-0.5 rounded transition-colors ${
                                  translations[activity.id]?.lang === "ko"
                                    ? "bg-blue-600 text-white"
                                    : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                                } ${
                                  translating === activity.id
                                    ? "opacity-50 cursor-wait"
                                    : ""
                                }`}
                              >
                                KR
                              </button>
                            </div>
                          </div>
                          <p className="text-sm text-gray-900 mt-1">
                            {translations[activity.id]?.text ||
                              activity.metadata.name}
                          </p>
                          {translations[activity.id] && (
                            <p className="text-xs text-gray-400 mt-1">
                              🌐 Translated to{" "}
                              {translations[activity.id].lang === "ko"
                                ? "Korean"
                                : "English"}
                            </p>
                          )}
                        </div>
                      )}
                      {activity.metadata?.size && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">
                            File Size:
                          </span>
                          <p className="text-sm text-gray-900">
                            {formatSize(activity.metadata.size)}
                          </p>
                        </div>
                      )}
                      {/* Action Buttons */}
                      <div className="flex flex-wrap gap-2 mt-3">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            const recordingId =
                              activity.metadata?.recording_id || activity.id;
                            if (recordingId) {
                              setSelectedTemplate("transcript");
                              handleViewRecordingDetail(recordingId);
                            }
                          }}
                          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
                        >
                          📄 Transcript
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            const recordingId =
                              activity.metadata?.recording_id || activity.id;
                            if (recordingId) {
                              setSelectedTemplate("default");
                              handleViewRecordingDetail(recordingId);
                            }
                          }}
                          className="px-3 py-1.5 bg-purple-600 text-white text-sm rounded hover:bg-purple-700 transition-colors"
                        >
                          🤖 AI Summary
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            const recordingId =
                              activity.metadata?.recording_id || activity.id;
                            if (recordingId) {
                              setSelectedTemplate("action_items");
                              handleViewRecordingDetail(recordingId);
                            }
                          }}
                          className="px-3 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700 transition-colors"
                        >
                          ✅ Actions
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            const recordingId =
                              activity.metadata?.recording_id || activity.id;
                            if (recordingId) {
                              setSelectedTemplate("quick_recap");
                              handleViewRecordingDetail(recordingId);
                            }
                          }}
                          className="px-3 py-1.5 bg-orange-600 text-white text-sm rounded hover:bg-orange-700 transition-colors"
                        >
                          ⚡ Quick Recap
                        </button>
                        {activity.metadata?.webViewLink && (
                          <a
                            href={activity.metadata.webViewLink}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="px-3 py-1.5 bg-gray-600 text-white text-sm rounded hover:bg-gray-700 transition-colors"
                          >
                            🔗 Google Docs
                          </a>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>

      {data?.activities.length === 0 && (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">
            No activities found
          </h3>
          <p className="mt-1 text-sm text-gray-500">
            No activities match the current filters.
          </p>
        </div>
      )}

      {/* Meeting Analysis Modal (for Recordings) */}
      {showTranscript && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-5xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold text-gray-900">
                    📹{" "}
                    {translations[`recording_name_${recordingDetail?.id || meetingAnalysis?.id}`]?.text ||
                      recordingDetail?.name ||
                      meetingAnalysis?.meeting_title ||
                      "Loading..."}
                  </h2>
                  {(recordingDetail?.name || meetingAnalysis?.meeting_title) && (
                    <div className="flex gap-1">
                      <button
                        onClick={() => {
                          const recordingId = recordingDetail?.id || meetingAnalysis?.id;
                          const name = recordingDetail?.name || meetingAnalysis?.meeting_title;
                          if (recordingId && name) {
                            handleTranslate(`recording_name_${recordingId}`, name, "en");
                          }
                        }}
                        disabled={translating === `recording_name_${recordingDetail?.id || meetingAnalysis?.id}`}
                        className={`text-xs px-2 py-1 rounded transition-colors ${
                          translations[`recording_name_${recordingDetail?.id || meetingAnalysis?.id}`]?.lang === "en"
                            ? "bg-blue-600 text-white"
                            : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                        } ${
                          translating === `recording_name_${recordingDetail?.id || meetingAnalysis?.id}`
                            ? "opacity-50 cursor-wait"
                            : ""
                        }`}
                      >
                        EN
                      </button>
                      <button
                        onClick={() => {
                          const recordingId = recordingDetail?.id || meetingAnalysis?.id;
                          const name = recordingDetail?.name || meetingAnalysis?.meeting_title;
                          if (recordingId && name) {
                            handleTranslate(`recording_name_${recordingId}`, name, "ko");
                          }
                        }}
                        disabled={translating === `recording_name_${recordingDetail?.id || meetingAnalysis?.id}`}
                        className={`text-xs px-2 py-1 rounded transition-colors ${
                          translations[`recording_name_${recordingDetail?.id || meetingAnalysis?.id}`]?.lang === "ko"
                            ? "bg-blue-600 text-white"
                            : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                        } ${
                          translating === `recording_name_${recordingDetail?.id || meetingAnalysis?.id}`
                            ? "opacity-50 cursor-wait"
                            : ""
                        }`}
                      >
                        KR
                      </button>
                    </div>
                  )}
                </div>
                {translations[`recording_name_${recordingDetail?.id || meetingAnalysis?.id}`] && (
                  <p className="text-xs text-gray-400 mt-1">
                    🌐 Translated to{" "}
                    {translations[`recording_name_${recordingDetail?.id || meetingAnalysis?.id}`].lang === "ko"
                      ? "Korean"
                      : "English"}
                  </p>
                )}
                {(recordingDetail || meetingAnalysis) && (
                  <p className="text-sm text-gray-500 mt-1">
                    {recordingDetail?.created_by ||
                      meetingAnalysis?.created_by ||
                      "Unknown"}{" "}
                    •{" "}
                    {formatTimestamp(
                      recordingDetail?.createdTime ||
                        meetingAnalysis?.meeting_date,
                      "MMM dd, yyyy HH:mm"
                    )}
                    {meetingAnalysis?.participants && (
                      <span className="ml-2">
                        • 👥 {meetingAnalysis.participants.join(", ")}
                      </span>
                    )}
                  </p>
                )}
              </div>
              <button
                onClick={() => {
                  setShowTranscript(false);
                  setRecordingDetail(null);
                  setMeetingAnalysis(null);
                  setSelectedTemplate("default");
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg
                  className="w-6 h-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            {/* Template Tabs (if AI analysis available) */}
            {meetingAnalysis?.analyses &&
              Object.keys(meetingAnalysis.analyses).length > 0 && (
                <div className="px-6 py-2 border-b border-gray-200 bg-gray-50">
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => setSelectedTemplate("transcript")}
                      className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
                        selectedTemplate === "transcript"
                          ? "bg-blue-600 text-white"
                          : "bg-white text-gray-600 hover:bg-gray-100 border border-gray-300"
                      }`}
                    >
                      📝 Transcript
                    </button>
                    {Object.keys(meetingAnalysis.analyses).map((template) => (
                      <button
                        key={template}
                        onClick={() => setSelectedTemplate(template)}
                        className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
                          selectedTemplate === template
                            ? "bg-blue-600 text-white"
                            : "bg-white text-gray-600 hover:bg-gray-100 border border-gray-300"
                        }`}
                      >
                        {template === "default" && "📊 Default"}
                        {template === "team_collaboration" &&
                          "🤝 Collaboration"}
                        {template === "action_items" && "✅ Actions"}
                        {template === "knowledge_base" && "📚 Knowledge"}
                        {template === "decision_log" && "📋 Decisions"}
                        {template === "quick_recap" && "⚡ Quick Recap"}
                        {template === "meeting_context" && "🎯 Context"}
                      </button>
                    ))}
                  </div>
                </div>
              )}

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6">
              {detailLoading || analysisLoading ? (
                <div className="flex items-center justify-center h-64">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
                </div>
              ) : selectedTemplate === "transcript" ? (
                // Show transcript only when explicitly selected
                <div className="prose max-w-none">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-medium text-gray-700">Transcript</h3>
                    {(meetingAnalysis?.content || recordingDetail?.content) && (
                      <div className="flex gap-1">
                        <button
                          onClick={() => {
                            const recordingId = recordingDetail?.id || meetingAnalysis?.id;
                            const content = meetingAnalysis?.content || recordingDetail?.content;
                            if (recordingId && content) {
                              handleTranslate(`recording_transcript_${recordingId}`, content, "en");
                            }
                          }}
                          disabled={translating === `recording_transcript_${recordingDetail?.id || meetingAnalysis?.id}`}
                          className={`text-xs px-2 py-1 rounded transition-colors ${
                            translations[`recording_transcript_${recordingDetail?.id || meetingAnalysis?.id}`]?.lang === "en"
                              ? "bg-blue-600 text-white"
                              : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                          } ${
                            translating === `recording_transcript_${recordingDetail?.id || meetingAnalysis?.id}`
                              ? "opacity-50 cursor-wait"
                              : ""
                          }`}
                        >
                          EN
                        </button>
                        <button
                          onClick={() => {
                            const recordingId = recordingDetail?.id || meetingAnalysis?.id;
                            const content = meetingAnalysis?.content || recordingDetail?.content;
                            if (recordingId && content) {
                              handleTranslate(`recording_transcript_${recordingId}`, content, "ko");
                            }
                          }}
                          disabled={translating === `recording_transcript_${recordingDetail?.id || meetingAnalysis?.id}`}
                          className={`text-xs px-2 py-1 rounded transition-colors ${
                            translations[`recording_transcript_${recordingDetail?.id || meetingAnalysis?.id}`]?.lang === "ko"
                              ? "bg-blue-600 text-white"
                              : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                          } ${
                            translating === `recording_transcript_${recordingDetail?.id || meetingAnalysis?.id}`
                              ? "opacity-50 cursor-wait"
                              : ""
                          }`}
                        >
                          KR
                        </button>
                      </div>
                    )}
                  </div>
                  {translations[`recording_transcript_${recordingDetail?.id || meetingAnalysis?.id}`] && (
                    <p className="text-xs text-gray-400 mb-2">
                      🌐 Translated to{" "}
                      {translations[`recording_transcript_${recordingDetail?.id || meetingAnalysis?.id}`].lang === "ko"
                        ? "Korean"
                        : "English"}
                    </p>
                  )}
                  <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans bg-gray-50 p-4 rounded">
                    {translations[`recording_transcript_${recordingDetail?.id || meetingAnalysis?.id}`]?.text ||
                      meetingAnalysis?.content ||
                      recordingDetail?.content ||
                      "No transcript available"}
                  </pre>
                </div>
              ) : !meetingAnalysis?.analyses ||
                Object.keys(meetingAnalysis.analyses).length === 0 ? (
                // No AI analyses available
                <div className="flex flex-col items-center justify-center h-64 text-gray-500">
                  <svg
                    className="w-16 h-16 mb-4 text-gray-300"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                    />
                  </svg>
                  <p className="text-lg font-medium">
                    No AI Analysis Available
                  </p>
                  <p className="text-sm mt-1">
                    This recording has not been processed by AI yet.
                  </p>
                  <button
                    onClick={() => setSelectedTemplate("transcript")}
                    className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    📄 View Transcript Instead
                  </button>
                </div>
              ) : meetingAnalysis?.analyses[selectedTemplate] ? (
                // Show AI analysis
                <div className="space-y-4">
                  {/* Analysis Status */}
                  <div className="flex items-center gap-2 text-sm text-gray-500">
                    <span
                      className={`px-2 py-0.5 rounded ${
                        meetingAnalysis.analyses[selectedTemplate].status ===
                        "success"
                          ? "bg-green-100 text-green-700"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {meetingAnalysis.analyses[selectedTemplate].status}
                    </span>
                    <span>•</span>
                    <span>
                      🤖{" "}
                      {meetingAnalysis.analyses[selectedTemplate].model_used ||
                        "Gemini"}
                    </span>
                    {meetingAnalysis.analyses[selectedTemplate]
                      .total_statements && (
                      <>
                        <span>•</span>
                        <span>
                          💬{" "}
                          {
                            meetingAnalysis.analyses[selectedTemplate]
                              .total_statements
                          }{" "}
                          statements
                        </span>
                      </>
                    )}
                  </div>

                  {/* Participant Stats */}
                  {meetingAnalysis.analyses[selectedTemplate]
                    .participant_stats && (
                    <div className="bg-blue-50 rounded-lg p-4">
                      <h4 className="font-medium text-blue-900 mb-2">
                        👥 Participant Stats
                      </h4>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {Object.entries(
                          meetingAnalysis.analyses[selectedTemplate]
                            .participant_stats
                        ).map(([name, stats]: [string, any]) => (
                          <div
                            key={name}
                            className="bg-white rounded p-2 text-sm"
                          >
                            <p className="font-medium text-gray-900">{name}</p>
                            <p className="text-gray-500">
                              {stats.speak_count || 0} speaks •{" "}
                              {stats.total_words || 0} words
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Analysis Content */}
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="font-medium text-gray-900">
                        {selectedTemplate === "default" && "📊 Analysis"}
                        {selectedTemplate === "team_collaboration" &&
                          "🤝 Team Collaboration Analysis"}
                        {selectedTemplate === "action_items" && "✅ Action Items"}
                        {selectedTemplate === "knowledge_base" &&
                          "📚 Knowledge Base Entry"}
                        {selectedTemplate === "decision_log" && "📋 Decision Log"}
                        {selectedTemplate === "quick_recap" && "⚡ Quick Recap"}
                        {selectedTemplate === "meeting_context" &&
                          "🎯 Meeting Context"}
                      </h4>
                      {meetingAnalysis.analyses[selectedTemplate].analysis && (
                        <div className="flex gap-1">
                          <button
                            onClick={() => {
                              const recordingId = recordingDetail?.id || meetingAnalysis?.id;
                              const analysisText = meetingAnalysis.analyses[selectedTemplate].analysis;
                              if (recordingId && analysisText) {
                                handleTranslate(
                                  `recording_analysis_${recordingId}_${selectedTemplate}`,
                                  analysisText,
                                  "en"
                                );
                              }
                            }}
                            disabled={
                              translating ===
                              `recording_analysis_${recordingDetail?.id || meetingAnalysis?.id}_${selectedTemplate}`
                            }
                            className={`text-xs px-2 py-1 rounded transition-colors ${
                              translations[
                                `recording_analysis_${recordingDetail?.id || meetingAnalysis?.id}_${selectedTemplate}`
                              ]?.lang === "en"
                                ? "bg-blue-600 text-white"
                                : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                            } ${
                              translating ===
                              `recording_analysis_${recordingDetail?.id || meetingAnalysis?.id}_${selectedTemplate}`
                                ? "opacity-50 cursor-wait"
                                : ""
                            }`}
                          >
                            EN
                          </button>
                          <button
                            onClick={() => {
                              const recordingId = recordingDetail?.id || meetingAnalysis?.id;
                              const analysisText = meetingAnalysis.analyses[selectedTemplate].analysis;
                              if (recordingId && analysisText) {
                                handleTranslate(
                                  `recording_analysis_${recordingId}_${selectedTemplate}`,
                                  analysisText,
                                  "ko"
                                );
                              }
                            }}
                            disabled={
                              translating ===
                              `recording_analysis_${recordingDetail?.id || meetingAnalysis?.id}_${selectedTemplate}`
                            }
                            className={`text-xs px-2 py-1 rounded transition-colors ${
                              translations[
                                `recording_analysis_${recordingDetail?.id || meetingAnalysis?.id}_${selectedTemplate}`
                              ]?.lang === "ko"
                                ? "bg-blue-600 text-white"
                                : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                            } ${
                              translating ===
                              `recording_analysis_${recordingDetail?.id || meetingAnalysis?.id}_${selectedTemplate}`
                                ? "opacity-50 cursor-wait"
                                : ""
                            }`}
                          >
                            KR
                          </button>
                        </div>
                      )}
                    </div>
                    {translations[
                      `recording_analysis_${recordingDetail?.id || meetingAnalysis?.id}_${selectedTemplate}`
                    ] && (
                      <p className="text-xs text-gray-400 mb-2">
                        🌐 Translated to{" "}
                        {translations[
                          `recording_analysis_${recordingDetail?.id || meetingAnalysis?.id}_${selectedTemplate}`
                        ].lang === "ko"
                          ? "Korean"
                          : "English"}
                      </p>
                    )}
                    <div className="prose max-w-none">
                      <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans">
                        {translations[
                          `recording_analysis_${recordingDetail?.id || meetingAnalysis?.id}_${selectedTemplate}`
                        ]?.text ||
                          meetingAnalysis.analyses[selectedTemplate].analysis ||
                          "No analysis available"}
                      </pre>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-gray-500 text-center">
                  No content available
                </p>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-gray-200 flex justify-between items-center">
              <div className="text-sm text-gray-500">
                {meetingAnalysis?.analyses && (
                  <span>
                    {Object.keys(meetingAnalysis.analyses).length} AI analyses
                    available
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                {(recordingDetail?.webViewLink ||
                  meetingAnalysis?.web_view_link) && (
                  <a
                    href={
                      recordingDetail?.webViewLink ||
                      meetingAnalysis?.web_view_link
                    }
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Open in Google Docs →
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Daily Analysis Detail Modal */}
      {showDailyAnalysisDetail && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold text-gray-900">
                    Daily Analysis - {selectedDailyAnalysis?.target_date || "Loading..."}
                  </h2>
                  {selectedDailyAnalysis?.target_date && (
                    <div className="flex gap-1">
                      <button
                        onClick={() => {
                          const dateId = selectedDailyAnalysis.target_date;
                          const title = `Daily Analysis - ${selectedDailyAnalysis.target_date}`;
                          if (dateId && title) {
                            handleTranslate(`daily_analysis_title_${dateId}`, title, "en");
                          }
                        }}
                        disabled={translating === `daily_analysis_title_${selectedDailyAnalysis?.target_date}`}
                        className={`text-xs px-2 py-1 rounded transition-colors ${
                          translations[`daily_analysis_title_${selectedDailyAnalysis?.target_date}`]?.lang === "en"
                            ? "bg-blue-600 text-white"
                            : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                        } ${
                          translating === `daily_analysis_title_${selectedDailyAnalysis?.target_date}`
                            ? "opacity-50 cursor-wait"
                            : ""
                        }`}
                      >
                        EN
                      </button>
                      <button
                        onClick={() => {
                          const dateId = selectedDailyAnalysis.target_date;
                          const title = `Daily Analysis - ${selectedDailyAnalysis.target_date}`;
                          if (dateId && title) {
                            handleTranslate(`daily_analysis_title_${dateId}`, title, "ko");
                          }
                        }}
                        disabled={translating === `daily_analysis_title_${selectedDailyAnalysis?.target_date}`}
                        className={`text-xs px-2 py-1 rounded transition-colors ${
                          translations[`daily_analysis_title_${selectedDailyAnalysis?.target_date}`]?.lang === "ko"
                            ? "bg-blue-600 text-white"
                            : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                        } ${
                          translating === `daily_analysis_title_${selectedDailyAnalysis?.target_date}`
                            ? "opacity-50 cursor-wait"
                            : ""
                        }`}
                      >
                        KR
                      </button>
    </div>
                  )}
                </div>
                {translations[`daily_analysis_title_${selectedDailyAnalysis?.target_date}`] && (
                  <p className="text-xs text-gray-400 mt-1">
                    🌐 Translated to{" "}
                    {translations[`daily_analysis_title_${selectedDailyAnalysis?.target_date}`].lang === "ko"
                      ? "Korean"
                      : "English"}
                  </p>
                )}
                {selectedDailyAnalysis && (
                  <p className="text-sm text-gray-500 mt-1">
                    {selectedDailyAnalysis.meeting_count} meetings •{" "}
                    {selectedDailyAnalysis.total_meeting_time} • {selectedDailyAnalysis.model_used}
                  </p>
                )}
              </div>
              <button
                onClick={() => {
                  setShowDailyAnalysisDetail(false);
                  setSelectedDailyAnalysis(null);
                  setDailyAnalysisTab("overview");
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg
                  className="w-6 h-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            {/* Tab Navigation */}
            {selectedDailyAnalysis?.analysis && (
              <div className="px-6 py-2 border-b border-gray-200 bg-gray-50">
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => setDailyAnalysisTab("overview")}
                    className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
                      dailyAnalysisTab === "overview"
                        ? "bg-blue-600 text-white"
                        : "bg-white text-gray-600 hover:bg-gray-100 border border-gray-300"
                    }`}
                  >
                    📊 Overview
                  </button>
                  {selectedDailyAnalysis.analysis?.summary?.topics &&
                    selectedDailyAnalysis.analysis.summary.topics.length > 0 && (
                      <button
                        onClick={() => setDailyAnalysisTab("topics")}
                        className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
                          dailyAnalysisTab === "topics"
                            ? "bg-blue-600 text-white"
                            : "bg-white text-gray-600 hover:bg-gray-100 border border-gray-300"
                        }`}
                      >
                        💬 Topics
                      </button>
                    )}
                  {selectedDailyAnalysis.analysis?.summary?.key_decisions &&
                    selectedDailyAnalysis.analysis.summary.key_decisions.length > 0 && (
                      <button
                        onClick={() => setDailyAnalysisTab("decisions")}
                        className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
                          dailyAnalysisTab === "decisions"
                            ? "bg-blue-600 text-white"
                            : "bg-white text-gray-600 hover:bg-gray-100 border border-gray-300"
                        }`}
                      >
                        📋 Decisions
                      </button>
                    )}
                  {selectedDailyAnalysis.analysis?.summary?.major_achievements &&
                    selectedDailyAnalysis.analysis.summary.major_achievements.length > 0 && (
                      <button
                        onClick={() => setDailyAnalysisTab("achievements")}
                        className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
                          dailyAnalysisTab === "achievements"
                            ? "bg-blue-600 text-white"
                            : "bg-white text-gray-600 hover:bg-gray-100 border border-gray-300"
                        }`}
                      >
                        🏆 Achievements
                      </button>
                    )}
                  {selectedDailyAnalysis.analysis?.summary?.common_issues &&
                    selectedDailyAnalysis.analysis.summary.common_issues.length > 0 && (
                      <button
                        onClick={() => setDailyAnalysisTab("issues")}
                        className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
                          dailyAnalysisTab === "issues"
                            ? "bg-blue-600 text-white"
                            : "bg-white text-gray-600 hover:bg-gray-100 border border-gray-300"
                        }`}
                      >
                        ⚠️ Issues
                      </button>
                    )}
                  {selectedDailyAnalysis.analysis?.participants &&
                    selectedDailyAnalysis.analysis.participants.length > 0 && (
                      <button
                        onClick={() => setDailyAnalysisTab("participants")}
                        className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
                          dailyAnalysisTab === "participants"
                            ? "bg-blue-600 text-white"
                            : "bg-white text-gray-600 hover:bg-gray-100 border border-gray-300"
                        }`}
                      >
                        👥 Participants
                      </button>
                    )}
                  {selectedDailyAnalysis.analysis?.full_analysis_text && (
                    <button
                      onClick={() => setDailyAnalysisTab("full")}
                      className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
                        dailyAnalysisTab === "full"
                          ? "bg-blue-600 text-white"
                          : "bg-white text-gray-600 hover:bg-gray-100 border border-gray-300"
                      }`}
                    >
                      📄 Full Analysis
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6">
              {dailyAnalysisLoading ? (
                <div className="flex items-center justify-center h-full">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
                </div>
              ) : selectedDailyAnalysis?.analysis ? (
                <div className="space-y-6">
                  {/* Overview Tab */}
                  {dailyAnalysisTab === "overview" &&
                    selectedDailyAnalysis.analysis?.summary?.overview && (
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-lg font-semibold text-gray-900">
                          Overview
                        </h3>
                        <div className="flex gap-1">
                          <button
                            onClick={() => {
                              const dateId = selectedDailyAnalysis.target_date;
                              const overviewText = JSON.stringify(selectedDailyAnalysis.analysis.summary.overview);
                              if (dateId && overviewText) {
                                handleTranslate(`daily_analysis_overview_${dateId}`, overviewText, "en");
                              }
                            }}
                            disabled={translating === `daily_analysis_overview_${selectedDailyAnalysis?.target_date}`}
                            className={`text-xs px-2 py-1 rounded transition-colors ${
                              translations[`daily_analysis_overview_${selectedDailyAnalysis?.target_date}`]?.lang === "en"
                                ? "bg-blue-600 text-white"
                                : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                            } ${
                              translating === `daily_analysis_overview_${selectedDailyAnalysis?.target_date}`
                                ? "opacity-50 cursor-wait"
                                : ""
                            }`}
                          >
                            EN
                          </button>
                          <button
                            onClick={() => {
                              const dateId = selectedDailyAnalysis.target_date;
                              const overviewText = JSON.stringify(selectedDailyAnalysis.analysis.summary.overview);
                              if (dateId && overviewText) {
                                handleTranslate(`daily_analysis_overview_${dateId}`, overviewText, "ko");
                              }
                            }}
                            disabled={translating === `daily_analysis_overview_${selectedDailyAnalysis?.target_date}`}
                            className={`text-xs px-2 py-1 rounded transition-colors ${
                              translations[`daily_analysis_overview_${selectedDailyAnalysis?.target_date}`]?.lang === "ko"
                                ? "bg-blue-600 text-white"
                                : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                            } ${
                              translating === `daily_analysis_overview_${selectedDailyAnalysis?.target_date}`
                                ? "opacity-50 cursor-wait"
                                : ""
                            }`}
                          >
                            KR
                          </button>
                        </div>
                      </div>
                      {translations[`daily_analysis_overview_${selectedDailyAnalysis?.target_date}`] && (
                        <p className="text-xs text-gray-400 mb-2">
                          🌐 Translated to{" "}
                          {translations[`daily_analysis_overview_${selectedDailyAnalysis?.target_date}`].lang === "ko"
                            ? "Korean"
                            : "English"}
                        </p>
                      )}
                      
                      {translations[`daily_analysis_overview_${selectedDailyAnalysis?.target_date}`]?.text ? (
                        <div className="bg-gray-50 rounded-lg p-4 whitespace-pre-wrap text-sm text-gray-700 font-sans">
                          {translations[`daily_analysis_overview_${selectedDailyAnalysis?.target_date}`]?.text}
                        </div>
                      ) : (
                        <div className="bg-gray-50 rounded-lg p-4">
                          <div className="grid grid-cols-3 gap-4 mb-4">
                            <div>
                              <div className="text-sm text-gray-500">Meetings</div>
                              <div className="text-xl font-bold text-gray-900">
                                {selectedDailyAnalysis.analysis.summary.overview.meeting_count}
                              </div>
                            </div>
                            <div>
                              <div className="text-sm text-gray-500">Total Time</div>
                              <div className="text-xl font-bold text-gray-900">
                                {selectedDailyAnalysis.analysis.summary.overview.total_time}
                              </div>
                            </div>
                            <div>
                              <div className="text-sm text-gray-500">Main Topics</div>
                              <div className="text-xl font-bold text-gray-900">
                                {selectedDailyAnalysis.analysis.summary.topics?.length || 0}
                              </div>
                            </div>
                          </div>
                        {/* Meeting Titles */}
                        {selectedDailyAnalysis.meeting_titles &&
                          selectedDailyAnalysis.meeting_titles.length > 0 && (
                            <div className="mb-4">
                              <div className="text-sm text-gray-500 mb-2">
                                Meeting Titles:
                              </div>
                              <div className="flex flex-wrap gap-2">
                                {selectedDailyAnalysis.meeting_titles.map(
                                  (title: string, idx: number) => (
                                    <span
                                      key={idx}
                                      className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded"
                                    >
                                      {title}
                                    </span>
                                  )
                                )}
                              </div>
                            </div>
                          )}
                        {/* Main Topics - Use topics from Topics tab */}
                        {selectedDailyAnalysis.analysis.summary.topics &&
                          selectedDailyAnalysis.analysis.summary.topics.length > 0 && (
                            <div className="mb-4">
                              <div className="text-sm text-gray-500 mb-2">
                                Main Topics:
                              </div>
                              <div className="flex flex-wrap gap-2">
                                {selectedDailyAnalysis.analysis.summary.topics.map(
                                  (topic: any, idx: number) => (
                                    <button
                                      key={idx}
                                      onClick={() => {
                                        // Switch to topics tab
                                        setDailyAnalysisTab("topics");
                                        // Scroll to the specific topic after a short delay
                                        setTimeout(() => {
                                          const topicElement = document.getElementById(`topic-${idx}`);
                                          if (topicElement) {
                                            topicElement.scrollIntoView({ behavior: "smooth", block: "start" });
                                            // Highlight the topic briefly
                                            topicElement.classList.add("ring-2", "ring-blue-500");
                                            setTimeout(() => {
                                              topicElement.classList.remove("ring-2", "ring-blue-500");
                                            }, 2000);
                                          }
                                        }, 100);
                                      }}
                                      className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded hover:bg-blue-200 transition-colors cursor-pointer"
                                    >
                                      {topic.topic}
                                    </button>
                                  )
                                )}
                              </div>
                            </div>
                          )}
                        {/* Participants Summary */}
                        {selectedDailyAnalysis.analysis.participants &&
                          selectedDailyAnalysis.analysis.participants.length > 0 && (
                            <div>
                              <div className="text-sm text-gray-500 mb-2">
                                Participants ({(() => {
                                  // Filter and sort participants
                                  let filtered = [...selectedDailyAnalysis.analysis.participants];
                                  
                                  // Apply member filter if set
                                  if (memberFilter) {
                                    filtered = filtered.filter((p: any) =>
                                      p.name?.toLowerCase().includes(memberFilter.toLowerCase())
                                    );
                                  }
                                  
                                  // Sort alphabetically by name
                                  filtered.sort((a: any, b: any) => {
                                    const nameA = (a.name || "").toLowerCase();
                                    const nameB = (b.name || "").toLowerCase();
                                    return nameA.localeCompare(nameB);
                                  });
                                  
                                  return filtered.length;
                                })()}):
                              </div>
                              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                                {(() => {
                                  // Filter and sort participants
                                  let filtered = [...selectedDailyAnalysis.analysis.participants];
                                  
                                  // Apply member filter if set
                                  if (memberFilter) {
                                    filtered = filtered.filter((p: any) =>
                                      p.name?.toLowerCase().includes(memberFilter.toLowerCase())
                                    );
                                  }
                                  
                                  // Sort alphabetically by name
                                  filtered.sort((a: any, b: any) => {
                                    const nameA = (a.name || "").toLowerCase();
                                    const nameB = (b.name || "").toLowerCase();
                                    return nameA.localeCompare(nameB);
                                  });
                                  
                                  return filtered;
                                })().map(
                                  (participant: any, idx: number) => (
                                    <div
                                      key={idx}
                                      className="bg-white rounded-lg p-2 border border-gray-200"
                                    >
                                      <div className="font-medium text-sm text-gray-900">
                                        {participant.name}
                                      </div>
                                      <div className="text-xs text-gray-500">
                                        {participant.speaking_time} ({participant.speaking_percentage?.toFixed(1) || 0}%)
                                      </div>
                                    </div>
                                  )
                                )}
                              </div>
                            </div>
                          )}
                      </div>
                    )}
                  </div>
                )}

                  {/* Topics Tab */}
                  {dailyAnalysisTab === "topics" &&
                    selectedDailyAnalysis.analysis?.summary?.topics &&
                    selectedDailyAnalysis.analysis.summary.topics.length > 0 && (
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="text-lg font-semibold text-gray-900">
                            Topics
                          </h3>
                          <div className="flex gap-1">
                            <button
                              onClick={async () => {
                                const dateId = selectedDailyAnalysis.target_date;
                                const topics = selectedDailyAnalysis.analysis.summary.topics;
                                
                                // Collect all translation promises for parallel execution
                                const translationPromises: Promise<void>[] = [];
                                
                                topics.forEach((topic: any, idx: number) => {
                                  const topicKey = `daily_analysis_topic_${dateId}_${idx}`;
                                  
                                  if (topic.key_discussions?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${topicKey}_key_discussions`, topic.key_discussions.join("\n"), "en", "ko")
                                    );
                                  }
                                  if (topic.key_decisions?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${topicKey}_key_decisions`, topic.key_decisions.join("\n"), "en", "ko")
                                    );
                                  }
                                  if (topic.progress?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${topicKey}_progress`, topic.progress.join("\n"), "en", "ko")
                                    );
                                  }
                                  if (topic.issues?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${topicKey}_issues`, topic.issues.join("\n"), "en", "ko")
                                    );
                                  }
                                });
                                
                                // Execute all translations in parallel
                                await Promise.all(translationPromises);
                              }}
                              disabled={Array.from(translatingSet).some(key => key.startsWith("daily_analysis_topic_"))}
                              className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700 transition-colors disabled:opacity-50 disabled:cursor-wait"
                            >
                              EN
                            </button>
                            <button
                              onClick={async () => {
                                const dateId = selectedDailyAnalysis.target_date;
                                const topics = selectedDailyAnalysis.analysis.summary.topics;
                                
                                // Collect all translation promises for parallel execution
                                const translationPromises: Promise<void>[] = [];
                                
                                topics.forEach((topic: any, idx: number) => {
                                  const topicKey = `daily_analysis_topic_${dateId}_${idx}`;
                                  
                                  if (topic.key_discussions?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${topicKey}_key_discussions`, topic.key_discussions.join("\n"), "ko", "en")
                                    );
                                  }
                                  if (topic.key_decisions?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${topicKey}_key_decisions`, topic.key_decisions.join("\n"), "ko", "en")
                                    );
                                  }
                                  if (topic.progress?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${topicKey}_progress`, topic.progress.join("\n"), "ko", "en")
                                    );
                                  }
                                  if (topic.issues?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${topicKey}_issues`, topic.issues.join("\n"), "ko", "en")
                                    );
                                  }
                                });
                                
                                // Execute all translations in parallel
                                await Promise.all(translationPromises);
                              }}
                              disabled={Array.from(translatingSet).some(key => key.startsWith("daily_analysis_topic_"))}
                              className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700 transition-colors disabled:opacity-50 disabled:cursor-wait"
                            >
                              KR
                            </button>
                          </div>
                        </div>
                        <div className="space-y-4">
                          {selectedDailyAnalysis.analysis.summary.topics.map(
                            (topic: any, idx: number) => {
                              const dateId = selectedDailyAnalysis.target_date;
                              const topicKey = `daily_analysis_topic_${dateId}_${idx}`;
                              
                              // Helper function to get translated text for a field
                              const getTranslatedField = (fieldName: string, originalArray: string[]) => {
                                const translationKey = `${topicKey}_${fieldName}`;
                                const translatedText = translations[translationKey]?.text;
                                
                                if (translatedText && translatedText.trim()) {
                                  const translatedItems = translatedText.split("\n").filter((item: string) => item.trim());
                                  if (translatedItems.length > 0) {
                                    return translatedItems;
                                  }
                                }
                                return originalArray;
                              };
                              
                              return (
                                <div
                                  key={idx}
                                  id={`topic-${idx}`}
                                  className="border border-gray-200 rounded-lg p-4 transition-all"
                                >
                                  <h4 className="font-semibold text-gray-900 mb-2">
                                    {topic.topic}
                                  </h4>
                                  {topic.key_discussions &&
                                    topic.key_discussions.length > 0 && (
                                      <div className="mb-2">
                                        <div className="text-sm text-gray-500 mb-1">
                                          Key Discussions:
                                        </div>
                                        <ul className="list-disc list-inside text-sm text-gray-700">
                                          {getTranslatedField("key_discussions", topic.key_discussions).map((disc: string, i: number) => (
                                            <li key={i}>{disc}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                  {topic.key_decisions &&
                                    topic.key_decisions.length > 0 && (
                                      <div className="mb-2">
                                        <div className="text-sm text-gray-500 mb-1">
                                          Key Decisions:
                                        </div>
                                        <ul className="list-disc list-inside text-sm text-gray-700">
                                          {getTranslatedField("key_decisions", topic.key_decisions).map((dec: string, i: number) => (
                                            <li key={i}>{dec}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                  {topic.progress &&
                                    topic.progress.length > 0 && (
                                      <div className="mb-2">
                                        <div className="text-sm text-gray-500 mb-1">
                                          Progress:
                                        </div>
                                        <ul className="list-disc list-inside text-sm text-gray-700">
                                          {getTranslatedField("progress", topic.progress).map((prog: string, i: number) => (
                                            <li key={i}>{prog}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                  {topic.issues &&
                                    topic.issues.length > 0 && (
                                      <div className="mb-2">
                                        <div className="text-sm text-gray-500 mb-1">
                                          Issues:
                                        </div>
                                        <ul className="list-disc list-inside text-sm text-gray-700">
                                          {getTranslatedField("issues", topic.issues).map((issue: string, i: number) => (
                                            <li key={i}>{issue}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                </div>
                              );
                            }
                          )}
                        </div>
                      </div>
                    )}

                  {/* Decisions Tab */}
                  {dailyAnalysisTab === "decisions" &&
                    selectedDailyAnalysis.analysis?.summary?.key_decisions &&
                    selectedDailyAnalysis.analysis.summary.key_decisions.length > 0 && (
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="text-lg font-semibold text-gray-900">
                            Key Decisions
                          </h3>
                          <div className="flex gap-1">
                            <button
                              onClick={() => {
                                const dateId = selectedDailyAnalysis.target_date;
                                const decisionsText = selectedDailyAnalysis.analysis.summary.key_decisions.join("\n");
                                if (dateId && decisionsText) {
                                  handleTranslate(`daily_analysis_decisions_${dateId}`, decisionsText, "en");
                                }
                              }}
                              disabled={translating === `daily_analysis_decisions_${selectedDailyAnalysis?.target_date}`}
                              className={`text-xs px-2 py-1 rounded transition-colors ${
                                translations[`daily_analysis_decisions_${selectedDailyAnalysis?.target_date}`]?.lang === "en"
                                  ? "bg-blue-600 text-white"
                                  : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                              } ${
                                translating === `daily_analysis_decisions_${selectedDailyAnalysis?.target_date}`
                                  ? "opacity-50 cursor-wait"
                                  : ""
                              }`}
                            >
                              EN
                            </button>
                            <button
                              onClick={() => {
                                const dateId = selectedDailyAnalysis.target_date;
                                const decisionsText = selectedDailyAnalysis.analysis.summary.key_decisions.join("\n");
                                if (dateId && decisionsText) {
                                  handleTranslate(`daily_analysis_decisions_${dateId}`, decisionsText, "ko");
                                }
                              }}
                              disabled={translating === `daily_analysis_decisions_${selectedDailyAnalysis?.target_date}`}
                              className={`text-xs px-2 py-1 rounded transition-colors ${
                                translations[`daily_analysis_decisions_${selectedDailyAnalysis?.target_date}`]?.lang === "ko"
                                  ? "bg-blue-600 text-white"
                                  : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                              } ${
                                translating === `daily_analysis_decisions_${selectedDailyAnalysis?.target_date}`
                                  ? "opacity-50 cursor-wait"
                                  : ""
                              }`}
                            >
                              KR
                            </button>
                          </div>
                        </div>
                        {translations[`daily_analysis_decisions_${selectedDailyAnalysis?.target_date}`] && (
                          <p className="text-xs text-gray-400 mb-2">
                            🌐 Translated to{" "}
                            {translations[`daily_analysis_decisions_${selectedDailyAnalysis?.target_date}`].lang === "ko"
                              ? "Korean"
                              : "English"}
                          </p>
                        )}
                        <ul className="list-disc list-inside space-y-1 text-sm text-gray-700">
                          {(() => {
                            const translationKey = `daily_analysis_decisions_${selectedDailyAnalysis?.target_date}`;
                            const translatedText = translations[translationKey]?.text;
                            
                            if (translatedText && translatedText.trim()) {
                              // Split by newline and filter out empty lines
                              const translatedItems = translatedText.split("\n").filter((item: string) => item.trim());
                              if (translatedItems.length > 0) {
                                return translatedItems.map((decision: string, idx: number) => (
                                  <li key={idx}>{decision.trim()}</li>
                                ));
                              }
                            }
                            
                            // Fall back to original
                            return selectedDailyAnalysis.analysis.summary.key_decisions.map(
                              (decision: string, idx: number) => (
                                <li key={idx}>{decision}</li>
                              )
                            );
                          })()}
                        </ul>
                      </div>
                    )}

                  {/* Achievements Tab */}
                  {dailyAnalysisTab === "achievements" &&
                    selectedDailyAnalysis.analysis?.summary?.major_achievements &&
                    selectedDailyAnalysis.analysis.summary.major_achievements.length > 0 && (
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="text-lg font-semibold text-gray-900">
                            Major Achievements
                          </h3>
                          <div className="flex gap-1">
                            <button
                              onClick={() => {
                                const dateId = selectedDailyAnalysis.target_date;
                                const achievementsText = selectedDailyAnalysis.analysis.summary.major_achievements.join("\n");
                                if (dateId && achievementsText) {
                                  handleTranslate(`daily_analysis_achievements_${dateId}`, achievementsText, "en");
                                }
                              }}
                              disabled={translating === `daily_analysis_achievements_${selectedDailyAnalysis?.target_date}`}
                              className={`text-xs px-2 py-1 rounded transition-colors ${
                                translations[`daily_analysis_achievements_${selectedDailyAnalysis?.target_date}`]?.lang === "en"
                                  ? "bg-blue-600 text-white"
                                  : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                              } ${
                                translating === `daily_analysis_achievements_${selectedDailyAnalysis?.target_date}`
                                  ? "opacity-50 cursor-wait"
                                  : ""
                              }`}
                            >
                              EN
                            </button>
                            <button
                              onClick={() => {
                                const dateId = selectedDailyAnalysis.target_date;
                                const achievementsText = selectedDailyAnalysis.analysis.summary.major_achievements.join("\n");
                                if (dateId && achievementsText) {
                                  handleTranslate(`daily_analysis_achievements_${dateId}`, achievementsText, "ko");
                                }
                              }}
                              disabled={translating === `daily_analysis_achievements_${selectedDailyAnalysis?.target_date}`}
                              className={`text-xs px-2 py-1 rounded transition-colors ${
                                translations[`daily_analysis_achievements_${selectedDailyAnalysis?.target_date}`]?.lang === "ko"
                                  ? "bg-blue-600 text-white"
                                  : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                              } ${
                                translating === `daily_analysis_achievements_${selectedDailyAnalysis?.target_date}`
                                  ? "opacity-50 cursor-wait"
                                  : ""
                              }`}
                            >
                              KR
                            </button>
                          </div>
                        </div>
                        {translations[`daily_analysis_achievements_${selectedDailyAnalysis?.target_date}`] && (
                          <p className="text-xs text-gray-400 mb-2">
                            🌐 Translated to{" "}
                            {translations[`daily_analysis_achievements_${selectedDailyAnalysis?.target_date}`].lang === "ko"
                              ? "Korean"
                              : "English"}
                          </p>
                        )}
                        <ul className="list-disc list-inside space-y-1 text-sm text-gray-700">
                          {(() => {
                            const translationKey = `daily_analysis_achievements_${selectedDailyAnalysis?.target_date}`;
                            const translatedText = translations[translationKey]?.text;
                            
                            if (translatedText && translatedText.trim()) {
                              // Split by newline and filter out empty lines
                              const translatedItems = translatedText.split("\n").filter((item: string) => item.trim());
                              if (translatedItems.length > 0) {
                                return translatedItems.map((achievement: string, idx: number) => (
                                  <li key={idx}>{achievement.trim()}</li>
                                ));
                              }
                            }
                            
                            // Fall back to original
                            return selectedDailyAnalysis.analysis.summary.major_achievements.map(
                              (achievement: string, idx: number) => (
                                <li key={idx}>{achievement}</li>
                              )
                            );
                          })()}
                        </ul>
                      </div>
                    )}

                  {/* Issues Tab */}
                  {dailyAnalysisTab === "issues" &&
                    selectedDailyAnalysis.analysis?.summary?.common_issues &&
                    selectedDailyAnalysis.analysis.summary.common_issues.length > 0 && (
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="text-lg font-semibold text-gray-900">
                            Common Issues
                          </h3>
                          <div className="flex gap-1">
                            <button
                              onClick={() => {
                                const dateId = selectedDailyAnalysis.target_date;
                                const issuesText = selectedDailyAnalysis.analysis.summary.common_issues.join("\n");
                                if (dateId && issuesText) {
                                  handleTranslate(`daily_analysis_issues_${dateId}`, issuesText, "en");
                                }
                              }}
                              disabled={translating === `daily_analysis_issues_${selectedDailyAnalysis?.target_date}`}
                              className={`text-xs px-2 py-1 rounded transition-colors ${
                                translations[`daily_analysis_issues_${selectedDailyAnalysis?.target_date}`]?.lang === "en"
                                  ? "bg-blue-600 text-white"
                                  : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                              } ${
                                translating === `daily_analysis_issues_${selectedDailyAnalysis?.target_date}`
                                  ? "opacity-50 cursor-wait"
                                  : ""
                              }`}
                            >
                              EN
                            </button>
                            <button
                              onClick={() => {
                                const dateId = selectedDailyAnalysis.target_date;
                                const issuesText = selectedDailyAnalysis.analysis.summary.common_issues.join("\n");
                                if (dateId && issuesText) {
                                  handleTranslate(`daily_analysis_issues_${dateId}`, issuesText, "ko");
                                }
                              }}
                              disabled={translating === `daily_analysis_issues_${selectedDailyAnalysis?.target_date}`}
                              className={`text-xs px-2 py-1 rounded transition-colors ${
                                translations[`daily_analysis_issues_${selectedDailyAnalysis?.target_date}`]?.lang === "ko"
                                  ? "bg-blue-600 text-white"
                                  : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                              } ${
                                translating === `daily_analysis_issues_${selectedDailyAnalysis?.target_date}`
                                  ? "opacity-50 cursor-wait"
                                  : ""
                              }`}
                            >
                              KR
                            </button>
                          </div>
                        </div>
                        {translations[`daily_analysis_issues_${selectedDailyAnalysis?.target_date}`] && (
                          <p className="text-xs text-gray-400 mb-2">
                            🌐 Translated to{" "}
                            {translations[`daily_analysis_issues_${selectedDailyAnalysis?.target_date}`].lang === "ko"
                              ? "Korean"
                              : "English"}
                          </p>
                        )}
                        <ul className="list-disc list-inside space-y-1 text-sm text-gray-700">
                          {(() => {
                            const translationKey = `daily_analysis_issues_${selectedDailyAnalysis?.target_date}`;
                            const translatedText = translations[translationKey]?.text;
                            
                            if (translatedText && translatedText.trim()) {
                              // Split by newline and filter out empty lines
                              const translatedItems = translatedText.split("\n").filter((item: string) => item.trim());
                              if (translatedItems.length > 0) {
                                return translatedItems.map((issue: string, idx: number) => (
                                  <li key={idx}>{issue.trim()}</li>
                                ));
                              }
                            }
                            
                            // Fall back to original
                            return selectedDailyAnalysis.analysis.summary.common_issues.map(
                              (issue: string, idx: number) => (
                                <li key={idx}>{issue}</li>
                              )
                            );
                          })()}
                        </ul>
                      </div>
                    )}

                  {/* Participants Tab */}
                  {dailyAnalysisTab === "participants" &&
                    selectedDailyAnalysis.analysis?.participants &&
                    selectedDailyAnalysis.analysis.participants.length > 0 && (
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="text-lg font-semibold text-gray-900">
                            Participants
                          </h3>
                          <div className="flex gap-1">
                            <button
                              onClick={async () => {
                                const dateId = selectedDailyAnalysis.target_date;
                                const participants = selectedDailyAnalysis.analysis.participants;
                                
                                // Collect all translation promises for parallel execution
                                const translationPromises: Promise<void>[] = [];
                                
                                participants.forEach((participant: any, idx: number) => {
                                  const participantKey = `daily_analysis_participant_${dateId}_${idx}`;
                                  
                                  if (participant.key_activities?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${participantKey}_key_activities`, participant.key_activities.join("\n"), "en", "ko")
                                    );
                                  }
                                  if (participant.action_items?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${participantKey}_action_items`, participant.action_items.join("\n"), "en", "ko")
                                    );
                                  }
                                  if (participant.progress?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${participantKey}_progress`, participant.progress.join("\n"), "en", "ko")
                                    );
                                  }
                                  if (participant.issues?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${participantKey}_issues`, participant.issues.join("\n"), "en", "ko")
                                    );
                                  }
                                  if (participant.collaboration?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${participantKey}_collaboration`, participant.collaboration.join("\n"), "en", "ko")
                                    );
                                  }
                                });
                                
                                // Execute all translations in parallel
                                try {
                                  await Promise.all(translationPromises);
                                  // Small delay to ensure all translations are saved to state
                                  await new Promise(resolve => setTimeout(resolve, 100));
                                  // Force re-render by creating a new object reference
                                  setTranslations((prev) => {
                                    const updated = { ...prev };
                                    // Trigger re-render by updating reference
                                    return { ...updated };
                                  });
                                } catch (error) {
                                  console.error("Batch translation error:", error);
                                  // Even on error, try to refresh translations
                                  setTranslations((prev) => ({ ...prev }));
                                }
                              }}
                              disabled={Array.from(translatingSet).some(key => key.startsWith("daily_analysis_participant_"))}
                              className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700 transition-colors disabled:opacity-50 disabled:cursor-wait"
                            >
                              EN
                            </button>
                            <button
                              onClick={async () => {
                                const dateId = selectedDailyAnalysis.target_date;
                                const participants = selectedDailyAnalysis.analysis.participants;
                                
                                // Collect all translation promises for parallel execution
                                const translationPromises: Promise<void>[] = [];
                                
                                participants.forEach((participant: any, idx: number) => {
                                  const participantKey = `daily_analysis_participant_${dateId}_${idx}`;
                                  
                                  if (participant.key_activities?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${participantKey}_key_activities`, participant.key_activities.join("\n"), "ko", "en")
                                    );
                                  }
                                  if (participant.action_items?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${participantKey}_action_items`, participant.action_items.join("\n"), "ko", "en")
                                    );
                                  }
                                  if (participant.progress?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${participantKey}_progress`, participant.progress.join("\n"), "ko", "en")
                                    );
                                  }
                                  if (participant.issues?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${participantKey}_issues`, participant.issues.join("\n"), "ko", "en")
                                    );
                                  }
                                  if (participant.collaboration?.length > 0) {
                                    translationPromises.push(
                                      handleTranslate(`${participantKey}_collaboration`, participant.collaboration.join("\n"), "ko", "en")
                                    );
                                  }
                                });
                                
                                // Execute all translations in parallel
                                try {
                                  await Promise.all(translationPromises);
                                  // Small delay to ensure all translations are saved to state
                                  await new Promise(resolve => setTimeout(resolve, 100));
                                  // Force re-render by creating a new object reference
                                  setTranslations((prev) => {
                                    const updated = { ...prev };
                                    // Trigger re-render by updating reference
                                    return { ...updated };
                                  });
                                } catch (error) {
                                  console.error("Batch translation error:", error);
                                  // Even on error, try to refresh translations
                                  setTranslations((prev) => ({ ...prev }));
                                }
                              }}
                              disabled={Array.from(translatingSet).some(key => key.startsWith("daily_analysis_participant_"))}
                              className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700 transition-colors disabled:opacity-50 disabled:cursor-wait"
                            >
                              KR
                            </button>
                          </div>
                        </div>
                        <div className="space-y-4">
                          {(() => {
                            const dateId = selectedDailyAnalysis.target_date;
                            const allParticipants = selectedDailyAnalysis.analysis.participants;
                            
                            // Create a map of participant names to original indices for reliable key lookup
                            const participantIndexMap = new Map<string, number>();
                            allParticipants.forEach((p: any, idx: number) => {
                              participantIndexMap.set(p.name, idx);
                            });
                            
                            // Apply member filter if set
                            let filtered = [...allParticipants];
                            if (memberFilter) {
                              filtered = filtered.filter((p: any) =>
                                p.name?.toLowerCase().includes(memberFilter.toLowerCase())
                              );
                            }
                            
                            // Sort alphabetically by name
                            filtered.sort((a: any, b: any) => {
                              const nameA = (a.name || "").toLowerCase();
                              const nameB = (b.name || "").toLowerCase();
                              return nameA.localeCompare(nameB);
                            });
                            
                            return filtered.map(
                              (participant: any, displayIdx: number) => {
                                // Use the original index from the map to ensure consistency
                                const originalIdx = participantIndexMap.get(participant.name) ?? displayIdx;
                                const participantKey = `daily_analysis_participant_${dateId}_${originalIdx}`;
                                
                                // Helper function to get translated text for a field
                                const getTranslatedField = (fieldName: string, originalArray: string[]) => {
                                  const translationKey = `${participantKey}_${fieldName}`;
                                  const translatedText = translations[translationKey]?.text;
                                  
                                  if (translatedText && translatedText.trim()) {
                                    const translatedItems = translatedText.split("\n").filter((item: string) => item.trim());
                                    if (translatedItems.length > 0) {
                                      return translatedItems;
                                    }
                                  }
                                  return originalArray;
                                };
                                
                                
                                return (
                                  <div
                                    key={displayIdx}
                                    className="border border-gray-200 rounded-lg p-4"
                                  >
                                    <div className="flex items-center justify-between mb-2">
                                      <h4 className="font-semibold text-gray-900">
                                        {participant.name}
                                      </h4>
                                      <div className="text-sm text-gray-500">
                                        {participant.speaking_time} (
                                        {participant.speaking_percentage?.toFixed(1) || 0}%)
                                      </div>
                                    </div>
                                    <div className="grid grid-cols-3 gap-4 text-sm mb-3">
                                      <div>
                                        <span className="text-gray-500">Speaks:</span>{" "}
                                        <span className="font-medium">
                                          {participant.speak_count || 0}
                                        </span>
                                      </div>
                                      <div>
                                        <span className="text-gray-500">Words:</span>{" "}
                                        <span className="font-medium">
                                          {participant.word_count || 0}
                                        </span>
                                      </div>
                                      <div>
                                        <span className="text-gray-500">Time:</span>{" "}
                                        <span className="font-medium">
                                          {participant.speaking_time || "N/A"}
                                        </span>
                                      </div>
                                    </div>
                                    {participant.key_activities &&
                                      participant.key_activities.length > 0 && (
                                        <div className="mt-2">
                                          <div className="text-sm text-gray-500 mb-1">
                                            Key Activities:
                                          </div>
                                          <ul className="list-disc list-inside text-sm text-gray-700">
                                            {getTranslatedField("key_activities", participant.key_activities).map((item: string, i: number) => (
                                              <li key={i}>{item}</li>
                                            ))}
                                          </ul>
                                        </div>
                                      )}
                                    {participant.action_items &&
                                      participant.action_items.length > 0 && (
                                        <div className="mt-2">
                                          <div className="text-sm text-gray-500 mb-1">
                                            Action Items:
                                          </div>
                                          <ul className="list-disc list-inside text-sm text-gray-700">
                                            {getTranslatedField("action_items", participant.action_items).map((item: string, i: number) => (
                                              <li key={i}>{item}</li>
                                            ))}
                                          </ul>
                                        </div>
                                      )}
                                    {participant.progress &&
                                      participant.progress.length > 0 && (
                                        <div className="mt-2">
                                          <div className="text-sm text-gray-500 mb-1">
                                            Progress:
                                          </div>
                                          <ul className="list-disc list-inside text-sm text-gray-700">
                                            {getTranslatedField("progress", participant.progress).map((prog: string, i: number) => (
                                              <li key={i}>{prog}</li>
                                            ))}
                                          </ul>
                                        </div>
                                      )}
                                    {participant.issues &&
                                      participant.issues.length > 0 && (
                                        <div className="mt-2">
                                          <div className="text-sm text-gray-500 mb-1">
                                            Issues:
                                          </div>
                                          <ul className="list-disc list-inside text-sm text-gray-700">
                                            {getTranslatedField("issues", participant.issues).map((issue: string, i: number) => (
                                              <li key={i}>{issue}</li>
                                            ))}
                                          </ul>
                                        </div>
                                      )}
                                    {participant.collaboration &&
                                      participant.collaboration.length > 0 && (
                                        <div className="mt-2">
                                          <div className="text-sm text-gray-500 mb-1">
                                            Collaboration:
                                          </div>
                                          <ul className="list-disc list-inside text-sm text-gray-700">
                                            {getTranslatedField("collaboration", participant.collaboration).map((collab: string, i: number) => (
                                              <li key={i}>{collab}</li>
                                            ))}
                                          </ul>
                                        </div>
                                      )}
                                  </div>
                                );
                              }
                            );
                          })()}
                        </div>
                      </div>
                    )}

                  {/* Full Analysis Tab */}
                  {dailyAnalysisTab === "full" &&
                    selectedDailyAnalysis.analysis?.full_analysis_text && (
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-lg font-semibold text-gray-900">
                          Full Analysis
                        </h3>
                        <div className="flex gap-1">
                          <button
                            onClick={() => {
                              const dateId = selectedDailyAnalysis.target_date;
                              const analysisText = selectedDailyAnalysis.analysis.full_analysis_text;
                              if (dateId && analysisText) {
                                handleTranslate(`daily_analysis_full_${dateId}`, analysisText, "en");
                              }
                            }}
                            disabled={translating === `daily_analysis_full_${selectedDailyAnalysis?.target_date}`}
                            className={`text-xs px-2 py-1 rounded transition-colors ${
                              translations[`daily_analysis_full_${selectedDailyAnalysis?.target_date}`]?.lang === "en"
                                ? "bg-blue-600 text-white"
                                : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                            } ${
                              translating === `daily_analysis_full_${selectedDailyAnalysis?.target_date}`
                                ? "opacity-50 cursor-wait"
                                : ""
                            }`}
                          >
                            EN
                          </button>
                          <button
                            onClick={() => {
                              const dateId = selectedDailyAnalysis.target_date;
                              const analysisText = selectedDailyAnalysis.analysis.full_analysis_text;
                              if (dateId && analysisText) {
                                handleTranslate(`daily_analysis_full_${dateId}`, analysisText, "ko");
                              }
                            }}
                            disabled={translating === `daily_analysis_full_${selectedDailyAnalysis?.target_date}`}
                            className={`text-xs px-2 py-1 rounded transition-colors ${
                              translations[`daily_analysis_full_${selectedDailyAnalysis?.target_date}`]?.lang === "ko"
                                ? "bg-blue-600 text-white"
                                : "bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700"
                            } ${
                              translating === `daily_analysis_full_${selectedDailyAnalysis?.target_date}`
                                ? "opacity-50 cursor-wait"
                                : ""
                            }`}
                          >
                            KR
                          </button>
                        </div>
                      </div>
                      {translations[`daily_analysis_full_${selectedDailyAnalysis?.target_date}`] && (
                        <p className="text-xs text-gray-400 mb-2">
                          🌐 Translated to{" "}
                          {translations[`daily_analysis_full_${selectedDailyAnalysis?.target_date}`].lang === "ko"
                            ? "Korean"
                            : "English"}
                        </p>
                      )}
                      <div className="bg-gray-50 rounded-lg p-4">
                        <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans">
                          {translations[`daily_analysis_full_${selectedDailyAnalysis?.target_date}`]?.text ||
                            selectedDailyAnalysis.analysis.full_analysis_text}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-gray-500 text-center">
                  No analysis data available
                </p>
              )}
              {/* Show message if selected tab has no data */}
              {selectedDailyAnalysis?.analysis &&
                !dailyAnalysisLoading &&
                ((dailyAnalysisTab === "overview" &&
                  !selectedDailyAnalysis.analysis?.summary?.overview) ||
                  (dailyAnalysisTab === "topics" &&
                    (!selectedDailyAnalysis.analysis?.summary?.topics ||
                      selectedDailyAnalysis.analysis.summary.topics.length === 0)) ||
                  (dailyAnalysisTab === "decisions" &&
                    (!selectedDailyAnalysis.analysis?.summary?.key_decisions ||
                      selectedDailyAnalysis.analysis.summary.key_decisions.length === 0)) ||
                  (dailyAnalysisTab === "achievements" &&
                    (!selectedDailyAnalysis.analysis?.summary?.major_achievements ||
                      selectedDailyAnalysis.analysis.summary.major_achievements.length === 0)) ||
                  (dailyAnalysisTab === "issues" &&
                    (!selectedDailyAnalysis.analysis?.summary?.common_issues ||
                      selectedDailyAnalysis.analysis.summary.common_issues.length === 0)) ||
                  (dailyAnalysisTab === "participants" &&
                    (!selectedDailyAnalysis.analysis?.participants ||
                      selectedDailyAnalysis.analysis.participants.length === 0)) ||
                  (dailyAnalysisTab === "full" &&
                    !selectedDailyAnalysis.analysis?.full_analysis_text)) && (
                  <div className="text-center py-12">
                    <p className="text-gray-500">
                      No data available for this section
                    </p>
                  </div>
                )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
