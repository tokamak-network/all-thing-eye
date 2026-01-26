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
  SparklesIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import { useProject } from '@/graphql/hooks';
import ActivitiesView from '@/components/ActivitiesView';
import { api } from '@/lib/api';

// Types for AI Summary
interface ReportSummary {
  report_id: string;
  title: string;
  year: number;
  quarter: number;
  summary: string;
  progress_percentage: number | null;
  key_achievements: string[];
  challenges: string[];
  next_quarter_goals: string[];
  generated_at: string;
  is_cached: boolean;
}

interface ProjectSummary {
  project_key: string;
  project_name: string;
  overall_summary: string;
  progress_trend: 'improving' | 'stable' | 'declining';
  quarterly_summaries: ReportSummary[];
  generated_at: string;
}

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectKey = params.key as string;
  const [isReposExpanded, setIsReposExpanded] = useState(false);
  const [isReportsExpanded, setIsReportsExpanded] = useState(false);
  const [selectedReport, setSelectedReport] = useState<{ title: string; url: string; id?: string } | null>(null);
  
  // Summary state
  const [showSummaryModal, setShowSummaryModal] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [projectSummary, setProjectSummary] = useState<ProjectSummary | null>(null);
  const [reportSummary, setReportSummary] = useState<ReportSummary | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);

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

  // Fetch project-wide summary
  const handleFetchProjectSummary = async () => {
    setSummaryLoading(true);
    setSummaryError(null);
    setShowSummaryModal(true);
    setReportSummary(null);
    
    try {
      const data = await api.getProjectSummary(projectKey);
      setProjectSummary(data);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to generate summary';
      setSummaryError(errorMessage);
    } finally {
      setSummaryLoading(false);
    }
  };

  // Fetch individual report summary
  const handleFetchReportSummary = async (reportId: string, forceRefresh: boolean = false) => {
    setSummaryLoading(true);
    setSummaryError(null);
    setShowSummaryModal(true);
    setProjectSummary(null);
    
    try {
      const data = await api.summarizeGrantReport(projectKey, reportId, forceRefresh);
      setReportSummary(data);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to generate summary';
      setSummaryError(errorMessage);
    } finally {
      setSummaryLoading(false);
    }
  };

  // Get trend icon
  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'improving':
        return <span className="text-green-600">📈 Improving</span>;
      case 'declining':
        return <span className="text-red-600">📉 Declining</span>;
      default:
        return <span className="text-yellow-600">➡️ Stable</span>;
    }
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
            <div className="px-6 py-4 flex items-center justify-between border-b border-gray-100">
              <button
                onClick={() => setIsReportsExpanded(!isReportsExpanded)}
                className="flex items-center gap-2 hover:text-blue-600 transition-colors"
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
                  ({project.grantReports.length})
                </span>
              </button>
              <button
                onClick={handleFetchProjectSummary}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-purple-600 hover:text-purple-800 hover:bg-purple-50 rounded-lg transition-colors"
              >
                <SparklesIcon className="h-4 w-4" />
                AI Summary
              </button>
            </div>
            {isReportsExpanded && (
              <div className="px-6 py-4">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {project.grantReports.map((report) => (
                    <div
                      key={report.id}
                      className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:border-blue-300 transition-colors group"
                    >
                      <button
                        onClick={() => setSelectedReport({ title: report.title, url: report.driveUrl, id: report.id })}
                        className="flex items-center gap-3 flex-1 text-left"
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
                      <button
                        onClick={() => handleFetchReportSummary(report.id)}
                        className="flex-shrink-0 p-2 text-purple-500 hover:text-purple-700 hover:bg-purple-50 rounded-lg transition-colors"
                        title="Generate AI Summary"
                      >
                        <SparklesIcon className="h-4 w-4" />
                      </button>
                    </div>
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

        {/* AI Summary Modal */}
        {showSummaryModal && (
          <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
              {/* Modal Header */}
              <div className="flex justify-between items-center px-6 py-4 border-b bg-gradient-to-r from-purple-50 to-blue-50">
                <h3 className="text-lg font-medium text-gray-900 flex items-center gap-2">
                  <SparklesIcon className="h-5 w-5 text-purple-600" />
                  AI Summary
                </h3>
                <button
                  onClick={() => {
                    setShowSummaryModal(false);
                    setProjectSummary(null);
                    setReportSummary(null);
                    setSummaryError(null);
                  }}
                  className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <XMarkIcon className="h-5 w-5" />
                </button>
              </div>
              
              {/* Modal Content */}
              <div className="flex-1 overflow-y-auto p-6">
                {summaryLoading && (
                  <div className="flex flex-col items-center justify-center py-12">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mb-4"></div>
                    <p className="text-gray-600">Generating AI summary...</p>
                    <p className="text-sm text-gray-400 mt-2">This may take a minute</p>
                  </div>
                )}
                
                {summaryError && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <p className="text-red-800">{summaryError}</p>
                  </div>
                )}
                
                {/* Project Summary View */}
                {projectSummary && !summaryLoading && (
                  <div className="space-y-6">
                    <div className="bg-purple-50 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-semibold text-purple-900">{projectSummary.project_name}</h4>
                        <div className="text-sm">{getTrendIcon(projectSummary.progress_trend)}</div>
                      </div>
                      <p className="text-gray-700 whitespace-pre-wrap">{projectSummary.overall_summary}</p>
                    </div>
                    
                    {projectSummary.quarterly_summaries.length > 0 && (
                      <div>
                        <h4 className="font-semibold text-gray-900 mb-3">Quarterly Reports</h4>
                        <div className="space-y-3">
                          {projectSummary.quarterly_summaries.map((qs) => (
                            <div key={qs.report_id} className="border border-gray-200 rounded-lg p-4">
                              <div className="flex items-center justify-between mb-2">
                                <span className="font-medium text-gray-900">
                                  {qs.year} Q{qs.quarter}
                                </span>
                                {qs.progress_percentage !== null && (
                                  <span className="text-sm bg-blue-100 text-blue-800 px-2 py-0.5 rounded">
                                    {qs.progress_percentage}% progress
                                  </span>
                                )}
                              </div>
                              <p className="text-sm text-gray-600">
                                {qs.summary || 'No summary available - click to generate'}
                              </p>
                              {!qs.summary && (
                                <button
                                  onClick={() => handleFetchReportSummary(qs.report_id)}
                                  className="mt-2 text-sm text-purple-600 hover:text-purple-800"
                                >
                                  Generate Summary →
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                
                {/* Individual Report Summary View */}
                {reportSummary && !summaryLoading && (
                  <div className="space-y-6">
                    <div className="bg-gradient-to-r from-purple-50 to-blue-50 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-semibold text-gray-900">{reportSummary.title}</h4>
                        <div className="flex items-center gap-2">
                          {reportSummary.progress_percentage !== null && (
                            <span className="text-sm bg-blue-100 text-blue-800 px-2 py-0.5 rounded">
                              {reportSummary.progress_percentage}% progress
                            </span>
                          )}
                          {reportSummary.is_cached && (
                            <span className="text-xs text-gray-400">cached</span>
                          )}
                          <button
                            onClick={() => handleFetchReportSummary(reportSummary.report_id, true)}
                            className="p-1 text-gray-400 hover:text-purple-600 transition-colors"
                            title="Refresh summary"
                          >
                            <ArrowPathIcon className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                      <p className="text-sm text-gray-500 mb-3">
                        {reportSummary.year} Q{reportSummary.quarter}
                      </p>
                      <p className="text-gray-700 whitespace-pre-wrap">{reportSummary.summary}</p>
                    </div>
                    
                    {reportSummary.key_achievements.length > 0 && (
                      <div>
                        <h5 className="font-medium text-gray-900 mb-2 flex items-center gap-2">
                          <span className="text-green-500">✓</span> Key Achievements
                        </h5>
                        <ul className="space-y-1">
                          {reportSummary.key_achievements.map((item, idx) => (
                            <li key={idx} className="text-sm text-gray-600 pl-4">• {item}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    
                    {reportSummary.challenges.length > 0 && (
                      <div>
                        <h5 className="font-medium text-gray-900 mb-2 flex items-center gap-2">
                          <span className="text-orange-500">⚠</span> Challenges
                        </h5>
                        <ul className="space-y-1">
                          {reportSummary.challenges.map((item, idx) => (
                            <li key={idx} className="text-sm text-gray-600 pl-4">• {item}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    
                    {reportSummary.next_quarter_goals.length > 0 && (
                      <div>
                        <h5 className="font-medium text-gray-900 mb-2 flex items-center gap-2">
                          <span className="text-blue-500">🎯</span> Next Quarter Goals
                        </h5>
                        <ul className="space-y-1">
                          {reportSummary.next_quarter_goals.map((item, idx) => (
                            <li key={idx} className="text-sm text-gray-600 pl-4">• {item}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
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

