"use client";

import { useState } from "react";
import FieldSelector from "./components/FieldSelector";
import FilterPanel from "./components/FilterPanel";
import PreviewTable from "./components/PreviewTable";
import AIChatPanel from "./components/AIChatPanel";
import NotionExportPanel from "./components/NotionExportPanel";
import { api } from "@/lib/api";

export default function CustomExportPage() {
  const [activeTab, setActiveTab] = useState<"custom" | "notion">("custom");
  const [exportMode, setExportMode] = useState<"fields" | "collections">("fields");
  const [exportFormat, setExportFormat] = useState<"csv" | "json" | "toon">("csv");

  const [selectedFields, setSelectedFields] = useState<string[]>([
    "member.name",
    "member.email",
    "github.commits",
    "slack.messages",
  ]);

  const [selectedCollections, setSelectedCollections] = useState<Set<string>>(
    new Set()
  );

  const [filters, setFilters] = useState({
    startDate: "2025-11-01",
    endDate: "2025-11-27",
    project: "all",
    selectedMembers: [] as string[],
  });

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFieldToggle = (fieldId: string) => {
    setSelectedFields((prev) =>
      prev.includes(fieldId)
        ? prev.filter((f) => f !== fieldId)
        : [...prev, fieldId]
    );
  };

  const handleCollectionToggle = (collectionKey: string) => {
    setSelectedCollections((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(collectionKey)) {
        newSet.delete(collectionKey);
      } else {
        newSet.add(collectionKey);
      }
      return newSet;
    });
  };

  const handlePreview = () => {
    console.log("Current configuration:", {
      exportMode,
      selectedFields,
      selectedCollections: Array.from(selectedCollections),
      filters,
      exportFormat,
    });
  };

  const handleExport = async () => {
    if (exportMode === "fields") {
      // Custom fields export
      if (filters.selectedMembers.length === 0) {
        setError("Please select at least one member");
        return;
      }
      if (selectedFields.length === 0) {
        setError("Please select at least one data field");
        return;
      }

      try {
        setIsLoading(true);
        setError(null);

        const blob = await api.downloadCustomExport(
          {
            selected_members: filters.selectedMembers,
            start_date: filters.startDate,
            end_date: filters.endDate,
            project: filters.project !== "all" ? filters.project : undefined,
            selected_fields: selectedFields,
          },
          exportFormat
        );

        // Create download link
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const ext = exportFormat === "toon" ? "toon" : exportFormat;
        a.download = `custom_export_${filters.startDate}_${filters.endDate}.${ext}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } catch (err: any) {
        console.error("Export error:", err);
        setError(
          err.response?.data?.detail || err.message || "Failed to export data"
        );
      } finally {
        setIsLoading(false);
      }
    } else {
      // Collections export
      if (selectedCollections.size === 0) {
        setError("Please select at least one collection");
        return;
      }

      try {
        setIsLoading(true);
        setError(null);

        // Convert collection keys to API format
        const collectionsArray = Array.from(selectedCollections).map((key) => {
          const [source, ...collectionParts] = key.split(":");
          const collection = collectionParts.join(":"); // Handle collection names with colons
          return { source, collection };
        });

        // If single collection, export directly; otherwise use bulk
        if (collectionsArray.length === 1) {
          const collection = collectionsArray[0];
          const blob = await api.exportCollection(
            collection,
            exportFormat,
            filters.startDate || undefined,
            filters.endDate || undefined
          );

          const url = window.URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          const ext = exportFormat === "toon" ? "toon" : exportFormat;
          const collectionName = collection.collection.replace(/^(main|shared|gemini)\./, "");
          a.download = `${collectionName}_${filters.startDate || "all"}_${filters.endDate || "all"}.${ext}`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
        } else {
          // Bulk export as ZIP
          const blob = await api.exportCollectionsBulk(
            collectionsArray,
            exportFormat,
            filters.startDate || undefined,
            filters.endDate || undefined
          );

          const url = window.URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `collections_export_${filters.startDate || "all"}_${filters.endDate || "all"}.zip`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
        }
      } catch (err: any) {
        console.error("Export error:", err);
        setError(
          err.response?.data?.detail || err.message || "Failed to export data"
        );
      } finally {
        setIsLoading(false);
      }
    }
  };

  const handleSaveTemplate = () => {
    console.log("Save template clicked", {
      exportMode,
      selectedFields,
      selectedCollections: Array.from(selectedCollections),
      filters,
    });
    // TODO: Save template
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          📊 Custom Data Export Builder
        </h1>
        <p className="text-gray-600">
          Select fields from multiple data sources or entire collections and export custom reports
        </p>

        {/* Tabs */}
        <div className="mt-4 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab("custom")}
              className={`${
                activeTab === "custom"
                  ? "border-blue-500 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
            >
              🔧 Custom Export
            </button>
            <button
              onClick={() => setActiveTab("notion")}
              className={`${
                activeTab === "notion"
                  ? "border-blue-500 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
            >
              📝 Notion Documents
            </button>
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto">
        {activeTab === "notion" ? (
          /* Notion Export Tab */
          <NotionExportPanel />
        ) : (
          /* Custom Export Tab */
          <>
            {/* Export Mode Selection */}
            <div className="mb-6 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Export Mode
              </label>
              <div className="grid grid-cols-2 gap-4">
                <button
                  onClick={() => setExportMode("fields")}
                  className={`p-4 rounded-lg border-2 transition-all ${
                    exportMode === "fields"
                      ? "border-blue-500 bg-blue-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <div className="flex flex-col items-center text-center">
                    <span className="text-2xl mb-2">🔧</span>
                    <span className="font-medium text-gray-900">Custom Fields</span>
                    <span className="text-xs text-gray-500 mt-1">
                      Select specific fields from data sources
                    </span>
                  </div>
                </button>
                <button
                  onClick={() => setExportMode("collections")}
                  className={`p-4 rounded-lg border-2 transition-all ${
                    exportMode === "collections"
                      ? "border-blue-500 bg-blue-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <div className="flex flex-col items-center text-center">
                    <span className="text-2xl mb-2">🗄️</span>
                    <span className="font-medium text-gray-900">Collections</span>
                    <span className="text-xs text-gray-500 mt-1">
                      Export entire database collections
                    </span>
                  </div>
                </button>
              </div>
            </div>

            {/* Format Selection */}
            <div className="mb-6 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Export Format
              </label>
              <div className="grid grid-cols-3 gap-4">
                <button
                  onClick={() => setExportFormat("csv")}
                  className={`p-3 rounded-lg border-2 transition-all ${
                    exportFormat === "csv"
                      ? "border-blue-500 bg-blue-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <div className="flex flex-col items-center text-center">
                    <span className="text-xl mb-1">📊</span>
                    <span className="font-medium text-sm text-gray-900">CSV</span>
                    <span className="text-xs text-gray-500 mt-0.5">
                      Excel/Sheets
                    </span>
                  </div>
                </button>
                <button
                  onClick={() => setExportFormat("json")}
                  className={`p-3 rounded-lg border-2 transition-all ${
                    exportFormat === "json"
                      ? "border-green-500 bg-green-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <div className="flex flex-col items-center text-center">
                    <span className="text-xl mb-1">🔧</span>
                    <span className="font-medium text-sm text-gray-900">JSON</span>
                    <span className="text-xs text-gray-500 mt-0.5">
                      Developers
                    </span>
                  </div>
                </button>
                <button
                  onClick={() => setExportFormat("toon")}
                  className={`p-3 rounded-lg border-2 transition-all ${
                    exportFormat === "toon"
                      ? "border-purple-500 bg-purple-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <div className="flex flex-col items-center text-center">
                    <span className="text-xl mb-1">🤖</span>
                    <span className="font-medium text-sm text-gray-900">TOON</span>
                    <span className="text-xs text-gray-500 mt-0.5">
                      LLM Optimized
                    </span>
                  </div>
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left Column: Field/Collection Selector */}
              <div className="lg:col-span-1">
                <FieldSelector
                  selectedFields={selectedFields}
                  onFieldToggle={handleFieldToggle}
                  selectedCollections={selectedCollections}
                  onCollectionToggle={handleCollectionToggle}
                  mode={exportMode}
                />
              </div>

              {/* Right Column: Filters + Preview */}
              <div className="lg:col-span-2 space-y-6">
                {/* Filter Panel */}
                <FilterPanel
                  filters={filters}
                  onFiltersChange={setFilters}
                  onPreview={handlePreview}
                  onExport={handleExport}
                  onSaveTemplate={handleSaveTemplate}
                  isLoading={isLoading}
                  exportMode={exportMode}
                  exportFormat={exportFormat}
                />

                {/* Error Message */}
                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
                    ❌ {error}
                  </div>
                )}

                {/* Export Configuration Summary */}
                {exportMode === "fields" && (
                  <PreviewTable selectedFields={selectedFields} filters={filters} />
                )}

                {/* AI Chat Panel */}
                {exportMode === "fields" && (
                  <AIChatPanel selectedFields={selectedFields} filters={filters} />
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
