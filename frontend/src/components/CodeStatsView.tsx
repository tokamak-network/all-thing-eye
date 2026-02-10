"use client";

import { useState, useEffect } from "react";
import { format, formatDistanceToNow } from "date-fns";
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
    contributors?: Array<{
      name: string;
      github_id: string;
      additions: number;
      deletions: number;
      commits: number;
    }>;
  }>;
}

interface CommitInfo {
  sha: string;
  message: string;
  repository: string;
  date: string;
  additions: number;
  deletions: number;
  url: string;
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
  const [contributorPage, setContributorPage] = useState(1);
  const [repositoryPage, setRepositoryPage] = useState(1);
  const [expandedRepos, setExpandedRepos] = useState<Set<string>>(new Set());
  const [expandedContributors, setExpandedContributors] = useState<Set<string>>(new Set());
  const [contributorCommits, setContributorCommits] = useState<Record<string, CommitInfo[]>>({});
  const [loadingContributor, setLoadingContributor] = useState<string | null>(null);
  const [commitPage, setCommitPage] = useState<Record<string, number>>({});
  const CONTRIBUTORS_PER_PAGE = 10;
  const COMMITS_PER_PAGE = 10;
  const REPOSITORIES_PER_PAGE = 10;

  const toggleContributorExpand = async (name: string) => {
    if (expandedContributors.has(name)) {
      setExpandedContributors((prev) => {
        const newSet = new Set(prev);
        newSet.delete(name);
        return newSet;
      });
      return;
    }

    // Expand and load commits if not cached
    setExpandedContributors((prev) => new Set(prev).add(name));

    if (!contributorCommits[name]) {
      try {
        setLoadingContributor(name);
        const { startDate, endDate } = getDateRange(dateRange);
        const data = await api.getMemberCommits(name, startDate, endDate);
        setContributorCommits((prev) => ({
          ...prev,
          [name]: data.commits || [],
        }));
      } catch (err) {
        console.error("Failed to fetch member commits:", err);
        setContributorCommits((prev) => ({
          ...prev,
          [name]: [],
        }));
      } finally {
        setLoadingContributor(null);
      }
    }
  };

