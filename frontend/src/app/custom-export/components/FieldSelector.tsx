"use client";

import { useState, useEffect, useMemo } from "react";
import { api } from "@/lib/api";

interface FieldSelectorProps {
  selectedFields: string[];
  onFieldToggle: (fieldId: string) => void;
  selectedCollections: Set<string>;
  onCollectionToggle: (collectionKey: string) => void;
  mode: "fields" | "collections";
}

interface DataSource {
  id: string;
  name: string;
  icon: string;
  fields: Field[];
}

interface Field {
  id: string;
  name: string;
  description?: string;
}

interface Collection {
  name: string;
  count: number;
  source: string;
}

const staticDataSources: DataSource[] = [
  {
    id: "member",
    name: "Member Info",
    icon: "👤",
    fields: [
      { id: "member.name", name: "Name", description: "Member full name" },
      { id: "member.email", name: "Email", description: "Contact email" },
      { id: "member.role", name: "Role", description: "Team role" },
      { id: "member.team", name: "Team", description: "Team assignment" },
    ],
  },
  {
    id: "github",
    name: "GitHub",
    icon: "💻",
    fields: [
      {
        id: "github.commits",
        name: "Commits",
        description: "Total commit count",
      },
      {
        id: "github.additions",
        name: "Lines Added",
        description: "Code additions",
      },
      {
        id: "github.deletions",
        name: "Lines Deleted",
        description: "Code deletions",
      },
      { id: "github.prs", name: "Pull Requests", description: "PR count" },
      { id: "github.issues", name: "Issues", description: "Issue count" },
      {
        id: "github.reviews",
        name: "Code Reviews",
        description: "Review count",
      },
    ],
  },
  {
    id: "slack",
    name: "Slack",
    icon: "💬",
    fields: [
      { id: "slack.messages", name: "Messages", description: "Message count" },
      {
        id: "slack.threads",
        name: "Thread Replies",
        description: "Thread participation",
      },
      {
        id: "slack.reactions",
        name: "Reactions",
        description: "Reaction count",
      },
      { id: "slack.links", name: "Links Shared", description: "Shared URLs" },
      {
        id: "slack.files",
        name: "Files Uploaded",
        description: "File uploads",
      },
    ],
  },
  {
    id: "notion",
    name: "Notion",
    icon: "📝",
    fields: [
      { id: "notion.pages", name: "Pages Created", description: "Page count" },
      { id: "notion.edits", name: "Page Edits", description: "Edit count" },
      { id: "notion.comments", name: "Comments", description: "Comment count" },
    ],
  },
  {
    id: "drive",
    name: "Google Drive",
    icon: "📁",
    fields: [
      { id: "drive.files", name: "Files Created", description: "File count" },
      {
        id: "drive.changes",
        name: "File Changes",
        description: "Modification count",
      },
      { id: "drive.shares", name: "Shares", description: "Sharing activity" },
    ],
  },
  {
    id: "gemini",
    name: "Gemini AI",
    icon: "🤖",
    fields: [
      {
        id: "gemini.daily_analyses",
        name: "Daily Analyses",
        description: "Daily analysis count",
      },
      {
        id: "gemini.meetings_analyzed",
        name: "Meetings Analyzed",
        description: "Total meetings analyzed",
      },
      {
        id: "gemini.total_meeting_time",
        name: "Total Meeting Time",
        description: "Total time analyzed",
      },
      {
        id: "gemini.topics",
        name: "Topics Identified",
        description: "Number of topics found",
      },
      {
        id: "gemini.decisions",
        name: "Key Decisions",
        description: "Number of decisions made",
      },
      {
        id: "gemini.participants",
        name: "Participants",
        description: "Number of participants",
      },
    ],
  },
  {
    id: "recordings",
    name: "Recordings",
    icon: "🎙️",
    fields: [
      {
        id: "recordings.count",
        name: "Recordings Count",
        description: "Total recording count",
      },
      {
        id: "recordings.total_duration",
        name: "Total Duration",
        description: "Total recording duration",
      },
      {
        id: "recordings.by_member",
        name: "Recordings by Member",
        description: "Recordings created by member",
      },
    ],
  },
];

// Map collection names to source types
function getSourceFromCollectionName(collectionName: string, dbSource: string): string {
  // Remove database prefix if present
  const cleanName = collectionName.replace(/^(main|shared|gemini)\./, "");
  
  // Map to source based on collection name patterns
  if (cleanName.startsWith("github_")) {
    return "github";
  } else if (cleanName.startsWith("slack_")) {
    return "slack";
  } else if (cleanName.startsWith("notion_")) {
    return "notion";
  } else if (cleanName.startsWith("drive_")) {
    return "drive";
  } else if (cleanName === "members" || cleanName === "member_identifiers" || cleanName === "member_activities") {
    return "member";
  } else if (cleanName === "recordings_daily" || dbSource === "gemini") {
    return "gemini";
  } else if (cleanName === "recordings" || cleanName === "failed_recordings" || dbSource === "shared") {
    return "recordings";
  } else if (cleanName === "projects" || cleanName === "translations") {
    return "main";
  }
  
  // Default to main for unknown collections
  return "main";
}

