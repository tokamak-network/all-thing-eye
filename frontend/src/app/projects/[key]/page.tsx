'use client';

import { useEffect, useState, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { format } from 'date-fns';
import apiClient from '@/lib/api';
import {
  ArrowLeftIcon,
  FolderIcon,
  CodeBracketIcon,
  ChatBubbleLeftRightIcon,
  DocumentTextIcon,
  UserIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Legend,
} from 'recharts';
import { useProject, useActivities } from '@/graphql/hooks';
import ActivitiesView from '@/components/ActivitiesView';

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectKey = params.key as string;

  // GraphQL: Fetch project data
  const { data: projectData, loading: projectLoading, error: projectError } = useProject({
    key: projectKey,
  });

  const project = projectData?.project;

  // GraphQL: Fetch activities for this project (last 90 days)
  const dateRange = useMemo(() => {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - 90);
    return { start, end };
  }, []);

  const { data: activitiesData, loading: activitiesLoading } = useActivities({
    projectKey: projectKey,
    startDate: dateRange.start.toISOString(),
    endDate: dateRange.end.toISOString(),
    limit: 1000, // Get enough data for statistics
  });

  const activities = useMemo(() => activitiesData?.activities || [], [activitiesData]);

  // Calculate activity statistics
  const activityStats = useMemo(() => {
    const stats = {
      total: activities.length,
      bySource: {
        github: 0,
        slack: 0,
        notion: 0,
        drive: 0,
        recordings: 0,
      },
      byType: {} as Record<string, number>,
      dailyTrends: [] as Array<{
        date: string;
        github: number;
        slack: number;
        notion: number;
        drive: number;
        recordings: number;
      }>,
    };

    // Debug: Log activities count
    console.log('📊 Project activities:', {
      total: activities.length,
      sample: activities.slice(0, 3).map(a => ({
        source: a.sourceType,
        timestamp: a.timestamp,
        id: a.id,
      })),
    });

    // Count by source
    activities.forEach((activity) => {
      const source = activity.sourceType?.toLowerCase() || 'unknown';
      if (source === 'github') stats.bySource.github++;
      else if (source === 'slack') stats.bySource.slack++;
      else if (source === 'notion') stats.bySource.notion++;
      else if (source === 'drive' || source === 'google_drive') stats.bySource.drive++;
      else if (source === 'recordings') stats.bySource.recordings++;

      // Count by type
      const type = activity.activityType || 'unknown';
      stats.byType[type] = (stats.byType[type] || 0) + 1;
    });

    // Calculate daily trends (last 90 days)
    const trendMap: Record<string, { date: string; github: number; slack: number; notion: number; drive: number; recordings: number }> = {};
    
    // Initialize all dates with 0
    const startDate = new Date(dateRange.start);
    for (let i = 0; i < 90; i++) {
      const date = new Date(startDate);
      date.setDate(date.getDate() + i);
      const dateStr = format(date, 'yyyy-MM-dd');
      trendMap[dateStr] = {
        date: dateStr,
        github: 0,
        slack: 0,
        notion: 0,
        drive: 0,
        recordings: 0,
      };
    }

    // Fill in actual data
    let matchedCount = 0;
    activities.forEach((activity) => {
      if (!activity.timestamp) return;
      try {
        const date = new Date(activity.timestamp);
        const dateStr = format(date, 'yyyy-MM-dd');
        if (trendMap[dateStr]) {
          matchedCount++;
          const source = activity.sourceType?.toLowerCase() || 'unknown';
          if (source === 'github') trendMap[dateStr].github++;
          else if (source === 'slack') trendMap[dateStr].slack++;
          else if (source === 'notion') trendMap[dateStr].notion++;
          else if (source === 'drive' || source === 'google_drive') trendMap[dateStr].drive++;
          else if (source === 'recordings') trendMap[dateStr].recordings++;
        }
      } catch (e) {
        console.warn('Failed to parse timestamp:', activity.timestamp, e);
      }
    });

    console.log('📈 Daily trends:', {
      totalDates: Object.keys(trendMap).length,
      matchedActivities: matchedCount,
      sampleTrends: Object.values(trendMap).slice(0, 5),
    });

    stats.dailyTrends = Object.values(trendMap).sort((a, b) => a.date.localeCompare(b.date));

    return stats;
  }, [activities, dateRange]);

  const loading = projectLoading;
  const error = projectError?.message || null;

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <button
            onClick={() => router.push('/projects')}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6"
          >
            <ArrowLeftIcon className="h-5 w-5" />
            Back to Projects
          </button>
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error || 'Project not found'}
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
            onClick={() => router.push('/projects')}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeftIcon className="h-5 w-5" />
            Back to Projects
          </button>
          <div className="flex items-center gap-3 mb-2">
            <FolderIcon className="h-10 w-10 text-blue-600" />
            <div>
              <h1 className="text-3xl font-bold text-gray-900">{project.name}</h1>
              <p className="text-sm text-gray-500">{project.key}</p>
            </div>
            <span
              className={`ml-auto inline-flex px-3 py-1 text-sm font-semibold rounded-full ${
                project.isActive
                  ? 'bg-green-100 text-green-800'
                  : 'bg-gray-100 text-gray-800'
              }`}
            >
              {project.isActive ? 'Active' : 'Inactive'}
            </span>
          </div>
          <p className="mt-2 text-gray-600">
            {activityStats.total.toLocaleString()} activities recorded across all sources
          </p>
        </div>

        {/* Project Members */}
        {project.members && project.members.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
              <UserIcon className="h-5 w-5" />
              Project Members ({project.members.length})
            </h2>
            <div className="flex flex-wrap gap-2">
              {project.members.map((member) => (
                <a
                  key={member.id}
                  href={`/members/${member.id}`}
                  className="inline-flex items-center px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors"
                >
                  {member.name}
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Project Info Card */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Project Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {project.lead && (
              <div className="flex items-center gap-3">
                <UserIcon className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Lead</p>
                  <p className="text-gray-900">{project.lead}</p>
                </div>
              </div>
            )}
            {project.slackChannel && (
              <div className="flex items-center gap-3">
                <ChatBubbleLeftRightIcon className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Slack Channel</p>
                  {project.slackChannelId ? (
                    <a
                      href={`https://tokamaknetwork.slack.com/archives/${project.slackChannelId}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-800"
                    >
                      #{project.slackChannel}
                    </a>
                  ) : (
                    <p className="text-gray-900">#{project.slackChannel}</p>
                  )}
                </div>
              </div>
            )}
            {project.repositories && project.repositories.length > 0 && (
              <div className="flex items-center gap-3">
                <CodeBracketIcon className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Repositories</p>
                  <p className="text-gray-900">{project.repositories.length} repositories</p>
                </div>
              </div>
            )}
          </div>
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
            <div className="h-[300px] w-full">
              {activitiesLoading ? (
                <div className="h-full flex items-center justify-center text-gray-500">
                  <div className="flex flex-col items-center gap-2">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                    <span>Loading activity data...</span>
                  </div>
                </div>
              ) : activities.length === 0 ? (
                <div className="h-full flex items-center justify-center text-gray-500">
                  <div className="text-center">
                    <p className="text-sm">No activities found for this project</p>
                    <p className="text-xs mt-1 text-gray-400">
                      Try adjusting the date range or check project configuration
                    </p>
                  </div>
                </div>
              ) : activityStats.dailyTrends.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart
                    data={activityStats.dailyTrends}
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
                      tickFormatter={(value) => {
                        try {
                          // Handle both string and Date objects
                          const date = typeof value === 'string' ? new Date(value + 'T00:00:00') : value;
                          return format(date, 'MM/dd');
                        } catch (e) {
                          return value;
                        }
                      }}
                      interval="preserveStartEnd"
                    />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip
                      contentStyle={{
                        borderRadius: '8px',
                        border: 'none',
                        boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                      }}
                      labelFormatter={(value) => {
                        try {
                          const date = typeof value === 'string' ? new Date(value + 'T00:00:00') : value;
                          return format(date, 'MMM dd, yyyy');
                        } catch (e) {
                          return value;
                        }
                      }}
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
                    <Area
                      type="monotone"
                      dataKey="recordings"
                      name="Recordings"
                      stackId="1"
                      stroke="#EF4444"
                      fill="#EF4444"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500">
                  {activitiesLoading ? 'Loading trend data...' : 'No trend data available'}
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
                      subject: 'GitHub',
                      A: activityStats.bySource.github,
                      fullMark: Math.max(activityStats.bySource.github, activityStats.bySource.slack, activityStats.bySource.notion, activityStats.bySource.recordings) || 100,
                    },
                    {
                      subject: 'Slack',
                      A: activityStats.bySource.slack,
                      fullMark: Math.max(activityStats.bySource.github, activityStats.bySource.slack, activityStats.bySource.notion, activityStats.bySource.recordings) || 100,
                    },
                    {
                      subject: 'Notion',
                      A: activityStats.bySource.notion,
                      fullMark: Math.max(activityStats.bySource.github, activityStats.bySource.slack, activityStats.bySource.notion, activityStats.bySource.recordings) || 100,
                    },
                    {
                      subject: 'Recordings',
                      A: activityStats.bySource.recordings,
                      fullMark: Math.max(activityStats.bySource.github, activityStats.bySource.slack, activityStats.bySource.notion, activityStats.bySource.recordings) || 100,
                    },
                  ]}
                >
                  <PolarGrid />
                  <PolarAngleAxis
                    dataKey="subject"
                    tick={{ fill: '#4B5563', fontSize: 12 }}
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

        {/* Activity Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {/* Total Activities */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Total Activities</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">
                  {activityStats.total.toLocaleString()}
                </p>
              </div>
              <span className="text-4xl">📊</span>
            </div>
          </div>

          {/* GitHub Activities */}
          {activityStats.bySource.github > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">GitHub</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {activityStats.bySource.github.toLocaleString()}
                  </p>
                </div>
                <span className="text-4xl">🐙</span>
              </div>
            </div>
          )}

          {/* Slack Activities */}
          {activityStats.bySource.slack > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Slack</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {activityStats.bySource.slack.toLocaleString()}
                  </p>
                </div>
                <span className="text-4xl">💬</span>
              </div>
            </div>
          )}

          {/* Other Sources */}
          {(activityStats.bySource.notion > 0 || activityStats.bySource.recordings > 0) && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Other Sources</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {(activityStats.bySource.notion + activityStats.bySource.recordings).toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">Notion, Recordings</p>
                </div>
                <span className="text-4xl">📝</span>
              </div>
            </div>
          )}
        </div>

        {/* GitHub Repositories */}
        {project.repositories && project.repositories.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <CodeBracketIcon className="h-5 w-5" />
                GitHub Repositories
              </h2>
              <span className="text-sm text-gray-500">
                {project.repositories.length} {project.repositories.length === 1 ? 'repository' : 'repositories'}
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {project.repositories.map((repo) => (
                <a
                  key={repo}
                  href={`https://github.com/tokamak-network/${repo}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 p-3 border border-gray-200 rounded-lg hover:bg-gray-50 hover:border-blue-300 transition-colors"
                >
                  <CodeBracketIcon className="h-4 w-4 text-gray-400" />
                  <span className="text-sm text-gray-900">{repo}</span>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Activities Section */}
        <div className="mt-8">
          <ActivitiesView
            initialProjectFilter={projectKey}
            showMemberFilter={false}
          />
        </div>
      </div>
    </div>
  );
}

