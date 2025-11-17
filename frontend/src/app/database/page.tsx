"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

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
  const [collections, setCollections] = useState<CollectionsData | null>(null);
  const [selectedCollection, setSelectedCollection] = useState<string | null>(
    null
  );
  const [schema, setSchema] = useState<SchemaData | null>(null);
  const [documentsData, setDocumentsData] = useState<DocumentsData | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"documents" | "tree" | "schema">(
    "documents"
  );
  const [currentPage, setCurrentPage] = useState(1);
  const [documentsPerPage, setDocumentsPerPage] = useState(30);
  const [expandedDocs, setExpandedDocs] = useState<Set<number>>(new Set());
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadCollections();
  }, []);

  const loadCollections = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = (await api.getDatabaseCollections()) as CollectionsData;
      setCollections(data);
    } catch (err) {
      console.error("Failed to load collections:", err);
      setError("Failed to load database collections. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleCollectionClick = async (collectionName: string) => {
    setSelectedCollection(collectionName);
    setDetailLoading(true);
    setError(null);
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
      setError("Failed to load collection details. Please try again.");
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
      setError("Failed to load page. Please try again.");
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

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold text-gray-900 mb-8">
            Database Viewer
          </h1>
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading database...</p>
          </div>
        </div>
      </div>
    );
  }

  if (!collections) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold text-gray-900 mb-8">
            Database Viewer
          </h1>
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">
              Failed to load database. Please refresh the page.
            </p>
          </div>
        </div>
      </div>
    );
  }

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
              {collections.total_collections}
            </div>
            <div className="text-xs text-gray-600 mt-1">Collections</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-green-600">
              {collections.total_documents.toLocaleString()}
            </div>
            <div className="text-xs text-gray-600 mt-1">Total Documents</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-purple-600">
              {formatBytes(
                collections.collections.reduce(
                  (sum, c) => sum + c.storageSize,
                  0
                )
              )}
            </div>
            <div className="text-xs text-gray-600 mt-1">Storage Size</div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        <div className="grid grid-cols-12 gap-4">
          {/* Collections List */}
          <div className="col-span-2">
            <div className="bg-white rounded-lg shadow">
              <div className="p-4 border-b border-gray-200">
                <h2 className="text-xl font-semibold text-gray-900">
                  Collections
                </h2>
              </div>
              <div className="divide-y divide-gray-200 max-h-[calc(100vh-320px)] overflow-y-auto">
                {collections.collections.map((collection) => (
                  <button
                    key={collection.name}
                    onClick={() => handleCollectionClick(collection.name)}
                    className={`w-full text-left p-3 hover:bg-gray-50 transition-colors ${
                      selectedCollection === collection.name
                        ? "bg-blue-50 border-l-4 border-blue-600"
                        : ""
                    }`}
                  >
                    <div className="font-medium text-gray-900 mb-1 break-words text-sm">
                      {collection.name}
                    </div>
                    <div className="flex flex-col gap-0.5 text-xs text-gray-600">
                      <span>📄 {collection.count.toLocaleString()}</span>
                      <span>💾 {formatBytes(collection.size)}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Collection Details */}
          <div className="col-span-10">
            {!selectedCollection ? (
              <div className="bg-white rounded-lg shadow p-12 text-center">
                <div className="text-6xl mb-4">📊</div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">
                  Select a Collection
                </h3>
                <p className="text-gray-600">
                  Click on a collection from the list to browse its documents
                  and schema
                </p>
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
                          Firebase-style Tree View of{" "}
                          {documentsData.documents.length} documents
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

        {/* Info Box */}
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-medium text-blue-900 mb-2">
            💡 Database Viewer Features
          </h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>
              • <strong>Browse Documents:</strong> Navigate through all
              documents with pagination (30 per page)
            </li>
            <li>
              • <strong>Tree View:</strong> Firebase-style hierarchical JSON
              viewer with expand/collapse controls (NEW! 🔥)
            </li>
            <li>
              • <strong>Expand/Collapse:</strong> Click arrows (▶/▼) to expand
              or collapse nodes in tree view
            </li>
            <li>
              • <strong>Expand All / Collapse All:</strong> Quickly expand or
              collapse all nodes at once
            </li>
            <li>
              • <strong>Schema Analysis:</strong> View field types, nullability,
              and occurrence percentages
            </li>
            <li>
              • <strong>Type Highlighting:</strong> Different colors for
              strings, numbers, dates, ObjectIds, etc.
            </li>
            <li>
              • <strong>Fast Navigation:</strong> Jump to first/last page or
              navigate page by page
            </li>
            <li>
              • <strong>Real-time Data:</strong> Always shows current data from
              MongoDB
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
