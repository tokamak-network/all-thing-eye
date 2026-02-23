'use client';

import { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import api from '@/lib/api';

// --- Types ---

interface ExternalProject {
  owner: string;
  repo: string;
  full_name: string;
  display_name: string;
  category: string;
  is_active: boolean;
  stars: number;
  language: string | null;
  description: string;
}

interface InternalRepo {
  name: string;
  description: string | null;
  url: string;
  pushed_at: string;
}

interface ProjectCoverage {
  has_data: boolean;
  data_points: number;
  earliest: string | null;
  latest: string | null;
  is_external: boolean;
  needs_backfill: boolean;
}

interface ComparisonData {
  projects: string[];
  metric: string;
  start_date: string;
  end_date: string;
  granularity: string;
  summaries: Record<string, {
    total_commits: number;
    total_additions: number;
    total_deletions: number;
    total_prs_opened: number;
    total_prs_merged: number;
    total_issues_opened: number;
    total_issues_closed: number;
    avg_contributors: number;
    data_points: number;
  }>;
  chart_data: Record<string, any>[];
  coverage: Record<string, ProjectCoverage>;
}

// --- Constants ---

const DATE_PRESETS = [
  { label: '7 Days', days: 7 },
  { label: '14 Days', days: 14 },
  { label: '30 Days', days: 30 },
  { label: '90 Days', days: 90 },
];

const COLORS = [
  '#6366f1', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#06b6d4', '#84cc16',
];

function formatDate(d: Date): string {
  return d.toISOString().split('T')[0];
}

function displayRef(ref: string): string {
  if (ref.startsWith('internal:')) return ref.replace('internal:', '');
  return ref;
}

const LS_KEY_INTERNAL_REPOS = 'benchmarks:savedInternalRepos';

function loadSavedInternalRepos(): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const stored = localStorage.getItem(LS_KEY_INTERNAL_REPOS);
    return stored ? JSON.parse(stored) : [];
  } catch { return []; }
}

function saveSavedInternalRepos(repos: string[]) {
  try { localStorage.setItem(LS_KEY_INTERNAL_REPOS, JSON.stringify(repos)); } catch {}
}

// --- Component ---

