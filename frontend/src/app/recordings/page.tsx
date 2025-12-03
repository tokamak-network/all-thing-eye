"use client";

import { useState, useEffect } from "react";
import { api as apiClient } from "@/lib/api";

interface Recording {
  _id: string;
  id: string;
  name: string;
  created_by: string;
  createdTime: string;
  modifiedTime: string;
  webViewLink: string;
  size: string;
  mimeType: string;
}

interface RecordingDetail extends Recording {
  content: string;
}

interface RecordingsDaily {
  id: string;
  status: string;
  target_date: string;
  meeting_count: number;
  meeting_titles: string[];
  date_range: {
    start: string;
    end: string;
  };
  total_meeting_time: string;
  total_meeting_time_seconds: number;
  template_used: string;
  template_version?: string;
  model_used: string;
  timestamp: string;
  target_meetings: Array<{
    meeting_id: string;
    meeting_title: string;
    created_time: string;
  }>;
  analysis: {
    summary: {
      overview: {
        meeting_count: number;
        total_time: string;
        main_topics: string[];
      };
      topics: Array<{
        topic: string;
        related_meetings: string[];
        key_discussions: string[];
        key_decisions: string[];
        progress: string[];
        issues: string[];
      }>;
      key_decisions: string[];
      major_achievements: string[];
      common_issues: string[];
    };
    participants: Array<{
      name: string;
      speaking_time: string;
      speaking_time_seconds: number;
      speaking_percentage: number;
      speak_count: number;
      word_count: number;
      key_activities: string[];
      progress: string[];
      issues: string[];
      action_items: string[];
      collaboration: string[];
    }>;
    full_analysis_text: string;
  };
}

