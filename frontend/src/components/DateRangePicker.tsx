'use client';

import { useState, useEffect } from 'react';
import { format, subDays } from 'date-fns';

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

  // Format date as YYYY-MM-DD
  const formatDate = (date: Date): string => {
    return format(date, 'yyyy-MM-dd');
  };

  const handlePreset = (preset: string) => {
    const today = new Date();
    let start: Date;
    let end: Date;

    switch (preset) {
      case 'lastweek':
        // Last 7 days
        start = new Date(today);
        start.setDate(today.getDate() - 7);
        end = today;
        break;
      case 'thisweek':
        // This week (Monday to today)
        const dayOfWeek = today.getDay(); // 0 = Sunday, 1 = Monday, etc.
        const daysToMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1; // Convert Sunday (0) to 6
        start = new Date(today);
        start.setDate(today.getDate() - daysToMonday);
        end = today;
        break;
      case 'lastmonth':
        // Last month (first day to last day)
        const firstDayLastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        const lastDayLastMonth = new Date(today.getFullYear(), today.getMonth(), 0);
        start = firstDayLastMonth;
        end = lastDayLastMonth;
        break;
      case 'thismonth':
        // This month (first day to today)
        const thisMonthStart = new Date(today.getFullYear(), today.getMonth(), 1);
        start = thisMonthStart;
        end = today;
        break;
      case 'lastquarter':
        // Last quarter
        const currentQuarter = Math.floor(today.getMonth() / 3);
        const lastQuarterStart = currentQuarter === 0 
          ? new Date(today.getFullYear() - 1, 9, 1)
          : new Date(today.getFullYear(), (currentQuarter - 1) * 3, 1);
        const lastQuarterEnd = currentQuarter === 0
          ? new Date(today.getFullYear() - 1, 12, 0)
          : new Date(today.getFullYear(), currentQuarter * 3, 0);
        start = lastQuarterStart;
        end = lastQuarterEnd;
        break;
      case 'thisquarter':
        // This quarter (start of quarter to today)
        const thisQuarter = Math.floor(today.getMonth() / 3);
        const thisQuarterStart = new Date(today.getFullYear(), thisQuarter * 3, 1);
        start = thisQuarterStart;
        end = today;
        break;
      case 'lastyear':
        // Last year
        const lastYearStart = new Date(today.getFullYear() - 1, 0, 1);
        const lastYearEnd = new Date(today.getFullYear() - 1, 11, 31);
        start = lastYearStart;
        end = lastYearEnd;
        break;
      case 'thisyear':
        // This year (Jan 1 to today)
        const thisYearStart = new Date(today.getFullYear(), 0, 1);
        start = thisYearStart;
        end = today;
        break;
      default:
        return;
    }

    const startStr = formatDate(start);
    const endStr = formatDate(end);
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
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => handlePreset('lastweek')}
            className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-full hover:bg-blue-100 hover:text-blue-700 transition-colors"
          >
            Last Week
          </button>
          <button
            onClick={() => handlePreset('thisweek')}
            className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-full hover:bg-blue-100 hover:text-blue-700 transition-colors"
          >
            This Week
          </button>
          <button
            onClick={() => handlePreset('lastmonth')}
            className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-full hover:bg-blue-100 hover:text-blue-700 transition-colors"
          >
            Last Month
          </button>
          <button
            onClick={() => handlePreset('thismonth')}
            className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-full hover:bg-blue-100 hover:text-blue-700 transition-colors"
          >
            This Month
          </button>
          <button
            onClick={() => handlePreset('lastquarter')}
            className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-full hover:bg-blue-100 hover:text-blue-700 transition-colors"
          >
            Last Quarter
          </button>
          <button
            onClick={() => handlePreset('thisquarter')}
            className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-full hover:bg-blue-100 hover:text-blue-700 transition-colors"
          >
            This Quarter
          </button>
          <button
            onClick={() => handlePreset('lastyear')}
            className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-full hover:bg-blue-100 hover:text-blue-700 transition-colors"
          >
            Last Year
          </button>
          <button
            onClick={() => handlePreset('thisyear')}
            className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-full hover:bg-blue-100 hover:text-blue-700 transition-colors"
          >
            This Year
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

