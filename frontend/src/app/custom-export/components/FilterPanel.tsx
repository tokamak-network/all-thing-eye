"use client";

interface FilterPanelProps {
  filters: {
    startDate: string;
    endDate: string;
    project: string;
    members: string;
  };
  onFiltersChange: (filters: any) => void;
  onPreview: () => void;
  onExport: () => void;
  onSaveTemplate: () => void;
}

const projects = [
  { id: "all", name: "All Projects" },
  { id: "project-ooo", name: "Project OOO" },
  { id: "project-syb", name: "Project SYB" },
  { id: "project-trh", name: "Project TRH" },
  { id: "project-drb", name: "Project DRB" },
];

const memberGroups = [
  { id: "all", name: "All Members" },
  { id: "core-team", name: "Core Team" },
  { id: "developers", name: "Developers" },
  { id: "designers", name: "Designers" },
  { id: "managers", name: "Managers" },
];

export default function FilterPanel({
  filters,
  onFiltersChange,
  onPreview,
  onExport,
  onSaveTemplate,
}: FilterPanelProps) {
  const handleFilterChange = (key: string, value: string) => {
    onFiltersChange({
      ...filters,
      [key]: value,
    });
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      {/* Header */}
      <h2 className="text-lg font-semibold text-gray-900 mb-4">
        Filters & Actions
      </h2>

      {/* Filters */}
      <div className="space-y-4 mb-6">
        {/* Date Range */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            📅 Date Range
          </label>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <input
                type="date"
                value={filters.startDate}
                onChange={(e) =>
                  handleFilterChange("startDate", e.target.value)
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              />
              <p className="text-xs text-gray-500 mt-1">From</p>
            </div>
            <div>
              <input
                type="date"
                value={filters.endDate}
                onChange={(e) => handleFilterChange("endDate", e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              />
              <p className="text-xs text-gray-500 mt-1">To</p>
            </div>
          </div>
        </div>

        {/* Project Filter */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            🎯 Project
          </label>
          <select
            value={filters.project}
            onChange={(e) => handleFilterChange("project", e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </div>

        {/* Members Filter */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            👤 Members
          </label>
          <select
            value={filters.members}
            onChange={(e) => handleFilterChange("members", e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
          >
            {memberGroups.map((group) => (
              <option key={group.id} value={group.id}>
                {group.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="space-y-2">
        {/* Preview Button */}
        <button
          onClick={onPreview}
          className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium flex items-center justify-center gap-2"
        >
          <span>🔍</span>
          Preview Results
        </button>

        {/* Export Button */}
        <button
          onClick={onExport}
          className="w-full px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium flex items-center justify-center gap-2"
        >
          <span>💾</span>
          Export as CSV
        </button>

        {/* Save Template Button */}
        <button
          onClick={onSaveTemplate}
          className="w-full px-4 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors font-medium flex items-center justify-center gap-2"
        >
          <span>💾</span>
          Save as Template
        </button>
      </div>

      {/* Quick Date Presets */}
      <div className="mt-6 pt-4 border-t border-gray-200">
        <p className="text-xs font-medium text-gray-700 mb-2">Quick Presets:</p>
        <div className="grid grid-cols-3 gap-2">
          <button
            onClick={() => {
              const today = new Date();
              const lastWeek = new Date(today);
              lastWeek.setDate(today.getDate() - 7);
              onFiltersChange({
                ...filters,
                startDate: lastWeek.toISOString().split("T")[0],
                endDate: today.toISOString().split("T")[0],
              });
            }}
            className="text-xs px-2 py-1.5 bg-gray-50 text-gray-700 rounded hover:bg-gray-100 transition-colors"
          >
            Last Week
          </button>
          <button
            onClick={() => {
              const today = new Date();
              const lastMonth = new Date(today);
              lastMonth.setMonth(today.getMonth() - 1);
              onFiltersChange({
                ...filters,
                startDate: lastMonth.toISOString().split("T")[0],
                endDate: today.toISOString().split("T")[0],
              });
            }}
            className="text-xs px-2 py-1.5 bg-gray-50 text-gray-700 rounded hover:bg-gray-100 transition-colors"
          >
            Last Month
          </button>
          <button
            onClick={() => {
              const today = new Date();
              const thisMonth = new Date(
                today.getFullYear(),
                today.getMonth(),
                1
              );
              onFiltersChange({
                ...filters,
                startDate: thisMonth.toISOString().split("T")[0],
                endDate: today.toISOString().split("T")[0],
              });
            }}
            className="text-xs px-2 py-1.5 bg-gray-50 text-gray-700 rounded hover:bg-gray-100 transition-colors"
          >
            This Month
          </button>
        </div>
      </div>
    </div>
  );
}