  const toggleRepoExpand = (repoName: string) => {
    setExpandedRepos((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(repoName)) {
        newSet.delete(repoName);
      } else {
        newSet.add(repoName);
      }
      return newSet;
    });
  };

  // Fetch code stats when date range changes
  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        setError(null);
        setContributorPage(1); // Reset page when date range changes
        setRepositoryPage(1);
        setExpandedContributors(new Set());
        setContributorCommits({});
        setCommitPage({});
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
        {stats.by_member && stats.by_member.length > 0 && (() => {
          const totalMembers = stats.by_member.length;
          const totalPages = Math.ceil(totalMembers / CONTRIBUTORS_PER_PAGE);
          const startIndex = (contributorPage - 1) * CONTRIBUTORS_PER_PAGE;
          const endIndex = startIndex + CONTRIBUTORS_PER_PAGE;
          const currentPageMembers = stats.by_member.slice(startIndex, endIndex);

          return (
            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                  <span className="text-2xl">🏆</span>
                  Top Contributors
                </h2>
                <span className="text-sm text-gray-500">
                  {totalMembers} members
                </span>
              </div>
              <div className="space-y-3">
                {currentPageMembers.map((member, index) => {
                  const globalIndex = startIndex + index;
                  const isExpanded = expandedContributors.has(member.name);
                  const hasCommits = member.commits > 0;

                  return (
                    <div
                      key={member.name}
                      className="bg-gray-50 rounded-lg overflow-hidden"
                    >
                      <div
                        className={`flex items-center justify-between p-3 ${
                          hasCommits ? "cursor-pointer hover:bg-gray-100" : ""
                        }`}
                        onClick={() => hasCommits && toggleContributorExpand(member.name)}
                      >
                        <div className="flex items-center gap-3">
                          {hasCommits && (
                            <span
                              className={`text-gray-400 transition-transform ${
                                isExpanded ? "rotate-90" : ""
                              }`}
                            >
                              ▶
                            </span>
                          )}
                          <span
                            className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold ${
                              globalIndex === 0
                                ? "bg-yellow-500"
                                : globalIndex === 1
                                ? "bg-gray-400"
                                : globalIndex === 2
                                ? "bg-orange-400"
                                : "bg-gray-300"
                            }`}
                          >
                            {globalIndex + 1}
                          </span>
                          <div>
                            <p className="font-medium text-gray-900">{member.name}</p>
                            <p className="text-sm text-gray-500">
                              {member.commits} commits
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-semibold text-gray-700">
                            {(member.additions + member.deletions).toLocaleString()}
                          </p>
                          <p className="text-xs text-gray-500">
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

                      {/* Recent Commits (expandable) */}
                      {isExpanded && (
                        <div className="border-t border-gray-200 bg-white">
                          <div className="px-4 py-2 bg-gray-100 text-xs font-semibold text-gray-600 uppercase tracking-wider">
                            Recent Commits
                          </div>
                          {loadingContributor === member.name ? (
                            <div className="flex items-center justify-center py-4">
                              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-indigo-600"></div>
                              <span className="ml-2 text-sm text-gray-500">Loading commits...</span>
                            </div>
                          ) : (contributorCommits[member.name] || []).length === 0 ? (
                            <div className="px-4 py-3 text-sm text-gray-500">
                              No commits found for this period.
                            </div>
                          ) : (() => {
                            const allCommits = contributorCommits[member.name] || [];
                            const currentPage = commitPage[member.name] || 1;
                            const totalCommitPages = Math.ceil(allCommits.length / COMMITS_PER_PAGE);
                            const pageStart = (currentPage - 1) * COMMITS_PER_PAGE;
                            const pageCommits = allCommits.slice(pageStart, pageStart + COMMITS_PER_PAGE);

                            return (
                              <>
                                <div className="divide-y divide-gray-100">
                                  {pageCommits.map((commit, idx) => (
                                    <div
                                      key={`${commit.sha}-${idx}`}
                                      className="flex items-center justify-between px-4 py-2 hover:bg-gray-50"
                                    >
                                      <div className="flex-1 min-w-0 mr-3">
                                        <div className="flex items-center gap-2">
                                          <span className="text-xs font-mono text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded shrink-0">
                                            {commit.repository}
                                          </span>
                                          <span className="text-xs text-gray-400 shrink-0">
                                            {commit.date ? formatDistanceToNow(new Date(commit.date), { addSuffix: true }) : ""}
                                          </span>
                                        </div>
                                        <a
                                          href={commit.url}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="text-sm text-gray-800 hover:text-indigo-600 hover:underline truncate block mt-0.5"
                                          onClick={(e) => e.stopPropagation()}
                                        >
                                          {commit.message?.split("\n")[0] || "No message"}
                                        </a>
                                      </div>
                                      <div className="text-right shrink-0">
                                        <p className="text-xs text-gray-500">
                                          <span className="text-emerald-600">+{commit.additions}</span>
                                          {" / "}
                                          <span className="text-rose-600">-{commit.deletions}</span>
                                        </p>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                                {totalCommitPages > 1 && (
                                  <div
                                    className="flex items-center justify-center gap-2 px-4 py-2 border-t border-gray-100 bg-gray-50"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <button
                                      onClick={() => setCommitPage((prev) => ({ ...prev, [member.name]: Math.max(1, currentPage - 1) }))}
                                      disabled={currentPage === 1}
                                      className="px-2 py-0.5 text-xs border border-gray-300 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                      ‹
                                    </button>
                                    <span className="text-xs text-gray-600">
                                      {currentPage} / {totalCommitPages}
                                    </span>
                                    <button
                                      onClick={() => setCommitPage((prev) => ({ ...prev, [member.name]: Math.min(totalCommitPages, currentPage + 1) }))}
                                      disabled={currentPage === totalCommitPages}
                                      className="px-2 py-0.5 text-xs border border-gray-300 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                      ›
                                    </button>
                                  </div>
                                )}
                              </>
                            );
                          })()}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-6 pt-4 border-t border-gray-200">
                  <button
                    onClick={() => setContributorPage(1)}
                    disabled={contributorPage === 1}
                    className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    ««
                  </button>
                  <button
                    onClick={() => setContributorPage(p => Math.max(1, p - 1))}
                    disabled={contributorPage === 1}
                    className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    ‹
                  </button>
                  <span className="px-4 py-1 text-sm bg-indigo-50 text-indigo-700 rounded font-medium">
                    {contributorPage} / {totalPages}
                  </span>
                  <button
                    onClick={() => setContributorPage(p => Math.min(totalPages, p + 1))}
                    disabled={contributorPage === totalPages}
                    className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    ›
                  </button>
                  <button
                    onClick={() => setContributorPage(totalPages)}
                    disabled={contributorPage === totalPages}
                    className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    »»
                  </button>
                </div>
              )}
            </div>
          );
        })()}

        {/* Top Repositories */}
        {stats.by_repository && stats.by_repository.length > 0 && (() => {
          const totalRepos = stats.by_repository.length;
          const totalRepoPages = Math.ceil(totalRepos / REPOSITORIES_PER_PAGE);
          const repoStartIndex = (repositoryPage - 1) * REPOSITORIES_PER_PAGE;
          const repoEndIndex = repoStartIndex + REPOSITORIES_PER_PAGE;
          const currentPageRepos = stats.by_repository.slice(repoStartIndex, repoEndIndex);

          return (
            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                  <span className="text-2xl">📁</span>
                  Active Repositories
                </h2>
                <span className="text-sm text-gray-500">
                  {totalRepos} repositories
                </span>
              </div>
              <div className="space-y-3">
                {currentPageRepos.map((repo) => {
                  const isExpanded = expandedRepos.has(repo.name);
                  const hasContributors = repo.contributors && repo.contributors.length > 0;

                  return (
                    <div
                      key={repo.name}
                      className="bg-gray-50 rounded-lg overflow-hidden"
                    >
                      {/* Main repo row */}
                      <div
                        className={`flex items-center justify-between p-3 ${
                          hasContributors ? "cursor-pointer hover:bg-gray-100" : ""
                        }`}
                        onClick={() => hasContributors && toggleRepoExpand(repo.name)}
                      >
                        <div className="flex items-center gap-3">
                          {hasContributors && (
                            <span
                              className={`text-gray-400 transition-transform ${
                                isExpanded ? "rotate-90" : ""
                              }`}
                            >
                              ▶
                            </span>
                          )}
                          <span className="text-xl">🐙</span>
                          <div>
                            <a
                              href={`https://github.com/tokamak-network/${repo.name}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="font-medium text-gray-900 hover:text-indigo-600 hover:underline transition-colors"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {repo.name}
                            </a>
                            <p className="text-sm text-gray-500">
                              {repo.commits} commits
                              {hasContributors && (
                                <span className="text-gray-400 ml-2">
                                  · {repo.contributors!.length} contributor{repo.contributors!.length !== 1 ? "s" : ""}
                                </span>
                              )}
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-semibold text-gray-700">
                            {(repo.additions + repo.deletions).toLocaleString()}
                          </p>
                          <p className="text-xs text-gray-500">
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

                      {/* Contributor breakdown (expandable) */}
                      {isExpanded && hasContributors && (
                        <div className="border-t border-gray-200 bg-white">
                          <div className="px-4 py-2 bg-gray-100 text-xs font-semibold text-gray-600 uppercase tracking-wider">
                            Contributors
                          </div>
                          <div className="divide-y divide-gray-100">
                            {repo.contributors!.map((contributor, idx) => (
                              <div
                                key={contributor.github_id}
                                className="flex items-center justify-between px-4 py-2 hover:bg-gray-50"
                              >
                                <div className="flex items-center gap-3">
                                  <span
                                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white ${
                                      idx === 0
                                        ? "bg-yellow-500"
                                        : idx === 1
                                        ? "bg-gray-400"
                                        : idx === 2
                                        ? "bg-orange-400"
                                        : "bg-gray-300"
                                    }`}
                                  >
                                    {idx + 1}
                                  </span>
                                  <div>
                                    <p className="text-sm font-medium text-gray-900">
                                      {contributor.name}
                                    </p>
                                    <p className="text-xs text-gray-500">
                                      @{contributor.github_id} · {contributor.commits} commits
                                    </p>
                                  </div>
                                </div>
                                <div className="text-right">
                                  <p className="text-sm font-semibold text-gray-700">
                                    {(contributor.additions + contributor.deletions).toLocaleString()}
                                  </p>
                                  <p className="text-xs text-gray-500">
                                    <span className="text-emerald-600">
                                      +{contributor.additions.toLocaleString()}
                                    </span>
                                    {" / "}
                                    <span className="text-rose-600">
                                      -{contributor.deletions.toLocaleString()}
                                    </span>
                                  </p>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Pagination */}
              {totalRepoPages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-6 pt-4 border-t border-gray-200">
                  <button
                    onClick={() => setRepositoryPage(1)}
                    disabled={repositoryPage === 1}
                    className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    ««
                  </button>
                  <button
                    onClick={() => setRepositoryPage(p => Math.max(1, p - 1))}
                    disabled={repositoryPage === 1}
                    className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    ‹
                  </button>
                  <span className="px-4 py-1 text-sm bg-indigo-50 text-indigo-700 rounded font-medium">
                    {repositoryPage} / {totalRepoPages}
                  </span>
                  <button
                    onClick={() => setRepositoryPage(p => Math.min(totalRepoPages, p + 1))}
                    disabled={repositoryPage === totalRepoPages}
                    className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    ›
                  </button>
                  <button
                    onClick={() => setRepositoryPage(totalRepoPages)}
                    disabled={repositoryPage === totalRepoPages}
                    className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    »»
                  </button>
                </div>
              )}
            </div>
          );
        })()}
      </div>
    </div>
  );
}
