# Collaboration Network Scoring System

## 📋 Overview

The Collaboration Network feature calculates collaboration scores between team members based on their interactions across multiple platforms (GitHub, Slack, Meeting recordings). This document explains how collaboration scores are calculated and weighted.

---

## 🎯 Core Concept

**Collaboration Score** = Base Weight × Recency Multiplier

Each interaction between two members contributes to their total collaboration score. More recent interactions receive higher scores due to the recency multiplier.

---

## ⚖️ Collaboration Weights by Activity Type

### GitHub Collaborations

| Activity Type | Base Weight | Description |
|--------------|-------------|-------------|
| **GitHub PR Review** | 3.0 | When one member reviews another's pull request |
| **GitHub Issue Discussion** | 1.5 | When members interact in issue comments |
| **GitHub PR Co-commit** | 2.5 | When members commit to the same pull request |

**Example:**
- Ale reviews Jake's PR → Jake gets +3.0 collaboration score with Ale
- Jake comments on Ale's issue → Jake gets +1.5 collaboration score with Ale

---

### Slack Collaborations

| Activity Type | Base Weight | Description |
|--------------|-------------|-------------|
| **Slack Thread Participation** | 2.0 | When members participate in the same thread |
| **Slack Direct Mention** | 1.5 | When one member mentions another |
| **Slack Channel Collaboration** | 1.0 | When members are active in the same channel |

**Example:**
- Ale and Jake both reply in a Slack thread → Both get +2.0 collaboration score with each other
- Jake mentions Ale in a message → Jake gets +1.5 collaboration score with Ale

---

### Meeting Collaborations

| Activity Type | Base Weight | Description |
|--------------|-------------|-------------|
| **Meeting Co-attendance** | 2.2 | When members attend the same meeting |

**Example:**
- Ale and Jake attend the same meeting → Both get +2.2 collaboration score with each other

---

## ⏰ Recency Multiplier

Recent interactions are valued more than older ones. The recency multiplier gradually decreases over time.

### Formula

```
recency_multiplier = max(0.3, 1.0 - (days_ago / 90))
```

### Recency Score Table

| Days Ago | Multiplier | Effective Score (PR Review 3.0×) |
|----------|------------|----------------------------------|
| 0-1 days | 1.00 | 3.00 |
| 7 days   | 0.92 | 2.76 |
| 15 days  | 0.83 | 2.49 |
| 30 days  | 0.67 | 2.01 |
| 45 days  | 0.50 | 1.50 |
| 60 days  | 0.33 | 0.99 |
| 90+ days | 0.30 | 0.90 |

**Key Points:**
- ✅ Interactions in the last week retain ~90%+ of their value
- ⚠️ After 30 days, score drops to ~67%
- 🔻 Minimum multiplier is 0.3 (even very old interactions count for something)

---

## 📊 Score Calculation Examples

### Example 1: Recent PR Review

**Scenario:**
- Ale reviews Jake's PR today
- Base weight: 3.0 (PR Review)
- Days ago: 0
- Recency multiplier: 1.0

**Calculation:**
```
Score = 3.0 × 1.0 = 3.0
```

---

### Example 2: One-Month-Old Slack Thread

**Scenario:**
- Ale and Jake participated in a Slack thread 30 days ago
- Base weight: 2.0 (Thread Participation)
- Days ago: 30
- Recency multiplier: max(0.3, 1.0 - 30/90) = 0.67

**Calculation:**
```
Score = 2.0 × 0.67 = 1.34
```

---

### Example 3: Multiple Interactions

**Scenario:**
- Ale reviews Jake's PR #1 (today): 3.0 × 1.0 = 3.0
- Ale reviews Jake's PR #2 (7 days ago): 3.0 × 0.92 = 2.76
- Ale and Jake in Slack thread (15 days ago): 2.0 × 0.83 = 1.66
- Ale and Jake in meeting (45 days ago): 2.2 × 0.50 = 1.10

**Total Collaboration Score:**
```
Total = 3.0 + 2.76 + 1.66 + 1.10 = 8.52
```

**Interaction Count:** 4

---

## 🔍 Query Parameters

### Default Settings

```graphql
query {
  memberCollaborations(
    name: "Ale",
    days: 90,        # Look back 90 days (default)
    limit: 10,       # Return top 10 collaborators (default)
    minScore: 1.0    # Minimum score threshold (default)
  )
}
```

### Parameter Descriptions

| Parameter | Default | Description |
|-----------|---------|-------------|
| `days` | 90 | Time range to analyze (in days) |
| `limit` | 10 | Maximum number of top collaborators to return |
| `minScore` | 1.0 | Minimum collaboration score threshold |

**Adjusting Parameters:**
- 📈 **Increase `days`** (e.g., 180) to see long-term collaborations
- 📉 **Decrease `days`** (e.g., 30) to focus on recent collaborations
- 🎯 **Lower `minScore`** (e.g., 0.5) to see more collaborators
- 🎯 **Raise `minScore`** (e.g., 5.0) to see only frequent collaborators

---

## 📈 Interpretation Guide

### Score Ranges

| Total Score | Collaboration Level | Typical Interaction Pattern |
|-------------|---------------------|----------------------------|
| 50+ | 🔥 **Very High** | Daily interactions, multiple PR reviews per week |
| 20-50 | 💪 **High** | Weekly interactions, regular PR reviews |
| 10-20 | ✅ **Moderate** | Bi-weekly interactions, occasional reviews |
| 5-10 | 👍 **Light** | Monthly interactions |
| 1-5 | 👋 **Minimal** | Sporadic interactions |
| < 1 | ⚪ **Rare** | Very infrequent or old interactions |

