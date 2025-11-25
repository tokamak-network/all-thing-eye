"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useAppStats } from "@/hooks/useAppStats";

interface Collection {
  name: string;
  count: number;
  size: number;
  avgObjSize: number;
  storageSize: number;
  indexes: number;
}

interface CollectionsData {
  collections: Collection[];
  total_collections: number;
  total_documents: number;
}

interface SchemaField {
  types: string[];
  nullable: boolean;
  null_percentage: number;
  occurrence: number;
  occurrence_percentage: number;
  examples: any[];
}

interface SchemaData {
  collection: string;
  schema: Record<string, SchemaField>;
  sample_count: number;
  total_fields: number;
}

interface Pagination {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
  has_prev: boolean;
  has_next: boolean;
}

interface DocumentsData {
  collection: string;
  documents: any[];
  pagination: Pagination;
}

export default function DatabasePage() {
  // Use unified stats hook for consistent data
  const {
    stats: appStats,
    loading: statsLoading,
    error: statsError,
  } = useAppStats();

  const [collections, setCollections] = useState<CollectionsData | null>(null);
  const [lastCollected, setLastCollected] = useState<Record<string, string>>(
    {}
  );
  const [selectedCollection, setSelectedCollection] = useState<string | null>(
    null
  );
  const [schema, setSchema] = useState<SchemaData | null>(null);
  const [documentsData, setDocumentsData] = useState<DocumentsData | null>(
    null
  );
  const [detailLoading, setDetailLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"documents" | "tree" | "schema">(
    "documents"
  );
  const [currentPage, setCurrentPage] = useState(1);
  const [documentsPerPage, setDocumentsPerPage] = useState(30);
  const [expandedDocs, setExpandedDocs] = useState<Set<number>>(new Set());
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
    new Set(["members", "github", "slack", "notion", "drive"])
  );
  const [expandedCollections, setExpandedCollections] = useState<Set<string>>(
    new Set()
  );
  const [collectionPreviews, setCollectionPreviews] = useState<
    Record<string, { schema: any; samples: any[]; latest: any }>
  >({});
  const [loadingPreviews, setLoadingPreviews] = useState<Set<string>>(
    new Set()
  );

  // Load collections data
  useEffect(() => {
    const loadCollections = async () => {
      try {
        const data = await api.getDatabaseCollections();
        setCollections(data);
      } catch (err) {
        console.error("Failed to load collections:", err);
      }
    };
    loadCollections();
  }, []);

  // Load last collected times
  useEffect(() => {
    const loadLastCollected = async () => {
      try {
        const data = await api.getLastCollected();
        setLastCollected(data.last_collected || {});
      } catch (err) {
        console.error("Failed to load last collected times:", err);
      }
    };
    loadLastCollected();
  }, []);

  const handleCollectionClick = async (collectionName: string) => {
    setSelectedCollection(collectionName);
    setDetailLoading(true);
    setActiveTab("documents");
    setCurrentPage(1);
    setExpandedDocs(new Set());
    setExpandedPaths(new Set());

    try {
      // Load documents and schema
      const [documentsData, schemaData] = await Promise.all([
        api.getCollectionDocuments(
          collectionName,
          1,
          documentsPerPage
        ) as Promise<DocumentsData>,
        api.getCollectionSchema(collectionName) as Promise<SchemaData>,
      ]);

      setDocumentsData(documentsData);
      setSchema(schemaData);
    } catch (err) {
      console.error("Failed to load collection details:", err);
    } finally {
      setDetailLoading(false);
    }
  };

  const loadPage = async (page: number) => {
    if (!selectedCollection) return;

    setDetailLoading(true);
    try {
      const data = (await api.getCollectionDocuments(
        selectedCollection,
        page,
        documentsPerPage
      )) as DocumentsData;
      setDocumentsData(data);
      setCurrentPage(page);
      setExpandedDocs(new Set());
      setExpandedPaths(new Set()); // Clear tree view expansion state
    } catch (err) {
      console.error("Failed to load page:", err);
    } finally {
      setDetailLoading(false);
    }
  };

  const toggleDocExpansion = (index: number) => {
    setExpandedDocs((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  const togglePath = (path: string) => {
    setExpandedPaths((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(path)) {
        newSet.delete(path);
      } else {
        newSet.add(path);
      }
      return newSet;
    });
  };

  const expandAll = () => {
    if (!documentsData) return;
    const allPaths = new Set<string>();

    const collectPaths = (obj: any, path: string = "") => {
      if (obj && typeof obj === "object") {
        Object.keys(obj).forEach((key) => {
          const newPath = path ? `${path}.${key}` : key;
          allPaths.add(newPath);
          collectPaths(obj[key], newPath);
        });
      }
    };

    documentsData.documents.forEach((doc, idx) => {
      allPaths.add(`doc-${idx}`);
      collectPaths(doc, `doc-${idx}`);
    });

    setExpandedPaths(allPaths);
  };

  const collapseAll = () => {
    setExpandedPaths(new Set());
  };

  const toggleGroup = (group: string) => {
    setExpandedGroups((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(group)) {
        newSet.delete(group);
      } else {
        newSet.add(group);
      }
      return newSet;
    });
  };

  const toggleCollection = async (collectionName: string) => {
    const isExpanded = expandedCollections.has(collectionName);

    setExpandedCollections((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(collectionName)) {
        newSet.delete(collectionName);
      } else {
        newSet.add(collectionName);
      }
      return newSet;
    });

    // Load preview data if not already loaded and expanding
    if (!isExpanded && !collectionPreviews[collectionName]) {
      setLoadingPreviews((prev) => new Set(prev).add(collectionName));

      try {
        console.log(`🔍 Loading preview for: ${collectionName}`);

        const [schema, documents] = await Promise.all([
          api.getCollectionSchema(collectionName),
          api.getCollectionDocuments(collectionName, 1, 1), // Get most recent 1 doc
        ]);

        console.log(`✅ Schema loaded:`, schema);
        console.log(`✅ Documents loaded:`, documents);
        console.log(`✅ Latest document:`, documents.documents?.[0]);

        const latestDoc =
          documents.documents && documents.documents.length > 0
            ? documents.documents[0]
            : null;

        setCollectionPreviews((prev) => ({
          ...prev,
          [collectionName]: {
            schema: schema,
            samples: documents.documents || [],
            latest: latestDoc,
          },
        }));

        console.log(`✅ Preview set for ${collectionName}:`, {
          hasSchema: !!schema,
          hasSamples: !!(documents.documents && documents.documents.length > 0),
          hasLatest: !!latestDoc,
          latestDoc: latestDoc,
        });
      } catch (error) {
        console.error(
          `❌ Failed to load collection preview for ${collectionName}:`,
          error
        );
      } finally {
        setLoadingPreviews((prev) => {
          const newSet = new Set(prev);
          newSet.delete(collectionName);
          return newSet;
        });
      }
    }
  };

  const getCollectionGroup = (
    collectionName: string
  ): { group: string; color: string; icon: string } => {
    if (collectionName.startsWith("member")) {
      return { group: "members", color: "blue", icon: "👥" };
    } else if (collectionName.startsWith("github")) {
      return { group: "github", color: "green", icon: "🐙" };
    } else if (collectionName.startsWith("slack")) {
      return { group: "slack", color: "purple", icon: "💬" };
    } else if (collectionName.startsWith("notion")) {
      return { group: "notion", color: "orange", icon: "📝" };
    } else if (collectionName.startsWith("drive")) {
      return { group: "drive", color: "yellow", icon: "📁" };
    }
    return { group: "other", color: "gray", icon: "📦" };
  };

  const groupedCollections = () => {
    if (!collections) return {};

    const groups: Record<string, Collection[]> = {
      members: [],
      github: [],
      slack: [],
      notion: [],
      drive: [],
      other: [],
    };

    collections.collections.forEach((collection) => {
      const { group } = getCollectionGroup(collection.name);
      groups[group].push(collection);
    });

    return groups;
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
  };

  const getTypeColor = (type: string): string => {
    const colors: Record<string, string> = {
      str: "bg-blue-100 text-blue-800",
      int: "bg-green-100 text-green-800",
      float: "bg-green-100 text-green-800",
      bool: "bg-yellow-100 text-yellow-800",
      datetime: "bg-purple-100 text-purple-800",
      ObjectId: "bg-red-100 text-red-800",
      object: "bg-gray-100 text-gray-800",
      array: "bg-indigo-100 text-indigo-800",
      null: "bg-gray-100 text-gray-600",
    };
    return colors[type] || "bg-gray-100 text-gray-800";
  };

  // Tree View Component
  const TreeNode = ({
    data,
    path,
    level = 0,
    nodeKey,
  }: {
    data: any;
    path: string;
    level?: number;
    nodeKey?: string;
  }) => {
    const isExpanded = expandedPaths.has(path);
    const isExpandable =
      data && typeof data === "object" && Object.keys(data).length > 0;

    const getValueType = (val: any): string => {
      if (val === null) return "null";
      if (Array.isArray(val)) return "array";
      if (typeof val === "object") return "object";
      return typeof val;
    };

    const getValuePreview = (val: any): string => {
      if (val === null || val === undefined) return "null";
      if (typeof val === "boolean") return val ? "true" : "false";
      if (typeof val === "number") return String(val);
      if (typeof val === "string") {
        if (val.length > 50) return `"${val.substring(0, 50)}..."`;
        return `"${val}"`;
      }
      if (Array.isArray(val)) return `Array[${val.length}]`;
      if (typeof val === "object") return `Object{${Object.keys(val).length}}`;
      return String(val);
    };

    const getTypeColor = (type: string): string => {
      const colors: Record<string, string> = {
        string: "text-green-700",
        number: "text-blue-700",
        boolean: "text-purple-700",
        null: "text-gray-500",
        object: "text-gray-800",
        array: "text-gray-800",
      };
      return colors[type] || "text-gray-800";
    };

    if (!isExpandable) {
      // Leaf node
      return (
        <div
          className="flex items-start gap-2 py-0.5 hover:bg-gray-50"
          style={{ paddingLeft: `${level * 20}px` }}
        >
          <span className="text-gray-400 w-4 text-center">—</span>
          {nodeKey && (
            <span className="font-mono text-sm text-gray-700">{nodeKey}:</span>
          )}
          <span className={`text-sm ${getTypeColor(getValueType(data))}`}>
            {getValuePreview(data)}
          </span>
        </div>
      );
    }

    // Branch node
    return (
      <div>
        <div
          className="flex items-start gap-2 py-0.5 hover:bg-gray-100 cursor-pointer"
          style={{ paddingLeft: `${level * 20}px` }}
          onClick={() => togglePath(path)}
        >
          <button className="text-gray-500 hover:text-gray-700 w-4 text-center">
            {isExpanded ? "▼" : "▶"}
          </button>
          {nodeKey && (
            <span className="font-mono text-sm font-semibold text-gray-800">
              {nodeKey}:
            </span>
          )}
          <span className="text-xs text-gray-500">
            {Array.isArray(data)
              ? `Array[${data.length}]`
              : `Object{${Object.keys(data).length}}`}
          </span>
        </div>

        {isExpanded && (
          <div>
            {Array.isArray(data)
              ? data.map((item, idx) => (
                  <TreeNode
                    key={idx}
                    data={item}
                    path={`${path}.${idx}`}
                    level={level + 1}
                    nodeKey={String(idx)}
                  />
                ))
              : Object.entries(data).map(([key, value]) => (
                  <TreeNode
                    key={key}
                    data={value}
                    path={`${path}.${key}`}
                    level={level + 1}
                    nodeKey={key}
                  />
                ))}
          </div>
        )}
      </div>
    );
  };

  const renderValue = (value: any, key?: string): JSX.Element => {
    if (value === null || value === undefined) {
      return <span className="text-gray-400 italic">null</span>;
    }

    if (typeof value === "boolean") {
      return (
        <span className="text-yellow-700 font-mono">
          {value ? "true" : "false"}
        </span>
      );
    }

    if (typeof value === "number") {
      return <span className="text-green-700 font-mono">{value}</span>;
    }

    if (typeof value === "string") {
      // Check if it's an ObjectId
      if (key === "_id" || /^[a-f\d]{24}$/i.test(value)) {
        return <span className="text-red-700 font-mono text-xs">{value}</span>;
      }
      // Check if it's a date
      if (value.includes("T") && value.includes("Z")) {
        return (
          <span className="text-purple-700 font-mono text-xs">{value}</span>
        );
      }
      return <span className="text-blue-700">&quot;{value}&quot;</span>;
    }

    if (Array.isArray(value)) {
      return <span className="text-indigo-700">Array[{value.length}]</span>;
    }

    if (typeof value === "object") {
      return <span className="text-gray-700">Object</span>;
    }

    return <span>{String(value)}</span>;
  };

  // Loading state handled above with statsLoading

  // Collections check handled above with appStats

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-[95%] mx-auto">
        {/* Header */}
        <div className="mb-4">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            🗄️ Database Viewer
          </h1>
          <p className="text-gray-600">
            MongoDB data browser inspired by{" "}
            <a
              href="https://github.com/mongo-express/mongo-express"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline"
            >
              mongo-express
            </a>
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-blue-600">
              {collections?.total_collections ?? 0}
            </div>
            <div className="text-xs text-gray-600 mt-1">Collections</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-green-600">
              {(collections?.total_documents ?? 0).toLocaleString()}
            </div>
            <div className="text-xs text-gray-600 mt-1">Total Documents</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-purple-600">
              {/* Storage size calculation removed as not available in unified stats */}
              N/A
            </div>
            <div className="text-xs text-gray-600 mt-1">Storage Size</div>
          </div>
        </div>

        {/* Last Collection Times */}
        {Object.keys(lastCollected).length > 0 && (
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg shadow p-4 mb-6 border border-blue-200">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                <span className="text-lg">⏰</span>
                Last Data Collection
              </h3>
            </div>
            <div className="grid grid-cols-4 gap-4">
              {Object.entries(lastCollected).map(([source, time]) => {
                const sourceIcons: Record<string, string> = {
                  github: "🐙",
                  slack: "💬",
                  notion: "📝",
                  drive: "📁",
                };

                const sourceColors: Record<string, string> = {
                  github: "text-green-700 bg-green-100",
                  slack: "text-purple-700 bg-purple-100",
                  notion: "text-orange-700 bg-orange-100",
                  drive: "text-yellow-700 bg-yellow-100",
                };

                const getTimeAgo = (isoTime: string | null) => {
                  if (!isoTime) return "Never collected";
                  const date = new Date(isoTime);
                  const now = new Date();
                  const diffMs = now.getTime() - date.getTime();
                  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
                  const diffDays = Math.floor(diffHours / 24);

                  if (diffDays > 1) return `${diffDays} days ago`;
                  if (diffHours > 1) return `${diffHours} hours ago`;
                  if (diffHours === 1) return "1 hour ago";
                  return "Just now";
                };

                const getStatus = (isoTime: string | null) => {
                  if (!isoTime)
                    return { text: "No data", color: "text-gray-500" };
                  const date = new Date(isoTime);
                  const now = new Date();
                  const diffMs = now.getTime() - date.getTime();
                  const diffHours = diffMs / (1000 * 60 * 60);

                  if (diffHours < 24)
                    return { text: "✓ Fresh", color: "text-green-600" };
                  if (diffHours < 48)
                    return { text: "⚠ 1 day old", color: "text-yellow-600" };
                  return { text: "⚠ Stale", color: "text-red-600" };
                };

                const status = getStatus(time);

                return (
                  <div
                    key={source}
                    className={`rounded-lg p-3 ${
                      sourceColors[source] || "bg-gray-100"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-base">{sourceIcons[source]}</span>
                      <span className="font-semibold capitalize text-sm">
                        {source}
                      </span>
                    </div>
                    <div className="text-xs font-medium mb-1">
                      {getTimeAgo(time)}
                    </div>
                    <div className={`text-xs font-semibold ${status.color}`}>
                      {status.text}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Error Message */}
        {statsError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-800">{statsError}</p>
          </div>
        )}

        <div className="grid grid-cols-12 gap-4">
          {/* Collections List */}
          <div className="col-span-3">
            <div className="bg-white rounded-lg shadow">
              <div className="p-4 border-b border-gray-200">
                <h2 className="text-xl font-semibold text-gray-900">
                  Collections
                </h2>
              </div>
              <div className="max-h-[800px] overflow-y-auto">
                {Object.entries(groupedCollections()).map(
                  ([groupName, groupCollections]) => {
                    if (groupCollections.length === 0) return null;

                    const { icon, color } = getCollectionGroup(
                      groupCollections[0].name
                    );
                    const isGroupExpanded = expandedGroups.has(groupName);

                    const groupColors = {
                      blue: "bg-blue-100 text-blue-800 border-blue-200",
                      green: "bg-green-100 text-green-800 border-green-200",
                      purple: "bg-purple-100 text-purple-800 border-purple-200",
                      orange: "bg-orange-100 text-orange-800 border-orange-200",
                      yellow: "bg-yellow-100 text-yellow-800 border-yellow-200",
                      gray: "bg-gray-100 text-gray-800 border-gray-200",
                    };

                    return (
                      <div key={groupName} className="border-b border-gray-200">
                        {/* Group Header */}
                        <button
                          onClick={() => toggleGroup(groupName)}
                          className={`w-full text-left p-3 hover:bg-gray-50 transition-colors border-l-4 ${
                            groupColors[color as keyof typeof groupColors]
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <span className="text-sm">
                              {isGroupExpanded ? "▼" : "▶"}
                            </span>
                            <span className="text-base">{icon}</span>
                            <span className="font-semibold capitalize text-sm">
                              {groupName}
                            </span>
                            <span className="ml-auto text-xs text-gray-500">
                              {groupCollections.length}
                            </span>
                          </div>
                        </button>

                        {/* Group Collections */}
                        {isGroupExpanded && (
                          <div className="bg-gray-50">
                            {groupCollections.map((collection) => (
                              <button
                                key={collection.name}
                                onClick={() =>
                                  handleCollectionClick(collection.name)
                                }
                                className={`w-full text-left pl-8 pr-3 py-2 hover:bg-gray-100 transition-colors ${
                                  selectedCollection === collection.name
                                    ? "bg-blue-50 border-l-4 border-blue-600"
                                    : "border-l-4 border-transparent"
                                }`}
                              >
                                <div className="font-medium text-gray-900 mb-1 text-sm">
                                  {collection.name}
                                </div>
                                <div className="flex flex-col gap-0.5 text-xs text-gray-600">
                                  <span>
                                    📄 {collection.count.toLocaleString()}
                                  </span>
                                  <span>💾 {formatBytes(collection.size)}</span>
                                </div>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  }
                )}
              </div>
            </div>
          </div>

          {/* Collection Details */}
          <div className="col-span-9">
            {!selectedCollection ? (
              <div className="bg-white rounded-lg shadow">
                {/* Database Overview */}
                <div className="p-6 border-b border-gray-200">
                  <h2 className="text-2xl font-bold text-gray-900 mb-2">
                    📊 Database Overview
                  </h2>
                  <p className="text-gray-600">
                    Visual map of your MongoDB collections and schema structure
                  </p>
                </div>

                <div className="p-6">
                  {/* Firebase-style Collection Tree */}
                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 bg-gray-50 mb-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">
                      🔗 Database Structure
                    </h3>
                    <div className="font-mono text-sm space-y-1">
                      {Object.entries(groupedCollections()).map(
                        ([groupName, groupCollections]) => {
                          if (groupCollections.length === 0) return null;

                          const { icon, color } = getCollectionGroup(
                            groupCollections[0].name
                          );
                          const isExpanded = expandedGroups.has(groupName);

                          const colorClasses = {
                            blue: "bg-blue-50 hover:bg-blue-100 text-blue-900",
                            green:
                              "bg-green-50 hover:bg-green-100 text-green-900",
                            purple:
                              "bg-purple-50 hover:bg-purple-100 text-purple-900",
                            orange:
                              "bg-orange-50 hover:bg-orange-100 text-orange-900",
                            yellow:
                              "bg-yellow-50 hover:bg-yellow-100 text-yellow-900",
                            gray: "bg-gray-50 hover:bg-gray-100 text-gray-900",
                          };

                          const borderClasses = {
                            blue: "border-blue-200",
                            green: "border-green-200",
                            purple: "border-purple-200",
                            orange: "border-orange-200",
                            yellow: "border-yellow-200",
                            gray: "border-gray-200",
                          };

                          const textClasses = {
                            blue: "text-blue-700",
                            green: "text-green-700",
                            purple: "text-purple-700",
                            orange: "text-orange-700",
                            yellow: "text-yellow-700",
                            gray: "text-gray-700",
                          };

                          const totalDocs = groupCollections.reduce(
                            (sum, col) => sum + col.count,
                            0
                          );

                          return (
                            <div key={groupName}>
                              {/* Group Header */}
                              <div
                                onClick={() => toggleGroup(groupName)}
                                className={`flex items-center gap-2 px-3 py-2 rounded cursor-pointer border ${
                                  colorClasses[
                                    color as keyof typeof colorClasses
                                  ]
                                } ${
                                  borderClasses[
                                    color as keyof typeof borderClasses
                                  ]
                                }`}
                              >
                                <button className="text-gray-500 hover:text-gray-700 w-4">
                                  {isExpanded ? "▼" : "▶"}
                                </button>
                                <span className="text-lg">{icon}</span>
                                <span className="font-semibold capitalize">
                                  {groupName}
                                </span>
                                <span
                                  className={`text-xs ml-auto ${
                                    textClasses[
                                      color as keyof typeof textClasses
                                    ]
                                  }`}
                                >
                                  {groupCollections.length} collections,{" "}
                                  {totalDocs.toLocaleString()} docs
                                </span>
                              </div>

                              {/* Group Collections */}
                              {isExpanded && (
                                <div className="ml-6 mt-1 space-y-1">
                                  {groupCollections.map((collection) => {
                                    const isCollectionExpanded =
                                      expandedCollections.has(collection.name);
                                    const preview =
                                      collectionPreviews[collection.name];

                                    return (
                                      <div key={collection.name}>
                                        {/* Collection Header */}
                                        <div
                                          onClick={() =>
                                            toggleCollection(collection.name)
                                          }
                                          className="flex items-center gap-2 px-3 py-2 rounded hover:bg-white cursor-pointer border border-transparent hover:border-gray-200 transition-all"
                                        >
                                          <button className="text-gray-400 hover:text-gray-700 w-4">
                                            {isCollectionExpanded ? "▼" : "▶"}
                                          </button>
                                          <span className="text-gray-700">
                                            {collection.name}
                                          </span>
                                          <span className="text-xs text-gray-500 ml-auto">
                                            {collection.count.toLocaleString()}{" "}
                                            docs •{" "}
                                            {formatBytes(collection.size)}
                                          </span>
                                        </div>

                                        {/* Collection Preview */}
                                        {isCollectionExpanded && (
                                          <div className="ml-8 mt-2 mb-3 space-y-3 bg-white rounded-lg p-4 border border-gray-200">
                                            {/* Loading State */}
                                            {loadingPreviews.has(
                                              collection.name
                                            ) && (
                                              <div className="flex items-center justify-center py-8 text-gray-500">
                                                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3"></div>
                                                <span>Loading preview...</span>
                                              </div>
                                            )}

                                            {/* Latest Document */}
                                            {!loadingPreviews.has(
                                              collection.name
                                            ) &&
                                              preview?.latest && (
                                                <div>
                                                  <h4 className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-2">
                                                    <span>
                                                      📄 Latest Document
                                                    </span>
                                                    <span className="text-gray-500 font-normal">
                                                      (Most Recent)
                                                    </span>
                                                  </h4>
                                                  <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg p-3 border border-blue-200">
                                                    <div className="space-y-2 text-xs">
                                                      {Object.entries(
                                                        preview.latest
                                                      )
                                                        .slice(0, 8)
                                                        .map(([key, value]) => {
                                                          // Get field schema info
                                                          const fieldSchema =
                                                            preview.schema?.fields?.find(
                                                              (f: any) =>
                                                                f.field === key
                                                            );

                                                          return (
                                                            <div
                                                              key={key}
                                                              className="flex items-start gap-3 bg-white rounded px-3 py-2 border border-blue-100"
                                                            >
                                                              <div className="flex-shrink-0 min-w-[120px]">
                                                                <span className="font-mono font-semibold text-gray-800">
                                                                  {key}
                                                                </span>
                                                                {fieldSchema && (
                                                                  <div className="text-[10px] text-blue-600 mt-0.5">
                                                                    {
                                                                      fieldSchema
                                                                        .types[0]
                                                                    }
                                                                  </div>
                                                                )}
                                                              </div>
                                                              <div className="flex-1 min-w-0">
                                                                <div className="font-mono text-gray-700 break-all">
                                                                  {typeof value ===
                                                                  "object"
                                                                    ? JSON.stringify(
                                                                        value
                                                                      )
                                                                    : String(
                                                                        value
                                                                      )}
                                                                </div>
                                                              </div>
                                                            </div>
                                                          );
                                                        })}
                                                      {Object.keys(
                                                        preview.latest
                                                      ).length > 8 && (
                                                        <div className="text-gray-500 italic text-center py-1">
                                                          +
                                                          {Object.keys(
                                                            preview.latest
                                                          ).length - 8}{" "}
                                                          more fields...
                                                        </div>
                                                      )}
                                                    </div>
                                                  </div>
                                                </div>
                                              )}

                                            {/* Schema Summary */}
                                            {!loadingPreviews.has(
                                              collection.name
                                            ) &&
                                              preview?.schema?.fields && (
                                                <div>
                                                  <h4 className="text-xs font-semibold text-gray-700 mb-2">
                                                    📋 Schema Summary
                                                  </h4>
                                                  <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                                                    <div className="grid grid-cols-3 gap-2 text-xs">
                                                      <div className="flex flex-col items-center p-2 bg-white rounded">
                                                        <span className="text-gray-600">
                                                          Total Fields
                                                        </span>
                                                        <span className="text-lg font-bold text-blue-600">
                                                          {
                                                            preview.schema
                                                              .fields.length
                                                          }
                                                        </span>
                                                      </div>
                                                      <div className="flex flex-col items-center p-2 bg-white rounded">
                                                        <span className="text-gray-600">
                                                          Sample Size
                                                        </span>
                                                        <span className="text-lg font-bold text-green-600">
                                                          {preview.schema
                                                            .sample_size || 0}
                                                        </span>
                                                      </div>
                                                      <div className="flex flex-col items-center p-2 bg-white rounded">
                                                        <span className="text-gray-600">
                                                          Analyzed
                                                        </span>
                                                        <span className="text-lg font-bold text-purple-600">
                                                          {preview.schema
                                                            .analyzed_at
                                                            ? new Date(
                                                                preview.schema.analyzed_at
                                                              ).toLocaleDateString()
                                                            : "N/A"}
                                                        </span>
                                                      </div>
                                                    </div>
                                                  </div>
                                                </div>
                                              )}

                                            {!loadingPreviews.has(
                                              collection.name
                                            ) &&
                                              !preview?.latest &&
                                              preview && (
                                                <div className="text-center text-gray-500 text-xs py-4">
                                                  No documents found in this
                                                  collection
                                                </div>
                                              )}

                                            {/* View Full Collection Button */}
                                            {!loadingPreviews.has(
                                              collection.name
                                            ) && (
                                              <button
                                                onClick={(e) => {
                                                  e.stopPropagation();
                                                  handleCollectionClick(
                                                    collection.name
                                                  );
                                                }}
                                                className="w-full text-xs text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded px-3 py-2 border border-blue-200 transition-colors font-semibold"
                                              >
                                                View Full Collection →
                                              </button>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          );
                        }
                      )}
                    </div>

                    <div className="mt-4 text-xs text-gray-600 space-y-1">
                      <div>
                        <strong>💡 Navigation:</strong>
                      </div>
                      <ul className="ml-4 space-y-1">
                        <li>• Click group headers to expand/collapse groups</li>
                        <li>
                          • Click collection names (▶) to view inline schema &
                          samples
                        </li>
                        <li>
                          • Click &quot;View Full Collection&quot; to explore
                          all documents
                        </li>
                      </ul>
                    </div>
                  </div>

                  {/* Collections Grid */}
                  <div className="grid grid-cols-3 gap-4 mb-6">
                    {collections?.collections.map((collection) => (
                      <div
                        key={collection.name}
                        onClick={() => handleCollectionClick(collection.name)}
                        className="border-2 border-gray-200 rounded-lg p-4 hover:border-blue-500 hover:shadow-md transition-all cursor-pointer"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <span className="text-3xl">📦</span>
                          <span className="text-xs text-gray-500">
                            {collection.indexes} indexes
                          </span>
                        </div>
                        <h3 className="font-mono font-semibold text-gray-900 mb-2 text-sm truncate">
                          {collection.name}
                        </h3>
                        <div className="space-y-1">
                          <div className="flex justify-between text-xs">
                            <span className="text-gray-600">Documents:</span>
                            <span className="font-semibold text-blue-600">
                              {collection.count.toLocaleString()}
                            </span>
                          </div>
                          <div className="flex justify-between text-xs">
                            <span className="text-gray-600">Size:</span>
                            <span className="font-semibold text-green-600">
                              {formatBytes(collection.size)}
                            </span>
                          </div>
                          <div className="flex justify-between text-xs">
                            <span className="text-gray-600">Avg Doc:</span>
                            <span className="font-semibold text-purple-600">
                              {formatBytes(collection.avgObjSize)}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Tips */}
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <h4 className="font-semibold text-blue-900 mb-2">
                      💡 Quick Tips
                    </h4>
                    <ul className="text-sm text-blue-800 space-y-1">
                      <li>
                        • <strong>navigation:</strong> Click ▶/▼ to expand
                        collections inline
                      </li>
                      <li>
                        • <strong>Inline preview:</strong> See schema and sample
                        documents without leaving the overview
                      </li>
                      <li>
                        • <strong>Full exploration:</strong> Use &quot;View Full
                        Collection&quot; button to see all documents with tabs
                      </li>
                      <li>
                        • <strong>Color coding:</strong> Members (blue), GitHub
                        (green), Slack (purple), Notion (orange), Drive (yellow)
                      </li>
                      <li>
                        • <strong>Quick stats:</strong> Collection cards show
                        document count, size, and index count
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            ) : detailLoading && !documentsData ? (
              <div className="bg-white rounded-lg shadow p-12 text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <p className="text-gray-600">Loading collection details...</p>
              </div>
            ) : (
              <div className="bg-white rounded-lg shadow">
                {/* Tabs */}
                <div className="border-b border-gray-200">
                  <div className="flex p-4 space-x-4">
                    <button
                      onClick={() => setActiveTab("documents")}
                      className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                        activeTab === "documents"
                          ? "bg-blue-100 text-blue-700"
                          : "text-gray-600 hover:text-gray-900"
                      }`}
                    >
                      📄 Documents
                      {documentsData && (
                        <span className="ml-2 text-sm">
                          ({documentsData.pagination.total.toLocaleString()})
                        </span>
                      )}
                    </button>
                    <button
                      onClick={() => setActiveTab("tree")}
                      className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                        activeTab === "tree"
                          ? "bg-blue-100 text-blue-700"
                          : "text-gray-600 hover:text-gray-900"
                      }`}
                    >
                      🌲 Tree View
                      {documentsData && (
                        <span className="ml-2 text-sm">
                          ({documentsData.documents.length} on page)
                        </span>
                      )}
                    </button>
                    <button
                      onClick={() => setActiveTab("schema")}
                      className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                        activeTab === "schema"
                          ? "bg-blue-100 text-blue-700"
                          : "text-gray-600 hover:text-gray-900"
                      }`}
                    >
                      📋 Schema
                      {schema && (
                        <span className="ml-2 text-sm">
                          ({schema.total_fields} fields)
                        </span>
                      )}
                    </button>
                  </div>
                </div>

                {/* Content */}
                <div className="p-6">
                  {activeTab === "documents" && documentsData && (
                    <div>
                      {/* Pagination Top */}
                      <div className="flex items-center justify-between mb-4 pb-4 border-b border-gray-200">
                        <div className="text-sm text-gray-600">
                          Showing {documentsData.documents.length} of{" "}
                          {documentsData.pagination.total.toLocaleString()}{" "}
                          documents (Page {documentsData.pagination.page} of{" "}
                          {documentsData.pagination.total_pages})
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => loadPage(1)}
                            disabled={
                              !documentsData.pagination.has_prev ||
                              detailLoading
                            }
                            className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                          >
                            ««
                          </button>
                          <button
                            onClick={() =>
                              loadPage(documentsData.pagination.page - 1)
                            }
                            disabled={
                              !documentsData.pagination.has_prev ||
                              detailLoading
                            }
                            className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                          >
                            ‹ Prev
                          </button>
                          <span className="px-3 py-1 text-sm">
                            {documentsData.pagination.page}
                          </span>
                          <button
                            onClick={() =>
                              loadPage(documentsData.pagination.page + 1)
                            }
                            disabled={
                              !documentsData.pagination.has_next ||
                              detailLoading
                            }
                            className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                          >
                            Next ›
                          </button>
                          <button
                            onClick={() =>
                              loadPage(documentsData.pagination.total_pages)
                            }
                            disabled={
                              !documentsData.pagination.has_next ||
                              detailLoading
                            }
                            className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                          >
                            »»
                          </button>
                        </div>
                      </div>

                      {/* Documents Table */}
                      <div className="space-y-2 max-h-[calc(100vh-380px)] overflow-y-auto">
                        {documentsData.documents.map((doc, idx) => {
                          const isExpanded = expandedDocs.has(idx);
                          return (
                            <div
                              key={idx}
                              className="border border-gray-200 rounded overflow-hidden"
                            >
                              <div className="bg-gray-50 px-3 py-1.5 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                  <button
                                    onClick={() => toggleDocExpansion(idx)}
                                    className="text-gray-500 hover:text-gray-700"
                                  >
                                    {isExpanded ? "▼" : "▶"}
                                  </button>
                                  <span className="text-sm font-medium text-gray-700">
                                    Document #
                                    {idx +
                                      1 +
                                      (currentPage - 1) * documentsPerPage}
                                  </span>
                                </div>
                                <span className="text-xs font-mono text-gray-500">
                                  _id: {doc._id}
                                </span>
                              </div>
                              <div className="p-3">
                                {isExpanded ? (
                                  <pre className="text-xs bg-gray-50 p-3 rounded overflow-x-auto">
                                    {JSON.stringify(doc, null, 2)}
                                  </pre>
                                ) : (
                                  <div className="grid grid-cols-3 gap-x-4 gap-y-1.5">
                                    {Object.entries(doc)
                                      .slice(0, 9)
                                      .map(([key, value]) => (
                                        <div key={key} className="text-sm">
                                          <span className="font-mono text-gray-600 text-xs">
                                            {key}:
                                          </span>{" "}
                                          {renderValue(value, key)}
                                        </div>
                                      ))}
                                    {Object.keys(doc).length > 9 && (
                                      <div className="text-xs text-gray-500 italic col-span-3">
                                        +{Object.keys(doc).length - 9} more
                                        fields...
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {/* Pagination Bottom */}
                      <div className="flex items-center justify-center mt-6 pt-4 border-t border-gray-200">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => loadPage(1)}
                            disabled={
                              !documentsData.pagination.has_prev ||
                              detailLoading
                            }
                            className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                          >
                            First
                          </button>
                          <button
                            onClick={() =>
                              loadPage(documentsData.pagination.page - 1)
                            }
                            disabled={
                              !documentsData.pagination.has_prev ||
                              detailLoading
                            }
                            className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                          >
                            Previous
                          </button>
                          <span className="px-4 py-1 text-sm bg-blue-50 rounded">
                            Page {documentsData.pagination.page} of{" "}
                            {documentsData.pagination.total_pages}
                          </span>
                          <button
                            onClick={() =>
                              loadPage(documentsData.pagination.page + 1)
                            }
                            disabled={
                              !documentsData.pagination.has_next ||
                              detailLoading
                            }
                            className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                          >
                            Next
                          </button>
                          <button
                            onClick={() =>
                              loadPage(documentsData.pagination.total_pages)
                            }
                            disabled={
                              !documentsData.pagination.has_next ||
                              detailLoading
                            }
                            className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                          >
                            Last
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === "tree" && documentsData && (
                    <div>
                      {/* Tree Controls */}
                      <div className="flex items-center justify-between mb-4 pb-4 border-b border-gray-200">
                        <div className="text-sm text-gray-600">
                          Tree View of {documentsData.documents.length}{" "}
                          documents
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={expandAll}
                            className="px-3 py-1 border border-gray-300 rounded text-sm hover:bg-gray-50"
                          >
                            Expand All
                          </button>
                          <button
                            onClick={collapseAll}
                            className="px-3 py-1 border border-gray-300 rounded text-sm hover:bg-gray-50"
                          >
                            Collapse All
                          </button>
                        </div>
                      </div>

                      {/* Tree View */}
                      <div className="border border-gray-200 rounded-lg bg-white font-mono text-sm max-h-[calc(100vh-380px)] overflow-y-auto">
                        <div className="p-4">
                          {documentsData.documents.map((doc, idx) => (
                            <div key={idx} className="mb-4 last:mb-0">
                              <div
                                className="flex items-start gap-2 py-1 bg-gray-50 hover:bg-gray-100 cursor-pointer -mx-2 px-2 rounded"
                                onClick={() => togglePath(`doc-${idx}`)}
                              >
                                <button className="text-gray-500 hover:text-gray-700 w-4 text-center">
                                  {expandedPaths.has(`doc-${idx}`) ? "▼" : "▶"}
                                </button>
                                <span className="font-semibold text-blue-600">
                                  Document #
                                  {idx +
                                    1 +
                                    (currentPage - 1) * documentsPerPage}
                                </span>
                                <span className="text-xs text-gray-500 ml-2">
                                  {doc._id}
                                </span>
                              </div>
                              {expandedPaths.has(`doc-${idx}`) && (
                                <div className="mt-1">
                                  {Object.entries(doc).map(([key, value]) => (
                                    <TreeNode
                                      key={key}
                                      data={value}
                                      path={`doc-${idx}.${key}`}
                                      level={1}
                                      nodeKey={key}
                                    />
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Pagination for Tree View */}
                      <div className="flex items-center justify-center mt-6 pt-4 border-t border-gray-200">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => loadPage(1)}
                            disabled={
                              !documentsData.pagination.has_prev ||
                              detailLoading
                            }
                            className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                          >
                            First
                          </button>
                          <button
                            onClick={() =>
                              loadPage(documentsData.pagination.page - 1)
                            }
                            disabled={
                              !documentsData.pagination.has_prev ||
                              detailLoading
                            }
                            className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                          >
                            Previous
                          </button>
                          <span className="px-4 py-1 text-sm bg-blue-50 rounded">
                            Page {documentsData.pagination.page} of{" "}
                            {documentsData.pagination.total_pages}
                          </span>
                          <button
                            onClick={() =>
                              loadPage(documentsData.pagination.page + 1)
                            }
                            disabled={
                              !documentsData.pagination.has_next ||
                              detailLoading
                            }
                            className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                          >
                            Next
                          </button>
                          <button
                            onClick={() =>
                              loadPage(documentsData.pagination.total_pages)
                            }
                            disabled={
                              !documentsData.pagination.has_next ||
                              detailLoading
                            }
                            className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                          >
                            Last
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === "schema" && schema && (
                    <div className="max-h-[calc(100vh-380px)] overflow-y-auto">
                      <div className="mb-4">
                        <h3 className="text-lg font-semibold text-gray-900 mb-1">
                          {schema.collection}
                        </h3>
                        <p className="text-sm text-gray-600">
                          {schema.total_fields} fields analyzed from{" "}
                          {schema.sample_count} documents
                        </p>
                      </div>

                      <div className="space-y-4">
                        {Object.entries(schema.schema).map(
                          ([fieldName, fieldInfo]) => (
                            <div
                              key={fieldName}
                              className="border border-gray-200 rounded-lg p-4"
                            >
                              <div className="flex items-start justify-between mb-2">
                                <div className="font-mono font-medium text-gray-900">
                                  {fieldName}
                                </div>
                                <div className="flex gap-1">
                                  {fieldInfo.types.map((type) => (
                                    <span
                                      key={type}
                                      className={`px-2 py-1 rounded text-xs font-medium ${getTypeColor(
                                        type
                                      )}`}
                                    >
                                      {type}
                                    </span>
                                  ))}
                                </div>
                              </div>

                              <div className="grid grid-cols-2 gap-4 text-sm text-gray-600 mb-2">
                                <div>
                                  Occurrence:{" "}
                                  {fieldInfo.occurrence_percentage.toFixed(1)}%
                                </div>
                                {fieldInfo.nullable && (
                                  <div>
                                    Null: {fieldInfo.null_percentage.toFixed(1)}
                                    %
                                  </div>
                                )}
                              </div>

                              {fieldInfo.examples.length > 0 && (
                                <div className="mt-2">
                                  <div className="text-xs font-medium text-gray-500 mb-1">
                                    Examples:
                                  </div>
                                  <div className="space-y-1">
                                    {fieldInfo.examples.map((example, idx) => (
                                      <div
                                        key={idx}
                                        className="font-mono text-xs bg-gray-50 p-2 rounded overflow-x-auto"
                                      >
                                        {typeof example === "string"
                                          ? example
                                          : JSON.stringify(example)}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          )
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
