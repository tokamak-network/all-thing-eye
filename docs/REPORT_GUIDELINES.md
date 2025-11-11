# Team Activity Report Guidelines

This document defines the standards and requirements for generating team activity reports.

---

## 📋 Table of Contents

1. [Report Scope](#report-scope)
2. [Time Settings](#time-settings)
3. [Data Filtering](#data-filtering)
4. [Metrics and Evaluation](#metrics-and-evaluation)
5. [Formatting Standards](#formatting-standards)
6. [Project-Specific Configurations](#project-specific-configurations)

---

## 📊 Report Scope

### Channel-Based Scope

Reports are generated based on **Slack channel activity**. Only members who are active in the target channel during the reporting period should be included.

**Example:**
- For `project-ooo` report → Include only members active in `#project-ooo` Slack channel
- For `project-eco` report → Include only members active in `#project-eco` Slack channel

### Cross-Platform Data Integration

When integrating data from multiple sources (GitHub, Slack, etc.):

1. **Primary Scope**: Slack channel activity defines which members to include
2. **Secondary Data**: Include GitHub/other activities ONLY for members in scope
3. **Repository Filtering**: Include ONLY repositories relevant to the project (see [Data Filtering](#data-filtering))

---

## ⏰ Time Settings

### Timezone

**All timestamps must be in KST (Korea Standard Time, UTC+9)**

- Display times in reports: KST
- Database queries: Convert UTC to KST
- Date ranges: KST boundaries

### Reporting Period

**Weekly reports follow Friday-to-Thursday cycle:**

- **Start**: Friday 00:00:00 KST
- **End**: Thursday 23:59:59 KST

**Example:**
```
Week 44, 2025 (2025W44)
Period: 2025-10-31 00:00:00 KST ~ 2025-11-06 23:59:59 KST
```

### Date Range Parameters

When collecting data:
- Use `--last-week` for the most recently completed week
- Ensure GitHub and Slack data use **identical date ranges**

---

## 🔍 Data Filtering

### 1. Member Filtering

**Primary Filter: Slack Activity**
```
Include member IF:
  - Posted messages in target channel during reporting period, OR
  - Added reactions in target channel during reporting period, OR
  - Mentioned/tagged in target channel during reporting period
```

**Secondary Filter: GitHub Activity**
```
For each member in scope:
  - Include GitHub commits from project-related repositories
  - Include GitHub PRs from project-related repositories
  - Include GitHub issues from project-related repositories
  - EXCLUDE activities from non-project repositories
```

### 2. Repository Filtering

Members often work on multiple projects simultaneously. **Filter repositories by project relevance.**

**Implementation Methods:**

#### Option 1: Manual Repository List (Recommended)
Define project repositories in configuration:

```yaml
# config/config.yaml
projects:
  project-ooo:
    repositories:
      - tokamak-network/Tokamak-zk-EVM
      - tokamak-network/tokamak-zk-evm-docs
      - tokamak-network/Tokamak-zkp-channel-manager
    slack_channel: project-ooo
    
  project-eco:
    repositories:
      - tokamak-network/ecosystem-hub
      - tokamak-network/grants-program
    slack_channel: project-eco
```

#### Option 2: Repository Naming Convention
Filter by repository name patterns:

```
project-ooo → Include repos containing: "zk-evm", "zkp", "synthesizer"
project-eco → Include repos containing: "ecosystem", "grants", "community"
```

#### Option 3: Repository Tags/Topics
Use GitHub repository topics or internal tagging system.

### 3. Activity Filtering

**Include:**
- Direct contributions (commits, PRs, issues)
- Code reviews on project repositories
- Slack messages and threads
- Meaningful reactions (see weighting below)
- **Shared links and resources** (Figma, Notion, Google Drive, design files)
- **File uploads** (documents, images, designs, presentations)

**Exclude:**
- Bot activities
- Automated commits (CI/CD, dependabot, etc.)
- Spam or test messages
- Activities from non-project repositories

**Special Note for Non-Developer Roles:**
- Designers, PMs, and other non-developer roles may have limited GitHub activity
- Their contributions through Slack (links, files, design reviews) are equally valuable
- Ensure these contributions are captured and weighted appropriately

---

## 📈 Metrics and Evaluation

### Work-Life Balance

**❌ DO NOT use time-based metrics for work-life balance:**

- Team members are distributed globally (different timezones)
- Working hours vary by location and personal schedule
- "After-hours" is meaningless in a global remote team

**✅ ALTERNATIVE approaches:**
- Message frequency distribution (avoid burnout indicators)
- Response time patterns (optional, not scored)
- Workload volume (commit count, PR count)

### Contribution Weighting

When evaluating member contributions, use these relative weights:

| Activity Type | Weight | Rationale |
|--------------|--------|-----------|
| **Technical Contributions** | | |
| GitHub Commit | 1.0x | Core technical contribution |
| GitHub PR (merged) | 2.0x | Code review + integration effort |
| GitHub PR (open) | 1.5x | Work in progress, pending review |
| GitHub Issue (created) | 0.5x | Problem identification |
| Code Review Comment | 0.8x | Quality assurance contribution |
| **Communication Contributions** | | |
| Slack Message (substantive) | 0.3x | Communication and collaboration |
| Slack Thread Reply | 0.2x | Discussion participation |
| Slack Reaction | **0.1x** | **Low weight** - acknowledgment only |
| **Non-Developer Contributions** | | |
| Shared Link (Figma, Notion, etc.) | 0.5x | Resource sharing and documentation |
| File Upload (design, doc, etc.) | 0.8x | Deliverable contribution |
| Design Review/Feedback | 0.4x | Quality improvement input |
| Meeting Notes/Summary | 0.6x | Knowledge capture and sharing |

**Important Notes:**
- Reactions have **low weighting** as they indicate acknowledgment, not substantive contribution
- Quality over quantity: A single complex PR is worth more than many trivial commits
- Context matters: Adjust weights for project phases (e.g., documentation sprints, design reviews)
- **Non-developer roles** (designers, PMs, etc.) contribute primarily through Slack links, files, and communication
- Shared links to external tools (Figma, Notion, Google Drive) are valuable knowledge resources

### Key Performance Indicators (KPIs)

**Technical Metrics:**
- Commit count and code volume (additions/deletions)
- PR merge rate and review turnaround time
- Code quality indicators (test coverage if available)
- Issue resolution time

**Collaboration Metrics:**
- Cross-member interactions (PR reviews, mentions)
- Documentation contributions
- Knowledge sharing (threads, detailed explanations)
- Response times to questions/blockers

---

## 🎨 Formatting Standards

### Markdown Structure

```markdown
# Project {Name} - Weekly Activity Report
**Week {Number}, {Year} ({ISO Week})**

## 📅 Reporting Period
- **Start**: {Date} {Time} KST
- **End**: {Date} {Time} KST
- **Duration**: 7 days

## 📊 Executive Summary
{High-level overview with key metrics}

## 👥 Team Composition
{List of active members}

## 🔍 Detailed Analysis

### {Member Name}
**GitHub Contributions:**
- Commits: {count} ({additions}+ / {deletions}-)
- Pull Requests: {count}
- Issues: {count}

**Slack Activity:**
- Messages: {count}
- Reactions: {count}

**Key Achievements:**
- {Achievement with hyperlink to PR/issue}

## 📈 Team Statistics
{Aggregated metrics and trends}

## 🎯 Insights and Recommendations
{Actionable insights for team leads}
```

### Hyperlinks

**Always add hyperlinks for:**

1. **GitHub Repositories**
   ```markdown
   [tokamak-zk-EVM](https://github.com/tokamak-network/Tokamak-zk-EVM)
   ```

2. **Pull Requests**
   ```markdown
   PR [#131](https://github.com/tokamak-network/Tokamak-zk-EVM/pull/131): WASM verifier implementation
   ```

3. **Issues**
   ```markdown
   Issue [#42](https://github.com/tokamak-network/Tokamak-zk-EVM/issues/42): Memory leak in state sync
   ```

4. **Commits** (when highlighting specific changes)
   ```markdown
   Commit [`ff65a28`](https://github.com/tokamak-network/tokamak-zk-evm-docs/commit/ff65a28): Update L2 documentation
   ```

### Language and Tone

- **Language**: English for all reports (code, documentation, commit messages)
- **Tone**: Professional but friendly
- **Clarity**: Use bullet points, tables, and sections for readability
- **Objectivity**: Data-driven insights, avoid subjective judgments

---

## 🎯 Project-Specific Configurations

### Project-OOO

**Focus Areas:**
- Zero-knowledge proof implementation
- Synthesizer architecture
- State channel management
- WASM verifier development

**Key Repositories:**
- `tokamak-network/Tokamak-zk-EVM`
- `tokamak-network/tokamak-zk-evm-docs`
- `tokamak-network/Tokamak-zkp-channel-manager`

**Slack Channel:** `#project-ooo`

**Special Considerations:**
- High technical complexity → Value documentation PRs highly
- Cryptography focus → Prioritize code review thoroughness
- Multiple sub-components → Track cross-component contributions

---

### Project-ECO

**Focus Areas:**
- Ecosystem development
- Community engagement
- Developer grants
- Partnership programs

**Key Repositories:**
- `tokamak-network/ecosystem-hub`
- `tokamak-network/grants-program`

**Slack Channel:** `#project-eco`

---

### Project-SYB

**Focus Areas:**
- TBD (To Be Defined)

**Key Repositories:**
- TBD

**Slack Channel:** `#project-syb`

---

### Project-TRH

**Focus Areas:**
- TBD (To Be Defined)

**Key Repositories:**
- TBD

**Slack Channel:** `#project-trh`

---

## 🔄 Report Generation Workflow

### 1. Data Collection

```bash
# Collect GitHub data for last complete week
python tests/test_github_plugin.py --last-week

# Collect Slack data for specific channel
python tests/test_slack_plugin.py --last-week --channels {channel-name}
```

### 2. Verify Data Integrity

- Check member mapping is correct
- Ensure no duplicate activities (via `activity_id`)
- Verify date range matches across sources
- Confirm repository filtering is applied

### 3. Generate Report

Use SQL queries or reporting scripts to:
1. List active members from Slack channel
2. Aggregate GitHub activities for those members (filtered by repo)
3. Aggregate Slack activities
4. Apply contribution weights
5. Generate markdown report

### 4. Quality Check

**Before publishing, verify:**
- [ ] All members in scope are included
- [ ] No out-of-scope repositories appear
- [ ] All timestamps are in KST
- [ ] Hyperlinks work correctly
- [ ] Contribution weights are applied
- [ ] No work-life balance time-based metrics
- [ ] Language is English throughout
- [ ] Executive summary accurately reflects data

---

## 📋 Non-Developer Contribution Examples

### Examples of Valuable Non-Developer Contributions

**Designer (e.g., Monica)**:
- Shared Figma link to new UI mockups: 0.5x
- Uploaded final design files to Slack: 0.8x
- Provided design feedback on PR screenshots: 0.4x
- Posted meeting notes with design decisions: 0.6x
- **Total contribution**: Multiple valuable inputs tracked through Slack

**Product Manager**:
- Shared Notion roadmap document: 0.5x
- Uploaded requirements document: 0.8x
- Facilitated discussion with 15 messages: 15 × 0.3x = 4.5x
- Summarized sprint retrospective: 0.6x

**Technical Writer**:
- Shared Google Doc for review: 0.5x
- Posted draft documentation: 0.8x
- Provided copywriting feedback: 0.4x

### How to Track in Reports

For members without GitHub activity:

```markdown
### Monica (Designer)

**GitHub Contributions:**
- Commits: 0
- Pull Requests: 0
- Issues: 0

**Slack Activity:**
- Messages: 4
- Reactions: 0
- **Shared Links**: 2 (Figma designs, Notion docs)
- **File Uploads**: 1 (design mockup)

**Contribution Score**: 3.4
- Messages: 4 × 0.3 = 1.2
- Shared Links: 2 × 0.5 = 1.0
- File Upload: 1 × 0.8 = 0.8
- Design Review Comments: 2 × 0.4 = 0.4
- **Total**: 3.4 points

**Key Achievements:**
- 🎨 **UI Design**: Shared Figma mockup for L2 dashboard interface
- 📊 **Design System**: Updated design tokens in Notion
- 💬 **Active Collaboration**: Participated in design review discussions (4 messages)

**Impact**: Provided visual direction for upcoming features, ensuring consistent user experience
```

**Important**: Always highlight non-developer contributions explicitly, especially for roles like designers, PMs, and technical writers who may not have GitHub presence.

---

## 📝 Example Queries

### Get Active Slack Members for Period

```sql
SELECT DISTINCT m.name, m.email
FROM members m
JOIN member_activities ma ON m.id = ma.member_id
WHERE ma.source_type = 'slack'
  AND ma.activity_type IN ('message', 'reaction')
  AND json_extract(ma.metadata, '$.channel_id') = 'C06TY9X8XNQ'  -- project-ooo
  AND date(ma.timestamp) >= '2025-10-31'
  AND date(ma.timestamp) <= '2025-11-06'
ORDER BY m.name;
```

### Get GitHub Contributions for Members (with repo filter)

```sql
SELECT 
    m.name,
    COUNT(CASE WHEN ma.activity_type = 'github_commit' THEN 1 END) as commits,
    COUNT(CASE WHEN ma.activity_type = 'github_pull_request' THEN 1 END) as prs,
    SUM(CASE WHEN ma.activity_type = 'github_commit' 
        THEN json_extract(ma.metadata, '$.additions') ELSE 0 END) as additions
FROM members m
JOIN member_activities ma ON m.id = ma.member_id
WHERE ma.source_type = 'github'
  AND m.name IN (/* list of active Slack members */)
  AND json_extract(ma.metadata, '$.repository') IN (
      'Tokamak-zk-EVM',
      'tokamak-zk-evm-docs',
      'Tokamak-zkp-channel-manager'
  )
  AND date(ma.timestamp) >= '2025-10-31'
  AND date(ma.timestamp) <= '2025-11-06'
GROUP BY m.name;
```

---

## 🚀 Future Enhancements

**Planned improvements:**

1. **Automated Repository Mapping**
   - Use GitHub topics/labels
   - ML-based project classification
   - Automatic detection of project boundaries

2. **Advanced Metrics**
   - Code review quality scores
   - Bug fix vs feature ratio
   - Technical debt indicators
   - Collaboration network graphs

3. **Interactive Reports**
   - HTML/web-based dashboards
   - Drill-down capabilities
   - Trend visualizations
   - Comparative analysis tools

4. **AI-Powered Insights**
   - Automatic identification of blockers
   - Predictive analytics for sprint planning
   - Sentiment analysis from Slack messages
   - Code quality recommendations

---

## 📚 Related Documents

- [Database Schema Reference](./DATABASE_SCHEMA.md)
- [Slack Setup Guide](./SLACK_SETUP.md)
- [Project Rules](../README.md)
- [Members Configuration](../config/members.yaml)

---

## 📞 Questions or Feedback?

If you encounter issues or have suggestions for improving these guidelines:

1. Check existing documentation
2. Review example reports in `/reports/` directory
3. Consult with project leads
4. Update this document with improvements

---

**Last Updated:** 2025-11-11  
**Version:** 1.0.0  
**Maintained by:** All-Thing-Eye Development Team

