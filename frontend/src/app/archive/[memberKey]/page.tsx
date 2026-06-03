"use client";

import { useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeftIcon,
  UserCircleIcon,
  CodeBracketIcon,
  CalendarDaysIcon,
  DocumentTextIcon,
  VideoCameraIcon,
} from "@heroicons/react/24/outline";
import { useArchiveMember } from "@/graphql/archive";
import type { ArchiveArtifact } from "@/graphql/types";

function formatDate(dateStr?: string): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

function ArtifactRow({ artifact }: { artifact: ArchiveArtifact }) {
  return (
    <tr className="hover:bg-gray-50">
      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
        {formatDate(artifact.date)}
      </td>
      <td className="px-4 py-3 whitespace-nowrap">
        {artifact.type ? (
          <span className="px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-800">
            {artifact.type}
          </span>
        ) : (
          <span className="text-sm text-gray-400">—</span>
        )}
      </td>
      <td className="px-4 py-3 text-sm text-gray-800">
        {artifact.url ? (
          <a
            href={artifact.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-800 hover:underline"
          >
            {artifact.title || artifact.url}
          </a>
        ) : (
          artifact.title || "—"
        )}
        {artifact.scriptUrl && (
          <a
            href={artifact.scriptUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-3 text-xs text-gray-500 hover:text-gray-700 hover:underline"
          >
            script
          </a>
        )}
      </td>
      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
        {artifact.project || "—"}
      </td>
    </tr>
  );
}

export default function ArchiveMemberDetailPage() {
  const params = useParams();
  const router = useRouter();
  const memberKey = params.memberKey as string;

  const { data, loading, error } = useArchiveMember({ memberKey });

  const detail = data?.archiveMember;
  const member = detail?.member;

  // Group artifacts by source
  const artifactsBySource = useMemo(() => {
    if (!detail?.artifacts) return {} as Record<string, ArchiveArtifact[]>;
    return detail.artifacts.reduce<Record<string, ArchiveArtifact[]>>(
      (acc, artifact) => {
        const src = artifact.source || "Other";
        if (!acc[src]) acc[src] = [];
        acc[src].push(artifact);
        return acc;
      },
      {}
    );
  }, [detail?.artifacts]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading archive member...</p>
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
            <p className="text-red-600">
              {error?.message || "Archive member not found"}
            </p>
            <button
              onClick={() => router.push("/archive")}
              className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
            >
              Back to Archive
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Back button + header */}
        <div>
          <button
            onClick={() => router.push("/archive")}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeftIcon className="h-5 w-5" />
            Back to Archive
          </button>
          <h1 className="text-3xl font-bold text-gray-900">
            {member.memberName}
            {member.realNameKr && (
              <span className="ml-3 text-xl font-medium text-gray-500">
                {member.realNameKr}
              </span>
            )}
          </h1>
          {member.realNameEn && member.realNameEn !== member.memberName && (
            <p className="text-gray-500 mt-1">{member.realNameEn}</p>
          )}
        </div>

        {/* Profile Card */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
            <UserCircleIcon className="h-5 w-5 text-amber-500" />
            Profile
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* GitHub */}
            {member.githubUsername && (
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                  GitHub
                </p>
                <a
                  href={`https://github.com/${member.githubUsername}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-800 text-sm font-mono"
                >
                  @{member.githubUsername}
                </a>
              </div>
            )}

            {/* Active Era */}
            {member.activeEra && (
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                  Era
                </p>
                <span className="px-2 py-0.5 text-sm rounded-full bg-amber-100 text-amber-800">
                  {member.activeEra}
                </span>
              </div>
            )}

            {/* Status */}
            {member.status && (
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                  Status
                </p>
                <span className="px-2 py-0.5 text-sm rounded-full bg-gray-100 text-gray-700">
                  {member.status}
                </span>
              </div>
            )}

            {/* Tier */}
            {member.tierFinal && (
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                  Tier
                </p>
                <span className="text-sm font-medium text-gray-800">
                  {member.tierFinal}
                </span>
              </div>
            )}

            {/* Teams */}
            {member.vaultTeams.length > 0 && (
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                  Teams
                </p>
                <div className="flex flex-wrap gap-1">
                  {member.vaultTeams.map((t) => (
                    <span
                      key={t}
                      className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-700"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Roles */}
            {member.vaultRoles.length > 0 && (
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                  Roles
                </p>
                <div className="flex flex-wrap gap-1">
                  {member.vaultRoles.map((r) => (
                    <span
                      key={r}
                      className="px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-800"
                    >
                      {r}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Emails */}
            {member.emails.length > 0 && (
              <div className="md:col-span-2">
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                  Emails
                </p>
                <div className="flex flex-wrap gap-2">
                  {member.emails.map((email) => (
                    <span key={email} className="text-sm text-gray-700">
                      {email}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Stats Bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg shadow p-4 flex items-center gap-3">
            <CodeBracketIcon className="h-8 w-8 text-gray-400 flex-shrink-0" />
            <div>
              <p className="text-xs text-gray-500">Total Commits</p>
              <p className="text-xl font-bold text-gray-900">
                {member.totalCommits?.toLocaleString() ?? "—"}
              </p>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4 flex items-center gap-3">
            <CodeBracketIcon className="h-8 w-8 text-gray-400 flex-shrink-0" />
            <div>
              <p className="text-xs text-gray-500">Repos</p>
              <p className="text-xl font-bold text-gray-900">
                {member.totalRepos?.toLocaleString() ?? "—"}
              </p>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4 flex items-center gap-3">
            <CalendarDaysIcon className="h-8 w-8 text-gray-400 flex-shrink-0" />
            <div>
              <p className="text-xs text-gray-500">First Seen</p>
              <p className="text-sm font-medium text-gray-900">
                {formatDate(member.firstSeen)}
              </p>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4 flex items-center gap-3">
            <CalendarDaysIcon className="h-8 w-8 text-gray-400 flex-shrink-0" />
            <div>
              <p className="text-xs text-gray-500">Last Seen</p>
              <p className="text-sm font-medium text-gray-900">
                {formatDate(member.lastSeen)}
              </p>
            </div>
          </div>
        </div>

        {/* Artifacts by Source */}
        {Object.keys(artifactsBySource).length > 0 && (
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              <DocumentTextIcon className="h-5 w-5 text-blue-500" />
              Artifacts
              <span className="ml-2 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                {detail?.artifactCount ?? detail?.artifacts.length}
              </span>
            </h2>

            {Object.entries(artifactsBySource).map(([source, artifacts]) => (
              <div key={source} className="bg-white rounded-lg shadow overflow-hidden">
                <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                  <span className="text-sm font-semibold text-gray-700 uppercase tracking-wider">
                    {source}
                  </span>
                  <span className="ml-2 text-xs text-gray-500">
                    ({artifacts.length})
                  </span>
                </div>
                <table className="min-w-full divide-y divide-gray-100">
                  <thead>
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider w-28">
                        Date
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider w-32">
                        Type
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                        Title
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider w-32">
                        Project
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {artifacts.map((artifact) => (
                      <ArtifactRow
                        key={artifact.artifactId}
                        artifact={artifact}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        )}

        {/* Meetings */}
        {detail?.meetings && detail.meetings.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              <VideoCameraIcon className="h-5 w-5 text-purple-500" />
              Meetings
              <span className="ml-2 px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                {detail.meetings.length}
              </span>
            </h2>
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full divide-y divide-gray-100">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider w-28">
                      Date
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Title
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider w-24">
                      Role
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {detail.meetings.map((meeting) => (
                    <tr key={meeting.artifactId} className="hover:bg-gray-50">
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        {formatDate(meeting.date)}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-800">
                        {meeting.url ? (
                          <a
                            href={meeting.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 hover:underline"
                          >
                            {meeting.title || meeting.url}
                          </a>
                        ) : (
                          meeting.title || "—"
                        )}
                        {meeting.scriptUrl && (
                          <a
                            href={meeting.scriptUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="ml-3 text-xs text-gray-500 hover:text-gray-700 hover:underline"
                          >
                            script
                          </a>
                        )}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        {meeting.role || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Empty state when no artifacts or meetings */}
        {Object.keys(artifactsBySource).length === 0 &&
          (!detail?.meetings || detail.meetings.length === 0) && (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
              No artifacts or meetings recorded for this member.
            </div>
          )}
      </div>
    </div>
  );
}
