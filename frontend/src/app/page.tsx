'use client';

import Link from 'next/link';
import { useAppStats } from '@/hooks/useAppStats';
import { useEffect, useState } from 'react';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, BarChart, Bar
} from 'recharts';

export default function Home() {
  const { stats, loading, error } = useAppStats();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">Error: {error}</p>
        <p className="text-sm text-red-600 mt-2">
          Make sure the backend API is running at: {process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}
        </p>
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  // Calculate collection categories (matching database page)
  const collectionCategories = new Set<string>();
  stats.database.collections.forEach((col: any) => {
    if (col.name.startsWith('member')) collectionCategories.add('members');
    else if (col.name.startsWith('github')) collectionCategories.add('github');
    else if (col.name.startsWith('slack')) collectionCategories.add('slack');
    else if (col.name.startsWith('notion')) collectionCategories.add('notion');
    else if (col.name.startsWith('drive')) collectionCategories.add('drive');
    else if (col.name.startsWith('gemini.')) collectionCategories.add('gemini');
    else if (col.name.startsWith('shared.')) collectionCategories.add('shared');
    else collectionCategories.add('other');
  });

  // Get most recent collection time from last_collected
  const getMostRecentCollectionTime = () => {
    const times = Object.values(stats.last_collected).filter(t => t !== null) as string[];
    if (times.length === 0) return null;
    
    const dates = times.map(t => new Date(t));
    const mostRecent = new Date(Math.max(...dates.map(d => d.getTime())));
    return mostRecent;
  };

  const mostRecentUpdate = getMostRecentCollectionTime();

  // Calculate percentages for activity sources
  const activityData = Object.entries(stats.activity_summary).map(([source, data]) => ({
    source,
    name: source.charAt(0).toUpperCase() + source.slice(1),
    count: data.total_activities,
    types: Object.keys(data.activity_types).length,
    percentage: (data.total_activities / stats.database.total_documents) * 100,
    value: data.total_activities // for pie chart
  }));

  // Sort by count descending
  activityData.sort((a, b) => b.count - a.count);

  // Get source icons and colors
  const getSourceStyle = (source: string) => {
    const styles: Record<string, { icon: string; color: string; bgColor: string; borderColor: string; chartColor: string }> = {
      github: { icon: '🐙', color: 'text-green-700', bgColor: 'bg-green-50', borderColor: 'border-green-200', chartColor: '#10b981' },
      slack: { icon: '💬', color: 'text-purple-700', bgColor: 'bg-purple-50', borderColor: 'border-purple-200', chartColor: '#8b5cf6' },
      notion: { icon: '📝', color: 'text-orange-700', bgColor: 'bg-orange-50', borderColor: 'border-orange-200', chartColor: '#f97316' },
      drive: { icon: '📁', color: 'text-yellow-700', bgColor: 'bg-yellow-50', borderColor: 'border-yellow-200', chartColor: '#eab308' },
      recordings: { icon: '🎥', color: 'text-red-700', bgColor: 'bg-red-50', borderColor: 'border-red-200', chartColor: '#ef4444' }
    };
    return styles[source] || { icon: '📦', color: 'text-gray-700', bgColor: 'bg-gray-50', borderColor: 'border-gray-200', chartColor: '#6b7280' };
  };

  // Chart colors
  const CHART_COLORS = activityData.map(item => getSourceStyle(item.source).chartColor);

  // Format last collected time
  const formatLastCollected = (isoTime: string | null) => {
    if (!isoTime) return 'Never';
    
    try {
      const date = new Date(isoTime);
      const now = new Date();
      
      // Check if date is valid
      if (isNaN(date.getTime())) {
        return 'Invalid date';
      }
      
      const diffMs = now.getTime() - date.getTime();
      
      // Handle negative differences (future dates)
      if (diffMs < 0) {
        return 'In the future';
      }
      
      const diffSeconds = Math.floor(diffMs / 1000);
      const diffMinutes = Math.floor(diffSeconds / 60);
      const diffHours = Math.floor(diffMinutes / 60);
      const diffDays = Math.floor(diffHours / 24);
      
      if (diffDays > 0) return `${diffDays}d ago`;
      if (diffHours > 0) return `${diffHours}h ago`;
      if (diffMinutes > 0) return `${diffMinutes}m ago`;
      if (diffSeconds > 0) return `${diffSeconds}s ago`;
      
      return 'Just now';
    } catch {
      return 'Unknown';
    }
  };

  const getDataFreshness = (isoTime: string | null) => {
    if (!isoTime) return { status: 'Never', color: 'text-gray-500', bgColor: 'bg-gray-100' };
    
    const date = new Date(isoTime);
    const now = new Date();
    const diffHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);
    
    if (diffHours < 24) return { status: '✓ Fresh', color: 'text-green-600', bgColor: 'bg-green-100' };
    if (diffHours < 48) return { status: '⚠ 1d old', color: 'text-yellow-600', bgColor: 'bg-yellow-100' };
    return { status: '⚠ Stale', color: 'text-red-600', bgColor: 'bg-red-100' };
  };

  const formatTimeAgo = (isoTime: string | null) => {
    if (!isoTime) return 'Never';
    try {
      const date = new Date(isoTime);
      const now = new Date();
      const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

      if (seconds < 60) return `${seconds}s ago`;
      const minutes = Math.floor(seconds / 60);
      if (minutes < 60) return `${minutes}m ago`;
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return `${hours}h ago`;
      const days = Math.floor(hours / 24);
      if (days < 30) return `${days}d ago`;
      const months = Math.floor(days / 30);
      if (months < 12) return `${months}mo ago`;
      const years = Math.floor(months / 12);
      return `${years}y ago`;
    } catch (e) {
      console.error("Error formatting time ago:", e);
      return "Unknown";
    }
  };

  // Custom tooltip for charts
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-3 rounded-lg shadow-lg border border-gray-200">
          <p className="font-semibold text-gray-900">{payload[0].name}</p>
          <p className="text-sm text-gray-600">
            {payload[0].value.toLocaleString()} activities
          </p>
          <p className="text-xs text-gray-500">
            {((payload[0].value / stats.database.total_documents) * 100).toFixed(1)}%
          </p>
        </div>
      );
    }
    return null;
  };

  // Activity type breakdown for selected sources
  const getActivityTypeData = () => {
    const typeData: any[] = [];
    Object.entries(stats.activity_summary).forEach(([source, data]) => {
      Object.entries(data.activity_types).forEach(([type, count]) => {
        typeData.push({
          source: source.charAt(0).toUpperCase() + source.slice(1),
          type: type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
          count: count
        });
      });
    });
    return typeData;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-700 rounded-2xl shadow-2xl p-8 text-white relative overflow-hidden">
        <div className="absolute inset-0 bg-black opacity-10"></div>
        <div className="relative z-10">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-2 flex items-center gap-3">
                <span className="text-5xl">📊</span>
                Dashboard
              </h1>
              <p className="text-blue-100 text-lg">
                Team activity analytics and performance insights
              </p>
            </div>
            {mostRecentUpdate && (
              <div className="bg-white bg-opacity-20 backdrop-blur-sm rounded-lg px-4 py-2">
                <p className="text-blue-100 text-sm">
                  Last updated
                </p>
                <p className="text-white font-semibold">
                  {mostRecentUpdate.toLocaleString()}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Data Freshness */}
      <div className="bg-white rounded-xl shadow-lg p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <span className="text-3xl">⏰</span>
          Data Freshness
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.entries(stats.last_collected).map(([source, time]) => {
            const style = getSourceStyle(source);
            const freshness = getDataFreshness(time);
            return (
              <div
                key={source}
                className={`${style.bgColor} ${style.borderColor} border-2 rounded-lg p-4 hover:shadow-lg transition-shadow`}
              >
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-3xl">{style.icon}</span>
                  <div className="flex-1">
                    <div className="font-bold text-gray-900 capitalize">{source}</div>
                    <div className="text-sm text-gray-600">
                      {formatLastCollected(time)}
                    </div>
                  </div>
                </div>
                <div className={`${freshness.bgColor} ${freshness.color} font-semibold text-sm px-3 py-1 rounded-full text-center`}>
                  {freshness.status}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {/* Total Members */}
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl shadow-lg p-6 text-white transform hover:scale-105 transition-all duration-300 hover:shadow-2xl">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-blue-100 text-sm font-medium mb-1">Total Members</p>
              <p className="text-4xl font-bold">{stats.total_members}</p>
              <p className="text-blue-200 text-xs mt-2">Active team members</p>
            </div>
            <div className="text-6xl opacity-20">👥</div>
          </div>
        </div>

        {/* Total Activities */}
        <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-xl shadow-lg p-6 text-white transform hover:scale-105 transition-all duration-300 hover:shadow-2xl">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-green-100 text-sm font-medium mb-1">Total Activities</p>
              <p className="text-4xl font-bold">{stats.database.total_documents.toLocaleString()}</p>
              <p className="text-green-200 text-xs mt-2">Across all sources</p>
            </div>
            <div className="text-6xl opacity-20">📈</div>
          </div>
        </div>

        {/* Active Projects */}
        <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl shadow-lg p-6 text-white transform hover:scale-105 transition-all duration-300 hover:shadow-2xl">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-purple-100 text-sm font-medium mb-1">Active Projects</p>
              <p className="text-4xl font-bold">{stats.active_projects}</p>
              <p className="text-purple-200 text-xs mt-2">Currently tracked</p>
            </div>
            <div className="text-6xl opacity-20">📁</div>
          </div>
        </div>

        {/* Data Sources */}
        <div className="bg-gradient-to-br from-orange-500 to-orange-600 rounded-xl shadow-lg p-6 text-white transform hover:scale-105 transition-all duration-300 hover:shadow-2xl">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-orange-100 text-sm font-medium mb-1">Data Sources</p>
              <p className="text-4xl font-bold">{collectionCategories.size}</p>
              <p className="text-orange-200 text-xs mt-2">Collection categories</p>
            </div>
            <div className="text-6xl opacity-20">🗄️</div>
          </div>
        </div>
      </div>



      {/* Team Activity Flow (Activity Trends) */}
      <div className="bg-white rounded-xl shadow-lg p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <span className="text-3xl">🌊</span>
          Team Activity Flow
        </h2>
        {stats.daily_trends && stats.daily_trends.length > 0 ? (
          <div className="h-96">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={stats.daily_trends} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorGithub" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#24292e" stopOpacity={0.8}/>
                    <stop offset="95%" stopColor="#24292e" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorSlack" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4A154B" stopOpacity={0.8}/>
                    <stop offset="95%" stopColor="#4A154B" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorNotion" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f97316" stopOpacity={0.8}/>
                    <stop offset="95%" stopColor="#f97316" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorDrive" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0F9D58" stopOpacity={0.8}/>
                    <stop offset="95%" stopColor="#0F9D58" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis 
                  dataKey="date" 
                  tickFormatter={(str) => str.slice(5)} 
                  stroke="#9ca3af"
                  fontSize={12}
                  tickMargin={10}
                />
                <YAxis stroke="#9ca3af" fontSize={12} />
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#fff', borderRadius: '0.5rem', border: '1px solid #e5e7eb', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}
                  itemStyle={{ fontSize: '0.875rem' }}
                  labelStyle={{ fontWeight: 'bold', marginBottom: '0.5rem', color: '#111827' }}
                />
                <Legend wrapperStyle={{ paddingTop: '20px' }} />
                <Area type="monotone" dataKey="github" name="GitHub" stackId="1" stroke="#24292e" fill="url(#colorGithub)" animationDuration={1000} />
                <Area type="monotone" dataKey="slack" name="Slack" stackId="1" stroke="#4A154B" fill="url(#colorSlack)" animationDuration={1000} />
                <Area type="monotone" dataKey="notion" name="Notion" stackId="1" stroke="#f97316" fill="url(#colorNotion)" animationDuration={1000} />
                <Area type="monotone" dataKey="drive" name="Drive" stackId="1" stroke="#0F9D58" fill="url(#colorDrive)" animationDuration={1000} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-80 bg-gray-50 rounded-lg text-gray-400">
            <span className="text-4xl mb-2">📉</span>
            <p>No activity trend data available yet.</p>
            <p className="text-sm mt-1">Collecting data over time...</p>
          </div>
        )}
      </div>

      {/* Distribution & Health Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
           {/* Activity Distribution */}
           <div className="bg-white rounded-xl shadow-lg p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                 <span className="text-2xl">📊</span> Source Distribution
              </h2>
              <div className="h-80">
                 <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={activityData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, percentage }) => percentage > 3 ? `${name} (${percentage.toFixed(1)}%)` : ''}
                        outerRadius={100}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {activityData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip content={<CustomTooltip />} />
                      <Legend />
                    </PieChart>
                 </ResponsiveContainer>
              </div>
           </div>

           {/* System Health */}
           <div className="bg-white rounded-xl shadow-lg p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                 <span className="text-2xl">🏥</span> System Health
              </h2>
              <div className="space-y-4">
                  {[
                     { label: 'GitHub', key: 'github', time: stats.last_collected?.github, icon: '🐙' },
                     { label: 'Slack', key: 'slack', time: stats.last_collected?.slack, icon: '💬' },
                     { label: 'Notion', key: 'notion', time: stats.last_collected?.notion, icon: '📝' },
                     { label: 'Drive', key: 'drive', time: stats.last_collected?.drive, icon: '📁' },
                     { label: 'Database', key: 'database', time: stats.generated_at, icon: '🗄️' },
                  ].map((item, idx) => {
                     if (!item.time) return null;
                     const lastUpdate = new Date(item.time);
                     const now = new Date();
                     const diffHours = (now.getTime() - lastUpdate.getTime()) / (1000 * 60 * 60);
                     const isHealthy = diffHours < 25; // Allocating 1 hour buffer
                     
                     let infoText = '';
                     if (item.key === 'database') {
                        infoText = `Total: ${stats.database.total_documents.toLocaleString()} docs`;
                     } else {
                        // Use total summary instead of daily trend to prevent "0 activities" confusion due to UTC dates
                        const summary = (stats.activity_summary as any)[item.key];
                        const total = summary ? summary.total_activities : 0;
                        infoText = `Total: ${total.toLocaleString()}`;
                     }
                     
                     return (
                        <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                           <div className="flex items-center gap-3">
                              <span className="text-xl">{item.icon}</span>
                              <div>
                                 <div className="font-medium text-gray-900">{item.label}</div>
                                 <div className="text-xs text-gray-500">
                                    {infoText}
                                 </div>
                              </div>
                           </div>
                           <div className={`px-3 py-1 rounded-full text-xs font-medium flex items-center gap-1.5 ${
                              isHealthy ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                           }`}>
                              <div className={`w-2 h-2 rounded-full ${isHealthy ? 'bg-green-500' : 'bg-red-500'} animate-pulse`}></div>
                              {isHealthy ? 'Healthy' : 'Sync Needed'}
                           </div>
                        </div>
                     );
                  })}
              </div>
           </div>
        </div>



      {/* Quick Actions */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        <Link
          href="/members"
          className="group bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl shadow-lg p-6 hover:shadow-2xl transition-all transform hover:-translate-y-2 border-2 border-blue-200 hover:border-blue-400"
        >
          <div className="flex items-center gap-4 mb-3">
            <div className="text-5xl group-hover:scale-110 transition-transform">👥</div>
            <h3 className="text-xl font-bold text-gray-900 group-hover:text-blue-600 transition-colors">
              View Members
            </h3>
          </div>
          <p className="text-gray-600">
            Browse team members and their activity history
          </p>
          <div className="mt-4 flex items-center text-blue-600 font-semibold">
            Explore →
          </div>
        </Link>

        <Link
          href="/activities"
          className="group bg-gradient-to-br from-green-50 to-green-100 rounded-xl shadow-lg p-6 hover:shadow-2xl transition-all transform hover:-translate-y-2 border-2 border-green-200 hover:border-green-400"
        >
          <div className="flex items-center gap-4 mb-3">
            <div className="text-5xl group-hover:scale-110 transition-transform">📊</div>
            <h3 className="text-xl font-bold text-gray-900 group-hover:text-green-600 transition-colors">
              View Activities
            </h3>
          </div>
          <p className="text-gray-600">
            Explore detailed activity logs across all sources
          </p>
          <div className="mt-4 flex items-center text-green-600 font-semibold">
            Explore →
          </div>
        </Link>

        <Link
          href="/database"
          className="group bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl shadow-lg p-6 hover:shadow-2xl transition-all transform hover:-translate-y-2 border-2 border-purple-200 hover:border-purple-400"
        >
          <div className="flex items-center gap-4 mb-3">
            <div className="text-5xl group-hover:scale-110 transition-transform">🗄️</div>
            <h3 className="text-xl font-bold text-gray-900 group-hover:text-purple-600 transition-colors">
              Database Viewer
            </h3>
          </div>
          <p className="text-gray-600">
            Explore MongoDB collections and raw data
          </p>
          <div className="mt-4 flex items-center text-purple-600 font-semibold">
            Explore →
          </div>
        </Link>
      </div>

      {/* Add shimmer animation styles */}
      <style jsx>{`
        @keyframes shimmer {
          0% {
            transform: translateX(-100%);
          }
          100% {
            transform: translateX(100%);
          }
        }
        .animate-shimmer {
          animation: shimmer 2s infinite;
        }
      `}</style>
    </div>
  );
}
