"use client";

import { ActivityStats } from "@/graphql/types";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { format } from "date-fns";

interface MemberActivityStatsProps {
  stats: ActivityStats;
}

const COLORS = [
  "#8b5cf6", // purple for GitHub
  "#10b981", // green for Slack
  "#3b82f6", // blue for Notion
  "#f59e0b", // orange for Drive
];

export default function MemberActivityStats({
  stats,
}: MemberActivityStatsProps) {
  // Prepare data for pie chart
  const pieData = stats.bySource.map((source, index) => ({
    name: source.source.toUpperCase(),
    value: source.count,
    percentage: source.percentage,
    color: COLORS[index % COLORS.length],
  }));

  // Prepare data for line chart (weekly trend)
  const lineData = stats.weeklyTrend.map((week) => ({
    week: format(new Date(week.weekStart), "MMM d"),
    activities: week.count,
  }));

  return (
    <div className="space-y-8">
      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg shadow-lg p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-blue-100 text-sm font-medium">
                Total Activities
              </p>
              <p className="text-4xl font-bold mt-2">
                {stats.totalActivities.toLocaleString()}
              </p>
            </div>
            <div className="text-5xl opacity-20">📊</div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-lg shadow-lg p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-green-100 text-sm font-medium">Last 30 Days</p>
              <p className="text-4xl font-bold mt-2">
                {stats.last30Days.toLocaleString()}
              </p>
            </div>
            <div className="text-5xl opacity-20">📅</div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg shadow-lg p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-purple-100 text-sm font-medium">
                Daily Average
              </p>
              <p className="text-4xl font-bold mt-2">
                {Math.round(stats.last30Days / 30)}
              </p>
            </div>
            <div className="text-5xl opacity-20">⚡</div>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Source Distribution Pie Chart */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Activity by Source</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={(entry) =>
                  `${entry.name} (${entry.percentage.toFixed(1)}%)`
                }
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {pieData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>

          {/* Legend */}
          <div className="mt-4 space-y-2">
            {stats.bySource.map((source, index) => (
              <div
                key={source.source}
                className="flex items-center justify-between text-sm"
              >
                <div className="flex items-center space-x-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{
                      backgroundColor: COLORS[index % COLORS.length],
                    }}
                  />
                  <span className="font-medium">
                    {source.source.toUpperCase()}
                  </span>
                </div>
                <div className="text-gray-600">
                  {source.count.toLocaleString()} (
                  {source.percentage.toFixed(1)}%)
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Weekly Trend Line Chart */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">
            Weekly Trend (Last 4 Weeks)
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={lineData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="week" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="activities"
                stroke="#8b5cf6"
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Source Breakdown Bar Chart */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Activity Distribution</h3>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={stats.bySource}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="source" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="count" fill="#8b5cf6" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

