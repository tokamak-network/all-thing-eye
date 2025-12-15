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
