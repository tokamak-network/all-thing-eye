# MCP (Model Context Protocol) Integration

This document describes the MCP server implementation for All-Thing-Eye.

## Overview

The MCP server exposes All-Thing-Eye data to AI assistants through a standardized protocol. This enables:

1. **Web Chatbot**: Floating AI assistant on all pages
2. **Slack Bot** (future): Same data access via Slack
3. **CLI Tools** (future): Command-line data queries
4. **External AI Tools**: Any MCP-compatible AI client

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server (All-Thing-Eye)               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Resources (읽기 전용 데이터)                           │ │
│  │  - ate://members                                       │ │
│  │  - ate://projects                                      │ │
│  │  - ate://activities/summary                            │ │
│  │  - ate://github/stats                                  │ │
│  │  - ate://slack/stats                                   │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Tools (AI가 호출 가능한 함수)                          │ │
│  │  - get_member_activity                                 │ │
│  │  - get_project_activity                                │ │
│  │  - compare_contributors                                │ │
│  │  - get_top_contributors                                │ │
│  │  - search_activities                                   │ │
│  │  - get_weekly_summary                                  │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Prompts (사전 정의된 프롬프트 템플릿)                    │ │
│  │  - analyze_contributor                                 │ │
│  │  - project_health_check                                │ │
│  │  - weekly_report                                       │ │
│  │  - compare_team                                        │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
          ▲                    ▲                    ▲
          │                    │                    │
    ┌─────┴─────┐        ┌─────┴─────┐        ┌─────┴─────┐
    │  Web Chat │        │ Slack Bot │        │   CLI     │
    │  (Active) │        │ (Phase 2) │        │ (Phase 3) │
    └───────────┘        └───────────┘        └───────────┘
```

## HTTP API Endpoints

The MCP server is exposed via HTTP for web clients:

### Resources

```bash
# List all resources
GET /api/v1/mcp/resources

# Read a specific resource
GET /api/v1/mcp/resources/{path}

# Examples:
GET /api/v1/mcp/resources/members
GET /api/v1/mcp/resources/projects
GET /api/v1/mcp/resources/github/stats
```

### Tools

```bash
# List all tools
GET /api/v1/mcp/tools

# Call a tool
POST /api/v1/mcp/tools/call
Content-Type: application/json

{
  "name": "get_member_activity",
  "arguments": {
    "member_name": "Jake",
    "days": 30
  }
}
```

### Prompts

```bash
# List all prompts
GET /api/v1/mcp/prompts

# Get a prompt with arguments
POST /api/v1/mcp/prompts/get
Content-Type: application/json

{
  "name": "analyze_contributor",
  "arguments": {
    "member_name": "Jake",
    "period": "last week"
  }
}
```

### Context-Aware Chat

```bash
# Chat with automatic context injection
POST /api/v1/mcp/chat
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "Who is the most active in OOO?"}
  ],
  "model": "qwen3-235b",
  "context_hints": {
    "project_key": "project-ooo"
  }
}
```

## Available Tools

### get_member_activity

Get detailed activity statistics for a team member.

```json
{
  "member_name": "Jake",
  "days": 30
}
```

Returns: GitHub commits, PRs, Slack messages, project assignments.

### get_project_activity

Get activity statistics for a project.

```json
{
  "project_key": "project-ooo",
  "days": 30
}
```

Returns: Total commits, messages, contributor breakdown.

### compare_contributors

Compare activity between multiple team members.

```json
{
  "member_names": ["Jake", "Mehdi", "Aamir"],
  "metric": "all",
  "days": 30
}
```

Returns: Side-by-side comparison of commits, messages, PRs.

### get_top_contributors

Get the most active contributors by metric.

```json
{
  "metric": "commits",
  "project_key": "project-ooo",
  "days": 30,
  "limit": 10
}
```

Returns: Ranked list of top contributors.

### search_activities

Search for activities matching criteria.

```json
{
  "keyword": "zkEVM",
  "source": "all",
  "member_name": "Jake",
  "days": 7,
  "limit": 20
}
```

Returns: Matching commits, messages, etc.

### get_weekly_summary

Generate a weekly activity summary.

```json
{
  "project_key": "project-ooo",
  "week_offset": -1
}
```

Returns: Weekly statistics for commits, messages, top contributors.

## Frontend Integration

The floating chatbot (`FloatingAIChatbot.tsx`) uses MCP by default:

```typescript
// Toggle MCP mode
const [useMCP, setUseMCP] = useState(true);

// When MCP is enabled, use context-aware chat
if (useMCP) {
  response = await api.chatWithMCPContext(messages, model, contextHints);
} else {
  response = await api.chatWithAI(messages, model, context);
}
```

## Context Detection

The MCP chat endpoint automatically detects:

1. **Project mentions**: "OOO", "ECO", "TRH", etc.
2. **Member mentions**: Any team member name
3. **Time periods**: "last week", "last month", "today"

Example conversation:

```
User: "Who is the most active in OOO?"

→ MCP detects: project_key = "project-ooo"
→ Fetches: OOO project activity, top contributors
→ AI receives: Contextual data about OOO project
→ Response: "In Project OOO, Jake leads with 45 commits..."
```

## Running the Standalone MCP Server

For use with Claude Desktop or other MCP clients:

```bash
# Install dependencies
pip install mcp

# Run the server
python -m mcp_server.server
```

Configure in Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "all-thing-eye": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/all-thing-eye"
    }
  }
}
```

## Future Enhancements

### Phase 2: Slack Bot Integration

```python
# Slack bot will reuse MCP tools
@slack_event("app_mention")
async def handle_mention(event):
    message = event["text"]

    # Use MCP context-aware chat
    response = await mcp_chat(message, context_hints={
        "slack_channel": event["channel"]
    })

    await slack.post_message(event["channel"], response)
```

### Phase 3: Advanced Features

- **Streaming responses**: Real-time token streaming
- **File attachments**: Export data as CSV/PDF
- **Scheduled reports**: Daily/weekly summaries via Slack
- **Custom prompts**: User-defined analysis templates

## Troubleshooting

### MCP not working?

1. Check if backend is running: `curl http://localhost:8000/api/v1/mcp/resources`
2. Verify MongoDB connection
3. Check browser console for errors

### Context not being detected?

The context detection is case-insensitive. Try:

- "What's happening in OOO?" (project)
- "How active is Jake?" (member)
- "Show me last week's activity" (time)

### AI not responding?

1. Check `AI_API_KEY` in `.env`
2. Verify AI API is accessible
3. Check backend logs for errors

## API Reference

See full API documentation at:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
