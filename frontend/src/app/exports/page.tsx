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
  const [selectedTables, setSelectedTables] = useState<Set<string>>(new Set());
  const [downloading, setDownloading] = useState(false);
  const [bulkDownloading, setBulkDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTables();
  }, []);

  const loadTables = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getTables() as TablesData;
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
      
      const url = api.getExportTableCsvUrl(selectedSource, selectedTable);
      
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

  const toggleTableSelection = (source: string, table: string) => {
    const key = `${source}:${table}`;
    setSelectedTables((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(key)) {
        newSet.delete(key);
      } else {
        newSet.add(key);
      }
      return newSet;
    });
  };

  const handleBulkDownload = async () => {
    if (selectedTables.size === 0) {
      alert('Please select at least one table');
      return;
    }

    try {
      setBulkDownloading(true);
      setError(null);

      // Convert Set to array of {source, table} objects
      const tablesArray = Array.from(selectedTables).map((key) => {
        const [source, table] = key.split(':');
        return { source, table };
      });

      // Call API
      const blob = await api.exportBulkTables(tablesArray);

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `all_thing_eye_export_${new Date().toISOString().split('T')[0]}.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      // Clear selection after successful download
      setSelectedTables(new Set());
    } catch (err) {
      console.error('Bulk download failed:', err);
      setError('Failed to download ZIP file. Please try again.');
    } finally {
      setBulkDownloading(false);
    }
  };

  const selectAll = () => {
    if (!tables) return;
    const allTables = new Set<string>();
    Object.entries(tables.sources).forEach(([source, tableList]) => {
      tableList.forEach((table) => {
        allTables.add(`${source}:${table}`);
      });
    });
    setSelectedTables(allTables);
  };

  const clearSelection = () => {
    setSelectedTables(new Set());
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

        {/* Bulk Download Section */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Bulk Download (ZIP)</h2>
              <p className="text-sm text-gray-600 mt-1">
                Select multiple tables to download as a single ZIP file
              </p>
            </div>
            <div className="text-2xl font-bold text-purple-600">
              {selectedTables.size}
            </div>
          </div>
          
          <div className="flex gap-3">
            <button
              onClick={selectAll}
              className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 transition-colors text-sm"
            >
              Select All
            </button>
            <button
              onClick={clearSelection}
              disabled={selectedTables.size === 0}
              className={`px-4 py-2 border border-gray-300 rounded-md transition-colors text-sm ${
                selectedTables.size === 0
                  ? 'text-gray-400 cursor-not-allowed'
                  : 'text-gray-700 hover:bg-gray-50'
              }`}
            >
              Clear Selection
            </button>
            <button
              onClick={handleBulkDownload}
              disabled={selectedTables.size === 0 || bulkDownloading}
              className={`flex-1 px-6 py-2 rounded-md font-medium transition-colors ${
                selectedTables.size === 0 || bulkDownloading
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-purple-600 text-white hover:bg-purple-700'
              }`}
            >
              {bulkDownloading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Creating ZIP...
                </span>
              ) : (
                <>📦 Download {selectedTables.size} Selected as ZIP</>
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
                <h3 className="font-medium text-gray-900 mb-3">
                  📂 {source} <span className="text-sm text-gray-500">({tableList.length} tables)</span>
                </h3>
                <div className="space-y-2">
                  {tableList.map((table) => {
                    const key = `${source}:${table}`;
                    const isSelected = selectedTables.has(key);
                    return (
                      <div key={table} className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded">
                        <input
                          type="checkbox"
                          id={key}
                          checked={isSelected}
                          onChange={() => toggleTableSelection(source, table)}
                          className="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                        />
                        <label
                          htmlFor={key}
                          className="flex-1 text-sm text-gray-700 cursor-pointer"
                        >
                          {table}
                        </label>
                        <button
                          onClick={() => {
                            setSelectedSource(source);
                            setSelectedTable(table);
                            window.scrollTo({ top: 0, behavior: 'smooth' });
                          }}
                          className="px-3 py-1 text-xs bg-blue-50 hover:bg-blue-100 text-blue-700 rounded transition-colors"
                        >
                          Download CSV
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Info Box */}
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-medium text-blue-900 mb-2">💡 Usage Tips</h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• <strong>Single CSV:</strong> Use the selector at the top or click "Download CSV" next to each table</li>
            <li>• <strong>Multiple Tables (ZIP):</strong> Check the boxes next to tables and click "Download Selected as ZIP"</li>
            <li>• CSV files can be opened in Excel, Google Sheets, or any spreadsheet application</li>
            <li>• Large tables may take a few seconds to download</li>
            <li>• ZIP files include all selected tables with filenames like <code className="bg-blue-100 px-1 rounded">source_table.csv</code></li>
            <li>• All data is exported as-is from the database</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

