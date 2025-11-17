"use client";

interface FieldSelectorProps {
  selectedFields: string[];
  onFieldToggle: (fieldId: string) => void;
}

interface DataSource {
  id: string;
  name: string;
  icon: string;
  fields: Field[];
}

interface Field {
  id: string;
  name: string;
  description?: string;
}

const dataSources: DataSource[] = [
  {
    id: "member",
    name: "Member Info",
    icon: "👤",
    fields: [
      { id: "member.name", name: "Name", description: "Member full name" },
      { id: "member.email", name: "Email", description: "Contact email" },
      { id: "member.role", name: "Role", description: "Team role" },
      { id: "member.team", name: "Team", description: "Team assignment" },
    ],
  },
  {
    id: "github",
    name: "GitHub",
    icon: "💻",
    fields: [
      {
        id: "github.commits",
        name: "Commits",
        description: "Total commit count",
      },
      {
        id: "github.additions",
        name: "Lines Added",
        description: "Code additions",
      },
      {
        id: "github.deletions",
        name: "Lines Deleted",
        description: "Code deletions",
      },
      { id: "github.prs", name: "Pull Requests", description: "PR count" },
      { id: "github.issues", name: "Issues", description: "Issue count" },
      {
        id: "github.reviews",
        name: "Code Reviews",
        description: "Review count",
      },
    ],
  },
  {
    id: "slack",
    name: "Slack",
    icon: "💬",
    fields: [
      { id: "slack.messages", name: "Messages", description: "Message count" },
      {
        id: "slack.threads",
        name: "Thread Replies",
        description: "Thread participation",
      },
      {
        id: "slack.reactions",
        name: "Reactions",
        description: "Reaction count",
      },
      { id: "slack.links", name: "Links Shared", description: "Shared URLs" },
      {
        id: "slack.files",
        name: "Files Uploaded",
        description: "File uploads",
      },
    ],
  },
  {
    id: "notion",
    name: "Notion",
    icon: "📝",
    fields: [
      { id: "notion.pages", name: "Pages Created", description: "Page count" },
      { id: "notion.edits", name: "Page Edits", description: "Edit count" },
      { id: "notion.comments", name: "Comments", description: "Comment count" },
    ],
  },
  {
    id: "drive",
    name: "Google Drive",
    icon: "📁",
    fields: [
      { id: "drive.files", name: "Files Created", description: "File count" },
      {
        id: "drive.changes",
        name: "File Changes",
        description: "Modification count",
      },
      { id: "drive.shares", name: "Shares", description: "Sharing activity" },
    ],
  },
];

export default function FieldSelector({
  selectedFields,
  onFieldToggle,
}: FieldSelectorProps) {
  const totalFields = dataSources.reduce(
    (sum, ds) => sum + ds.fields.length,
    0
  );
  const selectedCount = selectedFields.length;

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      {/* Header */}
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">
          Data Sources & Fields
        </h2>
        <p className="text-sm text-gray-600">
          Selected:{" "}
          <span className="font-semibold text-blue-600">{selectedCount}</span> /{" "}
          {totalFields} fields
        </p>
      </div>

      {/* Data Sources */}
      <div className="space-y-6">
        {dataSources.map((source) => (
          <div
            key={source.id}
            className="border-b border-gray-100 last:border-0 pb-4 last:pb-0"
          >
            {/* Source Header */}
            <div className="flex items-center mb-3">
              <span className="text-2xl mr-2">{source.icon}</span>
              <h3 className="font-semibold text-gray-800">{source.name}</h3>
            </div>

            {/* Fields */}
            <div className="space-y-2 ml-8">
              {source.fields.map((field) => {
                const isSelected = selectedFields.includes(field.id);
                return (
                  <label
                    key={field.id}
                    className="flex items-start cursor-pointer group"
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => onFieldToggle(field.id)}
                      className="mt-1 h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <div className="ml-3">
                      <span
                        className={`text-sm font-medium ${
                          isSelected ? "text-gray-900" : "text-gray-700"
                        } group-hover:text-blue-600`}
                      >
                        {field.name}
                      </span>
                      {field.description && (
                        <p className="text-xs text-gray-500 mt-0.5">
                          {field.description}
                        </p>
                      )}
                    </div>
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="mt-6 pt-4 border-t border-gray-200 flex gap-2">
        <button
          onClick={() => {
            const allFieldIds = dataSources.flatMap((ds) =>
              ds.fields.map((f) => f.id)
            );
            allFieldIds.forEach((id) => {
              if (!selectedFields.includes(id)) {
                onFieldToggle(id);
              }
            });
          }}
          className="flex-1 text-xs px-3 py-2 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 transition-colors"
        >
          Select All
        </button>
        <button
          onClick={() => {
            selectedFields.forEach((id) => onFieldToggle(id));
          }}
          className="flex-1 text-xs px-3 py-2 bg-gray-50 text-gray-700 rounded hover:bg-gray-100 transition-colors"
        >
          Clear All
        </button>
      </div>
    </div>
  );
}





