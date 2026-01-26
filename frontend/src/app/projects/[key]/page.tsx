'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeftIcon,
  FolderIcon,
  CodeBracketIcon,
  ChatBubbleLeftRightIcon,
  UserIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  DocumentTextIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { useProject } from '@/graphql/hooks';
import ActivitiesView from '@/components/ActivitiesView';

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectKey = params.key as string;
  const [isReposExpanded, setIsReposExpanded] = useState(false);
  const [isReportsExpanded, setIsReportsExpanded] = useState(false);
  const [selectedReport, setSelectedReport] = useState<{ title: string; url: string } | null>(null);

  // GraphQL: Fetch project data
  const { data: projectData, loading: projectLoading, error: projectError } = useProject({
    key: projectKey,
  });

  const project = projectData?.project;

  // Extract file ID from Google Drive URL
  const extractFileId = (driveUrl: string): string | null => {
    const match = driveUrl.match(/\/d\/([a-zA-Z0-9_-]+)/);
    return match ? match[1] : null;
  };

  // Convert Drive URL to embeddable preview URL
  const getPreviewUrl = (driveUrl: string) => {
    const fileId = extractFileId(driveUrl);
    if (fileId) {
      return `https://drive.google.com/file/d/${fileId}/preview`;
    }
    // If it's a folder URL or other format, return as-is
    return driveUrl;
  };

  // Convert Drive URL to backend download URL (uses backend proxy to avoid CORS/auth issues)
  const getDownloadUrl = (driveUrl: string) => {
    const fileId = extractFileId(driveUrl);
    if (fileId) {
      // Use backend API to download the file
      return `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/projects-management/drive/file/${fileId}/download`;
    }
    return driveUrl;
  };

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
          {project.description && (
            <p className="mt-2 text-gray-600">{project.description}</p>
          )}
        </div>

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

          {/* Project Members */}
          {project.members && project.members.length > 0 && (
            <div className="mt-6 pt-6 border-t border-gray-200">
              <div className="flex items-center gap-2 mb-3">
                <UserIcon className="h-5 w-5 text-gray-400" />
                <p className="text-sm text-gray-500">Members ({project.members.length})</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {project.members.map((member) => (
                  <a
                    key={member.id}
                    href={`/members/${member.id}`}
                    className="inline-flex items-center px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors text-sm"
                  >
                    {member.name}
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* GitHub Repositories (Collapsible) */}
        {project.repositories && project.repositories.length > 0 && (
          <div className="bg-white rounded-lg shadow">
            <button
              onClick={() => setIsReposExpanded(!isReposExpanded)}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors rounded-lg"
            >
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                {isReposExpanded ? (
                  <ChevronDownIcon className="h-5 w-5 text-gray-500" />
                ) : (
                  <ChevronRightIcon className="h-5 w-5 text-gray-500" />
                )}
                <CodeBracketIcon className="h-5 w-5" />
                GitHub Repositories
              </h2>
              <span className="text-sm text-gray-500">
                {project.repositories.length} {project.repositories.length === 1 ? 'repository' : 'repositories'}
              </span>
            </button>
            {isReposExpanded && (
              <div className="px-6 pb-6">
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
          </div>
        )}

        {/* Grant Reports (Collapsible) */}
        {project.grantReports && project.grantReports.length > 0 && (
          <div className="bg-white rounded-lg shadow">
            <button
              onClick={() => setIsReportsExpanded(!isReportsExpanded)}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors rounded-lg"
            >
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                {isReportsExpanded ? (
                  <ChevronDownIcon className="h-5 w-5 text-gray-500" />
                ) : (
                  <ChevronRightIcon className="h-5 w-5 text-gray-500" />
                )}
                <DocumentTextIcon className="h-5 w-5" />
                Grant Reports
              </h2>
              <span className="text-sm text-gray-500">
                {project.grantReports.length} {project.grantReports.length === 1 ? 'report' : 'reports'}
              </span>
            </button>
            {isReportsExpanded && (
              <div className="px-6 pb-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {project.grantReports.map((report) => (
                    <button
                      key={report.id}
                      onClick={() => setSelectedReport({ title: report.title, url: report.driveUrl })}
                      className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-blue-50 hover:border-blue-300 transition-colors group text-left"
                    >
                      <div className="flex-shrink-0 w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center group-hover:bg-red-200 transition-colors">
                        <DocumentTextIcon className="h-5 w-5 text-red-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {report.title}
                        </p>
                        <p className="text-xs text-gray-500">
                          {report.year} Q{report.quarter}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* PDF Viewer Modal */}
        {selectedReport && (
          <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-6xl h-[90vh] flex flex-col">
              {/* Modal Header */}
              <div className="flex justify-between items-center px-6 py-4 border-b">
                <h3 className="text-lg font-medium text-gray-900">{selectedReport.title}</h3>
                <div className="flex items-center gap-2">
                  <a
                    href={getDownloadUrl(selectedReport.url)}
                    download
                    className="px-3 py-1.5 text-sm text-green-600 hover:text-green-800 hover:bg-green-50 rounded-lg transition-colors flex items-center gap-1"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Download
                  </a>
                  <a
                    href={selectedReport.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1.5 text-sm text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-lg transition-colors"
                  >
                    Open in Drive
                  </a>
                  <button
                    onClick={() => setSelectedReport(null)}
                    className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    <XMarkIcon className="h-5 w-5" />
                  </button>
                </div>
              </div>
              {/* PDF Viewer */}
              <div className="flex-1 bg-gray-100">
                <iframe
                  src={getPreviewUrl(selectedReport.url)}
                  className="w-full h-full"
                  allow="autoplay"
                  title={selectedReport.title}
                />
              </div>
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

