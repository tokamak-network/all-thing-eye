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

export default function RecordingsPage() {
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [selectedRecording, setSelectedRecording] =
    useState<RecordingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);

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

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatSize = (bytes: string) => {
    const size = parseInt(bytes);
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (loading) {
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
            View meeting transcripts and recordings from Google Drive
          </p>
        </div>

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
      </div>
    </div>
  );
}
