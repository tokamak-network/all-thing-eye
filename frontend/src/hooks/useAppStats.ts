/**
 * Unified App Statistics Hook
 * 
 * Provides consistent statistics data across all pages.
 * This ensures Dashboard and Database Viewer show identical numbers.
 */

import { useState, useEffect } from 'react';
import api from '@/lib/api';

export interface AppStats {
  // Main statistics
  total_members: number;
  total_activities: number;
  active_projects: number;
  data_sources: number;
  
  // Activity breakdown by source
  activity_summary: {
    [source: string]: {
      total_activities: number;
      activity_types: {
        [type: string]: number;
      };
    };
  };
  
  // Daily activity trends (Recent 30 days)
  daily_trends?: Array<{
    date: string;
    github: number;
    slack: number;
    notion: number;
    drive: number;
  }>;

  // Recent critical events
  recent_events?: Array<{
    source: string;
    type: string;
    title: string;
    user: string;
    time: string;
    url?: string;
    meta?: string;
  }>;
  
  // Database information
  database: {
    total_collections: number;
    total_documents: number;
    collections: Array<{
      name: string;
      count: number;
      database: string;
    }>;
  };
  
  // Last collection times
  last_collected: {
    [source: string]: string | null;
  };
  
  // Metadata
  generated_at: string;
}

interface UseAppStatsResult {
  stats: AppStats | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch unified app statistics
 * 
 * Usage:
 * ```tsx
 * const { stats, loading, error, refetch } = useAppStats();
 * 
 * if (loading) return <Spinner />;
 * if (error) return <Error message={error} />;
 * 
 * return <div>Total Activities: {stats.total_activities}</div>;
 * ```
 */
export function useAppStats(): UseAppStatsResult {
  const [stats, setStats] = useState<AppStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getAppStats();
      setStats(data);
    } catch (err: any) {
      console.error('Failed to fetch app stats:', err);
      setError(err.message || 'Failed to fetch statistics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  return {
    stats,
    loading,
    error,
    refetch: fetchStats
  };
}

