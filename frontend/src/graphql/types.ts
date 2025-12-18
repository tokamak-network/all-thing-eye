/**
 * GraphQL Types
 *
 * TypeScript types for GraphQL schema.
 */

// Source type enum
export enum SourceType {
  GITHUB = "GITHUB",
  SLACK = "SLACK",
  NOTION = "NOTION",
  DRIVE = "DRIVE",
  RECORDINGS = "RECORDINGS",
  RECORDINGS_DAILY = "RECORDINGS_DAILY",
}

// Member type (GraphQL)
export interface Member {
  id: string;
  name: string;
  email?: string;
  role?: string;
  team?: string;
  githubUsername?: string;
  slackId?: string;
  notionId?: string;
  eoaAddress?: string;
  activityCount?: number;
  recentActivities?: Activity[];
}

// Activity type
export interface Activity {
  id: string;
  memberName: string;
  sourceType: string;
  activityType: string;
  timestamp: string;
  metadata: Record<string, any>; // JSON metadata field
  message?: string;
  repository?: string;
  url?: string;
}

// Activity summary type
export interface ActivitySummary {
  total: number;
  bySource: Record<string, number>;
  byType: Record<string, number>;
  dateRangeStart?: string;
  dateRangeEnd?: string;
}

// Project type
export interface Project {
  id: string;
  key: string;
  name: string;
  description?: string;
  slackChannel?: string;
  lead?: string;
  repositories: string[];
  isActive: boolean;
  memberCount?: number;
  members?: Member[];
}

// Query variables types
export interface GetMembersVariables {
  limit?: number;
}

export interface GetMemberVariables {
  name: string;
}

export interface GetActivitiesVariables {
  source?: SourceType;
  memberName?: string;
  startDate?: string;
  endDate?: string;
  keyword?: string;
  projectKey?: string;
  limit?: number;
  offset?: number;
}

export interface GetActivitySummaryVariables {
  source?: SourceType;
  memberName?: string;
  startDate?: string;
  endDate?: string;
}

export interface GetProjectsVariables {
  isActive?: boolean;
}

export interface GetProjectVariables {
  key: string;
}

export interface GetMembersWithActivitiesVariables {
  limit?: number;
  activityLimit?: number;
}

// Query response types
export interface GetMembersResponse {
  members: Member[];
}

export interface GetMemberResponse {
  member: Member | null;
}

export interface GetActivitiesResponse {
  activities: Activity[];
}

export interface GetActivitySummaryResponse {
  activitySummary: ActivitySummary;
}

export interface GetProjectsResponse {
  projects: Project[];
}

export interface GetProjectResponse {
  project: Project | null;
}

export interface GetMembersWithActivitiesResponse {
  members: Member[];
}

// Collaborator type
export interface Collaborator {
  memberName: string;
  collaborationCount: number;
  collaborationType: string;
  lastCollaboration?: string;
}

// Repository activity type
export interface RepositoryActivity {
  repository: string;
  commitCount: number;
  prCount: number;
  issueCount: number;
  lastActivity?: string;
  additions: number;
  deletions: number;
}

// Source stats type
export interface SourceStats {
  source: string;
  count: number;
  percentage: number;
}

// Weekly stats type
export interface WeeklyStats {
  weekStart: string;
  count: number;
}

// Activity stats type
export interface ActivityStats {
  totalActivities: number;
  bySource: SourceStats[];
  weeklyTrend: WeeklyStats[];
  last30Days: number;
}

// Member detail type (extended member with additional fields)
export interface MemberDetail extends Member {
  topCollaborators?: Collaborator[];
  activeRepositories?: RepositoryActivity[];
  activityStats?: ActivityStats;
}

// Query variables for member detail
export interface GetMemberDetailVariables {
  name: string;
}

// Query response for member detail
export interface GetMemberDetailResponse {
  member: MemberDetail;
}

// Collaboration detail type
export interface CollaborationDetail {
  source: string;
  activityCount: number;
  score: number;
  recentActivity?: string;
}

// Collaboration type (single collaborator relationship)
export interface Collaboration {
  collaboratorName: string;
  collaboratorId?: string;
  totalScore: number;
  collaborationDetails: CollaborationDetail[];
  commonProjects: string[];
  interactionCount: number;
  firstInteraction?: string;
  lastInteraction?: string;
}

// Collaboration network type (full network for a member)
export interface CollaborationNetwork {
  memberName: string;
  memberId?: string;
  topCollaborators: Collaboration[];
  totalCollaborators: number;
  timeRangeDays: number;
  totalScore: number;
  generatedAt: string;
}

// Query variables for member collaborations
export interface GetMemberCollaborationsVariables {
  name: string;
  days?: number;
  limit?: number;
  minScore?: number;
}

// Query response for member collaborations
export interface GetMemberCollaborationsResponse {
  memberCollaborations: CollaborationNetwork;
}
