"use client";

interface PreviewTableProps {
  selectedFields: string[];
}

// Mock data for preview
const mockData = [
  {
    "member.name": "Monica",
    "member.email": "monica@tokamak.network",
    "member.role": "Developer",
    "member.team": "Core Team",
    "github.commits": 25,
    "github.additions": 1250,
    "github.deletions": 430,
    "github.prs": 8,
    "github.issues": 3,
    "github.reviews": 12,
    "slack.messages": 45,
    "slack.threads": 18,
    "slack.reactions": 67,
    "slack.links": 12,
    "slack.files": 5,
    "notion.pages": 7,
    "notion.edits": 23,
    "notion.comments": 15,
    "drive.files": 10,
    "drive.changes": 34,
    "drive.shares": 8,
  },
  {
    "member.name": "Bernard",
    "member.email": "bernard@tokamak.network",
    "member.role": "Developer",
    "member.team": "Core Team",
    "github.commits": 18,
    "github.additions": 890,
    "github.deletions": 320,
    "github.prs": 6,
    "github.issues": 2,
    "github.reviews": 15,
    "slack.messages": 32,
    "slack.threads": 12,
    "slack.reactions": 45,
    "slack.links": 8,
    "slack.files": 3,
    "notion.pages": 5,
    "notion.edits": 18,
    "notion.comments": 10,
    "drive.files": 8,
    "drive.changes": 25,
    "drive.shares": 6,
  },
  {
    "member.name": "Jake",
    "member.email": "jake@tokamak.network",
    "member.role": "Developer",
    "member.team": "Core Team",
    "github.commits": 32,
    "github.additions": 1560,
    "github.deletions": 580,
    "github.prs": 10,
    "github.issues": 5,
    "github.reviews": 8,
    "slack.messages": 56,
    "slack.threads": 22,
    "slack.reactions": 89,
    "slack.links": 15,
    "slack.files": 7,
    "notion.pages": 10,
    "notion.edits": 30,
    "notion.comments": 20,
    "drive.files": 12,
    "drive.changes": 40,
    "drive.shares": 10,
  },
  {
    "member.name": "Jamie",
    "member.email": "jamie@tokamak.network",
    "member.role": "Designer",
    "member.team": "Design Team",
    "github.commits": 0,
    "github.additions": 0,
    "github.deletions": 0,
    "github.prs": 0,
    "github.issues": 0,
    "github.reviews": 0,
    "slack.messages": 78,
    "slack.threads": 35,
    "slack.reactions": 120,
    "slack.links": 25,
    "slack.files": 18,
    "notion.pages": 15,
    "notion.edits": 45,
    "notion.comments": 30,
    "drive.files": 35,
    "drive.changes": 80,
    "drive.shares": 20,
  },
  {
    "member.name": "Alice",
    "member.email": "alice@tokamak.network",
    "member.role": "Manager",
    "member.team": "Management",
    "github.commits": 5,
    "github.additions": 120,
    "github.deletions": 50,
    "github.prs": 2,
    "github.issues": 1,
    "github.reviews": 3,
    "slack.messages": 92,
    "slack.threads": 40,
    "slack.reactions": 150,
    "slack.links": 30,
    "slack.files": 12,
    "notion.pages": 20,
    "notion.edits": 55,
    "notion.comments": 40,
    "drive.files": 25,
    "drive.changes": 60,
    "drive.shares": 15,
  },
];

// Field display names
const fieldNames: Record<string, string> = {
  "member.name": "Name",
  "member.email": "Email",
  "member.role": "Role",
  "member.team": "Team",
  "github.commits": "Commits",
  "github.additions": "Lines+",
  "github.deletions": "Lines-",
  "github.prs": "PRs",
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

export default function PreviewTable({ selectedFields }: PreviewTableProps) {
  // Filter data to only show selected fields
  const displayData = mockData.map((row) => {
    const filteredRow: Record<string, any> = {};
    selectedFields.forEach((field) => {
      if (field in row) {
        filteredRow[field] = row[field as keyof typeof row];
      }
    });
    return filteredRow;
  });

  if (selectedFields.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12">
        <div className="text-center text-gray-500">
          <div className="text-4xl mb-3">📊</div>
          <p className="text-lg font-medium mb-2">No fields selected</p>
          <p className="text-sm">
            Select fields from the left panel to preview data
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-900">Preview</h3>
            <p className="text-sm text-gray-600 mt-0.5">
              Showing first 10 rows • Total: {mockData.length} rows
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded">
              {selectedFields.length} columns
            </span>
            <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded">
              Mock Data
            </span>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              {selectedFields.map((field) => (
                <th
                  key={field}
                  className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider whitespace-nowrap"
                >
                  {fieldNames[field] || field}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {displayData.map((row, rowIndex) => (
              <tr key={rowIndex} className="hover:bg-gray-50 transition-colors">
                {selectedFields.map((field) => {
                  const value = row[field];
                  const isNumeric = typeof value === "number";

                  return (
                    <td
                      key={field}
                      className={`px-4 py-3 text-sm ${
                        isNumeric
                          ? "text-right font-mono text-gray-900"
                          : "text-left text-gray-700"
                      } whitespace-nowrap`}
                    >
                      {value !== undefined && value !== null ? (
                        isNumeric ? (
                          <span className={value === 0 ? "text-gray-400" : ""}>
                            {value.toLocaleString()}
                          </span>
                        ) : (
                          value
                        )
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between text-xs text-gray-600">
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
              Live Preview
            </span>
          </div>
          <div>Click &quot;Export as CSV&quot; to download full dataset</div>
        </div>
      </div>
    </div>
  );
}





