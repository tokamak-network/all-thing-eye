"use client";

import { useState } from "react";
import ActivitiesView from "@/components/ActivitiesView";
import CodeStatsView from "@/components/CodeStatsView";

type TabType = "activities" | "code-stats";

const TABS: { value: TabType; label: string; icon: string }[] = [
  { value: "activities", label: "Activities", icon: "📋" },
  { value: "code-stats", label: "Code Stats", icon: "💻" },
];

export default function ActivitiesPage() {
  const [activeTab, setActiveTab] = useState<TabType>("activities");

  return (
    <div className="space-y-6">
      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              className={`py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2 transition-colors ${
                activeTab === tab.value
                  ? "border-indigo-500 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
            >
              <span>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === "activities" && <ActivitiesView showProjectFilter={true} />}
      {activeTab === "code-stats" && <CodeStatsView />}
    </div>
  );
}
