/**
 * Type definitions for All-Thing-Eye
 */

export interface Member {
  id: number;
  name: string;
  email: string | null;
  created_at: string;
}

export interface MemberIdentifier {
  source_type: string;
  source_user_id: string;
}

export interface ActivitySummary {
  [source: string]: {
    [activityType: string]: {
      count: number;
      first_activity: string;
      last_activity: string;
    };
  };
}

export interface MemberDetail extends Member {
  identifiers: MemberIdentifier[];
  activity_summary: ActivitySummary;
}

export interface Activity {
  id: string;
  member_id: number;
  member_name: string;
  source_type: string;
  source: string; // Alias for source_type (used in filtering)
  activity_type: string;
  timestamp: string;
  metadata: Record<string, any>;
  activity_id: string | null;
}

export interface ActivityListResponse {
  total: number;
  activities: Activity[];
  filters: {
    source_type: string | null;
    activity_type: string | null;
    member_id: number | null;
    start_date: string | null;
    end_date: string | null;
    limit: number;
    offset: number;
  };
}

export interface Project {
  key: string;
  name: string;
  slack_channel: string;
  slack_channel_id: string;
  lead: string;
  repositories: string[];
  drive_folders?: string[];
  description: string;
}

export interface ProjectDetail {
  project: Project;
  statistics: {
    slack_activities: number;
    github_activities: number;
    google_drive_activities: number;
    active_members: Array<{
      name: string;
      email: string | null;
    }>;
  };
}

export interface MemberListResponse {
  total: number;
  members: Member[];
}

export interface ProjectListResponse {
  total: number;
  projects: Project[];
}

export interface ActivityTypesResponse {
  activity_types: {
    [source: string]: string[];
  };
}

export interface ActivitySummaryResponse {
  summary: {
    [source: string]: {
      total_activities: number;
      activity_types: {
        [activityType: string]: {
          count: number;
          unique_members: number;
          first_activity: string;
          last_activity: string;
        };
      };
    };
  };
  filters: {
    source_type: string | null;
    start_date: string | null;
    end_date: string | null;
  };
}

