'use client';

import Link from 'next/link';
import { useAppStats } from '@/hooks/useAppStats';
import { useEffect, useState } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, LineChart, Line, CartesianGrid, AreaChart, Area } from 'recharts';

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

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pie Chart - Activity Distribution */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
            <span className="text-3xl">🥧</span>
            Activity Distribution
          </h2>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={activityData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percentage }) => `${name} (${percentage.toFixed(1)}%)`}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {activityData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Bar Chart - Activities by Source */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
            <span className="text-3xl">📊</span>
            Activities by Source
          </h2>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={activityData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" stroke="#6b7280" />
                <YAxis stroke="#6b7280" />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                  {activityData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
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

      {/* Deep Insights Section: Pulse & Context */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Project Pulse Heatmap */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
            <span className="text-3xl">🔥</span>
            Project Pulse
          </h2>
          <div className="bg-gray-50 rounded-lg p-4 overflow-x-auto">
             <div className="grid grid-rows-7 grid-flow-col gap-1 w-max">
                {(() => {
                   const today = new Date();
                   const trendMap = new Map(stats.daily_trends?.map((d: any) => [d.date, d.github + d.slack + d.notion + d.drive]) || []);
                   
                   // Generate last 20 weeks (approx 140 days)
                   const weeks = 20;
                   const totalDays = weeks * 7;
                   
                   const cells = [];
                   for (let i = 0; i < totalDays; i++) {
                      // Calculate date from (today - totalDays) + i
                      const d = new Date(today);
                      d.setDate(d.getDate() - (totalDays - 1 - i));
                      const dateStr = d.toISOString().split('T')[0];
                      const count = trendMap.get(dateStr) || 0;
                      
                      let colorClass = "bg-gray-200";
                      if (count > 0) colorClass = "bg-green-200";
                      if (count > 5) colorClass = "bg-green-300";
                      if (count > 10) colorClass = "bg-green-400";
                      if (count > 20) colorClass = "bg-green-500";
                      if (count > 40) colorClass = "bg-green-600";
                      
                      cells.push(
                        <div 
                          key={dateStr} 
                          title={`${dateStr}: ${count} activities`}
                          className={`w-3 h-3 rounded-sm ${colorClass} hover:ring-1 ring-gray-400 cursor-pointer transition-colors`}
                        ></div>
                      );
                   }
                   return cells;
                })()}
             </div>
             <div className="flex justify-between items-center mt-2">
                <div className="text-xs text-gray-400">Last 20 weeks</div>
                <div className="flex items-center gap-2 text-xs text-gray-400">
                    <span>Less</span>
                    <div className="w-3 h-3 bg-gray-200 rounded-sm"></div>
                    <div className="w-3 h-3 bg-green-200 rounded-sm"></div>
                    <div className="w-3 h-3 bg-green-400 rounded-sm"></div>
                    <div className="w-3 h-3 bg-green-600 rounded-sm"></div>
                    <span>More</span>
                </div>
             </div>
          </div>
        </div>

        {/* Context Word Cloud */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
            <span className="text-3xl">🧠</span>
            Context Cloud
          </h2>
          <div className="bg-gray-50 rounded-lg p-6 min-h-[160px] flex flex-wrap gap-x-4 gap-y-2 justify-center items-center content-center h-full">
            {stats.top_keywords && stats.top_keywords.length > 0 ? (
                stats.top_keywords.map((kw: any, idx: number) => {
                   const maxVal = Math.max(...(stats.top_keywords?.map((k: any) => k.value) || [1]));
                   const minVal = Math.min(...(stats.top_keywords?.map((k: any) => k.value) || [0]));
                   
                   // Normalize size
                   const normalize = (val: number) => (val - minVal) / (maxVal - minVal || 1);
                   const size = 0.8 + normalize(kw.value) * 1.5; // 0.8rem to 2.3rem
                   
                   // Color intensity based on value
                   // e.g. from Slate-500 to Blue-600
                   const opacity = 0.5 + normalize(kw.value) * 0.5;
                   
                   return (
                      <span 
                        key={idx}
                        className="font-medium hover:text-blue-600 hover:scale-110 transition-all cursor-default"
                        style={{ 
                            fontSize: `${size}rem`, 
                            opacity,
                            color: `rgba(31, 41, 55, ${opacity + 0.2})` 
                        }}
                        title={`${kw.text}: ${kw.value} occurrences`}
                      >
                        {kw.text}
                      </span>
                   );
                })
            ) : (
                <div className="flex flex-col items-center justify-center text-gray-400 text-center">
                    <span className="text-2xl mb-2">☁️</span>
                   <span>Gathering context data...</span>
                   <span className="text-xs mt-1">Check back after data collection</span>
                </div>
            )}
          </div>
        </div>

      </div>

      {/* Database Overview */}
      <div className="bg-gradient-to-br from-indigo-50 to-purple-50 rounded-xl shadow-lg p-6 border-2 border-indigo-200">
        <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <span className="text-3xl">🗄️</span>
          Database Overview
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-lg p-6 shadow-md hover:shadow-xl transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className="text-4xl">📚</div>
              <div className="text-indigo-600 bg-indigo-100 rounded-full p-2">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z" />
                </svg>
              </div>
            </div>
            <div className="text-sm font-medium text-gray-600 mb-2">Total Collections</div>
            <div className="text-4xl font-bold text-indigo-900">
              {stats.database.total_collections}
            </div>
          </div>
          
          <div className="bg-white rounded-lg p-6 shadow-md hover:shadow-xl transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className="text-4xl">📄</div>
              <div className="text-pink-600 bg-pink-100 rounded-full p-2">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
            </div>
            <div className="text-sm font-medium text-gray-600 mb-2">Total Documents</div>
            <div className="text-4xl font-bold text-pink-900">
              {stats.database.total_documents.toLocaleString()}
            </div>
          </div>
          
          <div className="bg-white rounded-lg p-6 shadow-md hover:shadow-xl transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className="text-4xl">📊</div>
              <div className="text-teal-600 bg-teal-100 rounded-full p-2">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
            </div>
            <div className="text-sm font-medium text-gray-600 mb-2">Avg Docs/Collection</div>
            <div className="text-4xl font-bold text-teal-900">
              {Math.round(stats.database.total_documents / stats.database.total_collections).toLocaleString()}
            </div>
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
