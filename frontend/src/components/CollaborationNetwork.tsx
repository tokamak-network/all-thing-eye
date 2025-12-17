/**
 * Collaboration Network Component
 *
 * Displays collaboration relationships for a team member.
 * Shows top collaborators with detailed breakdown by source.
 */

"use client";

import React, { useState } from "react";
import { useMemberCollaborations } from "@/graphql/hooks";
import type { Collaboration, CollaborationDetail } from "@/graphql/types";

interface CollaborationNetworkProps {
  memberName: string;
  days?: number;
  limit?: number;
  minScore?: number;
}

export function CollaborationNetwork({
  memberName,
  days = 90,
  limit = 10,
  minScore = 5.0,
}: CollaborationNetworkProps) {
  const [selectedTimeRange, setSelectedTimeRange] = useState(days);
  const [showAll, setShowAll] = useState(false);
  
  const { data, loading, error } = useMemberCollaborations({
    name: memberName,
    days: selectedTimeRange,
    limit,
    minScore,
  });

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-20 bg-gray-100 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="text-red-600">
          <p className="font-semibold">❌ Error loading collaboration data</p>
          <p className="text-sm mt-2">{error.message}</p>
        </div>
      </div>
    );
  }

  if (!data?.memberCollaborations) {
    return null;
  }

  const network = data.memberCollaborations;

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            🤝 Collaboration Network
          </h2>
          <p className="text-sm text-gray-600 mt-1">
            Top collaborators based on interactions across GitHub, Slack, and meetings
          </p>
        </div>
        
        {/* Time Range Selector */}
        <div className="flex gap-2">
          {[30, 90, 180].map((range) => (
            <button
              key={range}
              onClick={() => setSelectedTimeRange(range)}
              className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                selectedTimeRange === range
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              {range} days
            </button>
          ))}
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-blue-50 rounded-lg p-4">
          <div className="text-sm text-blue-600 font-medium">Total Collaborators</div>
          <div className="text-2xl font-bold text-blue-900 mt-1">
            {network.totalCollaborators}
          </div>
        </div>
        <div className="bg-green-50 rounded-lg p-4">
          <div className="text-sm text-green-600 font-medium">Total Score</div>
          <div className="text-2xl font-bold text-green-900 mt-1">
            {network.totalScore.toFixed(1)}
          </div>
        </div>
        <div className="bg-purple-50 rounded-lg p-4">
          <div className="text-sm text-purple-600 font-medium">Time Range</div>
          <div className="text-2xl font-bold text-purple-900 mt-1">
            {network.timeRangeDays} days
          </div>
        </div>
      </div>

      {/* Top Collaborators List */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-gray-900">Top Collaborators</h3>
        
        {network.topCollaborators.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <p>No collaboration data found for the selected time range.</p>
            <p className="text-sm mt-2">Try selecting a longer time period.</p>
          </div>
        ) : (
          <>
            {network.topCollaborators
              .slice(0, showAll ? undefined : 3)
              .map((collab, index) => (
                <CollaboratorCard
                  key={collab.collaboratorName}
                  collaboration={collab}
                  rank={index + 1}
                  maxScore={network.topCollaborators[0].totalScore}
                />
              ))}
            
            {/* Show More/Less Button */}
            {network.topCollaborators.length > 3 && (
              <button
                onClick={() => setShowAll(!showAll)}
                className="w-full py-3 px-4 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-400 hover:text-blue-600 transition-all font-medium"
              >
                {showAll ? (
                  <>
                    ▲ Show Less
                  </>
                ) : (
                  <>
                    ▼ Show {network.topCollaborators.length - 3} More Collaborators
                  </>
                )}
              </button>
            )}
          </>
        )}
      </div>

      {/* Generated timestamp */}
      <div className="text-xs text-gray-400 mt-6 text-center">
        Generated at: {new Date(network.generatedAt).toLocaleString()}
      </div>
    </div>
  );
}