### Example Interpretations

**Scenario 1: Ale → Jake (Score: 18.0, 6 interactions)**
- 6 PR reviews over 90 days
- Average: ~1 review every 2 weeks
- **Interpretation:** Consistent code review collaboration, high trust relationship

**Scenario 2: Ale → Mehdi (Score: 45.5, 23 interactions)**
- Mix of Slack threads (15), PR reviews (5), meetings (3)
- **Interpretation:** Multi-channel collaboration, working closely together

**Scenario 3: Ale → Aamir (Score: 2.1, 1 interaction)**
- 1 Slack thread participation 60 days ago
- **Interpretation:** Minimal recent collaboration, might be on different projects

---

## 🎓 Best Practices

### For Team Leads

1. **Identify Key Collaborators**: Look for high scores (20+) to understand who works closely together
2. **Spot Silos**: Very low scores between team members might indicate communication gaps
3. **Project Transitions**: When assigning new projects, consider existing collaboration patterns
4. **Knowledge Transfer**: High collaboration scores suggest good candidates for knowledge sharing

### For Individual Contributors

1. **Understand Your Network**: See who you collaborate with most
2. **Expand Reach**: Low scores with certain team members might indicate opportunities to collaborate more
3. **Track Engagement**: Monitor how your collaboration patterns change over time

### For Engineering Managers

1. **Code Review Distribution**: Check if PR reviews are concentrated or well-distributed
2. **Cross-Team Collaboration**: Track collaboration across different project teams
3. **Onboarding**: New members should show increasing collaboration scores over time

---

## 🔧 Technical Implementation

### Data Sources

1. **GitHub** (`github_pull_requests` collection)
   - Tracks PRs, reviews, and review comments
   - Maps GitHub usernames to member names via `member_identifiers`

2. **Slack** (`slack_messages` collection)
   - Tracks thread participation and mentions
   - Maps Slack user IDs to member names via `member_identifiers`

3. **Recordings** (`recordings_daily` collection)
   - Tracks meeting attendance
   - Maps meeting participants to member names

### GraphQL Schema

```graphql
type Collaboration {
  collaboratorName: String!
  totalScore: Float!
  interactionCount: Int!
  collaborationDetails: [CollaborationDetail!]!
  commonProjects: [String!]!
  firstInteraction: DateTime
  lastInteraction: DateTime
}

type CollaborationDetail {
  source: String!           # e.g., "github_pr_review", "slack_thread"
  activityCount: Int!       # Number of interactions of this type
  score: Float!             # Total score for this activity type
  recentActivity: DateTime  # Most recent interaction
}

type CollaborationNetwork {
  memberName: String!
  topCollaborators: [Collaboration!]!
  totalCollaborators: Int!
  timeRangeDays: Int!
  totalScore: Float!
}
```

---

## 📊 Sample GraphQL Response

```json
{
  "data": {
    "memberCollaborations": {
      "memberName": "Ale",
      "totalCollaborators": 5,
      "totalScore": 67.3,
      "timeRangeDays": 90,
      "topCollaborators": [
        {
          "collaboratorName": "Jake",
          "totalScore": 18.0,
          "interactionCount": 6,
          "collaborationDetails": [
            {
              "source": "github_pr_review",
              "activityCount": 6,
              "score": 18.0,
              "recentActivity": "2025-12-15T10:30:00Z"
            }
          ],
          "commonProjects": ["project-ooo"],
          "firstInteraction": "2025-10-10T14:20:00Z",
          "lastInteraction": "2025-12-15T10:30:00Z"
        },
        {
          "collaboratorName": "Mehdi",
          "totalScore": 24.5,
          "interactionCount": 12,
          "collaborationDetails": [
            {
              "source": "slack_thread",
              "activityCount": 8,
              "score": 14.8
            },
            {
              "source": "github_pr_review",
              "activityCount": 2,
              "score": 5.7
            },
            {
              "source": "meeting_participation",
              "activityCount": 2,
              "score": 4.0
            }
          ],
          "commonProjects": ["project-ooo", "project-eco"],
          "firstInteraction": "2025-09-20T09:00:00Z",
          "lastInteraction": "2025-12-10T16:45:00Z"
        }
      ]
    }
  }
}
```

---

## 🚀 Future Enhancements

### Potential Improvements

1. **Adaptive Weights**: Adjust weights based on project phase (e.g., higher weight for code reviews during feature development)
2. **Bidirectional Scores**: Differentiate between "gives reviews" vs "receives reviews"
3. **Sentiment Analysis**: Incorporate positivity/constructiveness of interactions
4. **Project-Specific Weights**: Different weights for different types of projects
5. **Time-of-Day Patterns**: Identify optimal collaboration times

### Metrics to Add

- **Response Time**: How quickly members respond to each other
- **Code Review Quality**: Length and depth of review comments
- **Knowledge Sharing**: Documentation contributions to shared projects
- **Mentorship**: Pattern of junior-senior collaborations

---

## 📞 Questions?

For questions or suggestions about the collaboration scoring system:

1. Review the backend implementation: `backend/graphql/queries.py`
2. Check the GraphQL schema: `backend/graphql/types.py`
3. Test queries in GraphQL Playground: `http://localhost:8000/graphql`

---

**Last Updated:** 2025-12-17  
**Version:** 1.0.0  
**Maintained by:** All-Thing-Eye Development Team

