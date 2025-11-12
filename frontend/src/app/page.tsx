'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import api from '@/lib/api';
import type { ActivitySummaryResponse, ProjectListResponse, MemberListResponse } from '@/types';

export default function Home() {
  const [summary, setSummary] = useState<ActivitySummaryResponse | null>(null);
  const [projects, setProjects] = useState<ProjectListResponse | null>(null);
  const [members, setMembers] = useState<MemberListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const [summaryData, projectsData, membersData] = await Promise.all([
          api.getActivitiesSummary(),
          api.getProjects(),
          api.getMembers({ limit: 10 }),
        ]);
        setSummary(summaryData);
        setProjects(projectsData);
        setMembers(membersData);
      } catch (err: any) {
        console.error('Error fetching data:', err);
        setError(err.message || 'Failed to fetch data');
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, []);

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
        <p className="text-sm text-red-600 mt-2">
          Make sure the backend API is running at: {process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}
        </p>
      </div>
    );
  }

  const totalActivities = summary
    ? Object.values(summary.summary).reduce(
        (sum, source) => sum + source.total_activities,
        0
      )
    : 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-2 text-gray-600">
          Team activity analytics and performance insights
        </p>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <svg className="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Total Members
                  </dt>
                  <dd className="text-3xl font-semibold text-gray-900">
                    {members?.total || 0}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <svg className="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                </svg>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Total Activities
                  </dt>
                  <dd className="text-3xl font-semibold text-gray-900">
                    {totalActivities.toLocaleString()}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <svg className="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Active Projects
                  </dt>
                  <dd className="text-3xl font-semibold text-gray-900">
                    {projects?.total || 0}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <svg className="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
                </svg>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Data Sources
                  </dt>
                  <dd className="text-3xl font-semibold text-gray-900">
                    {summary ? Object.keys(summary.summary).length : 0}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Activity Summary by Source */}
      {summary && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
              Activity Summary by Source
            </h3>
            <div className="space-y-4">
              {Object.entries(summary.summary).map(([source, data]) => (
                <div key={source} className="border-l-4 border-primary-500 pl-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-base font-medium text-gray-900 capitalize">
                        {source}
                      </h4>
                      <p className="text-sm text-gray-500">
                        {data.total_activities.toLocaleString()} activities
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-gray-500">
                        {Object.keys(data.activity_types).length} activity types
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <Link
          href="/members"
          className="bg-white shadow rounded-lg p-6 hover:shadow-lg transition-shadow"
        >
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            View Members
          </h3>
          <p className="text-sm text-gray-500">
            Browse team members and their activity history
          </p>
        </Link>

        <Link
          href="/activities"
          className="bg-white shadow rounded-lg p-6 hover:shadow-lg transition-shadow"
        >
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            View Activities
          </h3>
          <p className="text-sm text-gray-500">
            Explore detailed activity logs across all sources
          </p>
        </Link>

        <Link
          href="/projects"
          className="bg-white shadow rounded-lg p-6 hover:shadow-lg transition-shadow"
        >
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            View Projects
          </h3>
          <p className="text-sm text-gray-500">
            See project-specific analytics and reports
          </p>
        </Link>
      </div>
    </div>
  );
}

