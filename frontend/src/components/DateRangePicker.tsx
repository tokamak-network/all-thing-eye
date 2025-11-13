'use client';

import { useState, useEffect } from 'react';
import { format, subDays, startOfWeek, endOfWeek, subWeeks } from 'date-fns';

interface DateRangePickerProps {
  startDate: string;
  endDate: string;
  onDateChange: (startDate: string, endDate: string) => void;
  className?: string;
}

export default function DateRangePicker({
  startDate,
  endDate,
  onDateChange,
  className = '',
}: DateRangePickerProps) {
  const [localStartDate, setLocalStartDate] = useState(startDate);
  const [localEndDate, setLocalEndDate] = useState(endDate);

  useEffect(() => {
    setLocalStartDate(startDate);
    setLocalEndDate(endDate);
  }, [startDate, endDate]);

  const handleApply = () => {
    if (localStartDate && localEndDate) {
      if (new Date(localStartDate) <= new Date(localEndDate)) {
        onDateChange(localStartDate, localEndDate);
      } else {
        alert('Start date must be before or equal to end date');
      }
    }
  };

  const handlePreset = (preset: string) => {
    const today = new Date();
    let start: Date;
    let end: Date;

    switch (preset) {
      case 'today':
        start = today;
        end = today;
        break;
      case 'yesterday':
        start = subDays(today, 1);
        end = subDays(today, 1);
        break;
      case 'last7days':
        start = subDays(today, 6);
        end = today;
        break;
      case 'last30days':
        start = subDays(today, 29);
        end = today;
        break;
      case 'thisweek':
        start = startOfWeek(today, { weekStartsOn: 1 }); // Monday
        end = today;
        break;
      case 'lastweek':
        const lastWeekStart = startOfWeek(subWeeks(today, 1), { weekStartsOn: 1 });
        const lastWeekEnd = endOfWeek(subWeeks(today, 1), { weekStartsOn: 1 });
        start = lastWeekStart;
        end = lastWeekEnd;
        break;
      default:
        return;
    }

    const startStr = format(start, 'yyyy-MM-dd');
    const endStr = format(end, 'yyyy-MM-dd');
    setLocalStartDate(startStr);
    setLocalEndDate(endStr);
    onDateChange(startStr, endStr);
  };

  const handleClear = () => {
    setLocalStartDate('');
    setLocalEndDate('');
    onDateChange('', '');
  };

  return (
    <div className={`bg-white rounded-lg border border-gray-200 p-4 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-900">📅 Date Range Filter</h3>
        {(localStartDate || localEndDate) && (
          <button
            onClick={handleClear}
            className="text-xs text-gray-500 hover:text-gray-700 underline"
          >
            Clear
          </button>
        )}
      </div>

      {/* Date Inputs */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Start Date
          </label>
          <input
            type="date"
            value={localStartDate}
            onChange={(e) => setLocalStartDate(e.target.value)}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            End Date
          </label>
          <input
            type="date"
            value={localEndDate}
            onChange={(e) => setLocalEndDate(e.target.value)}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Quick Presets */}
      <div className="mb-4">
        <label className="block text-xs font-medium text-gray-700 mb-2">
          Quick Select
        </label>
        <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
          <button
            onClick={() => handlePreset('today')}
            className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition-colors"
          >
            Today
          </button>
          <button
            onClick={() => handlePreset('yesterday')}
            className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition-colors"
          >
            Yesterday
          </button>
          <button
            onClick={() => handlePreset('last7days')}
            className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition-colors"
          >
            Last 7d
          </button>
          <button
            onClick={() => handlePreset('last30days')}
            className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition-colors"
          >
            Last 30d
          </button>
          <button
            onClick={() => handlePreset('thisweek')}
            className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition-colors"
          >
            This Week
          </button>
          <button
            onClick={() => handlePreset('lastweek')}
            className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition-colors"
          >
            Last Week
          </button>
        </div>
      </div>

      {/* Apply Button */}
      <button
        onClick={handleApply}
        disabled={!localStartDate || !localEndDate}
        className={`w-full px-4 py-2 rounded-md font-medium text-sm transition-colors ${
          !localStartDate || !localEndDate
            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
            : 'bg-blue-600 text-white hover:bg-blue-700'
        }`}
      >
        Apply Date Range
      </button>

      {/* Current Selection Display */}
      {localStartDate && localEndDate && (
        <div className="mt-3 p-2 bg-blue-50 rounded text-xs text-blue-800">
          <span className="font-medium">Current Range:</span> {localStartDate} to {localEndDate}
        </div>
      )}
    </div>
  );
}