export default function BenchmarksView() {
  const [externalProjects, setExternalProjects] = useState<ExternalProject[]>([]);
  const [selectedProjects, setSelectedProjects] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState(30);
  const [comparisonData, setComparisonData] = useState<ComparisonData | null>(null);
  const [loading, setLoading] = useState(false);
  const [projectsLoading, setProjectsLoading] = useState(true);

  const [savedInternalRepos, setSavedInternalRepos] = useState<string[]>([]);

  useEffect(() => {
    setSavedInternalRepos(loadSavedInternalRepos());
  }, []);

  const [repoSearch, setRepoSearch] = useState('');
  const [repoResults, setRepoResults] = useState<InternalRepo[]>([]);
  const [repoSearching, setRepoSearching] = useState(false);
  const [showRepoDropdown, setShowRepoDropdown] = useState(false);
  const repoSearchRef = useRef<HTMLDivElement>(null);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout>>();

  const selectedInternalRepos = useMemo(
    () => selectedProjects.filter(p => p.startsWith('internal:')).map(p => p.replace('internal:', '')),
    [selectedProjects]
  );

  const [backfilling, setBackfilling] = useState(false);
  const [backfillProjects, setBackfillProjects] = useState<string[]>([]);

  const [newRepoInput, setNewRepoInput] = useState('');
  const [addingProject, setAddingProject] = useState(false);
  const [addError, setAddError] = useState('');

  const { startDate, endDate } = useMemo(() => {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - dateRange);
    return { startDate: formatDate(start), endDate: formatDate(end) };
  }, [dateRange]);

  useEffect(() => {
    (async () => {
      setProjectsLoading(true);
      try {
        const res = await api.getExternalProjects();
        setExternalProjects(res.projects || []);
      } catch (e) {
        console.error('Failed to load external projects:', e);
      } finally {
        setProjectsLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (repoSearchRef.current && !repoSearchRef.current.contains(e.target as Node)) {
        setShowRepoDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  useEffect(() => {
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    if (!repoSearch.trim()) {
      setRepoResults([]);
      return;
    }
    searchTimerRef.current = setTimeout(async () => {
      setRepoSearching(true);
      try {
        const res = await api.searchInternalRepos(repoSearch, 15);
        setRepoResults(res.repos || []);
      } catch (e) {
        console.error('Repo search failed:', e);
      } finally {
        setRepoSearching(false);
      }
    }, 300);
    return () => { if (searchTimerRef.current) clearTimeout(searchTimerRef.current); };
  }, [repoSearch]);

  const loadComparison = useCallback(async () => {
    if (selectedProjects.length === 0) {
      setComparisonData(null);
      return;
    }
    setLoading(true);
    try {
      const data = await api.getBenchmarkComparison({
        projects: selectedProjects.join(','),
        start_date: startDate,
        end_date: endDate,
      });

      const needsBackfill = Object.entries(data.coverage || {})
        .filter(([, cov]: [string, any]) => cov.needs_backfill)
        .map(([ref]: [string, any]) => ref);

      if (needsBackfill.length > 0) {
        setComparisonData(data);
        setBackfilling(true);
        setBackfillProjects(needsBackfill);
        try {
          await api.backfillBenchmarkData(needsBackfill, startDate, endDate);
          const refreshed = await api.getBenchmarkComparison({
            projects: selectedProjects.join(','),
            start_date: startDate,
            end_date: endDate,
          });
          setComparisonData(refreshed);
        } catch (e) {
          console.error('Backfill failed:', e);
        } finally {
          setBackfilling(false);
          setBackfillProjects([]);
        }
      } else {
        setComparisonData(data);
      }
    } catch (e) {
      console.error('Failed to load comparison:', e);
    } finally {
      setLoading(false);
    }
  }, [selectedProjects, startDate, endDate]);

  useEffect(() => {
    loadComparison();
  }, [loadComparison]);

  const toggleProject = (ref: string) => {
    setSelectedProjects(prev =>
      prev.includes(ref) ? prev.filter(p => p !== ref) : [...prev, ref]
    );
  };

  const selectInternalRepo = (repoName: string) => {
    const ref = `internal:${repoName}`;
    if (!selectedProjects.includes(ref)) {
      setSelectedProjects(prev => [...prev, ref]);
    }
    setSavedInternalRepos(prev => {
      if (prev.includes(repoName)) return prev;
      const updated = [...prev, repoName];
      saveSavedInternalRepos(updated);
      return updated;
    });
    setRepoSearch('');
    setShowRepoDropdown(false);
  };

  const removeInternalRepo = (repoName: string) => {
    setSelectedProjects(prev => prev.filter(p => p !== `internal:${repoName}`));
  };

  const deleteSavedInternalRepo = (repoName: string) => {
    setSavedInternalRepos(prev => {
      const updated = prev.filter(n => n !== repoName);
      saveSavedInternalRepos(updated);
      return updated;
    });
    setSelectedProjects(prev => prev.filter(p => p !== `internal:${repoName}`));
  };

  const handleAddProject = async () => {
    const input = newRepoInput.trim();
    if (!input) return;
    let owner: string, repo: string;
    const urlMatch = input.match(/github\.com\/([^/]+)\/([^/\s]+)/);
    if (urlMatch) {
      owner = urlMatch[1];
      repo = urlMatch[2].replace(/\.git$/, '');
    } else if (input.includes('/')) {
      [owner, repo] = input.split('/');
    } else {
      setAddError('Format: owner/repo or GitHub URL');
      return;
    }
    setAddingProject(true);
    setAddError('');
    try {
      await api.addExternalProject(owner, repo);
      setNewRepoInput('');
      const res = await api.getExternalProjects();
      setExternalProjects(res.projects || []);
    } catch (e: any) {
      setAddError(e.response?.data?.detail || 'Failed to add project');
    } finally {
      setAddingProject(false);
    }
  };

  const handleRemoveProject = async (fullName: string) => {
    if (!confirm(`Remove ${fullName} and all its benchmark data?`)) return;
    try {
      await api.removeExternalProject(fullName);
      setSelectedProjects(prev => prev.filter(p => p !== fullName));
      const res = await api.getExternalProjects();
      setExternalProjects(res.projects || []);
    } catch (e) {
      console.error('Failed to remove project:', e);
    }
  };

  const projectColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    selectedProjects.forEach((ref, i) => {
      map[ref] = COLORS[i % COLORS.length];
    });
    return map;
  }, [selectedProjects]);

  return (
    <div>
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left sidebar - Project Selection */}
        <div className="lg:col-span-1 space-y-4">

          {/* Internal Repos */}
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
              Internal Repos
            </h3>

            {savedInternalRepos.length > 0 && (
              <div className="space-y-1 mb-3">
                {savedInternalRepos.map(name => {
                  const ref = `internal:${name}`;
                  const isChecked = selectedProjects.includes(ref);
                  return (
                    <div key={name} className="flex items-center gap-2 p-2 rounded hover:bg-gray-50">
                      <label className="flex items-center gap-2 cursor-pointer flex-1 min-w-0">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleProject(ref)}
                          className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span className="text-sm font-medium text-gray-900 truncate">{name}</span>
                      </label>
                      {isChecked && (
                        <div
                          className="w-3 h-3 rounded-full flex-shrink-0"
                          style={{ backgroundColor: projectColorMap[ref] }}
                        />
                      )}
                      <button
                        onClick={() => deleteSavedInternalRepo(name)}
                        className="text-gray-300 hover:text-red-500 flex-shrink-0"
                        title="Remove from list"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            <div ref={repoSearchRef} className="relative">
              <input
                type="text"
                value={repoSearch}
                onChange={e => { setRepoSearch(e.target.value); setShowRepoDropdown(true); }}
                onFocus={() => repoSearch.trim() && setShowRepoDropdown(true)}
                placeholder="Search to add repo..."
                className="w-full text-sm border border-gray-300 rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
              />
              {repoSearching && (
                <div className="absolute right-2 top-2">
                  <div className="animate-spin h-4 w-4 border-2 border-indigo-500 border-t-transparent rounded-full" />
                </div>
              )}

              {showRepoDropdown && repoSearch.trim() && (
                <div className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-md shadow-lg max-h-60 overflow-y-auto">
                  {repoResults.length === 0 && !repoSearching ? (
                    <div className="px-3 py-2 text-sm text-gray-400">No repos found</div>
                  ) : (
                    repoResults.map(repo => {
                      const isSaved = savedInternalRepos.includes(repo.name);
                      return (
                        <button
                          key={repo.name}
                          onClick={() => selectInternalRepo(repo.name)}
                          disabled={isSaved}
                          className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 border-b border-gray-50 last:border-0 ${
                            isSaved ? 'opacity-50 cursor-not-allowed bg-gray-50' : ''
                          }`}
                        >
                          <div className="font-medium text-gray-900">
                            {repo.name}
                            {isSaved && <span className="ml-1 text-indigo-500 text-xs">(added)</span>}
                          </div>
                          {repo.description && (
                            <div className="text-xs text-gray-400 truncate">{repo.description}</div>
                          )}
                        </button>
                      );
                    })
                  )}
                </div>
              )}
            </div>
          </div>

          {/* External Projects */}
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
              External Projects
            </h3>
            {projectsLoading ? (
              <div className="animate-pulse space-y-2">
                {[1, 2].map(i => (
                  <div key={i} className="h-8 bg-gray-100 rounded" />
                ))}
              </div>
            ) : externalProjects.length === 0 ? (
              <p className="text-sm text-gray-400 mb-3">No external projects yet</p>
            ) : (
              <div className="space-y-1 mb-3">
                {externalProjects.map(p => (
                  <div key={p.full_name} className="flex items-center gap-2 p-2 rounded hover:bg-gray-50">
                    <label className="flex items-center gap-2 cursor-pointer flex-1 min-w-0">
                      <input
                        type="checkbox"
                        checked={selectedProjects.includes(p.full_name)}
                        onChange={() => toggleProject(p.full_name)}
                        className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-gray-900 truncate">
                          {p.display_name}
                        </div>
                        <div className="text-xs text-gray-400">
                          {p.full_name} {p.stars ? `| ${p.stars.toLocaleString()} stars` : ''}
                        </div>
                      </div>
                    </label>
                    {selectedProjects.includes(p.full_name) && (
                      <div
                        className="w-3 h-3 rounded-full flex-shrink-0"
                        style={{ backgroundColor: projectColorMap[p.full_name] }}
                      />
                    )}
                    <button
                      onClick={() => handleRemoveProject(p.full_name)}
                      className="text-gray-300 hover:text-red-500 flex-shrink-0"
                      title="Remove project"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Add project form */}
            <div className="border-t pt-3">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newRepoInput}
                  onChange={e => { setNewRepoInput(e.target.value); setAddError(''); }}
                  onKeyDown={e => e.key === 'Enter' && !addingProject && handleAddProject()}
                  placeholder="owner/repo"
                  disabled={addingProject}
                  className="flex-1 min-w-0 text-sm border border-gray-300 rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 disabled:bg-gray-50"
                />
                <button
                  onClick={handleAddProject}
                  disabled={addingProject || !newRepoInput.trim()}
                  className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
                >
                  {addingProject ? (
                    <div className="flex items-center gap-1.5">
                      <div className="animate-spin h-3.5 w-3.5 border-2 border-white border-t-transparent rounded-full" />
                    </div>
                  ) : 'Add'}
                </button>
              </div>
              {addingProject && (
                <p className="mt-1.5 text-xs text-indigo-600 flex items-center gap-1">
                  <span className="animate-spin h-3 w-3 border-2 border-indigo-600 border-t-transparent rounded-full flex-shrink-0" />
                  Collecting 30 days of data...
                </p>
              )}
              {addError && (
                <p className="mt-1 text-xs text-red-500">{addError}</p>
              )}
            </div>
          </div>
        </div>

        {/* Main content */}
        <div className="lg:col-span-3 space-y-6">
          {/* Date range */}
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-500">Period:</span>
              <div className="flex gap-1">
                {DATE_PRESETS.map(p => (
                  <button
                    key={p.days}
                    onClick={() => setDateRange(p.days)}
                    className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                      dateRange === p.days
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <span className="text-xs text-gray-400 ml-auto">
                {startDate} ~ {endDate}
              </span>
            </div>
          </div>

          {/* Comparison Table */}
          {selectedProjects.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-12 text-center">
              <div className="text-gray-400 mb-2">
                <svg className="w-12 h-12 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <p className="text-gray-500 text-sm">
                Search and select repos from the sidebar to start comparing
              </p>
            </div>
          ) : loading ? (
            <div className="bg-white rounded-lg shadow p-12 flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
            </div>
          ) : comparisonData && Object.keys(comparisonData.summaries).length > 0 ? (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead>
                    <tr className="bg-gray-50">
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider sticky left-0 bg-gray-50 z-10">
                        Project
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        Commits
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        Additions
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        Deletions
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        <span title="Opened / Merged">PRs (O/M)</span>
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        <span title="Opened / Closed">Issues (O/C)</span>
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        Avg Contributors
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        Active Days
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-100">
                    {selectedProjects.map((ref, i) => {
                      const s = comparisonData.summaries[ref];
                      if (!s) {
                        const isBackfillingThis = backfilling && backfillProjects.includes(ref);
                        return (
                          <tr key={ref} className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900 sticky left-0 bg-white">
                              <div className="flex items-center gap-2">
                                <div
                                  className="w-3 h-3 rounded-full flex-shrink-0"
                                  style={{ backgroundColor: COLORS[i % COLORS.length] }}
                                />
                                {displayRef(ref)}
                              </div>
                            </td>
                            <td colSpan={7} className="px-4 py-3 text-sm text-center text-gray-400">
                              {isBackfillingThis ? (
                                <span className="inline-flex items-center gap-2 text-indigo-600">
                                  <span className="animate-spin h-4 w-4 border-2 border-indigo-600 border-t-transparent rounded-full" />
                                  Fetching data from GitHub...
                                </span>
                              ) : (
                                'No data for this period'
                              )}
                            </td>
                          </tr>
                        );
                      }
                      return (
                        <tr key={ref} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900 sticky left-0 bg-white">
                            <div className="flex items-center gap-2">
                              <div
                                className="w-3 h-3 rounded-full flex-shrink-0"
                                style={{ backgroundColor: COLORS[i % COLORS.length] }}
                              />
                              {displayRef(ref)}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-sm text-right font-medium text-gray-900">
                            {s.total_commits.toLocaleString()}
                          </td>
                          <td className="px-4 py-3 text-sm text-right text-green-600 font-medium">
                            +{s.total_additions.toLocaleString()}
                          </td>
                          <td className="px-4 py-3 text-sm text-right text-red-500 font-medium">
                            -{s.total_deletions.toLocaleString()}
                          </td>
                          <td className="px-4 py-3 text-sm text-right text-gray-700">
                            {s.total_prs_opened} / {s.total_prs_merged}
                          </td>
                          <td className="px-4 py-3 text-sm text-right text-gray-700">
                            {s.total_issues_opened} / {s.total_issues_closed}
                          </td>
                          <td className="px-4 py-3 text-sm text-right text-gray-700">
                            {s.avg_contributors}
                          </td>
                          <td className="px-4 py-3 text-sm text-right text-gray-500">
                            {s.data_points}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow p-12 text-center">
              <p className="text-gray-500 text-sm">
                No benchmark data available for the selected period.
                Run the collection script first.
              </p>
              <code className="mt-2 block text-xs text-gray-400">
                python scripts/external_project_collection.py --days 30
              </code>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
