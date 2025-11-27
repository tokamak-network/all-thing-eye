"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

interface Member {
  name: string;
  email?: string;
}

interface Project {
  id: string;
  name: string;
  slack_channel?: string;
  repositories?: string[];
}

interface FilterPanelProps {
  filters: {
    startDate: string;
    endDate: string;
    project: string;
    selectedMembers: string[];
  };
  onFiltersChange: (filters: any) => void;
  onPreview: () => void;
  onExport: () => void;
  onSaveTemplate: () => void;
  isLoading?: boolean;
}

export default function FilterPanel({
  filters,
  onFiltersChange,
  onPreview,
  onExport,
  onSaveTemplate,
  isLoading = false,
}: FilterPanelProps) {
  const [members, setMembers] = useState<Member[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [membersExpanded, setMembersExpanded] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch members and projects on mount
  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        
        // Fetch members
        const membersResponse = await api.getMembers({ limit: 1000 });
        const memberList = membersResponse
          .map((m: any) => ({ name: m.name, email: m.email }))
          .filter((m: Member) => m.name)
          .sort((a: Member, b: Member) => a.name.localeCompare(b.name));
        setMembers(memberList);

        // Use static project list (API for projects not implemented yet)
        // Note: DRB is part of TRH project
        setProjects([
          { id: "all", name: "All Projects" },
          { id: "project-ooo", name: "Project OOO" },
          { id: "project-eco", name: "Project ECO" },
          { id: "project-syb", name: "Project SYB" },
          { id: "project-trh", name: "Project TRH" },
        ]);
      } catch (error) {
        console.error("Failed to fetch filter data:", error);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  const handleFilterChange = (key: string, value: any) => {
    onFiltersChange({
      ...filters,
      [key]: value,
    });
  };

  // Format date as YYYY-MM-DD in local timezone (not UTC)
  const formatDate = (date: Date): string => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  const handleMemberToggle = (memberName: string) => {
    const currentSelected = filters.selectedMembers || [];
    const newSelected = currentSelected.includes(memberName)
      ? currentSelected.filter((m) => m !== memberName)
      : [...currentSelected, memberName];
    handleFilterChange("selectedMembers", newSelected);
  };

  const handleSelectAll = () => {
    const allMemberNames = filteredMembers.map((m) => m.name);
    handleFilterChange("selectedMembers", allMemberNames);
  };

  const handleDeselectAll = () => {
    handleFilterChange("selectedMembers", []);
  };

  // Filter members by search query
  const filteredMembers = members.filter((m) =>
    m.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const selectedCount = (filters.selectedMembers || []).length;

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      {/* Header */}
      <h2 className="text-lg font-semibold text-gray-900 mb-4">
        Filters & Actions
      </h2>

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : (
        <>
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
              {/* Quick Presets */}
              <div className="flex flex-wrap gap-1.5 mt-3">
                <button
                  onClick={() => {
                    const today = new Date();
                    const lastWeek = new Date(today);
                    lastWeek.setDate(today.getDate() - 7);
                    onFiltersChange({
                      ...filters,
                      startDate: formatDate(lastWeek),
                      endDate: formatDate(today),
                    });
                  }}
                  className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-full hover:bg-blue-100 hover:text-blue-700 transition-colors"
                >
                  Last Week
                </button>
                <button
                  onClick={() => {
                    const today = new Date();
                    const firstDayLastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
                    const lastDayLastMonth = new Date(today.getFullYear(), today.getMonth(), 0);
                    onFiltersChange({
                      ...filters,
                      startDate: formatDate(firstDayLastMonth),
                      endDate: formatDate(lastDayLastMonth),
                    });
                  }}
                  className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-full hover:bg-blue-100 hover:text-blue-700 transition-colors"
                >
                  Last Month
                </button>
                <button
                  onClick={() => {
                    const today = new Date();
                    const thisMonth = new Date(today.getFullYear(), today.getMonth(), 1);
                    onFiltersChange({
                      ...filters,
                      startDate: formatDate(thisMonth),
                      endDate: formatDate(today),
                    });
                  }}
                  className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-full hover:bg-blue-100 hover:text-blue-700 transition-colors"
                >
                  This Month
                </button>
                <button
                  onClick={() => {
                    const today = new Date();
                    const currentQuarter = Math.floor(today.getMonth() / 3);
                    const lastQuarterStart = currentQuarter === 0 
                      ? new Date(today.getFullYear() - 1, 9, 1)
                      : new Date(today.getFullYear(), (currentQuarter - 1) * 3, 1);
                    const lastQuarterEnd = currentQuarter === 0
                      ? new Date(today.getFullYear() - 1, 12, 0)
                      : new Date(today.getFullYear(), currentQuarter * 3, 0);
                    onFiltersChange({
                      ...filters,
                      startDate: formatDate(lastQuarterStart),
                      endDate: formatDate(lastQuarterEnd),
                    });
                  }}
                  className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-full hover:bg-blue-100 hover:text-blue-700 transition-colors"
                >
                  Last Quarter
                </button>
                <button
                  onClick={() => {
                    const today = new Date();
                    const currentQuarter = Math.floor(today.getMonth() / 3);
                    const thisQuarterStart = new Date(today.getFullYear(), currentQuarter * 3, 1);
                    onFiltersChange({
                      ...filters,
                      startDate: formatDate(thisQuarterStart),
                      endDate: formatDate(today),
                    });
                  }}
                  className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-full hover:bg-blue-100 hover:text-blue-700 transition-colors"
                >
                  This Quarter
                </button>
                <button
                  onClick={() => {
                    const today = new Date();
                    const lastYearStart = new Date(today.getFullYear() - 1, 0, 1);
                    const lastYearEnd = new Date(today.getFullYear() - 1, 11, 31);
                    onFiltersChange({
                      ...filters,
                      startDate: formatDate(lastYearStart),
                      endDate: formatDate(lastYearEnd),
                    });
                  }}
                  className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-full hover:bg-blue-100 hover:text-blue-700 transition-colors"
                >
                  Last Year
                </button>
                <button
                  onClick={() => {
                    const today = new Date();
                    const thisYearStart = new Date(today.getFullYear(), 0, 1);
                    onFiltersChange({
                      ...filters,
                      startDate: formatDate(thisYearStart),
                      endDate: formatDate(today),
                    });
                  }}
                  className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-full hover:bg-blue-100 hover:text-blue-700 transition-colors"
                >
                  This Year
                </button>
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

            {/* Members Filter - Multi-select Checkboxes */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-gray-700">
                  👤 Members
                  {selectedCount > 0 && (
                    <span className="ml-2 px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full">
                      {selectedCount} selected
                    </span>
                  )}
                </label>
                <button
                  onClick={() => setMembersExpanded(!membersExpanded)}
                  className="text-sm text-gray-500 hover:text-gray-700"
                >
                  {membersExpanded ? "▼ Collapse" : "▶ Expand"}
                </button>
              </div>

              {membersExpanded && (
                <div className="border border-gray-300 rounded-md">
                  {/* Search and Select All */}
                  <div className="p-2 border-b border-gray-200 bg-gray-50">
                    <input
                      type="text"
                      placeholder="Search members..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <div className="flex gap-2 mt-2">
                      <button
                        onClick={handleSelectAll}
                        className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                      >
                        Select All ({filteredMembers.length})
                      </button>
                      <button
                        onClick={handleDeselectAll}
                        className="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                      >
                        Deselect All
                      </button>
                    </div>
                  </div>

                  {/* Member Checkboxes */}
                  <div className="max-h-64 overflow-y-auto p-2">
                    {filteredMembers.length === 0 ? (
                      <p className="text-sm text-gray-500 text-center py-4">
                        No members found
                      </p>
                    ) : (
                      <div className="grid grid-cols-2 gap-1">
                        {filteredMembers.map((member) => (
                          <label
                            key={member.name}
                            className={`flex items-center p-2 rounded cursor-pointer hover:bg-gray-50 ${
                              (filters.selectedMembers || []).includes(member.name)
                                ? "bg-blue-50"
                                : ""
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={(filters.selectedMembers || []).includes(
                                member.name
                              )}
                              onChange={() => handleMemberToggle(member.name)}
                              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                            />
                            <span className="ml-2 text-sm text-gray-700">
                              {member.name}
                            </span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
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
              disabled={isLoading}
              className={`w-full px-4 py-3 text-white rounded-lg transition-colors font-medium flex items-center justify-center gap-2 ${
                isLoading
                  ? "bg-green-400 cursor-not-allowed"
                  : "bg-green-600 hover:bg-green-700"
              }`}
            >
              {isLoading ? (
                <>
                  <span className="animate-spin">⏳</span>
                  Exporting...
                </>
              ) : (
                <>
                  <span>💾</span>
                  Export as CSV
                </>
              )}
            </button>

            {/* Save Template Button */}
            <button
              onClick={onSaveTemplate}
              className="w-full px-4 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors font-medium flex items-center justify-center gap-2"
            >
              <span>📋</span>
              Save as Template
            </button>
          </div>

        </>
      )}
    </div>
  );
}
