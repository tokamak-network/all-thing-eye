'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import api from '@/lib/api';
import type { ProjectListResponse } from '@/types';

export default function ProjectsPage() {
  const [data, setData] = useState<ProjectListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchProjects() {
      try {
        setLoading(true);
        const response = await api.getProjects();
        setData(response);
      } catch (err: any) {
        console.error('Error fetching projects:', err);
        setError(err.message || 'Failed to fetch projects');
      } finally {
        setLoading(false);
      }
    }

    fetchProjects();
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
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Projects</h1>
        <p className="mt-2 text-gray-600">
          {data?.total || 0} active projects
        </p>
      </div>

      {/* Projects Grid */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {data?.projects.map((project) => (
          <div
            key={project.key}
            className="bg-white overflow-hidden shadow rounded-lg hover:shadow-lg transition-shadow"
          >
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900">
                  {project.name}
                </h3>
              </div>
              
              <div className="space-y-3">
                <div>
                  <p className="text-sm text-gray-500">Project Lead</p>
                  <p className="text-sm font-medium text-gray-900">{project.lead}</p>
                </div>

                <div>
                  <p className="text-sm text-gray-500">Slack Channel</p>
                  <p className="text-sm font-medium text-gray-900">#{project.slack_channel}</p>
                </div>

                <div>
                  <p className="text-sm text-gray-500">Repositories</p>
                  <p className="text-sm font-medium text-gray-900">
                    {project.repositories.length} repositories
                  </p>
                </div>

                {project.description && (
                  <div>
                    <p className="text-sm text-gray-600 line-clamp-2">
                      {project.description}
                    </p>
                  </div>
                )}
              </div>

              <div className="mt-4">
                <a
                  href={api.getExportProjectUrl(project.key, 'csv')}
                  download
                  className="inline-flex items-center text-sm text-primary-600 hover:text-primary-700"
                >
                  <svg className="mr-1 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Export Data
                </a>
              </div>
            </div>
          </div>
        ))}
      </div>

      {data?.projects.length === 0 && (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No projects found</h3>
          <p className="mt-1 text-sm text-gray-500">
            No projects are configured in the system yet.
          </p>
        </div>
      )}
    </div>
  );
}