// Source display configuration
const sourceConfig: Record<string, { name: string; icon: string }> = {
  member: { name: "Member Info", icon: "👤" },
  github: { name: "GitHub", icon: "💻" },
  slack: { name: "Slack", icon: "💬" },
  notion: { name: "Notion", icon: "📝" },
  drive: { name: "Google Drive", icon: "📁" },
  gemini: { name: "Gemini AI", icon: "🤖" },
  recordings: { name: "Recordings", icon: "🎙️" },
  main: { name: "Other", icon: "🗄️" },
};

export default function FieldSelector({
  selectedFields,
  onFieldToggle,
  selectedCollections,
  onCollectionToggle,
  mode,
}: FieldSelectorProps) {
  const [collections, setCollections] = useState<{
    main: Collection[];
    shared: Collection[];
    gemini: Collection[];
  }>({ main: [], shared: [], gemini: [] });
  const [loading, setLoading] = useState(true);
  const [expandedSources, setExpandedSources] = useState<Set<string>>(
    new Set(["member", "github", "slack", "notion", "drive", "gemini", "recordings"])
  );
  const [expandedCollectionSources, setExpandedCollectionSources] = useState<Set<string>>(
    new Set(["member", "github", "slack", "notion", "drive", "gemini", "recordings"])
  );

  useEffect(() => {
    if (mode === "collections") {
    loadCollections();
    }
  }, [mode]);

  const loadCollections = async () => {
    try {
      setLoading(true);
      const data = await api.getCustomExportCollections();
      setCollections(data.sources || { main: [], shared: [], gemini: [] });
    } catch (err) {
      console.error("Failed to load collections:", err);
    } finally {
      setLoading(false);
    }
  };

  // Group collections by source (like Custom Fields)
  const collectionsBySource = useMemo(() => {
    const grouped: Record<string, Array<{ collection: Collection; key: string }>> = {};
    
    // Process all collections from all databases
    Object.entries(collections).forEach(([dbSource, collectionList]) => {
      collectionList.forEach((col) => {
        const source = getSourceFromCollectionName(col.name, dbSource);
        if (!grouped[source]) {
          grouped[source] = [];
        }
        // Create key with database source prefix
        const key = `${dbSource}:${col.name}`;
        grouped[source].push({ collection: col, key });
      });
    });
    
    return grouped;
  }, [collections]);

  const totalFields = staticDataSources.reduce(
    (sum, ds) => sum + ds.fields.length,
    0
  );
  const selectedCount = selectedFields.length;
  const totalCollections = Object.values(collectionsBySource).reduce(
    (sum, cols) => sum + cols.length,
    0
  );
  const selectedCollectionsCount = selectedCollections.size;

  const toggleSourceExpansion = (sourceId: string) => {
    setExpandedSources((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(sourceId)) {
        newSet.delete(sourceId);
      } else {
        newSet.add(sourceId);
      }
      return newSet;
    });
  };

  const toggleCollectionSourceExpansion = (source: string) => {
    setExpandedCollectionSources((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(source)) {
        newSet.delete(source);
      } else {
        newSet.add(source);
      }
      return newSet;
    });
  };

  const toggleAllCollectionsInSource = (source: string) => {
    const sourceCollections = collectionsBySource[source] || [];
    const allSelected = sourceCollections.every((item) =>
      selectedCollections.has(item.key)
    );

    sourceCollections.forEach((item) => {
      if (allSelected) {
        if (selectedCollections.has(item.key)) {
          onCollectionToggle(item.key);
        }
      } else {
        if (!selectedCollections.has(item.key)) {
          onCollectionToggle(item.key);
        }
      }
    });
  };

  if (mode === "collections") {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        {/* Header */}
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">
            Database Collections
          </h2>
          <p className="text-sm text-gray-600">
            Selected:{" "}
            <span className="font-semibold text-blue-600">
              {selectedCollectionsCount}
            </span>{" "}
            / {totalCollections} collections
          </p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Group collections by source (like Custom Fields) */}
            {Object.entries(collectionsBySource)
              .sort(([a], [b]) => {
                // Sort order: member, github, slack, notion, drive, gemini, recordings, main
                const order = ["member", "github", "slack", "notion", "drive", "gemini", "recordings", "main"];
                const aIndex = order.indexOf(a);
                const bIndex = order.indexOf(b);
                return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
              })
              .map(([source, items]) => {
                const config = sourceConfig[source] || sourceConfig.main;
                const isExpanded = expandedCollectionSources.has(source);
                const allSelected = items.every((item) =>
                  selectedCollections.has(item.key)
                );

                return (
                  <div key={source} className="border-b border-gray-200 pb-3 last:border-0">
                    <div className="flex items-center justify-between mb-2">
                      <button
                        onClick={() => toggleCollectionSourceExpansion(source)}
                        className="flex items-center gap-2 text-sm font-semibold text-gray-800 hover:text-blue-600"
                      >
                        <span>{isExpanded ? "▼" : "▶"}</span>
                        <span>{config.icon}</span>
                        <span>{config.name} ({items.length})</span>
                      </button>
                      <button
                        onClick={() => toggleAllCollectionsInSource(source)}
                        className="text-xs text-blue-600 hover:text-blue-800"
                      >
                        {allSelected ? "Deselect All" : "Select All"}
                      </button>
                    </div>
                    {isExpanded && (
                      <div className="ml-6 space-y-1 mt-2">
                        {items.map((item) => {
                          const { collection: col, key } = item;
                          const isSelected = selectedCollections.has(key);
                          // Remove database prefix for display
                          const displayName = col.name.replace(/^(main|shared|gemini)\./, "");

                          return (
                            <label
                              key={key}
                              className="flex items-center cursor-pointer group py-1"
                            >
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => onCollectionToggle(key)}
                                className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                              />
                              <div className="ml-2 flex-1">
                                <span
                                  className={`text-sm ${
                                    isSelected
                                      ? "text-gray-900 font-medium"
                                      : "text-gray-700"
                                  } group-hover:text-blue-600`}
                                >
                                  {displayName}
                                </span>
                                <span className="ml-2 text-xs text-gray-500">
                                  ({col.count.toLocaleString()})
                                </span>
                              </div>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
          </div>
        )}

        {/* Quick Actions */}
        <div className="mt-6 pt-4 border-t border-gray-200 flex gap-2">
          <button
            onClick={() => {
              Object.values(collectionsBySource)
                .flat()
                .forEach((item) => {
                  if (!selectedCollections.has(item.key)) {
                    onCollectionToggle(item.key);
                  }
                });
            }}
            className="flex-1 text-xs px-3 py-2 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 transition-colors"
          >
            Select All
          </button>
          <button
            onClick={() => {
              selectedCollections.forEach((key) => onCollectionToggle(key));
            }}
            className="flex-1 text-xs px-3 py-2 bg-gray-50 text-gray-700 rounded hover:bg-gray-100 transition-colors"
          >
            Clear All
          </button>
        </div>
      </div>
    );
  }

  // Fields mode (existing functionality)
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      {/* Header */}
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-2">
          Data Sources & Fields
        </h2>
        
        {/* Quick Actions */}
        <div className="mb-2 flex gap-2">
          <button
            onClick={() => {
              const allFieldIds = staticDataSources.flatMap((ds) =>
                ds.fields.map((f) => f.id)
              );
              allFieldIds.forEach((id) => {
                if (!selectedFields.includes(id)) {
                  onFieldToggle(id);
                }
              });
            }}
            className="flex-1 text-xs px-3 py-2 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 transition-colors"
          >
            Select All
          </button>
          <button
            onClick={() => {
              selectedFields.forEach((id) => onFieldToggle(id));
            }}
            className="flex-1 text-xs px-3 py-2 bg-gray-50 text-gray-700 rounded hover:bg-gray-100 transition-colors"
          >
            Clear All
          </button>
        </div>
        
        <p className="text-sm text-gray-600">
          Selected:{" "}
          <span className="font-semibold text-blue-600">{selectedCount}</span> /{" "}
          {totalFields} fields
        </p>
      </div>

      {/* Data Sources */}
      <div className="space-y-6">
        {staticDataSources.map((source) => (
          <div
            key={source.id}
            className="border-b border-gray-100 last:border-0 pb-4 last:pb-0"
          >
            {/* Source Header */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center">
              <span className="text-2xl mr-2">{source.icon}</span>
              <h3 className="font-semibold text-gray-800">{source.name}</h3>
              </div>
              <button
                onClick={() => toggleSourceExpansion(source.id)}
                className="text-gray-500 hover:text-gray-700"
              >
                {expandedSources.has(source.id) ? "▼" : "▶"}
              </button>
            </div>

            {/* Fields */}
            {expandedSources.has(source.id) && (
            <div className="space-y-2 ml-8">
              {source.fields.map((field) => {
                const isSelected = selectedFields.includes(field.id);
                return (
                  <label
                    key={field.id}
                    className="flex items-start cursor-pointer group"
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => onFieldToggle(field.id)}
                      className="mt-1 h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <div className="ml-3">
                      <span
                        className={`text-sm font-medium ${
                          isSelected ? "text-gray-900" : "text-gray-700"
                        } group-hover:text-blue-600`}
                      >
                        {field.name}
                      </span>
                      {field.description && (
                        <p className="text-xs text-gray-500 mt-0.5">
                          {field.description}
                        </p>
                      )}
                    </div>
                  </label>
                );
              })}
            </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
