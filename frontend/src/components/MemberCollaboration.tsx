"use client";

import { Collaborator, RepositoryActivity } from "@/graphql/types";
import { format } from "date-fns";

interface MemberCollaborationProps {
  collaborators: Collaborator[];
  repositories: RepositoryActivity[];
}

export default function MemberCollaboration({
  collaborators,
  repositories,
}: MemberCollaborationProps) {
  return (
    <div className="space-y-8">
      {/* Top Collaborators Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4 flex items-center">
          <svg
            className="w-6 h-6 mr-2 text-blue-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
            />
          </svg>
          Top Collaborators
        </h2>

        {collaborators.length === 0 ? (
          <p className="text-gray-500 text-center py-4">
            No collaboration data available
          </p>
        ) : (
          <div className="space-y-3">
            {collaborators.map((collab, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <div className="flex items-center space-x-3">
                  <div className="flex-shrink-0">
                    <div className="w-10 h-10 bg-gradient-to-br from-blue-400 to-blue-600 rounded-full flex items-center justify-center text-white font-semibold">
                      {collab.memberName.charAt(0).toUpperCase()}
                    </div>
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">
                      {collab.memberName}
                    </p>
                    <div className="flex items-center space-x-2 text-sm text-gray-500">
                      <span>{collab.collaborationCount} interactions</span>
                      <span>•</span>
                      <span className="flex items-center space-x-1">
                        {collab.collaborationType === "both" && (
                          <>
                            <span className="text-purple-600">🐙 GitHub</span>
                            <span>+</span>
                            <span className="text-green-600">💬 Slack</span>
                          </>
                        )}
                        {collab.collaborationType === "github" && (
                          <span className="text-purple-600">🐙 GitHub</span>
                        )}
                        {collab.collaborationType === "slack" && (
                          <span className="text-green-600">💬 Slack</span>
                        )}
                      </span>
                    </div>
                    {collab.lastCollaboration && (
                      <p className="text-xs text-gray-400 mt-1">
                        Last:{" "}
                        {format(new Date(collab.lastCollaboration), "PPp")}
                      </p>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-blue-600">
                    #{index + 1}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Active Repositories Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4 flex items-center">
          <svg
            className="w-6 h-6 mr-2 text-purple-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
            />
          </svg>
          Active Repositories
        </h2>

        {repositories.length === 0 ? (
          <p className="text-gray-500 text-center py-4">
            No repository activity found
          </p>
        ) : (
          <div className="space-y-3">
            {repositories.map((repo, index) => (
              <div
                key={index}
                className="p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors border border-gray-200"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 mb-2">
                      {repo.repository}
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <div className="flex items-center space-x-2">
                        <span className="text-2xl">💾</span>
                        <div>
                          <p className="text-xs text-gray-500">Commits</p>
                          <p className="text-lg font-semibold text-gray-900">
                            {repo.commitCount}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-2xl">🔀</span>
                        <div>
                          <p className="text-xs text-gray-500">PRs</p>
                          <p className="text-lg font-semibold text-gray-900">
                            {repo.prCount}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-2xl">➕</span>
                        <div>
                          <p className="text-xs text-gray-500">Additions</p>
                          <p className="text-lg font-semibold text-green-600">
                            +{repo.additions.toLocaleString()}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-2xl">➖</span>
                        <div>
                          <p className="text-xs text-gray-500">Deletions</p>
                          <p className="text-lg font-semibold text-red-600">
                            -{repo.deletions.toLocaleString()}
                          </p>
                        </div>
                      </div>
                    </div>
                    {repo.lastActivity && (
                      <p className="text-xs text-gray-400 mt-2">
                        Last activity:{" "}
                        {format(new Date(repo.lastActivity), "PPp")}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

