'use client';

import { useState, useEffect } from 'react';
import { useAccount } from 'wagmi';
import { useRouter } from 'next/navigation';
import { 
  ShieldCheckIcon, 
  ArrowPathIcon, 
  FolderIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline';

// Admin wallet address (case-insensitive comparison)
const ADMIN_ADDRESS = '0xF9Fa94D45C49e879E46Ea783fc133F41709f3bc7'.toLowerCase();

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface SyncResult {
  project_key: string;
  action: string;
  discovered: number;
  new_reports_added: number;
  total_reports: number;
  reports: Array<{ year: number; quarter: number; title: string }>;
}

interface ProjectSyncStatus {
  project_key: string;
  status: 'idle' | 'syncing' | 'success' | 'error';
  result?: SyncResult;
  error?: string;
}

const PROJECTS = [
  { key: 'project-ooo', name: 'Ooo (zk-EVM)', color: 'bg-purple-500' },
  { key: 'project-eco', name: 'ECO (L2 Economics)', color: 'bg-green-500' },
  { key: 'project-syb', name: 'SYB (Sybil)', color: 'bg-blue-500' },
  { key: 'project-trh', name: 'TRH', color: 'bg-orange-500' },
];

export default function AdminPage() {
  const { address, isConnected } = useAccount();
  const router = useRouter();
  const [isAdmin, setIsAdmin] = useState(false);
  const [isChecking, setIsChecking] = useState(true);
  const [syncStatuses, setSyncStatuses] = useState<Record<string, ProjectSyncStatus>>({});
  const [isSyncingAll, setIsSyncingAll] = useState(false);

  // Check admin access
  useEffect(() => {
    if (!isConnected) {
      setIsChecking(false);
      return;
    }

    const checkAdmin = address?.toLowerCase() === ADMIN_ADDRESS;
    setIsAdmin(checkAdmin);
    setIsChecking(false);

    // Initialize sync statuses
    const initialStatuses: Record<string, ProjectSyncStatus> = {};
    PROJECTS.forEach(p => {
      initialStatuses[p.key] = { project_key: p.key, status: 'idle' };
    });
    setSyncStatuses(initialStatuses);
  }, [address, isConnected]);

  // Sync single project
  const syncProject = async (projectKey: string, replaceExisting: boolean = false) => {
    setSyncStatuses(prev => ({
      ...prev,
      [projectKey]: { ...prev[projectKey], status: 'syncing' }
    }));

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/projects-management/projects/${projectKey}/grant-reports/sync?replace_existing=${replaceExisting}`,
        { method: 'POST' }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result: SyncResult = await response.json();
      setSyncStatuses(prev => ({
        ...prev,
        [projectKey]: { project_key: projectKey, status: 'success', result }
      }));
    } catch (error) {
      setSyncStatuses(prev => ({
        ...prev,
        [projectKey]: { 
          project_key: projectKey, 
          status: 'error', 
          error: error instanceof Error ? error.message : 'Unknown error' 
        }
      }));
    }
  };

  // Sync all projects
  const syncAllProjects = async (replaceExisting: boolean = false) => {
    setIsSyncingAll(true);
    
    for (const project of PROJECTS) {
      await syncProject(project.key, replaceExisting);
    }
    
    setIsSyncingAll(false);
  };

  // Loading state
  if (isChecking) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
          <p className="mt-4 text-gray-600">Verifying admin access...</p>
        </div>
      </div>
    );
  }

  // Not connected
  if (!isConnected) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md">
          <ExclamationTriangleIcon className="h-16 w-16 text-yellow-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Wallet Not Connected</h1>
          <p className="text-gray-600 mb-6">Please connect your wallet to access the admin panel.</p>
          <button
            onClick={() => router.push('/login')}
            className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition"
          >
            Go to Login
          </button>
        </div>
      </div>
    );
  }

  // Not admin
  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md">
          <XCircleIcon className="h-16 w-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Access Denied</h1>
          <p className="text-gray-600 mb-4">This page is restricted to admin users only.</p>
          <p className="text-sm text-gray-400 font-mono break-all">
            Connected: {address}
          </p>
          <button
            onClick={() => router.push('/')}
            className="mt-6 px-6 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition"
          >
            Go to Home
          </button>
        </div>
      </div>
    );
  }

  // Admin panel
  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <ShieldCheckIcon className="h-8 w-8 text-green-600" />
            <h1 className="text-2xl font-bold text-gray-900">Admin Panel</h1>
          </div>
          <p className="text-sm text-gray-500">
            Connected as admin: <span className="font-mono">{address}</span>
          </p>
        </div>

        {/* Grant Reports Sync Section */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="flex items-center gap-2 mb-6">
            <FolderIcon className="h-6 w-6 text-primary-600" />
            <h2 className="text-xl font-semibold text-gray-900">Grant Reports Sync</h2>
          </div>
          
          <p className="text-gray-600 mb-6">
            Automatically discover and sync grant report PDFs from Google Drive.
            This will search for quarterly reports matching each project&apos;s naming pattern.
          </p>

          {/* Sync All Button */}
          <div className="flex gap-3 mb-8">
            <button
              onClick={() => syncAllProjects(false)}
              disabled={isSyncingAll}
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              <ArrowPathIcon className={`h-5 w-5 ${isSyncingAll ? 'animate-spin' : ''}`} />
              {isSyncingAll ? 'Syncing...' : 'Sync All (Add New)'}
            </button>
            <button
              onClick={() => syncAllProjects(true)}
              disabled={isSyncingAll}
              className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              <ArrowPathIcon className={`h-5 w-5 ${isSyncingAll ? 'animate-spin' : ''}`} />
              {isSyncingAll ? 'Syncing...' : 'Sync All (Replace)'}
            </button>
          </div>

          {/* Project Cards */}
          <div className="space-y-4">
            {PROJECTS.map((project) => {
              const status = syncStatuses[project.key];
              return (
                <div
                  key={project.key}
                  className="border border-gray-200 rounded-lg p-4"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className={`w-3 h-3 rounded-full ${project.color}`} />
                      <h3 className="font-medium text-gray-900">{project.name}</h3>
                      <span className="text-sm text-gray-400 font-mono">{project.key}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {/* Status indicator */}
                      {status?.status === 'syncing' && (
                        <span className="flex items-center gap-1 text-sm text-blue-600">
                          <ArrowPathIcon className="h-4 w-4 animate-spin" />
                          Syncing...
                        </span>
                      )}
                      {status?.status === 'success' && (
                        <span className="flex items-center gap-1 text-sm text-green-600">
                          <CheckCircleIcon className="h-4 w-4" />
                          {status.result?.new_reports_added} new, {status.result?.total_reports} total
                        </span>
                      )}
                      {status?.status === 'error' && (
                        <span className="flex items-center gap-1 text-sm text-red-600">
                          <XCircleIcon className="h-4 w-4" />
                          {status.error}
                        </span>
                      )}
                      
                      {/* Action buttons */}
                      <button
                        onClick={() => syncProject(project.key, false)}
                        disabled={status?.status === 'syncing' || isSyncingAll}
                        className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition"
                      >
                        Add New
                      </button>
                      <button
                        onClick={() => syncProject(project.key, true)}
                        disabled={status?.status === 'syncing' || isSyncingAll}
                        className="px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200 disabled:opacity-50 disabled:cursor-not-allowed transition"
                      >
                        Replace All
                      </button>
                    </div>
                  </div>
                  
                  {/* Sync result details */}
                  {status?.status === 'success' && status.result && status.result.reports.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <p className="text-xs text-gray-500 mb-2">
                        Discovered {status.result.discovered} reports:
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {status.result.reports.map((r, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-1 text-xs bg-gray-100 rounded text-gray-600"
                          >
                            {r.year} Q{r.quarter}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 text-center text-sm text-gray-400">
          <p>Admin functions are restricted to authorized wallet addresses only.</p>
        </div>
      </div>
    </div>
  );
}
