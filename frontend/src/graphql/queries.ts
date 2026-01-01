/**
 * GraphQL Queries
 *
 * GraphQL queries for All-Thing-Eye frontend.
 */

import { gql } from "@apollo/client";
import {
  MEMBER_FRAGMENT,
  ACTIVITY_FRAGMENT,
  ACTIVITY_SUMMARY_FRAGMENT,
  PROJECT_FRAGMENT,
  COLLABORATOR_FRAGMENT,
  REPOSITORY_ACTIVITY_FRAGMENT,
  ACTIVITY_STATS_FRAGMENT,
  COLLABORATION_NETWORK_FRAGMENT,
} from "./fragments";

// Get all members
export const GET_MEMBERS = gql`
  ${MEMBER_FRAGMENT}
  query GetMembers($limit: Int) {
    members(limit: $limit) {
      ...MemberFields
      activityCount
    }
  }
`;

// Get single member
export const GET_MEMBER = gql`
  ${MEMBER_FRAGMENT}
  ${ACTIVITY_FRAGMENT}
  query GetMember($name: String!) {
    member(name: $name) {
      ...MemberFields
      activityCount
      recentActivities(limit: 10) {
        ...ActivityFields
      }
    }
  }
`;

// Get activities
export const GET_ACTIVITIES = gql`
  ${ACTIVITY_FRAGMENT}
  query GetActivities(
    $source: SourceType
    $memberName: String
    $startDate: DateTime
    $endDate: DateTime
    $keyword: String
    $projectKey: String
    $limit: Int
    $offset: Int
  ) {
    activities(
      source: $source
      memberName: $memberName
      startDate: $startDate
      endDate: $endDate
      keyword: $keyword
      projectKey: $projectKey
      limit: $limit
      offset: $offset
    ) {
      ...ActivityFields
    }
  }
`;

// Get activity summary
export const GET_ACTIVITY_SUMMARY = gql`
  ${ACTIVITY_SUMMARY_FRAGMENT}
  query GetActivitySummary(
    $source: SourceType
    $memberName: String
    $startDate: DateTime
    $endDate: DateTime
  ) {
    activitySummary(
      source: $source
      memberName: $memberName
      startDate: $startDate
      endDate: $endDate
    ) {
      ...ActivitySummaryFields
    }
  }
`;

// Get projects
export const GET_PROJECTS = gql`
  ${PROJECT_FRAGMENT}
  ${MEMBER_FRAGMENT}
  query GetProjects($isActive: Boolean) {
    projects(isActive: $isActive) {
      ...ProjectFields
      memberCount
      members {
        ...MemberFields
      }
    }
  }
`;

// Get single project
export const GET_PROJECT = gql`
  ${PROJECT_FRAGMENT}
  ${MEMBER_FRAGMENT}
  query GetProject($key: String!) {
    project(key: $key) {
      ...ProjectFields
      memberCount
      members {
        ...MemberFields
      }
    }
  }
`;

// Get members with recent activities (for dashboard)
export const GET_MEMBERS_WITH_ACTIVITIES = gql`
  ${MEMBER_FRAGMENT}
  ${ACTIVITY_FRAGMENT}
  query GetMembersWithActivities($limit: Int, $activityLimit: Int) {
    members(limit: $limit) {
      ...MemberFields
      activityCount
      recentActivities(limit: $activityLimit) {
        ...ActivityFields
      }
    }
  }
`;

// Get member detail with collaboration and repository data
export const GET_MEMBER_DETAIL = gql`
  ${MEMBER_FRAGMENT}
  ${ACTIVITY_FRAGMENT}
  ${COLLABORATOR_FRAGMENT}
  ${REPOSITORY_ACTIVITY_FRAGMENT}
  ${ACTIVITY_STATS_FRAGMENT}
  query GetMemberDetail($name: String!) {
    member(name: $name) {
      ...MemberFields
      activityCount
      recentActivities(limit: 10) {
        ...ActivityFields
      }
      topCollaborators(limit: 10) {
        ...CollaboratorFields
      }
      activeRepositories(limit: 10) {
        ...RepositoryActivityFields
      }
      activityStats {
        ...ActivityStatsFields
      }
    }
  }
`;

// Get member collaboration network
export const GET_MEMBER_COLLABORATIONS = gql`
  ${COLLABORATION_NETWORK_FRAGMENT}
  query GetMemberCollaborations(
    $name: String!
    $days: Int
    $limit: Int
    $minScore: Float
  ) {
    memberCollaborations(
      name: $name
      days: $days
      limit: $limit
      minScore: $minScore
    ) {
      ...CollaborationNetworkFields
    }
  }
`;