interface CollaboratorCardProps {
  collaboration: Collaboration;
  rank: number;
  maxScore: number;
}

function CollaboratorCard({ collaboration, rank, maxScore }: CollaboratorCardProps) {
  const [expanded, setExpanded] = useState(false);
  
  const scorePercentage = (collaboration.totalScore / maxScore) * 100;
  
  // Get rank emoji
  const getRankEmoji = (rank: number) => {
    if (rank === 1) return "🥇";
    if (rank === 2) return "🥈";
    if (rank === 3) return "🥉";
    return `#${rank}`;
  };

  // Get source icon
  const getSourceIcon = (source: string) => {
    if (source.includes("github_pr")) return "💻";
    if (source.includes("slack")) return "💬";
    if (source.includes("meeting")) return "🎥";
    if (source.includes("github_issue")) return "🐛";
    return "📊";
  };

  // Get source label
  const getSourceLabel = (source: string) => {
    const labels: Record<string, string> = {
      github_pr_review: "GitHub PR Review",
      slack_thread: "Slack Thread",
      meeting: "Meeting",
      github_issue: "GitHub Issue",
    };
    return labels[source] || source;
  };

  return (
    <div className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
      {/* Header */}
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3 flex-1">
          {/* Rank */}
          <div className="text-2xl font-bold w-12 text-center">
            {getRankEmoji(rank)}
          </div>
          
          {/* Collaborator Info */}
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h4 className="text-lg font-semibold text-gray-900">
                {collaboration.collaboratorName}
              </h4>
              {collaboration.commonProjects.length > 0 && (
                <div className="flex gap-1">
                  {collaboration.commonProjects.map((project) => (
                    <span
                      key={project}
                      className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full"
                    >
                      {project.toUpperCase()}
                    </span>
                  ))}
                </div>
              )}
            </div>
            
            {/* Score Bar */}
            <div className="mt-2">
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-gray-600">
                  {collaboration.interactionCount} interactions
                </span>
                <span className="font-semibold text-blue-600">
                  {collaboration.totalScore.toFixed(1)} pts
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${scorePercentage}%` }}
                ></div>
              </div>
            </div>
          </div>
        </div>

        {/* Expand Button */}
        <button className="text-gray-400 hover:text-gray-600 p-2">
          {expanded ? "▲" : "▼"}
        </button>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="grid grid-cols-2 gap-4">
            {/* Collaboration Details */}
            <div>
              <h5 className="text-sm font-semibold text-gray-700 mb-2">
                Collaboration Breakdown
              </h5>
              <div className="space-y-2">
                {collaboration.collaborationDetails.map((detail) => (
                  <div
                    key={detail.source}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="text-gray-600">
                      {getSourceIcon(detail.source)} {getSourceLabel(detail.source)}
                    </span>
                    <span className="font-medium text-gray-900">
                      {detail.activityCount} ({detail.score.toFixed(1)} pts)
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Timeline */}
            <div>
              <h5 className="text-sm font-semibold text-gray-700 mb-2">
                Collaboration Timeline
              </h5>
              <div className="space-y-2 text-sm text-gray-600">
                {collaboration.firstInteraction && (
                  <div>
                    <span className="font-medium">First:</span>{" "}
                    {new Date(collaboration.firstInteraction).toLocaleDateString()}
                  </div>
                )}
                {collaboration.lastInteraction && (
                  <div>
                    <span className="font-medium">Latest:</span>{" "}
                    {new Date(collaboration.lastInteraction).toLocaleDateString()}
                  </div>
                )}
                <div>
                  <span className="font-medium">Duration:</span>{" "}
                  {collaboration.firstInteraction &&
                  collaboration.lastInteraction
                    ? Math.ceil(
                        (new Date(collaboration.lastInteraction).getTime() -
                          new Date(collaboration.firstInteraction).getTime()) /
                          (1000 * 60 * 60 * 24)
                      )
                    : 0}{" "}
                  days
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

