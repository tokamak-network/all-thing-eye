"use client";

import { useState } from "react";
import FieldSelector from "./components/FieldSelector";
import FilterPanel from "./components/FilterPanel";
import PreviewTable from "./components/PreviewTable";
import AIChatPanel from "./components/AIChatPanel";
import NotionExportPanel from "./components/NotionExportPanel";

export default function CustomExportPage() {
  const [activeTab, setActiveTab] = useState<"custom" | "notion">("notion");

  const [selectedFields, setSelectedFields] = useState<string[]>([
    "member.name",
    "member.email",
    "github.commits",
    "slack.messages",
  ]);

  const [filters, setFilters] = useState({
    startDate: "2025-11-01",
    endDate: "2025-11-07",
    project: "all",
    selectedMembers: [] as string[],
  });

  const handleFieldToggle = (fieldId: string) => {
    setSelectedFields((prev) =>
      prev.includes(fieldId)
        ? prev.filter((f) => f !== fieldId)
        : [...prev, fieldId]
    );
  };

  const handlePreview = () => {
    console.log("Preview clicked", { selectedFields, filters });
    // TODO: Fetch data from API
  };

  const handleExport = () => {
    console.log("Export clicked", { selectedFields, filters });
    // TODO: Export as CSV
  };

  const handleSaveTemplate = () => {
    console.log("Save template clicked", { selectedFields, filters });
    // TODO: Save template
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {/* TBD Notice - Top of Page */}
      <div className="max-w-7xl mx-auto mb-6 bg-blue-50 border-2 border-blue-300 rounded-lg p-6">
        <div className="flex items-start">
          <span className="text-3xl mr-4">🔨</span>
          <div>
            <h3 className="text-lg font-bold text-blue-900 mb-2">
              🚧 To Be Developed (TBD)
            </h3>
            <p className="text-sm text-blue-800 mb-2">
              This feature is currently under development and will be available in a future release.
            </p>
            <p className="text-sm text-blue-700">
              <strong>What&apos;s Coming:</strong> Advanced custom data export builder with AI-powered field selection, 
              multi-source data integration, and template saving functionality.
            </p>
          </div>
        </div>
      </div>

      {/* Header */}
      <div className="max-w-7xl mx-auto mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          📊 Custom Data Export Builder
        </h1>
        <p className="text-gray-600">
          Select fields from multiple data sources and export custom reports
          without SQL knowledge
        </p>

        {/* Tabs */}
        <div className="mt-4 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
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
            <button
              onClick={() => setActiveTab("custom")}
              className={`${
                activeTab === "custom"
                  ? "border-blue-500 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
            >
              🔧 Custom Fields (TBD)
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
          /* Custom Fields Tab (TBD) */
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column: Field Selector */}
            <div className="lg:col-span-1">
              <FieldSelector
                selectedFields={selectedFields}
                onFieldToggle={handleFieldToggle}
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
              />

              {/* Preview Table */}
              <PreviewTable selectedFields={selectedFields} />

              {/* AI Chat Panel */}
              <AIChatPanel selectedFields={selectedFields} filters={filters} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
