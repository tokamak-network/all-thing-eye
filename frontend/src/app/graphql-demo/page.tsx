/**
 * GraphQL Demo Page
 *
 * Demonstrates GraphQL integration with Apollo Client.
 */

"use client";

import { useState } from "react";
import { useMembers, useActivities, useActivitySummary } from "@/graphql/hooks";
import { SourceType } from "@/graphql/types";
import { format } from "date-fns";

export default function GraphQLDemoPage() {
  const [selectedMember, setSelectedMember] = useState<string | undefined>();
  const [selectedSource, setSelectedSource] = useState<
    SourceType | undefined
  >();

  // Fetch members
  const {
    data: membersData,
    loading: membersLoading,
    error: membersError,
  } = useMembers({ limit: 10 });

  // Fetch activities
  const {
    data: activitiesData,
    loading: activitiesLoading,
    error: activitiesError,
  } = useActivities({
    memberName: selectedMember,
    source: selectedSource,
    limit: 20,
  });

  // Fetch activity summary
  const { data: summaryData, loading: summaryLoading } = useActivitySummary({
    memberName: selectedMember,
    source: selectedSource,
  });

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="bg-white shadow rounded-lg p-6">
        <h1 className="text-3xl font-bold text-gray-900">GraphQL Demo</h1>
        <p className="mt-2 text-gray-600">
          Testing GraphQL API with Apollo Client
        </p>
      </div>

      {/* Filters */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">Filters</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Member filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Member
            </label>
            <select
              value={selectedMember || ""}
              onChange={(e) => setSelectedMember(e.target.value || undefined)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Members</option>
              {membersData?.members.map((member) => (
                <option key={member.name} value={member.name}>
                  {member.name} ({member.activityCount || 0} activities)
                </option>
              ))}
            </select>
          </div>

          {/* Source filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Source
            </label>
            <select
              value={selectedSource || ""}
              onChange={(e) =>
                setSelectedSource((e.target.value as SourceType) || undefined)
              }
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Sources</option>
              <option value={SourceType.GITHUB}>GitHub</option>
              <option value={SourceType.SLACK}>Slack</option>
              <option value={SourceType.NOTION}>Notion</option>
              <option value={SourceType.DRIVE}>Google Drive</option>
            </select>
          </div>
        </div>
      </div>

      {/* Members Section */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">Members (GraphQL)</h2>
        {membersLoading && <p className="text-gray-500">Loading members...</p>}
        {membersError && (
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-red-800">Error: {membersError.message}</p>
          </div>
        )}
        {membersData && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {membersData.members.map((member) => (
              <div
                key={member.name}
                className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
              >
                <h3 className="font-semibold text-lg">{member.name}</h3>
                {member.email && (
                  <p className="text-sm text-gray-600">{member.email}</p>
                )}
                {member.role && (
                  <span className="inline-block mt-2 px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded">
                    {member.role}
                  </span>
                )}
                <p className="mt-2 text-sm text-gray-700">
                  <strong>Activities:</strong> {member.activityCount || 0}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Activity Summary Section */}
      {summaryData && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">Activity Summary</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-blue-50 rounded-lg p-4">
              <p className="text-sm text-blue-600 font-medium">Total</p>
              <p className="text-2xl font-bold text-blue-900">
                {summaryData.activitySummary.total}
              </p>
            </div>
            {Object.entries(summaryData.activitySummary.bySource).map(
              ([source, count]) => (
                <div key={source} className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-600 font-medium capitalize">
                    {source}
                  </p>
                  <p className="text-2xl font-bold text-gray-900">{count}</p>
                </div>
              )
            )}
          </div>
        </div>
      )}

      {/* Activities Section */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">
          Recent Activities (GraphQL)
        </h2>
        {activitiesLoading && (
          <p className="text-gray-500">Loading activities...</p>
        )}
        {activitiesError && (
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-red-800">Error: {activitiesError.message}</p>
          </div>
        )}
        {activitiesData && (
          <div className="space-y-3">
            {activitiesData.activities.length === 0 ? (
              <p className="text-gray-500 text-center py-8">
                No activities found
              </p>
            ) : (
              activitiesData.activities.map((activity) => (
                <div
                  key={activity.id}
                  className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-semibold">
                          {activity.memberName}
                        </span>
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded">
                          {activity.sourceType}
                        </span>
                        <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded">
                          {activity.activityType}
                        </span>
                      </div>
                      {activity.message && (
                        <p className="text-sm text-gray-700 mt-2">
                          {activity.message}
                        </p>
                      )}
                      {activity.repository && (
                        <p className="text-sm text-gray-600 mt-1">
                          📦 {activity.repository}
                        </p>
                      )}
                    </div>
                    <div className="text-sm text-gray-500 ml-4">
                      {format(new Date(activity.timestamp), "MMM dd, HH:mm")}
                    </div>
                  </div>
                  {activity.url && (
                    <a
                      href={activity.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-800 text-sm mt-2 inline-block"
                    >
                      View →
                    </a>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="font-semibold text-blue-900 mb-2">
          ✅ GraphQL Features Working:
        </h3>
        <ul className="space-y-1 text-blue-800 text-sm">
          <li>✓ Apollo Client integration</li>
          <li>✓ useQuery hooks</li>
          <li>✓ DataLoader batch loading</li>
          <li>✓ Performance monitoring</li>
          <li>✓ Error handling</li>
          <li>✓ Real-time filtering</li>
        </ul>
      </div>
    </div>
  );
}

