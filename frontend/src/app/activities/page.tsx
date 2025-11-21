'use client';

import { useEffect, useState } from 'react';
import { format } from 'date-fns';
import api from '@/lib/api';
import type { ActivityListResponse } from '@/types';

// Helper function to safely format timestamps
function formatTimestamp(timestamp: string, formatStr: string): string {
  if (!timestamp) return 'N/A';
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return 'N/A';
  return format(date, formatStr);
}

export default function ActivitiesPage() {
  const [data, setData] = useState<ActivityListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string>('');

  useEffect(() => {
    async function fetchActivities() {
      try {
        setLoading(true);
        const response = await api.getActivities({
          limit: 50,
          source_type: sourceFilter || undefined,
        });
        setData(response);
      } catch (err: any) {
        console.error('Error fetching activities:', err);
        setError(err.message || 'Failed to fetch activities');
      } finally {
        setLoading(false);
      }
    }

    fetchActivities();
  }, [sourceFilter]);

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
      google_drive: 'bg-green-100 text-green-800',
    };
    return colors[source] || 'bg-gray-100 text-gray-800';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Activities</h1>
          <p className="mt-2 text-gray-600">
            {data?.total?.toLocaleString() || 0} activities recorded
          </p>
        </div>
        <div className="flex space-x-2">
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="block rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
          >
            <option value="">All Sources</option>
            <option value="github">GitHub</option>
            <option value="slack">Slack</option>
            <option value="notion">Notion</option>
            <option value="google_drive">Google Drive</option>
          </select>
          <a
            href={api.getExportActivitiesUrl('csv', {
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
            <li key={activity.id} className="px-4 py-4 sm:px-6">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getSourceColor(activity.source_type)}`}>
                      {activity.source_type}
                    </span>
                    <p className="text-sm font-medium text-gray-900">
                      {activity.member_name}
                    </p>
                    <p className="text-sm text-gray-500">
                      {activity.activity_type.replace(/_/g, ' ')}
                    </p>
                  </div>
                  <div className="mt-2 text-sm text-gray-600">
                    {activity.metadata?.title && (
                      <p className="line-clamp-1">{activity.metadata.title}</p>
                    )}
                    {activity.metadata?.message && (
                      <p className="line-clamp-1">{activity.metadata.message}</p>
                    )}
                    {activity.metadata?.repository && (
                      <p className="text-xs text-gray-500 mt-1">
                        Repository: {activity.metadata.repository}
                      </p>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm text-gray-500">
                    {formatTimestamp(activity.timestamp, 'MMM dd, yyyy')}
                  </p>
                  <p className="text-xs text-gray-400">
                    {formatTimestamp(activity.timestamp, 'HH:mm:ss')}
                  </p>
                </div>
              </div>
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
    </div>
  );
}

