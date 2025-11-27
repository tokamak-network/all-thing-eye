"use client";

interface FilterSummaryProps {
  selectedFields: string[];
  filters: {
    startDate: string;
    endDate: string;
    project: string;
    selectedMembers: string[];
  };
}

// Field category config
const fieldCategories: Record<
  string,
  { icon: string; name: string; fields: string[] }
> = {
  member: {
    icon: "👤",
    name: "Member Info",
    fields: ["member.name", "member.email", "member.role", "member.team"],
  },
  github: {
    icon: "💻",
    name: "GitHub",
    fields: [
      "github.commits",
      "github.additions",
      "github.deletions",
      "github.prs",
      "github.issues",
      "github.reviews",
    ],
  },
  slack: {
    icon: "💬",
    name: "Slack",
    fields: [
      "slack.messages",
      "slack.threads",
      "slack.reactions",
      "slack.links",
      "slack.files",
    ],
  },
  notion: {
    icon: "📝",
    name: "Notion",
    fields: ["notion.pages", "notion.edits", "notion.comments"],
  },
  drive: {
    icon: "📁",
    name: "Google Drive",
    fields: ["drive.files", "drive.changes", "drive.shares"],
  },
};

// Field display names
const fieldNames: Record<string, string> = {
  "member.name": "Name",
  "member.email": "Email",
  "member.role": "Role",
  "member.team": "Team",
  "github.commits": "Commits",
  "github.additions": "Lines Added",
  "github.deletions": "Lines Deleted",
  "github.prs": "Pull Requests",
  "github.issues": "Issues",
  "github.reviews": "Reviews",
  "slack.messages": "Messages",
  "slack.threads": "Threads",
  "slack.reactions": "Reactions",
  "slack.links": "Links",
  "slack.files": "Files",
  "notion.pages": "Pages",
  "notion.edits": "Edits",
  "notion.comments": "Comments",
  "drive.files": "Files",
  "drive.changes": "Changes",
  "drive.shares": "Shares",
};

export default function PreviewTable({
  selectedFields,
  filters,
}: FilterSummaryProps) {
  // Get selected sources
  const selectedSources = new Set<string>();
  selectedFields.forEach((field) => {
    const source = field.split(".")[0];
    selectedSources.add(source);
  });

  // Group selected fields by category
  const groupedFields: Record<string, string[]> = {};
  selectedFields.forEach((field) => {
    const source = field.split(".")[0];
    if (!groupedFields[source]) {
      groupedFields[source] = [];
    }
    groupedFields[source].push(field);
  });

  if (selectedFields.length === 0 && filters.selectedMembers.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
        <div className="text-center text-gray-500">
          <div className="text-4xl mb-3">📋</div>
          <p className="text-lg font-medium mb-2">No selection made</p>
          <p className="text-sm">
            Select members and data fields to configure your export
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-indigo-50">
        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
          📋 Export Configuration Summary
        </h3>
        <p className="text-sm text-gray-600 mt-1">
          Review your selections before exporting
        </p>
      </div>

      <div className="p-4 space-y-4">
        {/* Date Range */}
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center text-lg">
            📅
          </div>
          <div className="flex-1">
            <h4 className="font-medium text-gray-900">Date Range</h4>
            <p className="text-sm text-gray-600">
              {filters.startDate} ~ {filters.endDate}
            </p>
          </div>
        </div>

        {/* Selected Members */}
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center text-lg">
            👥
          </div>
          <div className="flex-1">
            <h4 className="font-medium text-gray-900">
              Members ({filters.selectedMembers.length})
            </h4>
            {filters.selectedMembers.length > 0 ? (
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {filters.selectedMembers.slice(0, 10).map((member) => (
                  <span
                    key={member}
                    className="px-2 py-0.5 bg-green-50 text-green-700 text-xs rounded-full border border-green-200"
                  >
                    {member}
                  </span>
                ))}
                {filters.selectedMembers.length > 10 && (
                  <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">
                    +{filters.selectedMembers.length - 10} more
                  </span>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-400 italic">
                No members selected
              </p>
            )}
          </div>
        </div>

        {/* Project */}
        {filters.project && filters.project !== "all" && (
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 bg-purple-100 rounded-lg flex items-center justify-center text-lg">
              🎯
            </div>
            <div className="flex-1">
              <h4 className="font-medium text-gray-900">Project</h4>
              <p className="text-sm text-gray-600">{filters.project}</p>
            </div>
          </div>
        )}

        {/* Data Sources */}
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 bg-orange-100 rounded-lg flex items-center justify-center text-lg">
            📊
          </div>
          <div className="flex-1">
            <h4 className="font-medium text-gray-900">
              Data Sources ({selectedSources.size})
            </h4>
            {Object.entries(groupedFields).length > 0 ? (
              <div className="mt-2 space-y-2">
                {Object.entries(groupedFields).map(([source, fields]) => {
                  const category = fieldCategories[source];
                  if (!category) return null;
                  return (
                    <div
                      key={source}
                      className="bg-gray-50 rounded-lg p-3 border border-gray-100"
                    >
                      <div className="flex items-center gap-2 mb-1.5">
                        <span>{category.icon}</span>
                        <span className="font-medium text-sm text-gray-800">
                          {category.name}
                        </span>
                        <span className="text-xs text-gray-500">
                          ({fields.length} fields)
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {fields.map((field) => (
                          <span
                            key={field}
                            className="px-2 py-0.5 bg-white text-gray-600 text-xs rounded border border-gray-200"
                          >
                            {fieldNames[field] || field.split(".")[1]}
                          </span>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-gray-400 italic mt-1">
                No data fields selected
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-4 text-gray-600">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-green-500"></span>
              Ready to export
            </span>
          </div>
          <div className="text-gray-500">
            Click <strong>&quot;Export as CSV&quot;</strong> to download
          </div>
        </div>
      </div>
    </div>
  );
}
