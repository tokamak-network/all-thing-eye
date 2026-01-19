"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ReportPreset {
  name: string;
  start_date: string;
  end_date: string;
}

interface ReportMetadata {
  start_date: string;
  end_date: string;
  use_ai: boolean;
  generated_at: string;
  stats: {
    total_commits: number;
    total_repos: number;
    total_prs: number;
    staked_ton: number;
    market_cap: number;
  };
}

export default function ReportGeneratorPanel() {
  // Date range state
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  
  // Options
  const [useAi, setUseAi] = useState<boolean>(true);
  
  // Presets
  const [presets, setPresets] = useState<ReportPreset[]>([]);
  const [loadingPresets, setLoadingPresets] = useState(true);
  
  // Generation state
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Generated report
  const [reportContent, setReportContent] = useState<string | null>(null);
  const [reportMetadata, setReportMetadata] = useState<ReportMetadata | null>(null);
  
  // View mode
  const [viewMode, setViewMode] = useState<"preview" | "raw">("preview");

  // Format date helper
  const formatDate = (date: Date): string => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };

  // Initialize with default date range (1st half of month)
  useEffect(() => {
    const today = new Date();
    const currentDay = today.getDate();
    
    // Always default to 1st half (1-15)
    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
    const fifteenth = new Date(today.getFullYear(), today.getMonth(), 15);
    
    setStartDate(formatDate(firstDay));
    // If we're still in the first half, use today; otherwise use the 15th
    setEndDate(currentDay <= 15 ? formatDate(today) : formatDate(fifteenth));
    
    // Fetch presets
    fetchPresets();
  }, []);

  const fetchPresets = async () => {
    try {
      setLoadingPresets(true);
      const response = await api.getReportPresets();
      setPresets(response.presets);
    } catch (err) {
      console.error("Failed to fetch presets:", err);
      // Use default presets
      const today = new Date();
      const currentDay = today.getDate();
      
      // This month first half
      const thisMonthFirstHalfStart = new Date(today.getFullYear(), today.getMonth(), 1);
      const thisMonthFirstHalfEnd = new Date(today.getFullYear(), today.getMonth(), 15);
      
      // This month second half
      const thisMonthSecondHalfStart = new Date(today.getFullYear(), today.getMonth(), 16);
      const lastDayOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
      const thisMonthSecondHalfEnd = new Date(today.getFullYear(), today.getMonth(), lastDayOfMonth);
      
      const defaultPresets: ReportPreset[] = [];
      
      // 1st half always first
      defaultPresets.push({
        name: "This month 1st half (1-15)",
        start_date: formatDate(thisMonthFirstHalfStart),
        end_date: currentDay >= 15 ? formatDate(thisMonthFirstHalfEnd) : formatDate(today),
      });
      
      // 2nd half only if we're past the 15th
      if (currentDay > 15) {
        defaultPresets.push({
          name: "This month 2nd half (16-end)",
          start_date: formatDate(thisMonthSecondHalfStart),
          end_date: formatDate(today),
        });
      }
      
      setPresets(defaultPresets);
    } finally {
      setLoadingPresets(false);
    }
  };

  const applyPreset = (preset: ReportPreset) => {
    setStartDate(preset.start_date);
    setEndDate(preset.end_date);
  };

  const handleGenerate = async () => {
    if (!startDate || !endDate) {
      setError("Please select a date range");
      return;
    }

    setIsGenerating(true);
    setError(null);
    setReportContent(null);
    setReportMetadata(null);

    try {
      const response = await api.generateReport(startDate, endDate, useAi);
      setReportContent(response.content);
      setReportMetadata(response.metadata);
    } catch (err: any) {
      console.error("Failed to generate report:", err);
      setError(
        err.response?.data?.detail || err.message || "Failed to generate report"
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = () => {
    if (!reportContent) return;

    const blob = new Blob([reportContent], { type: "text/markdown" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `biweekly-report-${endDate}.md`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  };

  const handleCopyToClipboard = () => {
    if (!reportContent) return;
    navigator.clipboard.writeText(reportContent);
  };

  return (
    <div className="space-y-6">
      {/* Configuration Panel */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          📊 Biweekly Report Generator
        </h2>
        <p className="text-sm text-gray-600 mb-6">
          Generate ecosystem reports with GitHub statistics, staking data, and
          market information.
        </p>

        {/* Date Range Selection */}
        <div className="space-y-4">
          <label className="block text-sm font-medium text-gray-700">
            Report Period
          </label>

          {/* Quick Presets */}
          <div className="flex flex-wrap gap-2 mb-3">
            {loadingPresets ? (
              <span className="text-sm text-gray-500">Loading presets...</span>
            ) : (
              presets.map((preset) => (
                <button
                  key={preset.name}
                  onClick={() => applyPreset(preset)}
                  className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
                    startDate === preset.start_date &&
                    endDate === preset.end_date
                      ? "bg-blue-100 border-blue-300 text-blue-700"
                      : "bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100"
                  }`}
                >
                  {preset.name}
                </button>
              ))
            )}
          </div>

          {/* Date Inputs */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                Start Date
              </label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                End Date
              </label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Options */}
        <div className="mt-6 space-y-4">
          <label className="block text-sm font-medium text-gray-700">
            Options
          </label>

          <div className="flex items-center gap-3">
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={useAi}
                onChange={(e) => setUseAi(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              <span className="ms-3 text-sm text-gray-700">
                🤖 Use AI for summaries
              </span>
            </label>
          </div>

          <p className="text-xs text-gray-500">
            {useAi
              ? "AI will generate intelligent summaries from commit messages and data."
              : "Basic summaries will be generated without AI processing."}
          </p>
        </div>

        {/* Generate Button */}
        <div className="mt-6">
          <button
            onClick={handleGenerate}
            disabled={isGenerating || !startDate || !endDate}
            className={`w-full py-3 px-4 rounded-lg font-medium transition-colors ${
              isGenerating || !startDate || !endDate
                ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                : "bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            {isGenerating ? (
              <span className="flex items-center justify-center gap-2">
                <svg
                  className="animate-spin h-5 w-5"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Generating Report...
              </span>
            ) : (
              "🚀 Generate Report"
            )}
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            ❌ {error}
          </div>
        )}
      </div>

      {/* Generated Report */}
      {reportContent && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          {/* Report Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-200">
            <div>
              <h3 className="font-semibold text-gray-900">Generated Report</h3>
              {reportMetadata && (
                <p className="text-xs text-gray-500 mt-1">
                  {reportMetadata.start_date} ~ {reportMetadata.end_date} •{" "}
                  {reportMetadata.stats.total_commits} commits •{" "}
                  {reportMetadata.stats.total_repos} repos
                </p>
              )}
            </div>

            <div className="flex items-center gap-2">
              {/* View Mode Toggle */}
              <div className="flex rounded-lg border border-gray-200 overflow-hidden">
                <button
                  onClick={() => setViewMode("preview")}
                  className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                    viewMode === "preview"
                      ? "bg-blue-600 text-white"
                      : "bg-white text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  Preview
                </button>
                <button
                  onClick={() => setViewMode("raw")}
                  className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                    viewMode === "raw"
                      ? "bg-blue-600 text-white"
                      : "bg-white text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  Raw
                </button>
              </div>

              {/* Action Buttons */}
              <button
                onClick={handleCopyToClipboard}
                className="px-3 py-1.5 text-xs font-medium bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
              >
                📋 Copy
              </button>
              <button
                onClick={handleDownload}
                className="px-3 py-1.5 text-xs font-medium bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
              >
                ⬇️ Download .md
              </button>
            </div>
          </div>

          {/* Report Content */}
          <div className="p-6 max-h-[600px] overflow-y-auto">
            {viewMode === "preview" ? (
              <article className="prose prose-sm max-w-none prose-h1:text-2xl prose-h1:font-bold prose-h1:text-gray-900 prose-h1:mt-6 prose-h1:mb-4 prose-h2:text-xl prose-h2:font-semibold prose-h2:text-gray-800 prose-h2:mt-5 prose-h2:mb-3 prose-h3:text-lg prose-h3:font-medium prose-h3:text-gray-700 prose-p:text-gray-700 prose-p:my-3 prose-a:text-blue-600 prose-strong:text-gray-900 prose-table:text-sm prose-li:my-1 prose-ul:my-2 prose-ol:my-2">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {reportContent}
                </ReactMarkdown>
              </article>
            ) : (
              <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono bg-gray-50 p-4 rounded-lg overflow-x-auto">
                {reportContent}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* Stats Panel (shown when report is generated) */}
      {reportMetadata && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-900 mb-4">📈 Report Stats</h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="text-center p-3 bg-blue-50 rounded-lg">
              <div className="text-2xl font-bold text-blue-600">
                {reportMetadata.stats.total_commits}
              </div>
              <div className="text-xs text-gray-600">Commits</div>
            </div>
            <div className="text-center p-3 bg-green-50 rounded-lg">
              <div className="text-2xl font-bold text-green-600">
                {reportMetadata.stats.total_repos}
              </div>
              <div className="text-xs text-gray-600">Repositories</div>
            </div>
            <div className="text-center p-3 bg-purple-50 rounded-lg">
              <div className="text-2xl font-bold text-purple-600">
                {reportMetadata.stats.total_prs}
              </div>
              <div className="text-xs text-gray-600">Pull Requests</div>
            </div>
            <div className="text-center p-3 bg-yellow-50 rounded-lg">
              <div className="text-2xl font-bold text-yellow-600">
                {(reportMetadata.stats.staked_ton / 1_000_000).toFixed(1)}M
              </div>
              <div className="text-xs text-gray-600">Staked TON</div>
            </div>
            <div className="text-center p-3 bg-red-50 rounded-lg">
              <div className="text-2xl font-bold text-red-600">
                ${(reportMetadata.stats.market_cap / 1_000_000).toFixed(1)}M
              </div>
              <div className="text-xs text-gray-600">Market Cap</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
