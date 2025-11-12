'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';

interface TablesData {
  sources: Record<string, string[]>;
  total_sources: number;
  total_tables: number;
}

export default function ExportsPage() {
  const [tables, setTables] = useState<TablesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedSource, setSelectedSource] = useState<string>('');
  const [selectedTable, setSelectedTable] = useState<string>('');
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTables();
  }, []);

  const loadTables = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.get<TablesData>('/exports/tables');
      setTables(data);
      
      // Auto-select first source and table
      if (data.sources && Object.keys(data.sources).length > 0) {
        const firstSource = Object.keys(data.sources)[0];
        setSelectedSource(firstSource);
        if (data.sources[firstSource].length > 0) {
          setSelectedTable(data.sources[firstSource][0]);
        }
      }
    } catch (err) {
      console.error('Failed to load tables:', err);
      setError('Failed to load table list. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!selectedSource || !selectedTable) {
      alert('Please select both source and table');
      return;
    }

    try {
      setDownloading(true);
      setError(null);
      
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const url = `${apiUrl}/api/v1/exports/tables/${selectedSource}/${selectedTable}/csv`;
      
      // Create a temporary link to trigger download
      const link = document.createElement('a');
      link.href = url;
      link.download = `${selectedSource}_${selectedTable}_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
    } catch (err) {
      console.error('Download failed:', err);
      setError('Failed to download CSV. Please try again.');
    } finally {
      setDownloading(false);
    }
  };

  const handleSourceChange = (source: string) => {
    setSelectedSource(source);
    // Auto-select first table of new source
    if (tables && tables.sources[source] && tables.sources[source].length > 0) {
      setSelectedTable(tables.sources[source][0]);
    } else {
      setSelectedTable('');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl font-bold text-gray-900 mb-8">Export Tables</h1>
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading tables...</p>
          </div>
        </div>
      </div>
    );
  }

  if (!tables) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl font-bold text-gray-900 mb-8">Export Tables</h1>
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">Failed to load tables. Please refresh the page.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Export Tables</h1>
          <p className="text-gray-600">
            Download any table as CSV for analysis or backup
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-3xl font-bold text-blue-600">{tables.total_sources}</div>
            <div className="text-sm text-gray-600 mt-1">Data Sources</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-3xl font-bold text-green-600">{tables.total_tables}</div>
            <div className="text-sm text-gray-600 mt-1">Total Tables</div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {/* Selection Form */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Select Table to Export</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Source Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Data Source
              </label>
              <select
                value={selectedSource}
                onChange={(e) => handleSourceChange(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {Object.keys(tables.sources).map((source) => (
                  <option key={source} value={source}>
                    {source} ({tables.sources[source].length} tables)
                  </option>
                ))}
              </select>
            </div>

            {/* Table Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Table Name
              </label>
              <select
                value={selectedTable}
                onChange={(e) => setSelectedTable(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={!selectedSource || !tables.sources[selectedSource] || tables.sources[selectedSource].length === 0}
              >
                {selectedSource && tables.sources[selectedSource]?.map((table) => (
                  <option key={table} value={table}>
                    {table}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Download Button */}
          <div className="mt-6 flex items-center justify-between">
            <div className="text-sm text-gray-600">
              {selectedSource && selectedTable && (
                <span>
                  Selected: <span className="font-medium">{selectedSource}.{selectedTable}</span>
                </span>
              )}
            </div>
            <button
              onClick={handleDownload}
              disabled={!selectedSource || !selectedTable || downloading}
              className={`px-6 py-2 rounded-md font-medium transition-colors ${
                downloading || !selectedSource || !selectedTable
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              {downloading ? (
                <span className="flex items-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Downloading...
                </span>
              ) : (
                <>📥 Download CSV</>
              )}
            </button>
          </div>
        </div>

        {/* Table List by Source */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Available Tables</h2>
          
          <div className="space-y-4">
            {Object.entries(tables.sources).map(([source, tableList]) => (
              <div key={source} className="border border-gray-200 rounded-lg p-4">
                <h3 className="font-medium text-gray-900 mb-2">
                  📂 {source} <span className="text-sm text-gray-500">({tableList.length} tables)</span>
                </h3>
                <div className="flex flex-wrap gap-2">
                  {tableList.map((table) => (
                    <button
                      key={table}
                      onClick={() => {
                        setSelectedSource(source);
                        setSelectedTable(table);
                        window.scrollTo({ top: 0, behavior: 'smooth' });
                      }}
                      className="px-3 py-1 bg-gray-100 hover:bg-blue-100 text-gray-700 hover:text-blue-700 rounded text-sm transition-colors"
                    >
                      {table}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Info Box */}
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-medium text-blue-900 mb-2">💡 Usage Tips</h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• CSV files can be opened in Excel, Google Sheets, or any spreadsheet application</li>
            <li>• Large tables may take a few seconds to download</li>
            <li>• Downloaded files include a timestamp in the filename</li>
            <li>• All data is exported as-is from the database</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

