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
  recordingName?: string;
  projectKeys?: string[];
  projectDetails?: Project[];
  activityCount?: number;
  recentActivities?: Activity[];
  // Employment status fields
  isActive?: boolean;
  resignedAt?: string;
  resignationReason?: string;
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

// Grant report type
export interface GrantReport {
  id: string;
  title: string;
  year: number;
  quarter: number;
  driveUrl: string;
  fileName?: string;
  createdAt?: string;
}

// Project type
export interface Project {
  id: string;
  key: string;
  name: string;
  description?: string;
  slackChannel?: string;
  slackChannelId?: string;
  lead?: string;
  repositories: string[];
  isActive: boolean;
  memberIds: string[];
  memberCount?: number;
  members?: Member[];
  grantReports?: GrantReport[];
}

// Query variables types
export interface GetMembersVariables {
  limit?: number;
  includeInactive?: boolean;
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

// Mutation types

// Member update result
export interface MemberUpdateResult {
  success: boolean;
  message: string;
  member?: Member;
}

// Deactivate member mutation variables
export interface DeactivateMemberVariables {
  memberId: string;
  resignationReason?: string;
  resignedAt?: string;
}

// Reactivate member mutation variables
export interface ReactivateMemberVariables {
  memberId: string;
}

// Deactivate member mutation response
export interface DeactivateMemberResponse {
  deactivateMember: MemberUpdateResult;
}

// Reactivate member mutation response
export interface ReactivateMemberResponse {
  reactivateMember: MemberUpdateResult;
}

// ============================================
// Archive Types
// ============================================

export interface ArchiveStats {
  members: number;
  artifacts: number;
  recordings: number;
}

export interface ArchiveMember {
  memberKey: string;
  memberName: string;
  githubUsername?: string;
  realNameEn?: string;
  realNameKr?: string;
  emails: string[];
  status?: string;
  activeEra?: string;
  vaultTeams: string[];
  vaultRoles: string[];
  tierFinal?: string;
  totalCommits?: number;
  totalRepos?: number;
  artifactCount?: number;
  meetingCount?: number;
  firstSeen?: string;
  lastSeen?: string;
}

export interface ArchiveArtifact {
  artifactId: string;
  memberKey?: string;
  memberName?: string;
  source?: string;
  project?: string;
  date?: string;
  type?: string;
  title?: string;
  url?: string;
  scriptUrl?: string;
  role?: string;
  status?: string;
}

export interface ArchiveMemberDetail {
  member: ArchiveMember;
  artifactCount: number;
  artifacts: ArchiveArtifact[];
  meetings: ArchiveArtifact[];
}

export interface ArchiveRecording {
  fileId: string;
  date?: string;
  category?: string;
  title?: string;
  owner?: string;
  mime?: string;
  sizeMb?: number;
  viewUrl?: string;
}

// Archive query variables
export interface GetArchiveStatsVariables {}

export interface GetArchiveMembersVariables {
  q?: string;
  era?: string;
  team?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

export interface GetArchiveMemberVariables {
  memberKey: string;
}

export interface GetArchiveArtifactsVariables {
  member?: string;
  source?: string;
  project?: string;
  artifactType?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

export interface GetArchiveRecordingsVariables {
  category?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

// Archive query responses
export interface GetArchiveStatsResponse {
  archiveStats: ArchiveStats;
}

export interface GetArchiveMembersResponse {
  archiveMembers: ArchiveMember[];
}

export interface GetArchiveMemberResponse {
  archiveMember: ArchiveMemberDetail | null;
}

export interface GetArchiveArtifactsResponse {
  archiveArtifacts: ArchiveArtifact[];
}

export interface GetArchiveRecordingsResponse {
  archiveRecordings: ArchiveRecording[];
}
