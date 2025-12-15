/**
 * GraphQL Hooks
 *
 * Custom React hooks for GraphQL queries.
 */

import { useQuery, QueryResult } from "@apollo/client";
import {
  GET_MEMBERS,
  GET_MEMBER,
  GET_ACTIVITIES,
  GET_ACTIVITY_SUMMARY,
  GET_PROJECTS,
  GET_PROJECT,
  GET_MEMBERS_WITH_ACTIVITIES,
  GET_MEMBER_DETAIL,
} from "./queries";
import type {
  GetMembersVariables,
  GetMembersResponse,
  GetMemberVariables,
  GetMemberResponse,
  GetActivitiesVariables,
  GetActivitiesResponse,
  GetActivitySummaryVariables,
  GetActivitySummaryResponse,
  GetProjectsVariables,
  GetProjectsResponse,
  GetProjectVariables,
  GetProjectResponse,
  GetMembersWithActivitiesVariables,
  GetMembersWithActivitiesResponse,
  GetMemberDetailVariables,
  GetMemberDetailResponse,
} from "./types";

/**
 * Hook to fetch all members
 */
export function useMembers(
  variables?: GetMembersVariables
): QueryResult<GetMembersResponse, GetMembersVariables> {
  return useQuery<GetMembersResponse, GetMembersVariables>(GET_MEMBERS, {
    variables,
  });
}

/**
 * Hook to fetch a single member
 */
export function useMember(
  variables: GetMemberVariables
): QueryResult<GetMemberResponse, GetMemberVariables> {
  return useQuery<GetMemberResponse, GetMemberVariables>(GET_MEMBER, {
    variables,
    skip: !variables.name,
  });
}

/**
 * Hook to fetch activities
 */
export function useActivities(
  variables?: GetActivitiesVariables
): QueryResult<GetActivitiesResponse, GetActivitiesVariables> {
  return useQuery<GetActivitiesResponse, GetActivitiesVariables>(
    GET_ACTIVITIES,
    {
      variables,
      fetchPolicy: "network-only", // Always fetch fresh data for activities
    }
  );
}

/**
 * Hook to fetch activity summary
 */
export function useActivitySummary(
  variables?: GetActivitySummaryVariables
): QueryResult<GetActivitySummaryResponse, GetActivitySummaryVariables> {
  return useQuery<GetActivitySummaryResponse, GetActivitySummaryVariables>(
    GET_ACTIVITY_SUMMARY,
    {
      variables,
    }
  );
}

/**
 * Hook to fetch projects
 */
export function useProjects(
  variables?: GetProjectsVariables
): QueryResult<GetProjectsResponse, GetProjectsVariables> {
  return useQuery<GetProjectsResponse, GetProjectsVariables>(GET_PROJECTS, {
    variables,
  });
}

/**
 * Hook to fetch a single project
 */
export function useProject(
  variables: GetProjectVariables
): QueryResult<GetProjectResponse, GetProjectVariables> {
  return useQuery<GetProjectResponse, GetProjectVariables>(GET_PROJECT, {
    variables,
    skip: !variables.key,
  });
}

/**
 * Hook to fetch members with their recent activities
 */
export function useMembersWithActivities(
  variables?: GetMembersWithActivitiesVariables
): QueryResult<
  GetMembersWithActivitiesResponse,
  GetMembersWithActivitiesVariables
> {
  return useQuery<
    GetMembersWithActivitiesResponse,
    GetMembersWithActivitiesVariables
  >(GET_MEMBERS_WITH_ACTIVITIES, {
    variables,
  });
}

/**
 * Hook to fetch member detail with collaboration and repository data
 */
export function useMemberDetail(
  variables: GetMemberDetailVariables
): QueryResult<GetMemberDetailResponse, GetMemberDetailVariables> {
  return useQuery<GetMemberDetailResponse, GetMemberDetailVariables>(
    GET_MEMBER_DETAIL,
    {
      variables,
      // Skip if name is empty
      skip: !variables.name,
    }
  );
}
