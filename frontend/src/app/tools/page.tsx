"use client";

import Link from "next/link";
import {
  WrenchScrewdriverIcon,
  ClockIcon,
} from "@heroicons/react/24/outline";

const tools = [
  {
    name: "Weekly Output Bot",
    description:
      "Schedule weekly output threads in any Slack channel with automated reminders.",
    href: "/tools/weekly-output",
    icon: ClockIcon,
    color: "bg-blue-500",
  },
];

export default function ToolsPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <div className="flex items-center space-x-3">
          <WrenchScrewdriverIcon className="h-8 w-8 text-gray-700" />
          <h1 className="text-2xl font-bold text-gray-900">Tools</h1>
        </div>
        <p className="mt-2 text-gray-600">
          ATI bot tools and automation utilities.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {tools.map((tool) => (
          <Link
            key={tool.href}
            href={tool.href}
            className="block group rounded-lg border border-gray-200 bg-white p-6 shadow-sm hover:shadow-md hover:border-gray-300 transition-all"
          >
            <div className="flex items-center space-x-3 mb-3">
              <div
                className={`${tool.color} rounded-lg p-2 text-white group-hover:scale-105 transition-transform`}
              >
                <tool.icon className="h-6 w-6" />
              </div>
              <h2 className="text-lg font-semibold text-gray-900">
                {tool.name}
              </h2>
            </div>
            <p className="text-sm text-gray-600">{tool.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