export default function RecordingsPage() {
  const [activeTab, setActiveTab] = useState<"recordings" | "daily">("recordings");
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [dailyAnalyses, setDailyAnalyses] = useState<RecordingsDaily[]>([]);
  const [selectedRecording, setSelectedRecording] =
    useState<RecordingDetail | null>(null);
  const [selectedDaily, setSelectedDaily] = useState<RecordingsDaily | null>(null);
  const [loading, setLoading] = useState(true);
  const [dailyLoading, setDailyLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);
  const [showDailyDetail, setShowDailyDetail] = useState(false);

  useEffect(() => {
    const fetchRecordings = async () => {
      try {
        const response = await apiClient.get("/database/recordings?limit=50");
        setRecordings(response.recordings);
      } catch (err: any) {
        setError(err.response?.data?.detail || "Failed to fetch recordings");
      } finally {
        setLoading(false);
      }
    };

    fetchRecordings();
  }, []);

  useEffect(() => {
    if (activeTab === "daily") {
      fetchDailyAnalyses();
    }
  }, [activeTab]);

  const fetchDailyAnalyses = async () => {
    setDailyLoading(true);
    try {
      const response = await apiClient.getRecordingsDaily({ limit: 50 });
      setDailyAnalyses(response.analyses);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to fetch daily analyses");
    } finally {
      setDailyLoading(false);
    }
  };

  const handleViewDetail = async (recordingId: string) => {
    setDetailLoading(true);
    setShowTranscript(true);

    try {
      const response = await apiClient.get(
        `/database/recordings/${recordingId}`
      );
      setSelectedRecording(response);
    } catch (err: any) {
      alert("Failed to load recording details");
    } finally {
      setDetailLoading(false);
    }
  };

  const handleViewDailyDetail = (daily: RecordingsDaily) => {
    setSelectedDaily(daily);
    setShowDailyDetail(true);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatDateOnly = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const formatSize = (bytes: string) => {
    const size = parseInt(bytes);
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (loading && activeTab === "recordings") {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading recordings...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-8 text-center">
            <p className="text-red-800">Error: {error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4 sm:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            📹 Meeting Recordings
          </h1>
          <p className="text-gray-600">
            View meeting transcripts, recordings, and daily AI analyses
          </p>
        </div>

        {/* Tabs */}
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="border-b border-gray-200">
            <nav className="flex -mb-px">
              <button
                onClick={() => setActiveTab("recordings")}
                className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === "recordings"
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                }`}
              >
                📝 Recordings ({recordings.length})
              </button>
              <button
                onClick={() => setActiveTab("daily")}
                className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === "daily"
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                }`}
              >
                📊 Daily Analysis ({dailyAnalyses.length})
              </button>
            </nav>
          </div>
        </div>

        {/* Recordings Tab */}
        {activeTab === "recordings" && (
          <>
            {/* Stats */}
            <div className="bg-white rounded-lg shadow p-4 mb-6">
              <div className="flex items-center gap-4">
                <div>
                  <div className="text-2xl font-bold text-blue-600">
                    {recordings.length}
                  </div>
                  <div className="text-xs text-gray-600">Total Recordings</div>
                </div>
              </div>
            </div>

            {/* Recordings Table */}
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Meeting Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Created By
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Date
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Size
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {recordings.map((recording) => (
                    <tr key={recording._id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <div className="text-sm font-medium text-gray-900 max-w-md truncate">
                          {recording.name}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {recording.created_by}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {formatDate(recording.createdTime)}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {formatSize(recording.size)}
                      </td>
                      <td className="px-6 py-4 text-sm space-x-2">
                        <button
                          onClick={() => handleViewDetail(recording.id)}
                          className="text-blue-600 hover:text-blue-800 font-medium"
                        >
                          View Transcript
                        </button>
                        <span className="text-gray-300">|</span>
                        <a
                          href={recording.webViewLink}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 font-medium"
                        >
                          Open in Google Docs →
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* Daily Analysis Tab */}
        {activeTab === "daily" && (
          <>
            {dailyLoading ? (
              <div className="bg-white rounded-lg shadow p-8 text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
                <p className="mt-4 text-gray-600">Loading daily analyses...</p>
              </div>
            ) : (
              <>
                {/* Stats */}
                <div className="bg-white rounded-lg shadow p-4 mb-6">
                  <div className="flex items-center gap-6">
                    <div>
                      <div className="text-2xl font-bold text-blue-600">
                        {dailyAnalyses.length}
                      </div>
                      <div className="text-xs text-gray-600">Daily Analyses</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-green-600">
                        {dailyAnalyses.reduce(
                          (sum, d) => sum + d.meeting_count,
                          0
                        )}
                      </div>
                      <div className="text-xs text-gray-600">Total Meetings</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-purple-600">
                        {Math.round(
                          dailyAnalyses.reduce(
                            (sum, d) => sum + d.total_meeting_time_seconds,
                            0
                          ) / 3600
                        )}
                      </div>
                      <div className="text-xs text-gray-600">Total Hours</div>
                    </div>
                  </div>
                </div>

                {/* Daily Analyses List */}
                <div className="space-y-4">
                  {dailyAnalyses.map((daily) => (
                    <div
                      key={daily.id}
                      className="bg-white rounded-lg shadow p-6 hover:shadow-md transition-shadow"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <h3 className="text-lg font-semibold text-gray-900">
                              {formatDateOnly(daily.target_date)}
                            </h3>
                            <span
                              className={`px-2 py-1 text-xs rounded-full ${
                                daily.status === "success"
                                  ? "bg-green-100 text-green-800"
                                  : "bg-yellow-100 text-yellow-800"
                              }`}
                            >
                              {daily.status}
                            </span>
                          </div>
                          <div className="grid grid-cols-3 gap-4 mt-4">
                            <div>
                              <div className="text-sm text-gray-500">Meetings</div>
                              <div className="text-lg font-semibold text-gray-900">
                                {daily.meeting_count}
                              </div>
                            </div>
                            <div>
                              <div className="text-sm text-gray-500">Total Time</div>
                              <div className="text-lg font-semibold text-gray-900">
                                {daily.total_meeting_time}
                              </div>
                            </div>
                            <div>
                              <div className="text-sm text-gray-500">Model</div>
                              <div className="text-lg font-semibold text-gray-900">
                                {daily.model_used}
                              </div>
                            </div>
                          </div>
                          {daily.meeting_titles.length > 0 && (
                            <div className="mt-4">
                              <div className="text-sm text-gray-500 mb-2">
                                Meeting Titles:
                              </div>
                              <div className="flex flex-wrap gap-2">
                                {daily.meeting_titles.slice(0, 5).map((title, idx) => (
                                  <span
                                    key={idx}
                                    className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded"
                                  >
                                    {title}
                                  </span>
                                ))}
                                {daily.meeting_titles.length > 5 && (
                                  <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded">
                                    +{daily.meeting_titles.length - 5} more
                                  </span>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                        <button
                          onClick={() => handleViewDailyDetail(daily)}
                          className="ml-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                        >
                          View Details
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </>
        )}

        {/* Transcript Modal */}
        {showTranscript && (
          <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
              {/* Modal Header */}
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-gray-900">
                    {selectedRecording?.name || "Loading..."}
                  </h2>
                  {selectedRecording && (
                    <p className="text-sm text-gray-500 mt-1">
                      By {selectedRecording.created_by} •{" "}
                      {formatDate(selectedRecording.createdTime)}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => {
                    setShowTranscript(false);
                    setSelectedRecording(null);
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

              {/* Modal Body */}
              <div className="flex-1 overflow-y-auto p-6">
                {detailLoading ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
                  </div>
                ) : selectedRecording ? (
                  <div className="prose max-w-none">
                    <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans">
                      {selectedRecording.content}
                    </pre>
                  </div>
                ) : (
                  <p className="text-gray-500 text-center">
                    No content available
                  </p>
                )}
              </div>

              {/* Modal Footer */}
              {selectedRecording && (
                <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
                  <a
                    href={selectedRecording.webViewLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Open in Google Docs →
                  </a>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Daily Analysis Detail Modal */}
        {showDailyDetail && selectedDaily && (
          <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col">
              {/* Modal Header */}
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-gray-900">
                    Daily Analysis - {formatDateOnly(selectedDaily.target_date)}
                  </h2>
                  <p className="text-sm text-gray-500 mt-1">
                    {selectedDaily.meeting_count} meetings •{" "}
                    {selectedDaily.total_meeting_time} • {selectedDaily.model_used}
                  </p>
                </div>
                <button
                  onClick={() => {
                    setShowDailyDetail(false);
                    setSelectedDaily(null);
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

              {/* Modal Body */}
              <div className="flex-1 overflow-y-auto p-6">
                <div className="space-y-6">
                  {/* Overview */}
                  {selectedDaily.analysis?.summary?.overview && (
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 mb-3">
                        Overview
                      </h3>
                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="grid grid-cols-3 gap-4 mb-4">
                          <div>
                            <div className="text-sm text-gray-500">Meetings</div>
                            <div className="text-xl font-bold text-gray-900">
                              {selectedDaily.analysis.summary.overview.meeting_count}
                            </div>
                          </div>
                          <div>
                            <div className="text-sm text-gray-500">Total Time</div>
                            <div className="text-xl font-bold text-gray-900">
                              {selectedDaily.analysis.summary.overview.total_time}
                            </div>
                          </div>
                          <div>
                            <div className="text-sm text-gray-500">Main Topics</div>
                            <div className="text-xl font-bold text-gray-900">
                              {selectedDaily.analysis.summary.overview.main_topics?.length || 0}
                            </div>
                          </div>
                        </div>
                        {selectedDaily.analysis.summary.overview.main_topics &&
                          selectedDaily.analysis.summary.overview.main_topics.length > 0 && (
                            <div>
                              <div className="text-sm text-gray-500 mb-2">
                                Main Topics:
                              </div>
                              <div className="flex flex-wrap gap-2">
                                {selectedDaily.analysis.summary.overview.main_topics.map(
                                  (topic, idx) => (
                                    <span
                                      key={idx}
                                      className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded"
                                    >
                                      {topic}
                                    </span>
                                  )
                                )}
                              </div>
                            </div>
                          )}
                      </div>
                    </div>
                  )}

                  {/* Topics */}
                  {selectedDaily.analysis?.summary?.topics &&
                    selectedDaily.analysis.summary.topics.length > 0 && (
                      <div>
                        <h3 className="text-lg font-semibold text-gray-900 mb-3">
                          Topics
                        </h3>
                        <div className="space-y-4">
                          {selectedDaily.analysis.summary.topics.map(
                            (topic, idx) => (
                              <div
                                key={idx}
                                className="border border-gray-200 rounded-lg p-4"
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
                                        {topic.key_discussions.map((disc, i) => (
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
                                        {topic.key_decisions.map((dec, i) => (
                                          <li key={i}>{dec}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                              </div>
                            )
                          )}
                        </div>
                      </div>
                    )}

                  {/* Participants */}
                  {selectedDaily.analysis?.participants &&
                    selectedDaily.analysis.participants.length > 0 && (
                      <div>
                        <h3 className="text-lg font-semibold text-gray-900 mb-3">
                          Participants
                        </h3>
                        <div className="space-y-4">
                          {selectedDaily.analysis.participants.map(
                            (participant, idx) => (
                              <div
                                key={idx}
                                className="border border-gray-200 rounded-lg p-4"
                              >
                                <div className="flex items-center justify-between mb-2">
                                  <h4 className="font-semibold text-gray-900">
                                    {participant.name}
                                  </h4>
                                  <div className="text-sm text-gray-500">
                                    {participant.speaking_time} (
                                    {participant.speaking_percentage.toFixed(1)}%)
                                  </div>
                                </div>
                                <div className="grid grid-cols-3 gap-4 text-sm mb-3">
                                  <div>
                                    <span className="text-gray-500">Speaks:</span>{" "}
                                    <span className="font-medium">
                                      {participant.speak_count}
                                    </span>
                                  </div>
                                  <div>
                                    <span className="text-gray-500">Words:</span>{" "}
                                    <span className="font-medium">
                                      {participant.word_count}
                                    </span>
                                  </div>
                                  <div>
                                    <span className="text-gray-500">Time:</span>{" "}
                                    <span className="font-medium">
                                      {participant.speaking_time}
                                    </span>
                                  </div>
                                </div>
                                {participant.action_items &&
                                  participant.action_items.length > 0 && (
                                    <div className="mt-2">
                                      <div className="text-sm text-gray-500 mb-1">
                                        Action Items:
                                      </div>
                                      <ul className="list-disc list-inside text-sm text-gray-700">
                                        {participant.action_items.map((item, i) => (
                                          <li key={i}>{item}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                              </div>
                            )
                          )}
                        </div>
                      </div>
                    )}

                  {/* Full Analysis Text */}
                  {selectedDaily.analysis?.full_analysis_text && (
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 mb-3">
                        Full Analysis
                      </h3>
                      <div className="bg-gray-50 rounded-lg p-4">
                        <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans">
                          {selectedDaily.analysis.full_analysis_text}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
