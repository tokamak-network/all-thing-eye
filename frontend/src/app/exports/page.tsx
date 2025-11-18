"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import DateRangePicker from "@/components/DateRangePicker";
import { format, subDays } from "date-fns";

interface TablesData {
  sources: Record<string, string[]>;
  total_sources: number;
  total_tables: number;
}

export default function ExportsPage() {
  const [tables, setTables] = useState<TablesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedTables, setSelectedTables] = useState<Set<string>>(new Set());
  const [bulkDownloading, setBulkDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exportFormat, setExportFormat] = useState<"csv" | "json" | "toon">(
    "csv"
  );

  // Date range state - default to last 30 days
  const [startDate, setStartDate] = useState<string>(
    format(subDays(new Date(), 29), "yyyy-MM-dd")
  );
  const [endDate, setEndDate] = useState<string>(
    format(new Date(), "yyyy-MM-dd")
  );

  useEffect(() => {
    loadTables();
  }, []);

  const loadTables = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = (await api.getTables()) as TablesData;
      setTables(data);
    } catch (err) {
      console.error("Failed to load tables:", err);
      setError("Failed to load table list. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleDateRangeChange = (start: string, end: string) => {
    setStartDate(start);
    setEndDate(end);
  };

  const toggleTableSelection = (source: string, table: string) => {
    const key = `${source}:${table}`;
    setSelectedTables((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(key)) {
        newSet.delete(key);
      } else {
        newSet.add(key);
      }
      return newSet;
    });
  };

  const toggleSourceSelection = (source: string) => {
    if (!tables) return;

    const sourceTables = tables.sources[source] || [];
    const sourceKeys = sourceTables.map((table) => `${source}:${table}`);

    // Check if all tables in this source are already selected
    const allSelected = sourceKeys.every((key) => selectedTables.has(key));

    setSelectedTables((prev) => {
      const newSet = new Set(prev);

      if (allSelected) {
        // Deselect all tables in this source
        sourceKeys.forEach((key) => newSet.delete(key));
      } else {
        // Select all tables in this source
        sourceKeys.forEach((key) => newSet.add(key));
      }

      return newSet;
    });
  };

  const isSourceSelected = (source: string): boolean => {
    if (!tables) return false;
    const sourceTables = tables.sources[source] || [];
    if (sourceTables.length === 0) return false;
    const sourceKeys = sourceTables.map((table) => `${source}:${table}`);
    return sourceKeys.every((key) => selectedTables.has(key));
  };

  const isSourcePartiallySelected = (source: string): boolean => {
    if (!tables) return false;
    const sourceTables = tables.sources[source] || [];
    if (sourceTables.length === 0) return false;
    const sourceKeys = sourceTables.map((table) => `${source}:${table}`);
    const someSelected = sourceKeys.some((key) => selectedTables.has(key));
    const allSelected = sourceKeys.every((key) => selectedTables.has(key));
    return someSelected && !allSelected;
  };

  const handleBulkDownload = async () => {
    if (selectedTables.size === 0) {
      alert("Please select at least one table");
      return;
    }

    try {
      setBulkDownloading(true);
      setError(null);

      // Convert Set to array of {source, table} objects
      const tablesArray = Array.from(selectedTables).map((key) => {
        const [source, table] = key.split(":");
        return { source, table };
      });

      // Call API with date range and format
      const blob = await api.exportBulkTables(
        tablesArray,
        startDate || undefined,
        endDate || undefined,
        exportFormat
      );

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      const dateRangeSuffix =
        startDate && endDate ? `_${startDate}_${endDate}` : "";
      const formatSuffix = exportFormat !== "csv" ? `_${exportFormat}` : "";
      link.download = `all_thing_eye_export${dateRangeSuffix}${formatSuffix}_${
        new Date().toISOString().split("T")[0]
      }.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      // Clear selection after successful download
      setSelectedTables(new Set());
    } catch (err) {
      console.error("Bulk download failed:", err);
      setError("Failed to download ZIP file. Please try again.");
    } finally {
      setBulkDownloading(false);
    }
  };

  const selectAll = () => {
    if (!tables) return;
    const allTables = new Set<string>();
    Object.entries(tables.sources).forEach(([source, tableList]) => {
      tableList.forEach((table) => {
        allTables.add(`${source}:${table}`);
      });
    });
    setSelectedTables(allTables);
  };

  const clearSelection = () => {
    setSelectedTables(new Set());
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl font-bold text-gray-900 mb-8">
            Export Tables
          </h1>
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading tables...</p>
          </div>
        </div>
      </div>
    );
  }

  if (!tables) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl font-bold text-gray-900 mb-8">
            Export Tables
          </h1>
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">
              Failed to load tables. Please refresh the page.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Export Tables
          </h1>
          <p className="text-gray-600">
            Download data in CSV, JSON, or TOON format for analysis, backup, or
            AI applications
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-3xl font-bold text-blue-600">
              {tables.total_sources}
            </div>
            <div className="text-sm text-gray-600 mt-1">Data Sources</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-3xl font-bold text-green-600">
              {tables.total_tables}
            </div>
            <div className="text-sm text-gray-600 mt-1">Total Tables</div>
          </div>
        </div>

        {/* Date Range Picker */}
        <div className="mb-8">
          <DateRangePicker
            startDate={startDate}
            endDate={endDate}
            onDateChange={handleDateRangeChange}
          />
        </div>

        {/* Format Selector */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">
            Export Format
          </h2>
          <div className="grid grid-cols-3 gap-4">
            {/* CSV Option */}
            <button
              onClick={() => setExportFormat("csv")}
              className={`p-4 rounded-lg border-2 transition-all ${
                exportFormat === "csv"
                  ? "border-blue-500 bg-blue-50"
                  : "border-gray-200 hover:border-gray-300"
              }`}
            >
              <div className="flex flex-col items-center text-center">
                <span className="text-2xl mb-2">📊</span>
                <span className="font-medium text-gray-900">CSV</span>
                <span className="text-xs text-gray-500 mt-1">
                  Traditional format for Excel/Sheets
                </span>
              </div>
            </button>

            {/* JSON Option */}
            <button
              onClick={() => setExportFormat("json")}
              className={`p-4 rounded-lg border-2 transition-all ${
                exportFormat === "json"
                  ? "border-green-500 bg-green-50"
                  : "border-gray-200 hover:border-gray-300"
              }`}
            >
              <div className="flex flex-col items-center text-center">
                <span className="text-2xl mb-2">🔧</span>
                <span className="font-medium text-gray-900">JSON</span>
                <span className="text-xs text-gray-500 mt-1">
                  Structured data for developers
                </span>
              </div>
            </button>

            {/* TOON Option */}
            <button
              onClick={() => setExportFormat("toon")}
              className={`p-4 rounded-lg border-2 transition-all ${
                exportFormat === "toon"
                  ? "border-purple-500 bg-purple-50"
                  : "border-gray-200 hover:border-gray-300"
              }`}
            >
              <div className="flex flex-col items-center text-center">
                <span className="text-2xl mb-2">🤖</span>
                <span className="font-medium text-gray-900">TOON</span>
                <span className="text-xs text-gray-500 mt-1">
                  LLM-optimized (20-40% fewer tokens)
                </span>
              </div>
            </button>
          </div>

          {/* Format Info */}
          {exportFormat === "toon" && (
            <div className="mt-4 p-3 bg-purple-50 border border-purple-200 rounded-lg">
              <p className="text-sm text-purple-900">
                <strong>TOON (Token-Oriented Object Notation)</strong> is
                optimized for AI/LLM applications:
              </p>
              <ul className="text-sm text-purple-800 mt-2 space-y-1 ml-4">
                <li>• 20-40% fewer tokens than JSON</li>
                <li>
                  • Explicit structure with array lengths and field headers
                </li>
                <li>• Human-readable and self-documenting</li>
                <li>
                  • Perfect for feeding data to ChatGPT, Claude, or other LLMs
                </li>
              </ul>
            </div>
          )}
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {/* Bulk Download Section */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-semibold text-gray-900">
                Bulk Download (ZIP)
              </h2>
              <p className="text-sm text-gray-600 mt-1">
                Select multiple tables to download as a single ZIP file
              </p>
            </div>
            <div className="text-2xl font-bold text-purple-600">
              {selectedTables.size}
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={selectAll}
              className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 transition-colors text-sm"
            >
              Select All
            </button>
            <button
              onClick={clearSelection}
              disabled={selectedTables.size === 0}
              className={`px-4 py-2 border border-gray-300 rounded-md transition-colors text-sm ${
                selectedTables.size === 0
                  ? "text-gray-400 cursor-not-allowed"
                  : "text-gray-700 hover:bg-gray-50"
              }`}
            >
              Clear Selection
            </button>
            <button
              onClick={handleBulkDownload}
              disabled={selectedTables.size === 0 || bulkDownloading}
              className={`flex-1 px-6 py-2 rounded-md font-medium transition-colors ${
                selectedTables.size === 0 || bulkDownloading
                  ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                  : "bg-purple-600 text-white hover:bg-purple-700"
              }`}
            >
              {bulkDownloading ? (
                <span className="flex items-center justify-center">
                  <svg
                    className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    ></circle>
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
                  Creating ZIP...
                </span>
              ) : (
                <>📦 Download {selectedTables.size} Selected as ZIP</>
              )}
            </button>
          </div>
        </div>

        {/* Table List by Source */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Available Tables
          </h2>

          <div className="space-y-4">
            {Object.entries(tables.sources).map(([source, tableList]) => {
              const isFullySelected = isSourceSelected(source);
              const isPartiallySelected = isSourcePartiallySelected(source);

              return (
                <div
                  key={source}
                  className="border border-gray-200 rounded-lg p-4"
                >
                  {/* Source Header with Checkbox */}
                  <div className="flex items-center gap-3 mb-3 pb-3 border-b border-gray-200">
                    <input
                      type="checkbox"
                      id={`source-${source}`}
                      checked={isFullySelected}
                      ref={(el) => {
                        if (el) {
                          el.indeterminate = isPartiallySelected;
                        }
                      }}
                      onChange={() => toggleSourceSelection(source)}
                      className="w-5 h-5 text-purple-600 border-gray-300 rounded focus:ring-purple-500 cursor-pointer"
                    />
                    <label
                      htmlFor={`source-${source}`}
                      className="flex-1 font-medium text-gray-900 cursor-pointer hover:text-purple-600 transition-colors"
                    >
                      📂 {source}{" "}
                      <span className="text-sm text-gray-500 font-normal">
                        ({tableList.length} tables)
                      </span>
                    </label>
                  </div>

                  {/* Individual Tables */}
                  <div className="space-y-2 pl-8">
                    {tableList.map((table) => {
                      const key = `${source}:${table}`;
                      const isSelected = selectedTables.has(key);
                      return (
                        <div
                          key={table}
                          className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded"
                        >
                          <input
                            type="checkbox"
                            id={key}
                            checked={isSelected}
                            onChange={() => toggleTableSelection(source, table)}
                            className="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                          />
                          <label
                            htmlFor={key}
                            className="flex-1 text-sm text-gray-700 cursor-pointer"
                          >
                            {table}
                          </label>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Info Box */}
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-medium text-blue-900 mb-2">💡 Usage Tips</h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>
              • <strong>Export Format:</strong> Choose between CSV
              (traditional), JSON (structured), or TOON (LLM-optimized)
            </li>
            <li>
              • <strong>Select All Tables in Source:</strong> Click the checkbox
              next to a source name (e.g., &quot;github&quot;) to select all tables under
              it
            </li>
            <li>
              • <strong>Select Individual Tables:</strong> Check the boxes next
              to specific tables you want to export
            </li>
            <li>
              • <strong>Date Range Filter:</strong> Use the date picker to
              filter exports by timestamp (applies to tables with timestamp
              columns)
            </li>
            <li>
              • <strong>Quick Presets:</strong> Click preset buttons (Last 7d,
              Last 30d, etc.) for common date ranges
            </li>
            <li>
              • <strong>Bulk Download:</strong> Select multiple tables and click
              &quot;Download Selected as ZIP&quot; to get all tables in one file
            </li>
            <li>
              • CSV files can be opened in Excel, Google Sheets, or any
              spreadsheet application
            </li>
            <li>
              • JSON files are best for programmatic data processing and API
              integration
            </li>
            <li>
              • TOON files are optimized for AI/LLM applications (ChatGPT,
              Claude, etc.) with 20-40% fewer tokens
            </li>
            <li>• Large tables may take a few seconds to download</li>
            <li>
              • ZIP files include all selected tables with filenames like{" "}
              <code className="bg-blue-100 px-1 rounded">
                source_table.{"{format}"}
              </code>
            </li>
            <li>
              • Date filtering only applies to tables with
              timestamp/posted_at/created_at columns
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
