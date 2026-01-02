# GraphQL Query Examples

This document contains working GraphQL query examples for the AI assistant.

## ⚠️ CRITICAL: Always Query BOTH GitHub AND Slack

For any "most active", "contributor", or general "activity" question, you MUST query BOTH sources.

---

## Example 1: Most Active Contributor (CORRECT)

**Question**: "Who is the most active contributor?"

```graphql
query MostActiveContributor {
  github: activities(source: GITHUB, startDate: "2025-12-01T00:00:00Z", limit: 300) {
    memberName
    sourceType
    timestamp
  }
  slack: activities(source: SLACK, startDate: "2025-12-01T00:00:00Z", limit: 300) {
    memberName
    sourceType
    timestamp
  }
}
```

**How to analyze the result:**
1. Count activities per member from `github` array
2. Count activities per member from `slack` array
3. **Add them together** for total activity
4. Rank by total

---

## Example 2: Last Month Activity (CORRECT)

**Question**: "지난 달 가장 활발한 멤버"

```graphql
query LastMonthActivity {
  github: activities(
    source: GITHUB
    startDate: "2025-12-01T00:00:00Z"
    endDate: "2025-12-31T23:59:59Z"
    limit: 500
  ) {
    memberName
    sourceType
    timestamp
  }
  slack: activities(
    source: SLACK
    startDate: "2025-12-01T00:00:00Z"
    endDate: "2025-12-31T23:59:59Z"
    limit: 500
  ) {
    memberName
    sourceType
    timestamp
  }
}
```

---

## Example 3: This Week Activity (CORRECT)

**Question**: "이번 주 활동 현황"

```graphql
query ThisWeekActivity {
  github: activities(
    source: GITHUB
    startDate: "2025-12-26T00:00:00Z"
    limit: 300
  ) {
    memberName
    sourceType
    timestamp
  }
  slack: activities(
    source: SLACK
    startDate: "2025-12-26T00:00:00Z"
    limit: 300
  ) {
    memberName
    sourceType
    timestamp
  }
}
```

---

## Example 4: Project Activity (CORRECT)

**Question**: "OOO 프로젝트 현황"

```graphql
query ProjectOOOActivity {
  github: activities(
    source: GITHUB
    projectKey: "project-ooo"
    startDate: "2025-12-01T00:00:00Z"
    limit: 200
  ) {
    memberName
    sourceType
    timestamp
  }
  slack: activities(
    source: SLACK
    projectKey: "project-ooo"
    startDate: "2025-12-01T00:00:00Z"
    limit: 200
  ) {
    memberName
    sourceType
    timestamp
  }
}
```

---

## Example 5: Specific Member Activity (CORRECT)

**Question**: "Jake's activity"

```graphql
query JakeActivity {
  github: activities(
    source: GITHUB
    memberName: "Jake"
    startDate: "2025-12-01T00:00:00Z"
    limit: 100
  ) {
    memberName
    sourceType
    timestamp
    metadata
  }
  slack: activities(
    source: SLACK
    memberName: "Jake"
    startDate: "2025-12-01T00:00:00Z"
    limit: 100
  ) {
    memberName
    sourceType
    timestamp
    metadata
  }
}
```

---

## Example 6: GitHub Only (When specifically asked)

**Question**: "Who has the most GitHub commits?"

```graphql
query GitHubCommits {
  activities(
    source: GITHUB
    startDate: "2025-12-01T00:00:00Z"
    limit: 300
  ) {
    memberName
    sourceType
    timestamp
  }
}
```

---

## Example 7: Slack Only (When specifically asked)

**Question**: "Slack 메시지가 가장 많은 사람"

```graphql
query SlackMessages {
  activities(
    source: SLACK
    startDate: "2025-12-01T00:00:00Z"
    limit: 300
  ) {
    memberName
    sourceType
    timestamp
  }
}
```

---

## ❌ WRONG Examples (DO NOT DO THIS)

### Wrong 1: Missing source
```graphql
# WRONG! Will include broken DRIVE data
query WrongQuery {
  activities(startDate: "2025-12-01T00:00:00Z", limit: 200) {
    memberName
  }
}
```

### Wrong 2: Only GitHub for "most active" question
```graphql
# WRONG! Must include Slack too
query WrongQuery {
  activities(source: GITHUB, startDate: "2025-12-01T00:00:00Z") {
    memberName
  }
}
```

### Wrong 3: Using old dates
```graphql
# WRONG! Using 2024 dates when current year is 2026
query WrongQuery {
  activities(source: GITHUB, startDate: "2024-01-01T00:00:00Z") {
    memberName
  }
}
```

---

## Summary

| Question Type | Sources to Query |
|---------------|------------------|
| "Most active", "contributor", "activity" | **BOTH** GitHub + Slack |
| "Commits", "code", "PR" | GitHub only |
| "Messages", "Slack", "communication" | Slack only |
| Project status | **BOTH** GitHub + Slack |
| Member activity | **BOTH** GitHub + Slack |

