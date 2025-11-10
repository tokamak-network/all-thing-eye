# Query Engine and AI Formatter Guide

This guide explains how to use the Query Engine to aggregate member activity data and format it for AI analysis.

## Table of Contents

1. [Overview](#overview)
2. [Query Engine](#query-engine)
3. [AI Formatter](#ai-formatter)
4. [Usage Examples](#usage-examples)
5. [Output Formats](#output-formats)

---

## Overview

The integration layer provides two main components:

1. **Query Engine** (`src/integrations/query_engine.py`)
   - Aggregates member activities from multiple data sources
   - Provides member-centric views of GitHub data
   - Calculates statistics and identifies patterns

2. **AI Formatter** (`src/integrations/ai_formatter.py`)
   - Formats query results for AI analysis
   - Generates structured prompts for performance reviews
   - Exports data in multiple formats (JSON, Markdown)

---

## Query Engine

### Key Features

- **Member-centric queries**: Get all activities for a specific member
- **Time-based filtering**: Query activities within date ranges
- **Automatic aggregation**: Calculate statistics across commits, PRs, and issues
- **Repository insights**: Identify top repositories and files

### Main Methods

#### `get_member_github_activities(member_name, start_date, end_date)`

Get comprehensive GitHub activities for a member.

```python
from src.core.config import Config
from src.core.database import DatabaseManager
from src.core.member_index import MemberIndex
from src.integrations.query_engine import QueryEngine
from datetime import datetime, timedelta

# Initialize
config = Config()
db_manager = DatabaseManager(config)
member_index = MemberIndex(db_manager)
query_engine = QueryEngine(db_manager, member_index)

# Query last 7 days
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

data = query_engine.get_member_github_activities(
    member_name="Kevin",
    start_date=start_date,
    end_date=end_date
)
```

**Returns:**
```python
{
    'member_name': 'Kevin',
    'github_id': 'kevin-username',
    'period': {
        'start': '2024-01-01T00:00:00',
        'end': '2024-01-07T23:59:59'
    },
    'statistics': {
        'commits': {
            'total': 42,
            'additions': 1250,
            'deletions': 380,
            'changed_files': 65,
            'net_lines': 870
        },
        'pull_requests': {
            'total': 8,
            'merged': 6,
            'open': 1,
            'closed': 1,
            'additions': 1100,
            'deletions': 350
        },
        'issues': {
            'total': 5,
            'closed': 3,
            'open': 2
        },
        'files': {
            'total_modified': 85,
            'unique_files': 45
        }
    },
    'commits': [...],  # Detailed commit list
    'pull_requests': [...],  # Detailed PR list
    'issues': [...],  # Detailed issue list
    'top_repositories': [...],  # Top repos by activity
    'top_files': [...]  # Most modified files
}
```

#### `get_all_members_summary(start_date, end_date)`

Get activity summaries for all team members.

```python
team_data = query_engine.get_all_members_summary(
    start_date=start_date,
    end_date=end_date
)
```

**Returns:**
```python
[
    {
        'member_name': 'Kevin',
        'github_id': 'kevin-username',
        'statistics': {...},
        'top_repositories': [...]
    },
    {
        'member_name': 'Alice',
        'github_id': 'alice-username',
        'statistics': {...},
        'top_repositories': [...]
    },
    # ... more members
]
```

---

## AI Formatter

### Key Features

- **Multiple template types**: Performance review, team summary, technical depth analysis
- **Structured prompts**: Well-formatted for AI model consumption
- **Multiple export formats**: Text prompts, JSON, Markdown
- **Customizable detail levels**: Include/exclude detailed activity logs

### Main Methods

#### `format_member_performance(member_data, include_details)`

Generate a performance review prompt.

```python
from src.integrations.ai_formatter import AIPromptFormatter

formatter = AIPromptFormatter()

# Get data from query engine
member_data = query_engine.get_member_github_activities("Kevin", start_date, end_date)

# Format for AI
prompt = formatter.format_member_performance(
    member_data,
    include_details=True  # Include commit/PR lists
)

# Send to AI service
# response = openai.chat.completions.create(
#     model="gpt-4",
#     messages=[{"role": "user", "content": prompt}]
# )
```

#### `format_team_summary(team_data, period)`

Generate a team-wide summary prompt.

```python
team_data = query_engine.get_all_members_summary(start_date, end_date)

team_prompt = formatter.format_team_summary(
    team_data,
    period={'start': start_date.isoformat(), 'end': end_date.isoformat()}
)
```

#### `format_technical_depth_analysis(member_data)`

Generate a technical depth analysis prompt.

```python
technical_prompt = formatter.format_technical_depth_analysis(member_data)
```

#### Export Methods

```python
# Export as JSON
json_data = formatter.export_as_json(member_data)

# Export as Markdown report
markdown_report = formatter.export_as_markdown(member_data)
```

---

## Usage Examples

### Example 1: Single Member Analysis

```bash
# Using the test script
python tests/test_query_and_ai.py --member Kevin

# For last week's data
python tests/test_query_and_ai.py --member Kevin --last-week

# Export only AI prompt
python tests/test_query_and_ai.py --member Kevin --format prompt

# Export as JSON
python tests/test_query_and_ai.py --member Kevin --format json
```

### Example 2: Team Summary

```bash
# Current week team summary
python tests/test_query_and_ai.py --team-summary

# Last week team summary
python tests/test_query_and_ai.py --team-summary --last-week
```

### Example 3: Custom Integration

```python
from src.core.config import Config
from src.core.database import DatabaseManager
from src.core.member_index import MemberIndex
from src.integrations.query_engine import QueryEngine
from src.integrations.ai_formatter import AIPromptFormatter
from src.utils.date_helpers import get_last_week_range

# Initialize components
config = Config()
db_manager = DatabaseManager(config)
member_index = MemberIndex(db_manager)
query_engine = QueryEngine(db_manager, member_index)
formatter = AIPromptFormatter()

# Get last week's date range
start_date, end_date = get_last_week_range()

# Query member data
member_data = query_engine.get_member_github_activities(
    "Kevin",
    start_date,
    end_date
)

# Generate different analysis types
performance_prompt = formatter.format_member_performance(member_data, include_details=True)
technical_prompt = formatter.format_technical_depth_analysis(member_data)

# Save to files
with open('output/kevin_performance.txt', 'w') as f:
    f.write(performance_prompt)

with open('output/kevin_technical.txt', 'w') as f:
    f.write(technical_prompt)

# Export as JSON for API
json_data = formatter.export_as_json(member_data)
with open('output/kevin_data.json', 'w') as f:
    f.write(json_data)
```

---

## Output Formats

### 1. AI Prompt (Text)

Structured text prompt ready for AI analysis:

```
# Team Member Performance Analysis

## Basic Information
- Name: Kevin
- GitHub ID: kevin-username
- Analysis Period: 2024-01-01 to 2024-01-07

## GitHub Activity Summary
...

## Analysis Request
Based on the above data, please provide:
1. Overall Activity Assessment
2. Strengths Identified
3. Areas for Improvement
...
```

**Use case**: Send directly to OpenAI, Claude, or other AI services

### 2. JSON Format

Machine-readable data structure:

```json
{
  "member_name": "Kevin",
  "github_id": "kevin-username",
  "period": {
    "start": "2024-01-01T00:00:00",
    "end": "2024-01-07T23:59:59"
  },
  "statistics": {
    "commits": {...},
    "pull_requests": {...},
    "issues": {...}
  }
}
```

**Use case**: API responses, data processing, storage

### 3. Markdown Report

Human-readable report with detailed information:

```markdown
# Team Member Performance Analysis

## Basic Information
- **Name**: Kevin
- **GitHub ID**: kevin-username

## GitHub Activity Summary

### Code Contributions
- **Total Commits**: 42
- **Lines Added**: +1,250
...

## Detailed Activity Log

### Recent Commits (Top 10)
1. [abc1234](url) Add authentication module
   - Repository: project-name
   ...
```

**Use case**: Documentation, sharing with team, archiving

---

## Advanced Usage

### Filtering by Date Range

```python
from datetime import datetime, timedelta

# Last 30 days
end_date = datetime.now()
start_date = end_date - timedelta(days=30)

# Specific date range
start_date = datetime(2024, 1, 1)
end_date = datetime(2024, 1, 31)

data = query_engine.get_member_github_activities(
    "Kevin",
    start_date,
    end_date
)
```

### Analyzing Multiple Members

```python
members = ["Kevin", "Alice", "Bob"]
results = {}

for member in members:
    data = query_engine.get_member_github_activities(
        member,
        start_date,
        end_date
    )
    
    if 'error' not in data:
        prompt = formatter.format_member_performance(data)
        results[member] = prompt
        
        # Save individual reports
        with open(f'output/{member}_report.txt', 'w') as f:
            f.write(prompt)
```

### Custom Statistics

```python
# Get raw data
member_data = query_engine.get_member_github_activities("Kevin", start_date, end_date)

# Calculate custom metrics
commits = member_data['commits']
avg_changes_per_commit = (
    member_data['statistics']['commits']['additions'] + 
    member_data['statistics']['commits']['deletions']
) / len(commits) if commits else 0

print(f"Average changes per commit: {avg_changes_per_commit:.2f}")

# Find largest commits
largest_commits = sorted(
    commits,
    key=lambda c: c['additions'] + c['deletions'],
    reverse=True
)[:5]

for commit in largest_commits:
    print(f"- {commit['sha'][:7]}: +{commit['additions']} -{commit['deletions']}")
```

---

## Integration with AI Services

### OpenAI Example

```python
import openai

# Generate prompt
prompt = formatter.format_member_performance(member_data, include_details=True)

# Send to OpenAI
response = openai.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are an HR performance analyst."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.7,
    max_tokens=2000
)

analysis = response.choices[0].message.content
print(analysis)
```

### Claude Example

```python
import anthropic

client = anthropic.Anthropic(api_key="your-api-key")

prompt = formatter.format_member_performance(member_data, include_details=True)

message = client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=2000,
    messages=[
        {"role": "user", "content": prompt}
    ]
)

analysis = message.content[0].text
print(analysis)
```

---

## Troubleshooting

### Member Not Found

```python
data = query_engine.get_member_github_activities("NonExistent", start_date, end_date)

if 'error' in data:
    print(f"Error: {data['error']}")
    # Handle error appropriately
```

### No GitHub ID Mapped

Ensure the member has a GitHub identifier in the member index:

```bash
# Check member configuration
cat config/members.yaml
```

### Empty Results

If a member has no activity in the date range, the statistics will show zeros:

```python
stats = data['statistics']
if stats['commits']['total'] == 0:
    print("No commits found in this period")
```

---

## Best Practices

1. **Use appropriate date ranges**
   - Weekly reviews: Use `get_current_week_range()` or `get_last_week_range()`
   - Monthly reviews: Use first and last day of month
   - Quarterly reviews: Use quarter boundaries

2. **Cache results**
   - Query results are expensive to compute
   - Cache formatted prompts if analyzing multiple members

3. **Include context**
   - When sending to AI, include information about team size and project type
   - Adjust prompts based on role (junior vs senior developer)

4. **Export multiple formats**
   - JSON for archiving and API responses
   - Markdown for human readability
   - Text prompts for AI analysis

5. **Regular monitoring**
   - Set up weekly automated reports
   - Track trends over time
   - Identify patterns early

---

## Related Documentation

- [Architecture Overview](ARCHITECTURE.md)
- [GitHub Setup Guide](GITHUB_SETUP.md)
- [Member Management](MEMBER_MANAGEMENT.md)
- [Weekly Data Collection](WEEKLY_COLLECTION.md)

