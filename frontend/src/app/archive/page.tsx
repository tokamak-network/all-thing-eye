"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  ArchiveBoxIcon,
  MagnifyingGlassIcon,
  UserGroupIcon,
  DocumentTextIcon,
  VideoCameraIcon,
} from "@heroicons/react/24/outline";
import { useArchiveStats, useArchiveMembers } from "@/graphql/archive";
import type { ArchiveMember } from "@/graphql/types";

export default function ArchivePage() {
  const router = useRouter();

  const [q, setQ] = useState("");
  const [era, setEra] = useState("");
  const [team, setTeam] = useState("");

  // Debounce search: only pass q when non-empty
  const queryVars = useMemo(
    () => ({
      q: q.trim() || undefined,
      era: era || undefined,
      team: team || undefined,
      limit: 200,
    }),
    [q, era, team]
  );

  const { data: statsData, loading: statsLoading } = useArchiveStats();
  const { data, loading, error } = useArchiveMembers(queryVars);

  const members: ArchiveMember[] = data?.archiveMembers || [];
  const stats = statsData?.archiveStats;

  // Derive unique eras and teams from loaded members for filter dropdowns
  const eras = useMemo(() => {
    const allEras = data?.archiveMembers
      .map((m) => m.activeEra)
      .filter((e): e is string => Boolean(e));
    return Array.from(new Set(allEras)).sort();
  }, [data]);

  const teams = useMemo(() => {
    const allTeams = data?.archiveMembers
      .flatMap((m) => m.vaultTeams)
      .filter((t): t is string => Boolean(t));
    return Array.from(new Set(allTeams)).sort();
  }, [data]);

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
            <ArchiveBoxIcon className="h-8 w-8 text-amber-600" />
            Archive
          </h1>
          <p className="text-gray-600 mt-2">
            Retired members archive — historical activity records
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <div className="bg-white rounded-lg shadow p-5 flex items-center gap-4">
            <UserGroupIcon className="h-10 w-10 text-amber-500 flex-shrink-0" />
            <div>
              <p className="text-sm text-gray-500">Archived Members</p>
              <p className="text-2xl font-bold text-gray-900">
                {statsLoading ? "—" : (stats?.members ?? "—")}
              </p>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-5 flex items-center gap-4">
            <DocumentTextIcon className="h-10 w-10 text-blue-500 flex-shrink-0" />
            <div>
              <p className="text-sm text-gray-500">Artifacts</p>
              <p className="text-2xl font-bold text-gray-900">
                {statsLoading ? "—" : (stats?.artifacts ?? "—")}
              </p>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-5 flex items-center gap-4">
            <VideoCameraIcon className="h-10 w-10 text-purple-500 flex-shrink-0" />
            <div>
              <p className="text-sm text-gray-500">Recordings</p>
              <p className="text-2xl font-bold text-gray-900">
                {statsLoading ? "—" : (stats?.recordings ?? "—")}
              </p>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow p-4 mb-6 flex flex-wrap gap-3 items-center">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px]">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search by name, GitHub, email..."
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
            />
          </div>

          {/* Era filter */}
          <select
            value={era}
            onChange={(e) => setEra(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
          >
            <option value="">All Eras</option>
            {eras.map((e) => (
              <option key={e} value={e}>
                {e}
              </option>
            ))}
          </select>

          {/* Team filter */}
          <select
            value={team}
            onChange={(e) => setTeam(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
          >
            <option value="">All Teams</option>
            {teams.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>

          {(q || era || team) && (
            <button
              onClick={() => {
                setQ("");
                setEra("");
                setTeam("");
              }}
              className="px-3 py-2 text-sm text-gray-500 hover:text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Clear
            </button>
          )}
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
            {error.message}
          </div>
        )}

        {/* Members Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Member
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Era
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Teams
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Artifacts
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Meetings
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {loading && members.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-600 mx-auto"></div>
                    <p className="mt-3 text-gray-500 text-sm">Loading archive...</p>
                  </td>
                </tr>
              ) : members.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-6 py-12 text-center text-gray-500 text-sm"
                  >
                    No archived members found.
                  </td>
                </tr>
              ) : (
                members.map((member) => (
                  <tr
                    key={member.memberKey}
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() =>
                      router.push(`/archive/${member.memberKey}`)
                    }
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <button className="text-sm font-medium text-amber-700 hover:text-amber-900 hover:underline text-left">
                          {member.memberName}
                        </button>
                        {member.realNameKr && (
                          <p className="text-xs text-gray-500 mt-0.5">
                            {member.realNameKr}
                          </p>
                        )}
                        {member.githubUsername && (
                          <p className="text-xs text-gray-400 mt-0.5 font-mono">
                            @{member.githubUsername}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {member.activeEra ? (
                        <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-amber-100 text-amber-800">
                          {member.activeEra}
                        </span>
                      ) : (
                        <span className="text-sm text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {member.vaultTeams.length > 0 ? (
                          member.vaultTeams.map((t) => (
                            <span
                              key={t}
                              className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-700"
                            >
                              {t}
                            </span>
                          ))
                        ) : (
                          <span className="text-sm text-gray-400">—</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                      {member.artifactCount ?? "—"}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                      {member.meetingCount ?? "—"}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {member.status ? (
                        <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-600">
                          {member.status}
                        </span>
                      ) : (
                        <span className="text-sm text-gray-400">—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Row count */}
        {!loading && members.length > 0 && (
          <div className="mt-4 text-sm text-gray-600">
            {members.length} member{members.length !== 1 ? "s" : ""}
          </div>
        )}
      </div>
    </div>
  );
}
