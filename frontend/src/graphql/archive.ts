/**
 * Archive GraphQL
 *
 * Queries, fragments, and hooks for the retired-members archive.
 */

import { gql } from "@apollo/client";
import { useQuery, QueryResult } from "@apollo/client";
import type {
  GetArchiveStatsVariables,
  GetArchiveStatsResponse,
  GetArchiveMembersVariables,
  GetArchiveMembersResponse,
  GetArchiveMemberVariables,
  GetArchiveMemberResponse,
  GetArchiveRecordingsVariables,
  GetArchiveRecordingsResponse,
} from "./types";

// ============================================
// Fragments
// ============================================

export const ARCHIVE_MEMBER_FRAGMENT = gql`
  fragment ArchiveMemberFields on ArchiveMember {
    memberKey
    memberName
    githubUsername
    realNameEn
    realNameKr
    emails
    status
    activeEra
    vaultTeams
    vaultRoles
    tierFinal
    totalCommits
    totalRepos
    artifactCount
    meetingCount
    firstSeen
    lastSeen
  }
`;

export const ARCHIVE_ARTIFACT_FRAGMENT = gql`
  fragment ArchiveArtifactFields on ArchiveArtifact {
    artifactId
    memberKey
    memberName
    source
    project
    date
    type
    title
    url
    scriptUrl
    role
    status
  }
`;

export const ARCHIVE_RECORDING_FRAGMENT = gql`
  fragment ArchiveRecordingFields on ArchiveRecording {
    fileId
    date
    category
    title
    owner
    mime
    sizeMb
    viewUrl
  }
`;

// ============================================
// Queries
// ============================================

export const GET_ARCHIVE_STATS = gql`
  query GetArchiveStats {
    archiveStats {
      members
      artifacts
      recordings
    }
  }
`;

export const GET_ARCHIVE_MEMBERS = gql`
  ${ARCHIVE_MEMBER_FRAGMENT}
  query GetArchiveMembers(
    $q: String
    $era: String
    $team: String
    $status: String
    $limit: Int
    $offset: Int
  ) {
    archiveMembers(
      q: $q
      era: $era
      team: $team
      status: $status
      limit: $limit
      offset: $offset
    ) {
      ...ArchiveMemberFields
    }
  }
`;

export const GET_ARCHIVE_MEMBER = gql`
  ${ARCHIVE_MEMBER_FRAGMENT}
  ${ARCHIVE_ARTIFACT_FRAGMENT}
  query GetArchiveMember($memberKey: String!) {
    archiveMember(memberKey: $memberKey) {
      member {
        ...ArchiveMemberFields
      }
      artifactCount
      artifacts {
        ...ArchiveArtifactFields
      }
      meetings {
        ...ArchiveArtifactFields
      }
    }
  }
`;

export const GET_ARCHIVE_RECORDINGS = gql`
  ${ARCHIVE_RECORDING_FRAGMENT}
  query GetArchiveRecordings($category: String, $q: String, $limit: Int, $offset: Int) {
    archiveRecordings(category: $category, q: $q, limit: $limit, offset: $offset) {
      ...ArchiveRecordingFields
    }
  }
`;

// ============================================
// Hooks
// ============================================

/**
 * Hook to fetch archive stats (totals for header display)
 */
export function useArchiveStats(): QueryResult<
  GetArchiveStatsResponse,
  GetArchiveStatsVariables
> {
  return useQuery<GetArchiveStatsResponse, GetArchiveStatsVariables>(
    GET_ARCHIVE_STATS,
    { fetchPolicy: "cache-and-network" }
  );
}

/**
 * Hook to fetch list of archive members with optional search/filters
 */
export function useArchiveMembers(
  variables?: GetArchiveMembersVariables
): QueryResult<GetArchiveMembersResponse, GetArchiveMembersVariables> {
  return useQuery<GetArchiveMembersResponse, GetArchiveMembersVariables>(
    GET_ARCHIVE_MEMBERS,
    {
      variables,
      fetchPolicy: "cache-and-network",
    }
  );
}

/**
 * Hook to fetch a single archive member detail
 */
export function useArchiveMember(
  variables: GetArchiveMemberVariables
): QueryResult<GetArchiveMemberResponse, GetArchiveMemberVariables> {
  return useQuery<GetArchiveMemberResponse, GetArchiveMemberVariables>(
    GET_ARCHIVE_MEMBER,
    {
      variables,
      skip: !variables.memberKey,
      fetchPolicy: "cache-and-network",
    }
  );
}

/**
 * Hook to fetch archive recordings
 */
export function useArchiveRecordings(
  variables?: GetArchiveRecordingsVariables
): QueryResult<GetArchiveRecordingsResponse, GetArchiveRecordingsVariables> {
  return useQuery<GetArchiveRecordingsResponse, GetArchiveRecordingsVariables>(
    GET_ARCHIVE_RECORDINGS,
    {
      variables,
      fetchPolicy: "cache-and-network",
    }
  );
}
