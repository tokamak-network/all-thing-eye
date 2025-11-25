'use client';

import { useEffect, useState } from 'react';
import { format } from 'date-fns';
import { api as apiClient } from '@/lib/api';
import type { ActivityListResponse } from '@/types';

// Helper function to safely format timestamps (converts to browser's local timezone)
function formatTimestamp(timestamp: string, formatStr: string): string {
  if (!timestamp) return 'N/A';
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return 'N/A';
  return format(date, formatStr);
}

// Helper function to get timezone offset string (e.g., "UTC+9", "UTC-5")
function getTimezoneString(): string {
  const offset = -new Date().getTimezoneOffset() / 60;
  const sign = offset >= 0 ? '+' : '';
  return `UTC${sign}${offset}`;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ActivitiesPage() {
  const [allActivities, setAllActivities] = useState<ActivityListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string>('');
  const [memberFilter, setMemberFilter] = useState<string>('');
  const [expandedActivity, setExpandedActivity] = useState<string | null>(null);
  const [recordingDetail, setRecordingDetail] = useState<any>(null);
  const [showTranscript, setShowTranscript] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);

  // Load all activities once on mount
  useEffect(() => {
    async function fetchActivities() {
      try {
        setLoading(true);
        const response = await apiClient.getActivities({
          limit: 500, // Load more activities upfront
        });
        setAllActivities(response);
      } catch (err: any) {
        console.error('Error fetching activities:', err);
        setError(err.message || 'Failed to fetch activities');
      } finally {
        setLoading(false);
      }
    }

    fetchActivities();
  }, []); // Only run once on mount

  // Extract unique member names from activities
  const uniqueMembers = allActivities
    ? Array.from(
        new Set(
          allActivities.activities
            .map((activity) => activity.member_name)
            .filter((name) => name) // Remove null/undefined
        )
      ).sort()
    : [];

  // Filter activities on the client side
  const data =
    (sourceFilter || memberFilter) && allActivities
      ? {
          ...allActivities,
          activities: allActivities.activities.filter((activity) => {
            const matchesSource = !sourceFilter || activity.source_type === sourceFilter;
            const matchesMember = !memberFilter || activity.member_name === memberFilter;
            return matchesSource && matchesMember;
          }),
          total: allActivities.activities.filter((activity) => {
            const matchesSource = !sourceFilter || activity.source_type === sourceFilter;
            const matchesMember = !memberFilter || activity.member_name === memberFilter;
            return matchesSource && matchesMember;
          }).length,
        }
      : allActivities;

  const toggleActivity = (activityId: string) => {
    setExpandedActivity(expandedActivity === activityId ? null : activityId);
  };

  const handleViewRecordingDetail = async (recordingId: string) => {
    setDetailLoading(true);
    setShowTranscript(true);

    try {
      const response = await apiClient.get(`/database/recordings/${recordingId}`);
      setRecordingDetail(response);
    } catch (err: any) {
      alert('Failed to load recording details');
    } finally {
      setDetailLoading(false);
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
      github: 'bg-gray-100 text-gray-800',
      slack: 'bg-purple-100 text-purple-800',
      notion: 'bg-blue-100 text-blue-800',
      drive: 'bg-green-100 text-green-800',
      recordings: 'bg-red-100 text-red-800',
    };
    return colors[source] || 'bg-gray-100 text-gray-800';
  };

  const getSourceIcon = (source: string) => {
    const icons: Record<string, string> = {
      github: '🐙',
      slack: '💬',
      notion: '📝',
      drive: '📁',
      recordings: '📹',
    };
    return icons[source] || '📋';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">📋 Activities</h1>
          <p className="mt-2 text-gray-600">
            {data?.total?.toLocaleString() || 0} activities recorded across all sources
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
          </select>
          <select
            value={memberFilter}
            onChange={(e) => setMemberFilter(e.target.value)}
            className="block rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
          >
            <option value="">All Members</option>
            {uniqueMembers.map((member) => (
              <option key={member} value={member}>
                {member}
              </option>
            ))}
          </select>
          <a
            href={apiClient.getExportActivitiesUrl('csv', {
              limit: 10000,
              source_type: sourceFilter || undefined,
            })}
            download
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
          >
            <svg className="mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export CSV
          </a>
        </div>
      </div>

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
                      <span className="text-2xl">{getSourceIcon(activity.source_type)}</span>
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getSourceColor(activity.source_type)}`}>
                        {activity.source_type}
                      </span>
                      
                      {/* Activity Type Badge for GitHub */}
                      {activity.source_type === 'github' && (
                        <>
                          {activity.activity_type === 'commit' && (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                              💾 commit
                            </span>
                          )}
                          {activity.activity_type === 'pull_request' && (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                              🔀 pull request
                            </span>
                          )}
                          {activity.activity_type === 'issue' && (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                              ⚠️ issue
                            </span>
                          )}
                        </>
                      )}
                      
                      {/* Activity Type Badge for Slack */}
                      {activity.source_type === 'slack' && (
                        <>
                          {activity.activity_type === 'message' && (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                              💬 message
                            </span>
                          )}
                          {activity.activity_type === 'thread_reply' && (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
                              💭 thread reply
                            </span>
                          )}
                          {activity.activity_type === 'file_share' && (
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
                        {activity.member_name}
                      </p>
                    </div>
                    <div className="mt-2 text-sm text-gray-600">
                      {activity.metadata?.title && (
                        <p className="line-clamp-1 font-medium">{activity.metadata.title}</p>
                      )}
                      {activity.metadata?.name && (
                        <p className="line-clamp-1 font-medium">{activity.metadata.name}</p>
                      )}
                      {activity.metadata?.message && (
                        <p className="line-clamp-1">{activity.metadata.message}</p>
                      )}
                      {activity.metadata?.text && (
                        <p className="line-clamp-1">{activity.metadata.text}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center space-x-4">
                    <div className="text-right min-w-[160px]">
                      <p className="text-sm font-medium text-gray-900">
                        {formatTimestamp(activity.timestamp, 'MMM dd, yyyy')}
                      </p>
                      <p className="text-xs text-gray-600">
                        {formatTimestamp(activity.timestamp, 'HH:mm:ss')}
                      </p>
                    </div>
                    <svg
                      className={`h-5 w-5 text-gray-400 transition-transform ${expandedActivity === activity.id ? 'transform rotate-180' : ''}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </div>
              </div>

              {/* Expanded Details */}
              {expandedActivity === activity.id && (
                <div className="px-4 py-4 sm:px-6 bg-gray-50 border-t border-gray-200">
                  {/* GitHub Details */}
                  {activity.source_type === 'github' && (
                    <div className="space-y-3">
                      {/* Activity Type Badge */}
                      <div className="flex items-center space-x-2">
                        {activity.activity_type === 'commit' && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            💾 Commit
                          </span>
                        )}
                        {activity.activity_type === 'pull_request' && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                            🔀 Pull Request
                          </span>
                        )}
                        {activity.activity_type === 'issue' && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                            ⚠️ Issue
                          </span>
                        )}
                        {activity.metadata?.state && (
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${activity.metadata.state === 'open' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                            {activity.metadata.state}
                          </span>
                        )}
                      </div>

                      {/* Timestamp */}
                      <div>
                        <span className="text-xs font-medium text-gray-500">Time:</span>
                        <p className="text-sm text-gray-900">
                          {formatTimestamp(activity.timestamp, 'yyyy-MM-dd HH:mm:ss')}
                        </p>
                      </div>

                      {activity.metadata?.repository && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">Repository:</span>
                          <p className="text-sm text-gray-900">tokamak-network/{activity.metadata.repository}</p>
                        </div>
                      )}
                      
                      {activity.metadata?.sha && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">Commit SHA:</span>
                          <p className="text-sm font-mono text-gray-900">{activity.metadata.sha.substring(0, 7)}</p>
                        </div>
                      )}
                      
                      {activity.metadata?.number && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">
                            {activity.activity_type === 'pull_request' ? 'PR Number:' : 'Issue Number:'}
                          </span>
                          <p className="text-sm text-gray-900">#{activity.metadata.number}</p>
                        </div>
                      )}
                      
                      {(activity.metadata?.additions !== undefined || activity.metadata?.deletions !== undefined) && (
                        <div className="flex items-center space-x-4">
                          <div className="flex items-center space-x-1">
                            <span className="text-xs font-medium text-gray-500">Changes:</span>
                            <span className="text-xs font-medium text-green-600">+{activity.metadata.additions || 0}</span>
                            <span className="text-xs font-medium text-red-600">-{activity.metadata.deletions || 0}</span>
                          </div>
                        </div>
                      )}

                      {activity.metadata?.github_username && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">GitHub:</span>
                          <p className="text-sm text-gray-600">@{activity.metadata.github_username}</p>
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
                  {activity.source_type === 'slack' && (
                    <div className="space-y-3">
                      {/* Activity Type Badge */}
                      <div className="flex items-center space-x-2">
                        {activity.activity_type === 'message' && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                            💬 Message
                          </span>
                        )}
                        {activity.activity_type === 'thread_reply' && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
                            💭 Thread Reply
                          </span>
                        )}
                        {activity.activity_type === 'file_share' && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            📎 File Share
                          </span>
                        )}
                      </div>

                      {/* Timestamp */}
                      <div>
                        <span className="text-xs font-medium text-gray-500">Time:</span>
                        <p className="text-sm text-gray-900">
                          {formatTimestamp(activity.timestamp, 'yyyy-MM-dd HH:mm:ss')}
                        </p>
                      </div>

                      {activity.metadata?.channel && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">Channel:</span>
                          <p className="text-sm text-gray-900">#{activity.metadata.channel}</p>
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
                      
                      {/* Stats */}
                      <div className="flex flex-wrap gap-3 text-sm">
                        {activity.metadata?.reactions > 0 && (
                          <div className="flex items-center space-x-1">
                            <span className="text-gray-500">👍 Reactions:</span>
                            <span className="font-medium text-gray-900">{activity.metadata.reactions}</span>
                          </div>
                        )}
                        {activity.metadata?.reply_count > 0 && (
                          <div className="flex items-center space-x-1">
                            <span className="text-gray-500">💬 Replies:</span>
                            <span className="font-medium text-gray-900">{activity.metadata.reply_count}</span>
                          </div>
                        )}
                        {activity.metadata?.links > 0 && (
                          <div className="flex items-center space-x-1">
                            <span className="text-gray-500">🔗 Links:</span>
                            <span className="font-medium text-gray-900">{activity.metadata.links}</span>
                          </div>
                        )}
                        {activity.metadata?.files > 0 && (
                          <div className="flex items-center space-x-1">
                            <span className="text-gray-500">📎 Files:</span>
                            <span className="font-medium text-gray-900">{activity.metadata.files}</span>
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
                  {activity.source_type === 'notion' && (
                    <div className="space-y-3">
                      {/* Timestamp */}
                      <div>
                        <span className="text-xs font-medium text-gray-500">Time:</span>
                        <p className="text-sm text-gray-900">
                          {formatTimestamp(activity.timestamp, 'yyyy-MM-dd HH:mm:ss')}
                        </p>
                      </div>

                      {activity.metadata?.title && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">Page Title:</span>
                          <p className="text-sm text-gray-900">{activity.metadata.title}</p>
                        </div>
                      )}
                      {activity.metadata?.comments && (
                        <div>
                          <span className="text-sm text-gray-500">💬 {activity.metadata.comments} comments</span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Google Drive Details */}
                  {activity.source_type === 'drive' && (
                    <div className="space-y-3">
                      {/* Timestamp */}
                      <div>
                        <span className="text-xs font-medium text-gray-500">Time:</span>
                        <p className="text-sm text-gray-900">
                          {formatTimestamp(activity.timestamp, 'yyyy-MM-dd HH:mm:ss')}
                        </p>
                      </div>

                      {activity.metadata?.action && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">Action:</span>
                          <p className="text-sm text-gray-900">{activity.metadata.action}</p>
                        </div>
                      )}
                      {activity.metadata?.doc_title && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">Document:</span>
                          <p className="text-sm text-gray-900">{activity.metadata.doc_title}</p>
                        </div>
                      )}
                      {activity.metadata?.doc_type && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">Type:</span>
                          <p className="text-sm text-gray-900">{activity.metadata.doc_type}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Recordings Details */}
                  {activity.source_type === 'recordings' && (
                    <div className="space-y-3">
                      {/* Timestamp */}
                      <div>
                        <span className="text-xs font-medium text-gray-500">Time:</span>
                        <p className="text-sm text-gray-900">
                          {formatTimestamp(activity.timestamp, 'yyyy-MM-dd HH:mm:ss')}
                        </p>
                      </div>

                      {activity.metadata?.name && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">Recording Name:</span>
                          <p className="text-sm text-gray-900">{activity.metadata.name}</p>
                        </div>
                      )}
                      {activity.metadata?.size && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">File Size:</span>
                          <p className="text-sm text-gray-900">{formatSize(activity.metadata.size)}</p>
                        </div>
                      )}
                      <div className="flex space-x-2 mt-3">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (activity.metadata?.recording_id) {
                              handleViewRecordingDetail(activity.metadata.recording_id);
                            }
                          }}
                          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
                        >
                          📄 View Transcript
                        </button>
                        {activity.metadata?.webViewLink && (
                          <a
                            href={activity.metadata.webViewLink}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="px-3 py-1.5 bg-gray-600 text-white text-sm rounded hover:bg-gray-700 transition-colors"
                          >
                            🔗 Open in Google Docs
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
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No activities found</h3>
          <p className="mt-1 text-sm text-gray-500">
            No activities match the current filters.
          </p>
        </div>
      )}

      {/* Transcript Modal (for Recordings) */}
      {showTranscript && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-gray-900">
                  📹 {recordingDetail?.name || 'Loading...'}
                </h2>
                {recordingDetail && (
                  <p className="text-sm text-gray-500 mt-1">
                    By {recordingDetail.created_by} • {formatTimestamp(recordingDetail.createdTime, 'MMM dd, yyyy HH:mm')}
                  </p>
                )}
              </div>
              <button
                onClick={() => {
                  setShowTranscript(false);
                  setRecordingDetail(null);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6">
              {detailLoading ? (
                <div className="flex items-center justify-center h-full">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
                </div>
              ) : recordingDetail ? (
                <div className="prose max-w-none">
                  <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans bg-gray-50 p-4 rounded">
                    {recordingDetail.content || 'No transcript available'}
                  </pre>
                </div>
              ) : (
                <p className="text-gray-500 text-center">No content available</p>
              )}
            </div>

            {/* Modal Footer */}
            {recordingDetail && recordingDetail.webViewLink && (
              <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
                <a
                  href={recordingDetail.webViewLink}
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
  );
}
