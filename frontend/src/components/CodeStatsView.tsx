"use client";

import { useState, useEffect } from "react";
import { format } from "date-fns";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { api } from "@/lib/api";

// Date range presets
type DateRangePreset = "3d" | "7d" | "14d" | "month" | "lastMonth";

const DATE_RANGE_PRESETS: {
  value: DateRangePreset;
  label: string;
  days: number;
}[] = [
  { value: "3d", label: "3 Days", days: 3 },
  { value: "7d", label: "1 Week", days: 7 },
  { value: "14d", label: "2 Weeks", days: 14 },
  { value: "month", label: "This Month", days: -1 },
  { value: "lastMonth", label: "Last Month", days: -2 },
];

interface CodeStats {
  total: {
    additions: number;
    deletions: number;
  };
  daily: Array<{
    date: string;
    additions: number;
    deletions: number;
  }>;
  weekly: Array<{
    week: string;
    additions: number;
    deletions: number;
  }>;
  by_member?: Array<{
    name: string;
    additions: number;
    deletions: number;
    commits: number;
  }>;
  by_repository?: Array<{
    name: string;
    additions: number;
    deletions: number;
    commits: number;
  }>;
}

// Helper to calculate date range
function getDateRange(preset: DateRangePreset): { startDate: string; endDate: string } {
  const now = new Date();
  let startDate: Date;
  let endDate: Date = now;

  if (preset === "month") {
    startDate = new Date(now.getFullYear(), now.getMonth(), 1);
  } else if (preset === "lastMonth") {
    startDate = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    endDate = new Date(now.getFullYear(), now.getMonth(), 0);
  } else {
    const days = DATE_RANGE_PRESETS.find((p) => p.value === preset)?.days || 7;
    startDate = new Date(now);
    startDate.setDate(startDate.getDate() - days);
  }

  return {
    startDate: startDate.toISOString().split("T")[0],
    endDate: endDate.toISOString().split("T")[0],
  };
}

export default function CodeStatsView() {
  const [dateRange, setDateRange] = useState<DateRangePreset>("month");
  const [stats, setStats] = useState<CodeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch code stats when date range changes
  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        setError(null);
        const { startDate, endDate } = getDateRange(dateRange);
        const data = await api.getCodeStats(startDate, endDate);
        setStats(data);
      } catch (err: any) {
        console.error("Failed to fetch code stats:", err);
        setError(err.message || "Failed to fetch code statistics");
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, [dateRange]);

  // Use stats directly (already filtered by API)
  const dailyData = stats?.daily || [];
  const totals = stats?.total || { additions: 0, deletions: 0 };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">Error: {error}</p>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
        <p className="text-gray-600">No code statistics available</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-gray-800 via-gray-900 to-black rounded-xl shadow-lg p-6 text-white">
        <div className="flex items-center gap-3">
          <span className="text-4xl">🐙</span>
          <div>
            <h1 className="text-2xl font-bold">Code Statistics</h1>
            <p className="text-gray-300">
              GitHub commit analytics and code contribution insights
            </p>
          </div>
        </div>
      </div>

      {/* Date Range Filter */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-gray-700">Period:</span>
        {DATE_RANGE_PRESETS.map((preset) => (
          <button
            key={preset.value}
            onClick={() => setDateRange(preset.value)}
            className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-all ${
              dateRange === preset.value
                ? "bg-indigo-600 text-white shadow-md"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {preset.label}
          </button>
        ))}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-gradient-to-br from-emerald-500 to-emerald-600 rounded-xl shadow-lg p-6 text-white">
          <p className="text-emerald-100 text-sm font-medium mb-1">
            Lines Added
          </p>
          <p className="text-3xl font-bold">
            +{totals.additions.toLocaleString()}
          </p>
        </div>

        <div className="bg-gradient-to-br from-rose-500 to-rose-600 rounded-xl shadow-lg p-6 text-white">
          <p className="text-rose-100 text-sm font-medium mb-1">Lines Deleted</p>
          <p className="text-3xl font-bold">
            -{totals.deletions.toLocaleString()}
          </p>
        </div>

        <div className="bg-gradient-to-br from-indigo-500 to-indigo-600 rounded-xl shadow-lg p-6 text-white">
          <p className="text-indigo-100 text-sm font-medium mb-1">Net Change</p>
          <p className="text-3xl font-bold">
            {totals.additions - totals.deletions >= 0 ? "+" : ""}
            {(totals.additions - totals.deletions).toLocaleString()}
          </p>
        </div>

        <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl shadow-lg p-6 text-white">
          <p className="text-purple-100 text-sm font-medium mb-1">
            Total Changes
          </p>
          <p className="text-3xl font-bold">
            {(totals.additions + totals.deletions).toLocaleString()}
          </p>
        </div>
      </div>

      {/* Code Changes Chart */}
      {dailyData.length > 0 && (
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
            <span className="text-2xl">📈</span>
            Code Changes Over Time
          </h2>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={dailyData.map((d) => ({
                  ...d,
                  changes: d.additions + d.deletions,
                }))}
                margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="colorCodeChanges" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0.1} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                  stroke="#e5e7eb"
                />
                <XAxis
                  dataKey="date"
                  tickFormatter={(str) => format(new Date(str), "MM/dd")}
                  stroke="#9ca3af"
                  fontSize={12}
                />
                <YAxis stroke="#9ca3af" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#fff",
                    borderRadius: "0.5rem",
                    border: "1px solid #e5e7eb",
                    boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)",
                  }}
                  labelFormatter={(value) =>
                    format(new Date(value), "MMM dd, yyyy")
                  }
                  formatter={(value: number, name: string, props: any) => {
                    const item = props.payload;
                    return [
                      `${value.toLocaleString()} lines (+${item.additions.toLocaleString()} / -${item.deletions.toLocaleString()})`,
                      "Code Changes",
                    ];
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="changes"
                  name="Code Changes"
                  stroke="#6366f1"
                  fill="url(#colorCodeChanges)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Member Rankings & Repository Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Contributors */}
        {stats.by_member && stats.by_member.length > 0 && (
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
              <span className="text-2xl">🏆</span>
              Top Contributors
            </h2>
            <div className="space-y-4">
              {stats.by_member.slice(0, 10).map((member, index) => (
                <div
                  key={member.name}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold ${
                        index === 0
                          ? "bg-yellow-500"
                          : index === 1
                          ? "bg-gray-400"
                          : index === 2
                          ? "bg-orange-400"
                          : "bg-gray-300"
                      }`}
                    >
                      {index + 1}
                    </span>
                    <div>
                      <p className="font-medium text-gray-900">{member.name}</p>
                      <p className="text-sm text-gray-500">
                        {member.commits} commits
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm">
                      <span className="text-emerald-600">
                        +{member.additions.toLocaleString()}
                      </span>
                      {" / "}
                      <span className="text-rose-600">
                        -{member.deletions.toLocaleString()}
                      </span>
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Top Repositories */}
        {stats.by_repository && stats.by_repository.length > 0 && (
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
              <span className="text-2xl">📁</span>
              Active Repositories
            </h2>
            <div className="space-y-4">
              {stats.by_repository.slice(0, 10).map((repo, index) => (
                <div
                  key={repo.name}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xl">🐙</span>
                    <div>
                      <p className="font-medium text-gray-900">{repo.name}</p>
                      <p className="text-sm text-gray-500">
                        {repo.commits} commits
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm">
                      <span className="text-emerald-600">
                        +{repo.additions.toLocaleString()}
                      </span>
                      {" / "}
                      <span className="text-rose-600">
                        -{repo.deletions.toLocaleString()}
                      </span>
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
