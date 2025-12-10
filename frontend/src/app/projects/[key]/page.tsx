'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import apiClient from '@/lib/api';
import {
  ArrowLeftIcon,
  FolderIcon,
  CodeBracketIcon,
  ChatBubbleLeftRightIcon,
  DocumentTextIcon,
  UserIcon,
} from '@heroicons/react/24/outline';

interface Project {
  id: string;
  key: string;
  name: string;
  description?: string;
  slack_channel?: string;
  slack_channel_id?: string;
  lead?: string;
  repositories: string[];
  repositories_synced_at?: string;
  github_team_slug?: string;
  drive_folders: string[];
  notion_page_ids: string[];
  notion_parent_page_id?: string;
  sub_projects: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectKey = params.key as string;

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchProject() {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getProjectManagement(projectKey);
        setProject(data);
      } catch (err: any) {
        console.error('Error fetching project:', err);
        setError(err.response?.data?.detail || err.message || 'Failed to load project');
      } finally {
        setLoading(false);
      }
    }

    if (projectKey) {
      fetchProject();
    }
  }, [projectKey]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
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
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
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
                project.is_active
                  ? 'bg-green-100 text-green-800'
                  : 'bg-gray-100 text-gray-800'
              }`}
            >
              {project.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>
          {project.description && (
            <p className="text-gray-600 mt-2">{project.description}</p>
          )}
        </div>

        {/* Project Details */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {/* Basic Information */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Basic Information</h2>
            <dl className="space-y-3">
              {project.lead && (
                <div>
                  <dt className="text-sm font-medium text-gray-500 flex items-center gap-2">
                    <UserIcon className="h-4 w-4" />
                    Lead
                  </dt>
                  <dd className="mt-1 text-sm text-gray-900">{project.lead}</dd>
                </div>
              )}
              {project.slack_channel && (
                <div>
                  <dt className="text-sm font-medium text-gray-500 flex items-center gap-2">
                    <ChatBubbleLeftRightIcon className="h-4 w-4" />
                    Slack Channel
                  </dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {project.slack_channel_id ? (
                      <a
                        href={`https://tokamaknetwork.slack.com/archives/${project.slack_channel_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-800"
                      >
                        #{project.slack_channel}
                      </a>
                    ) : (
                      `#${project.slack_channel}`
                    )}
                  </dd>
                </div>
              )}
              {project.github_team_slug && (
                <div>
                  <dt className="text-sm font-medium text-gray-500 flex items-center gap-2">
                    <CodeBracketIcon className="h-4 w-4" />
                    GitHub Team
                  </dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    <a
                      href={`https://github.com/orgs/tokamak-network/teams/${project.github_team_slug}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-800"
                    >
                      {project.github_team_slug}
                    </a>
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {/* Metadata */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Metadata</h2>
            <dl className="space-y-3">
              <div>
                <dt className="text-sm font-medium text-gray-500">Created</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {new Date(project.created_at).toLocaleDateString()}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Last Updated</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {new Date(project.updated_at).toLocaleDateString()}
                </dd>
              </div>
              {project.repositories_synced_at && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Repositories Last Synced</dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {new Date(project.repositories_synced_at).toLocaleString()}
                  </dd>
                </div>
              )}
            </dl>
          </div>
        </div>

        {/* GitHub Repositories */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <CodeBracketIcon className="h-5 w-5" />
              GitHub Repositories
            </h2>
            <span className="text-sm text-gray-500">
              {project.repositories.length} {project.repositories.length === 1 ? 'repository' : 'repositories'}
            </span>
          </div>
          {project.repositories.length > 0 ? (
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
          ) : (
            <div className="text-center py-8 text-gray-500">
              <CodeBracketIcon className="h-12 w-12 mx-auto mb-3 text-gray-300" />
              <p className="text-sm">No repositories found</p>
              <p className="text-xs mt-1">
                Repositories are automatically synced from GitHub Teams at midnight (KST)
              </p>
            </div>
          )}
        </div>

        {/* Drive Folders */}
        {project.drive_folders.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <FolderIcon className="h-5 w-5" />
              Google Drive Folders
            </h2>
            <div className="flex flex-wrap gap-2">
              {project.drive_folders.map((folderId) => (
                <a
                  key={folderId}
                  href={`https://drive.google.com/drive/folders/${folderId}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-3 py-2 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors"
                >
                  <FolderIcon className="h-4 w-4" />
                  <span className="text-sm">{folderId}</span>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Notion Pages */}
        {project.notion_page_ids.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <DocumentTextIcon className="h-5 w-5" />
              Notion Pages
            </h2>
            <div className="flex flex-wrap gap-2">
              {project.notion_page_ids.map((pageId) => (
                <a
                  key={pageId}
                  href={`https://www.notion.so/${pageId.replace(/-/g, '')}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-3 py-2 bg-purple-50 text-purple-700 rounded-lg hover:bg-purple-100 transition-colors"
                >
                  <DocumentTextIcon className="h-4 w-4" />
                  <span className="text-sm">{pageId}</span>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Sub Projects */}
        {project.sub_projects.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Sub Projects</h2>
            <div className="flex flex-wrap gap-2">
              {project.sub_projects.map((subProject) => (
                <span
                  key={subProject}
                  className="inline-flex items-center px-3 py-1 bg-gray-100 text-gray-800 rounded-lg text-sm"
                >
                  {subProject}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

