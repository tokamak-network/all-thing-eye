/**
 * GraphQL Mutations
 *
 * GraphQL mutations for All-Thing-Eye frontend.
 */

import { gql } from "@apollo/client";
import { MEMBER_FRAGMENT } from "./fragments";

// Deactivate member (mark as resigned)
export const DEACTIVATE_MEMBER = gql`
  ${MEMBER_FRAGMENT}
  mutation DeactivateMember(
    $memberId: String!
    $resignationReason: String
    $resignedAt: DateTime
  ) {
    deactivateMember(
      memberId: $memberId
      resignationReason: $resignationReason
      resignedAt: $resignedAt
    ) {
      success
      message
      member {
        ...MemberFields
      }
    }
  }
`;

// Reactivate member
export const REACTIVATE_MEMBER = gql`
  ${MEMBER_FRAGMENT}
  mutation ReactivateMember($memberId: String!) {
    reactivateMember(memberId: $memberId) {
      success
      message
      member {
        ...MemberFields
      }
    }
  }
`;

