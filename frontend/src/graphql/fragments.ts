/**
 * GraphQL Fragments
 *
 * Reusable fragments for GraphQL queries.
 */

import { gql } from "@apollo/client";

// Member fragment
export const MEMBER_FRAGMENT = gql`
  fragment MemberFields on Member {
    id
    name
    email
    role
    team
    githubUsername
    slackId
    notionId
    eoaAddress
    recordingName
    projectKeys
  }
`;

// Activity fragment
export const ACTIVITY_FRAGMENT = gql`
  fragment ActivityFields on Activity {
    id
    memberName
    sourceType
    activityType
    timestamp
    metadata
    message
    repository
    url
  }
`;

// Activity summary fragment
export const ACTIVITY_SUMMARY_FRAGMENT = gql`
  fragment ActivitySummaryFields on ActivitySummary {
    total
    bySource
    byType
    dateRangeStart
    dateRangeEnd
  }
`;

// Project fragment
export const PROJECT_FRAGMENT = gql`
  ${MEMBER_FRAGMENT}
  fragment ProjectFields on Project {
    id
    key
    name
    description
    slackChannel
    lead
    repositories
    isActive
    memberIds
    members {
      ...MemberFields
    }
  }
`;

// Collaborator fragment
export const COLLABORATOR_FRAGMENT = gql`
  fragment CollaboratorFields on Collaborator {
    memberName
    collaborationCount
    collaborationType
    lastCollaboration
  }
`;

// Repository activity fragment
export const REPOSITORY_ACTIVITY_FRAGMENT = gql`
  fragment RepositoryActivityFields on RepositoryActivity {
    repository
    commitCount
    prCount
    issueCount
    lastActivity
    additions
    deletions
  }
`;

// Activity stats fragment
export const ACTIVITY_STATS_FRAGMENT = gql`
  fragment ActivityStatsFields on ActivityStats {
    totalActivities
    bySource {
      source
      count
      percentage
    }
    weeklyTrend {
      weekStart
      count
    }
    last30Days
  }
`;

// Collaboration detail fragment
export const COLLABORATION_DETAIL_FRAGMENT = gql`
  fragment CollaborationDetailFields on CollaborationDetail {
    source
    activityCount
    score
    recentActivity
  }
`;

// Collaboration fragment (single collaborator)
export const COLLABORATION_FRAGMENT = gql`
  ${COLLABORATION_DETAIL_FRAGMENT}
  fragment CollaborationFields on Collaboration {
    collaboratorName
    collaboratorId
    totalScore
    collaborationDetails {
      ...CollaborationDetailFields
    }
    commonProjects
    interactionCount
    firstInteraction
    lastInteraction
  }
`;

// Collaboration network fragment (full network)
export const COLLABORATION_NETWORK_FRAGMENT = gql`
  ${COLLABORATION_FRAGMENT}
  fragment CollaborationNetworkFields on CollaborationNetwork {
    memberName
    memberId
    topCollaborators {
      ...CollaborationFields
    }
    totalCollaborators
    timeRangeDays
    totalScore
    generatedAt
  }
`;
