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
  fragment ProjectFields on Project {
    id
    key
    name
    description
    slackChannel
    repositories
    isActive
  }
`;
