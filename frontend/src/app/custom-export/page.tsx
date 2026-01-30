"use client";

import { useState, useMemo } from "react";
import { ChevronLeftIcon, ChevronRightIcon } from "@heroicons/react/24/outline";
import FieldSelector from "./components/FieldSelector";
import FilterPanel from "./components/FilterPanel";
import PreviewTable from "./components/PreviewTable";
import ReportGeneratorPanel from "./components/ReportGeneratorPanel";
import DataAIChatPanel from "./components/DataAIChatPanel";
import { api } from "@/lib/api";

// Helper function to get this month's date range (1st to today)
function getThisMonthRange(): { startDate: string; endDate: string } {
  const today = new Date();
  const firstDayOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  
  const formatDate = (date: Date) => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };
  
  return {
    startDate: formatDate(firstDayOfMonth),
    endDate: formatDate(today),
  };
}

export default function CustomExportPage() {
  const [activeTab, setActiveTab] = useState<"custom" | "report">("custom");
  const [exportMode, setExportMode] = useState<"fields" | "collections">(
    "fields"
  );
  const [exportFormat, setExportFormat] = useState<"csv" | "json" | "toon">(
    "csv"
  );

  const [selectedFields, setSelectedFields] = useState<string[]>([
    "member.name",
    "member.email",
    "github.commits",
    "slack.messages",
  ]);

  const [selectedCollections, setSelectedCollections] = useState<Set<string>>(
    new Set()
  );

  // Initialize with this month's date range
  const defaultDateRange = useMemo(() => getThisMonthRange(), []);
  
  const [filters, setFilters] = useState({
    startDate: defaultDateRange.startDate,
    endDate: defaultDateRange.endDate,
    project: "all",
    selectedMembers: [] as string[],
  });

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collapsedPanel, setCollapsedPanel] = useState<"filter" | "chat" | null>(null);

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

        // Handle 404 - No data found
        if (err.response?.status === 404) {
          setError(
            "📭 No data found for the selected filters.\n\n" +
              "Selected members: " +
              filters.selectedMembers.join(", ") +
              "\n" +
              "Selected fields: " +
              selectedFields.join(", ") +
              "\n\n" +
              "Try adjusting your member selection, date range, or data fields."
          );
        } else {
          setError(
            err.response?.data?.detail || err.message || "Failed to export data"
          );
        }
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
          const collectionName = collection.collection.replace(
            /^(main|shared|gemini)\./,
            ""
          );
          a.download = `${collectionName}_${filters.startDate || "all"}_${
            filters.endDate || "all"
          }.${ext}`;
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
          a.download = `collections_export_${filters.startDate || "all"}_${
            filters.endDate || "all"
          }.zip`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
        }
      } catch (err: any) {
        console.error("Export error:", err);

        // Handle 404 - No data found
        if (err.response?.status === 404) {
          const collectionNames = Array.from(selectedCollections).join(", ");
          setError(
            "📭 No data found for the selected collections.\n\n" +
              "Selected collections: " +
              collectionNames +
              "\n" +
              (filters.startDate || filters.endDate
                ? "Date range: " +
                  (filters.startDate || "any") +
                  " ~ " +
                  (filters.endDate || "any") +
                  "\n\n"
                : "\n") +
              "Try adjusting your collection selection or date range."
          );
        } else {
          setError(
            err.response?.data?.detail || err.message || "Failed to export data"
          );
        }
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
          Select fields from multiple data sources or entire collections and
          export custom reports
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
              onClick={() => setActiveTab("report")}
              className={`${
                activeTab === "report"
                  ? "border-blue-500 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
            >
              📊 Report Generator
            </button>
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto">
        {activeTab === "report" ? (
          /* Report Generator Tab */
          <ReportGeneratorPanel />
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
                    <span className="font-medium text-gray-900">
                      Custom Fields
                    </span>
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
                    <span className="font-medium text-gray-900">
                      Collections
                    </span>
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
                    <span className="font-medium text-sm text-gray-900">
                      CSV
                    </span>
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
                    <span className="font-medium text-sm text-gray-900">
                      JSON
                    </span>
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
                    <span className="font-medium text-sm text-gray-900">
                      TOON
                    </span>
                    <span className="text-xs text-gray-500 mt-0.5">
                      LLM Optimized
                    </span>
                  </div>
                </button>
              </div>
            </div>

            <div className="flex gap-6 items-start">
              {/* Left Column: Field/Collection Selector */}
              <div className="w-80 flex-shrink-0">
                <FieldSelector
                  selectedFields={selectedFields}
                  onFieldToggle={handleFieldToggle}
                  selectedCollections={selectedCollections}
                  onCollectionToggle={handleCollectionToggle}
                  mode={exportMode}
                />
              </div>

              {/* Middle Column: Filters + Preview (Collapsible) */}
              <div className={`transition-all duration-300 ease-in-out ${
                collapsedPanel === "filter" ? "w-10" : "flex-1 min-w-[400px]"
              }`}>
                {collapsedPanel === "filter" ? (
                  <button
                    onClick={() => setCollapsedPanel(null)}
                    className="h-[600px] w-10 bg-white rounded-lg shadow-sm border border-gray-200 flex items-center justify-center hover:bg-gray-50 transition-colors"
                    title="Expand Filter Panel"
                  >
                    <div className="flex flex-col items-center gap-2">
                      <ChevronRightIcon className="w-5 h-5 text-gray-500" />
                      <span className="text-xs text-gray-500" style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>
                        Filters & Preview
                      </span>
                    </div>
                  </button>
                ) : (
                  <div className="relative">
                    <button
                      onClick={() => setCollapsedPanel("filter")}
                      className="absolute -right-3 top-4 z-10 w-6 h-6 bg-white rounded-full shadow-md border border-gray-200 flex items-center justify-center hover:bg-gray-50 transition-colors"
                      title="Collapse Filter Panel"
                    >
                      <ChevronLeftIcon className="w-4 h-4 text-gray-500" />
                    </button>

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

                    {error && (
                      <div className="mt-6 bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm whitespace-pre-line">
                        ❌ {error}
                      </div>
                    )}

                    {exportMode === "fields" && (
                      <div className="mt-6">
                        <PreviewTable
                          selectedFields={selectedFields}
                          filters={filters}
                        />
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Right Column: AI Chat Panel (Collapsible) */}
              <div className={`transition-all duration-300 ease-in-out flex-shrink-0 ${
                collapsedPanel === "chat" ? "w-10" : collapsedPanel === "filter" ? "flex-1" : "w-96"
              }`}>
                {collapsedPanel === "chat" ? (
                  <button
                    onClick={() => setCollapsedPanel(null)}
                    className="h-[600px] w-10 bg-gradient-to-b from-blue-500 to-purple-500 rounded-lg shadow-sm flex items-center justify-center hover:from-blue-600 hover:to-purple-600 transition-colors"
                    title="Expand AI Chat"
                  >
                    <div className="flex flex-col items-center gap-2">
                      <ChevronLeftIcon className="w-5 h-5 text-white" />
                      <span className="text-xs text-white font-medium" style={{ writingMode: 'vertical-rl' }}>
                        🤖 AI Chat
                      </span>
                    </div>
                  </button>
                ) : (
                  <div className="relative">
                    <button
                      onClick={() => setCollapsedPanel("chat")}
                      className="absolute -left-3 top-4 z-10 w-6 h-6 bg-white rounded-full shadow-md border border-gray-200 flex items-center justify-center hover:bg-gray-50 transition-colors"
                      title="Collapse AI Chat"
                    >
                      <ChevronRightIcon className="w-4 h-4 text-gray-500" />
                    </button>
                    <DataAIChatPanel
                      selectedFields={selectedFields}
                      filters={filters}
                    />
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>

    </div>
  );
}
