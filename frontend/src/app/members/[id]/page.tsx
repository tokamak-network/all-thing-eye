"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { api as apiClient } from "@/lib/api";
import {
  ArrowLeftIcon,
  EnvelopeIcon,
  BriefcaseIcon,
  FolderIcon,
} from "@heroicons/react/24/outline";
import {
  ChartBarIcon,
  ClockIcon,
  CodeBracketIcon,
  ChatBubbleLeftIcon,
  DocumentTextIcon,
  CloudIcon,
} from "@heroicons/react/24/solid";

interface MemberIdentifiers {
  email?: string;
  github?: string;
  slack?: string;
  notion?: string;
}

interface ActivityStats {
  total_activities: number;
  by_source: {
    [key: string]: {
      total: number;
      [key: string]: number;
    };
  };
  by_type: {
    [key: string]: number;
  };
  recent_activities: Array<{
    source: string;
    type: string;
    timestamp: string;
    description: string;
    repository?: string;
  }>;
}

interface MemberDetail {
  id: string;
  name: string;
  email: string;
  role?: string;
  project?: string;
  identifiers: MemberIdentifiers;
  activity_stats: ActivityStats;
  created_at?: string;
  updated_at?: string;
}

export default function MemberDetailPage() {
  const params = useParams();
  const router = useRouter();
  const memberId = params.id as string;
  
  const [member, setMember] = useState<MemberDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadMemberDetail();
  }, [memberId]);

  const loadMemberDetail = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.getMemberDetailById(memberId);
      setMember(data);
    } catch (err: any) {
      console.error("Error loading member detail:", err);
      setError(err.response?.data?.detail || err.message || "Failed to load member details");
    } finally {
      setLoading(false);
    }
  };

  const getSourceIcon = (source: string) => {
    switch (source) {
      case "github":
        return <CodeBracketIcon className="h-5 w-5" />;
      case "slack":
        return <ChatBubbleLeftIcon className="h-5 w-5" />;
      case "notion":
        return <DocumentTextIcon className="h-5 w-5" />;
      case "drive":
        return <CloudIcon className="h-5 w-5" />;
      default:
        return <ChartBarIcon className="h-5 w-5" />;
    }
  };

  const getSourceColor = (source: string) => {
    switch (source) {
      case "github":
        return "bg-gray-100 text-gray-800";
      case "slack":
        return "bg-purple-100 text-purple-800";
      case "notion":
        return "bg-blue-100 text-blue-800";
      case "drive":
        return "bg-green-100 text-green-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return "N/A";
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading member details...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !member) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-8">
            <h2 className="text-xl font-bold text-red-800 mb-2">Error</h2>
            <p className="text-red-600">{error || "Member not found"}</p>
            <button
              onClick={() => router.push("/members")}
              className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
            >
              Back to Members
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => router.push("/members")}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeftIcon className="h-5 w-5" />
            Back to Members
          </button>
          <h1 className="text-3xl font-bold text-gray-900">{member.name}</h1>
        </div>

        {/* Member Info Card */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Profile Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex items-center gap-3">
              <EnvelopeIcon className="h-5 w-5 text-gray-400" />
              <div>
                <p className="text-sm text-gray-500">Email</p>
                <p className="text-gray-900">{member.email}</p>
              </div>
            </div>

            {member.role && (
              <div className="flex items-center gap-3">
                <BriefcaseIcon className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Role</p>
                  <p className="text-gray-900">{member.role}</p>
                </div>
              </div>
            )}

            {member.project && (
              <div className="flex items-center gap-3">
                <FolderIcon className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Project</p>
                  <p className="text-gray-900">{member.project}</p>
                </div>
              </div>
            )}

            {member.identifiers.github && (
              <div className="flex items-center gap-3">
                <CodeBracketIcon className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">GitHub</p>
                  <a
                    href={`https://github.com/${member.identifiers.github}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800"
                  >
                    {member.identifiers.github}
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Activity Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
          {/* Total Activities */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Total Activities</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">
                  {member.activity_stats.total_activities}
                </p>
              </div>
              <ChartBarIcon className="h-10 w-10 text-blue-500" />
            </div>
          </div>

          {/* GitHub Activities */}
          {member.activity_stats.by_source.github && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">GitHub</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {member.activity_stats.by_source.github.total}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {member.activity_stats.by_source.github.commits || 0} commits, {member.activity_stats.by_source.github.pull_requests || 0} PRs
                  </p>
                </div>
                <CodeBracketIcon className="h-10 w-10 text-gray-500" />
              </div>
            </div>
          )}

          {/* Slack Activities */}
          {member.activity_stats.by_source.slack && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Slack</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {member.activity_stats.by_source.slack.total}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {member.activity_stats.by_source.slack.messages || 0} messages
                  </p>
                </div>
                <ChatBubbleLeftIcon className="h-10 w-10 text-purple-500" />
              </div>
            </div>
          )}

          {/* Other Sources */}
          {(member.activity_stats.by_source.notion || member.activity_stats.by_source.drive) && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Other Sources</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {(member.activity_stats.by_source.notion?.total || 0) + 
                     (member.activity_stats.by_source.drive?.total || 0)}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Notion, Drive
                  </p>
                </div>
                <DocumentTextIcon className="h-10 w-10 text-blue-500" />
              </div>
            </div>
          )}
        </div>

        {/* Recent Activities */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
            <ClockIcon className="h-6 w-6 text-gray-600" />
            Recent Activities
          </h2>

          {member.activity_stats.recent_activities.length === 0 ? (
            <p className="text-gray-500 text-center py-8">No recent activities found</p>
          ) : (
            <div className="space-y-4">
              {member.activity_stats.recent_activities.map((activity, index) => (
                <div
                  key={index}
                  className="border-l-4 border-gray-200 pl-4 py-2 hover:border-blue-500 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3 flex-1">
                      <div className={`p-2 rounded-lg ${getSourceColor(activity.source)}`}>
                        {getSourceIcon(activity.source)}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-gray-900 capitalize">
                            {activity.source}
                          </span>
                          <span className="text-sm text-gray-500">•</span>
                          <span className="text-sm text-gray-500 capitalize">
                            {activity.type}
                          </span>
                          {activity.repository && (
                            <>
                              <span className="text-sm text-gray-500">•</span>
                              <span className="text-sm text-gray-600 font-mono">
                                {activity.repository}
                              </span>
                            </>
                          )}
                        </div>
                        <p className="text-sm text-gray-600">{activity.description}</p>
                      </div>
                    </div>
                    <div className="text-right ml-4">
                      <p className="text-xs text-gray-500">
                        {formatDate(activity.timestamp)}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Activity Breakdown by Source */}
        <div className="bg-white rounded-lg shadow p-6 mt-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Activity Breakdown</h2>
          <div className="space-y-4">
            {Object.entries(member.activity_stats.by_source).map(([source, stats]) => {
              const percentage = (stats.total / member.activity_stats.total_activities) * 100;
              return (
                <div key={source}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-700 capitalize flex items-center gap-2">
                      {getSourceIcon(source)}
                      {source}
                    </span>
                    <span className="text-sm text-gray-600">
                      {stats.total} activities ({percentage.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${
                        source === "github" ? "bg-gray-600" :
                        source === "slack" ? "bg-purple-600" :
                        source === "notion" ? "bg-blue-600" :
                        "bg-green-600"
                      }`}
                      style={{ width: `${percentage}%` }}
                    ></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

