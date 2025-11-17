"use client";

import { useState } from "react";
import FieldSelector from "./components/FieldSelector";
import FilterPanel from "./components/FilterPanel";
import PreviewTable from "./components/PreviewTable";
import AIChatPanel from "./components/AIChatPanel";

export default function CustomExportPage() {
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
    members: "all",
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
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          📊 Custom Data Export Builder
        </h1>
        <p className="text-gray-600">
          Select fields from multiple data sources and export custom reports
          without SQL knowledge
        </p>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
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

      {/* Coming Soon Notice */}
      <div className="max-w-7xl mx-auto mt-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <div className="flex items-start">
          <span className="text-2xl mr-3">🚧</span>
          <div>
            <h3 className="font-semibold text-yellow-900 mb-1">
              UI Prototype - Functionality Coming Soon
            </h3>
            <p className="text-sm text-yellow-800">
              This is a visual prototype. The actual data export functionality
              will be implemented in Phase 2. Currently showing mock data for
              demonstration purposes.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
