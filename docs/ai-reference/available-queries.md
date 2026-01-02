# Available Queries Reference

This document describes all available data queries for the AI assistant.

## Query Types

### 1. Member Activity Query
Get detailed activity for a specific team member.

**Parameters:**
- `member_name`: Member's display name (e.g., "Ale", "Jake")
- `days`: Number of days to look back (default: 30)

**Returns:**
- GitHub commits count
- Pull requests count
- Slack messages count
- Recent Slack messages (last 5)
- Associated projects

**Example questions that trigger this:**
- "What is Ale's activity?"
- "Show me Jake's commits"
- "How active is Monica on Slack?"

---

### 2. Project Activity Query
Get activity summary for a specific project.

**Parameters:**
- `project_key`: Project identifier (e.g., "project-ooo", "project-eco")
- `days`: Number of days (default: 30)

**Returns:**
- Project name and lead
- Total commits across project repositories
- Total Slack messages in project channel
- List of repositories

**Example questions:**
- "What's the status of project OOO?"
- "Show ECO project activity"
- "How many commits in TRH this week?"

---

### 3. Top GitHub Contributors
Get ranked list of most active GitHub contributors.

**Parameters:**
- `days`: Time period (default: 30)
- `limit`: Number of results (default: 10)
- `project_key`: Optional filter by project

**Returns:**
- Ranked list with member name and commit count

**Example questions:**
- "Who are the top contributors?"
- "Most active developers this month"
- "Who committed the most to OOO?"

---

### 4. Top Slack Users
Get ranked list of most active Slack users.

**Parameters:**
- `days`: Time period (default: 30)
- `limit`: Number of results (default: 10)

**Returns:**
- Ranked list with member name, message count, active channels

**Example questions:**
- "Who is most active on Slack?"
- "Top communicators this week"
- "Slack activity ranking"

---

### 5. Top Repositories
Get most active GitHub repositories.

**Parameters:**
- `days`: Time period (default: 30)
- `limit`: Number of results (default: 10)

**Returns:**
- Repository name
- Commit count
- Additions/deletions
- Top contributors

**Example questions:**
- "Most active repositories"
- "Which repos have the most commits?"
- "Where is development happening?"

---

### 6. Comparison Query
Compare GitHub and Slack activity.

**Returns:**
- Total commits and messages
- Daily averages
- Ratio comparisons

**Example questions:**
- "Compare GitHub vs Slack"
- "Activity comparison"
- "Code vs communication ratio"

---

### 7. General Summary
Overview of all team activity.

**Returns:**
- Total commits, messages, PRs
- Member count, project count
- Top contributors (brief)

**Example questions:**
- "Overall team summary"
- "Activity overview"
- "How is the team doing?"

---

## Keyword Detection

The AI uses these keywords to determine what data to fetch:

### GitHub-related
```
github, commit, pr, pull request, repository, repo, 코드, 커밋, code
```

### Slack-related
```
slack, message, 메시지, 채팅, communication, chat
```

### Time periods
```
- "this week", "이번 주" → 7 days
- "last week", "지난 주" → 7 days
- "today", "오늘" → 1 day
- "this month", "이번 달" → 30 days
- "this year", "올해" → 365 days
```

### Rankings
```
top, most, best, active, highest, 가장, 활발, 최고
```

### Comparisons
```
compare, comparison, vs, versus, 비교
```

---

## Available Projects

| Key | Name | Lead | Slack Channel |
|-----|------|------|---------------|
| project-ooo | Ooo | Jake | C07JN9XR570 |
| project-eco | ECO | Jason | C07JU6K4KDY |
| project-syb | SYB | Jamie | C074PEUC2CR |
| project-trh | TRH | Praveen | C06UKCF86TE |

---

## Available Members

Current team members (use exact names for queries):

- Aamir, Ale, Aryan, Bernard, Eugenie, George
- Harvey, Irene, Jaden, Jake, Jamie, Jason
- Jeff, Kevin, Luca, Manish, Mehdi, Monica
- Muhammed, Nam, Nil, Praveen, Sahil, Singh
- Suhyeon, Theo, Thomas, Zena

---

## Response Format Guidelines

When answering questions:

1. **Be specific**: Use exact numbers from the data
2. **Include context**: Mention the time period
3. **Use names**: Display member names, not platform IDs
4. **Format well**: Use markdown tables for rankings
5. **Acknowledge limits**: If data isn't available, say so

### Example Response Format

For "Who is the most active contributor?":

```
Based on the last 30 days:

**Top GitHub Contributors:**
| Rank | Member | Commits |
|------|--------|---------|
| 1 | Ale | 262 |
| 2 | Nam | 125 |
| 3 | Jake | 112 |

**Top Slack Users:**
| Rank | Member | Messages |
|------|--------|----------|
| 1 | Jake | 421 |
| 2 | Mehdi | 401 |
| 3 | Luca | 253 |

Ale leads in code contributions while Jake is most active in communication.
```

