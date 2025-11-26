"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

interface NotionPage {
  id: string;
  title: string;
  content: string;
  content_length: number;
  created_by: {
    name: string;
    email: string;
  };
  created_time: string;
  last_edited_time: string;
  url?: string;
}

interface Author {
  name: string;
  email: string;
  page_count: number;
}

export default function NotionExportPanel() {
  const [searchParams, setSearchParams] = useState({
    titleContains: "",
    author: "",
    startDate: "",
    endDate: "",
  });

  const [pages, setPages] = useState<NotionPage[]>([]);
  const [authors, setAuthors] = useState<Author[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  // Load authors on mount
  useEffect(() => {
    loadAuthors();
  }, []);

  const loadAuthors = async () => {
    try {
      const response = await api.get("/notion/authors");
      setAuthors(response.authors || []);
    } catch (error) {
      console.error("Failed to load authors:", error);
    }
  };

  const handleSearch = async () => {
    setLoading(true);
    setSearched(true);
    try {
      const params = new URLSearchParams();
      if (searchParams.titleContains) params.append("title_contains", searchParams.titleContains);
      if (searchParams.author) params.append("author", searchParams.author);
      if (searchParams.startDate) params.append("start_date", searchParams.startDate);
      if (searchParams.endDate) params.append("end_date", searchParams.endDate);
      params.append("has_content", "true"); // Only show pages with content
      params.append("limit", "100");

      const response = await api.get(`/notion/search?${params.toString()}`);
      setPages(response.pages || []);
      setTotal(response.total || 0);
    } catch (error) {
      console.error("Failed to search pages:", error);
      alert("Failed to search Notion pages");
    } finally {
      setLoading(false);
    }
  };

  const handleExport = (format: "json" | "jsonl" | "csv") => {
    const params = new URLSearchParams();
    if (searchParams.titleContains) params.append("title_contains", searchParams.titleContains);
    if (searchParams.author) params.append("author", searchParams.author);
    if (searchParams.startDate) params.append("start_date", searchParams.startDate);
    if (searchParams.endDate) params.append("end_date", searchParams.endDate);
    params.append("format", format);
    params.append("limit", "10000");

    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const url = `${baseUrl}/api/v1/notion/export?${params.toString()}`;
    window.location.href = url;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center mb-4">
          <span className="text-3xl mr-3">📝</span>
          <div>
            <h2 className="text-xl font-bold text-gray-900">
              Notion Documents Export
            </h2>
            <p className="text-sm text-gray-600">
              Search and export Notion pages with full content for AI training
            </p>
          </div>
        </div>

        {/* Search Filters */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          {/* Title Search */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Title Contains
            </label>
            <input
              type="text"
              value={searchParams.titleContains}
              onChange={(e) =>
                setSearchParams({ ...searchParams, titleContains: e.target.value })
              }
              placeholder="e.g., Weekly Report, Meeting Notes"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Author Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Author
            </label>
            <select
              value={searchParams.author}
              onChange={(e) =>
                setSearchParams({ ...searchParams, author: e.target.value })
              }
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Authors</option>
              {authors.map((author) => (
                <option key={author.email} value={author.name}>
                  {author.name} ({author.page_count} pages)
                </option>
              ))}
            </select>
          </div>

          {/* Start Date */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Start Date
            </label>
            <input
              type="date"
              value={searchParams.startDate}
              onChange={(e) =>
                setSearchParams({ ...searchParams, startDate: e.target.value })
              }
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* End Date */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              End Date
            </label>
            <input
              type="date"
              value={searchParams.endDate}
              onChange={(e) =>
                setSearchParams({ ...searchParams, endDate: e.target.value })
              }
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex space-x-3 mt-4">
          <button
            onClick={handleSearch}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Searching..." : "🔍 Search"}
          </button>

          {searched && pages.length > 0 && (
            <>
              <button
                onClick={() => handleExport("json")}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
              >
                📥 Export JSON
              </button>
              <button
                onClick={() => handleExport("jsonl")}
                className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700"
              >
                📥 Export JSONL (AI)
              </button>
              <button
                onClick={() => handleExport("csv")}
                className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
              >
                📥 Export CSV
              </button>
            </>
          )}
        </div>

        {/* Stats */}
        {searched && (
          <div className="mt-4 p-3 bg-blue-50 rounded-md">
            <p className="text-sm text-blue-900">
              📊 Found <strong>{total}</strong> pages
              {pages.length > 0 && ` (showing first ${pages.length})`}
            </p>
          </div>
        )}
      </div>

      {/* Results */}
      {searched && (
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">
              Search Results
            </h3>
          </div>

          {loading ? (
            <div className="p-12 text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
              <p className="mt-4 text-gray-600">Searching...</p>
            </div>
          ) : pages.length === 0 ? (
            <div className="p-12 text-center text-gray-500">
              <svg
                className="mx-auto h-12 w-12 text-gray-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <p className="mt-2">No pages found</p>
              <p className="text-sm text-gray-400 mt-1">
                Try different search criteria
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {pages.map((page) => (
                <div key={page.id} className="p-6 hover:bg-gray-50">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h4 className="text-lg font-medium text-gray-900">
                        {page.title}
                      </h4>
                      <div className="mt-2 flex items-center space-x-4 text-sm text-gray-600">
                        <span>👤 {page.created_by.name}</span>
                        <span>
                          📅{" "}
                          {new Date(page.created_time).toLocaleDateString()}
                        </span>
                        <span>📝 {page.content_length.toLocaleString()} chars</span>
                      </div>
                      <div className="mt-2 text-sm text-gray-700">
                        <p className="line-clamp-2">
                          {page.content.substring(0, 200)}...
                        </p>
                      </div>
                    </div>
                    {page.url && (
                      <a
                        href={page.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-4 px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                      >
                        Open in Notion →
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

