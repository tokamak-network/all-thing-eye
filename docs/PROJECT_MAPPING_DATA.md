프로젝트별 멤버 목록 - 각 프로젝트에 참여하는 팀원들
GitHub 리포지토리 - 각 프로젝트에서 사용하는 리포지토리 목록
Google Drive 폴더 - 프로젝트별 공유 폴더 이름
Notion Database ID (선택) - 프로젝트별 Notion 필터링이 필요한 경우

# Project Mapping Data Collection

This document is used to collect project-specific mapping data for the Custom Export feature.

---

## Instructions

Please fill in the data for each project. This data will be used to:

1. Filter activities by project in Custom Export
2. Generate project-specific reports
3. Map team members to their respective projects

---

## Project: OOO (Zero-Knowledge Proof)

### Basic Info

| Field        | Value                                                            |
| ------------ | ---------------------------------------------------------------- |
| Project Key  | `project-ooo`                                                    |
| Project Name | Project OOO                                                      |
| Lead         | Jake                                                             |
| Description  | Zero-knowledge proof implementation and synthesizer architecture |

### Slack

| Field        | Value         |
| ------------ | ------------- |
| Channel Name | `project-ooo` |
| Channel ID   | `C07JN9XR570` |

### GitHub Repositories

| Repository Name             | Description            |
| --------------------------- | ---------------------- |
| Tokamak-zk-EVM              | Main ZK EVM repository |
| tokamak-zk-evm-docs         | Documentation          |
| Tokamak-zkp-channel-manager | Channel manager        |
| _(add more if needed)_      |                        |

### Google Drive Folders

| Folder Name            | Purpose            |
| ---------------------- | ------------------ |
| Meet Recordings        | Meeting recordings |
| singapore core         | Core documents     |
| Project OOO            | Project files      |
| _(add more if needed)_ |                    |

### Notion

| Field          | Value                                      |
| -------------- | ------------------------------------------ |
| Database ID(s) | _(TBD - if filtering by Notion is needed)_ |
| Parent Page ID | _(TBD)_                                    |

### Team Members

| Member Name  | Role         |
| ------------ | ------------ |
| Jake         | Project Lead |
| _(add more)_ |              |
|              |              |
|              |              |

---

## Project: ECO (Ecosystem Development)

### Basic Info

| Field        | Value                                          |
| ------------ | ---------------------------------------------- |
| Project Key  | `project-eco`                                  |
| Project Name | Project ECO                                    |
| Lead         | Jason                                          |
| Description  | Ecosystem development and community engagement |

### Slack

| Field        | Value         |
| ------------ | ------------- |
| Channel Name | `project-eco` |
| Channel ID   | _(TBD)_       |

### GitHub Repositories

| Repository Name        | Description |
| ---------------------- | ----------- |
| ecosystem-hub          |             |
| grants-program         |             |
| community-portal       |             |
| _(add more if needed)_ |             |

### Google Drive Folders

| Folder Name | Purpose |
| ----------- | ------- |
| _(TBD)_     |         |

### Notion

| Field          | Value   |
| -------------- | ------- |
| Database ID(s) | _(TBD)_ |
| Parent Page ID | _(TBD)_ |

### Team Members

| Member Name  | Role         |
| ------------ | ------------ |
| Jason        | Project Lead |
| _(add more)_ |              |
|              |              |

---

## Project: SYB (Sybil)

### Basic Info

| Field        | Value         |
| ------------ | ------------- |
| Project Key  | `project-syb` |
| Project Name | Project SYB   |
| Lead         | Jamie         |
| Description  | _(TBD)_       |

### Slack

| Field        | Value           |
| ------------ | --------------- |
| Channel Name | `project-sybil` |
| Channel ID   | _(TBD)_         |

### GitHub Repositories

| Repository Name | Description |
| --------------- | ----------- |
| _(TBD)_         |             |

### Google Drive Folders

| Folder Name | Purpose |
| ----------- | ------- |
| _(TBD)_     |         |

### Notion

| Field          | Value   |
| -------------- | ------- |
| Database ID(s) | _(TBD)_ |
| Parent Page ID | _(TBD)_ |

### Team Members

| Member Name  | Role         |
| ------------ | ------------ |
| Jamie        | Project Lead |
| _(add more)_ |              |
|              |              |

---

## Project: TRH

### Basic Info

| Field        | Value         |
| ------------ | ------------- |
| Project Key  | `project-trh` |
| Project Name | Project TRH   |
| Lead         | Praveen       |
| Description  | _(TBD)_       |

### Slack

| Field        | Value         |
| ------------ | ------------- |
| Channel Name | `project_trh` |
| Channel ID   | _(TBD)_       |

### GitHub Repositories

| Repository Name | Description |
| --------------- | ----------- |
| _(TBD)_         |             |

### Google Drive Folders

| Folder Name | Purpose |
| ----------- | ------- |
| _(TBD)_     |         |

### Notion

| Field          | Value   |
| -------------- | ------- |
| Database ID(s) | _(TBD)_ |
| Parent Page ID | _(TBD)_ |

### Team Members

| Member Name  | Role         |
| ------------ | ------------ |
| Praveen      | Project Lead |
| _(add more)_ |              |
|              |              |

---

## Project: DRB

### Basic Info

| Field        | Value         |
| ------------ | ------------- |
| Project Key  | `project-drb` |
| Project Name | Project DRB   |
| Lead         | _(TBD)_       |
| Description  | _(TBD)_       |

### Slack

| Field        | Value         |
| ------------ | ------------- |
| Channel Name | `project-drb` |
| Channel ID   | _(TBD)_       |

### GitHub Repositories

| Repository Name | Description |
| --------------- | ----------- |
| _(TBD)_         |             |

### Google Drive Folders

| Folder Name | Purpose |
| ----------- | ------- |
| _(TBD)_     |         |

### Notion

| Field          | Value   |
| -------------- | ------- |
| Database ID(s) | _(TBD)_ |
| Parent Page ID | _(TBD)_ |

### Team Members

| Member Name  | Role         |
| ------------ | ------------ |
| _(TBD)_      | Project Lead |
| _(add more)_ |              |
|              |              |

---

## How to Get IDs

### Slack Channel ID

Run this command in the project directory:

```bash
python scripts/get_slack_channels.py
```

### Notion Database ID

1. Open Notion database in browser
2. URL format: `https://notion.so/workspace/DATABASE_ID?v=...`
3. Extract the 32-character ID (add hyphens: 8-4-4-4-12 format)

### Google Drive Folder

Use the exact folder name as it appears in Google Drive.

---

## Data Format for config.yaml

Once filled, data will be added to `config/config.yaml`:

```yaml
projects:
  project-ooo:
    name: "Project OOO (Zero-Knowledge Proof)"
    slack_channel: "project-ooo"
    slack_channel_id: "C07JN9XR570"
    lead: "Jake"
    repositories:
      - "Tokamak-zk-EVM"
      - "tokamak-zk-evm-docs"
    drive_folders:
      - "Meet Recordings"
      - "Project OOO"
    notion_databases: []  # Add if needed
    members:
      - "Jake"
      - "Ale"
      # ... more members
    description: "Zero-knowledge proof implementation"
```

---

## Notes

- **Members**: List all team members who are actively working on this project
- **Repositories**: Only include repositories that are primarily for this project
- **Drive Folders**: Use exact folder names (case-sensitive)
- **Slack Channel ID**: Required for accurate Slack message filtering

---

**Last Updated**: _(Date)_
**Updated By**: _(Name)_
