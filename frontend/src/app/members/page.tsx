"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api as apiClient } from "@/lib/api";
import { useMembers } from "@/graphql/hooks";
import {
  UserGroupIcon,
  PlusIcon,
  PencilIcon,
  TrashIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";

interface MemberIdentifiers {
  email?: string;
  github?: string;
  slack?: string;
  notion?: string;
  drive?: string;
  [key: string]: string | undefined; // Allow other source types
}

interface Member {
  id: string;
  name: string;
  email: string;
  role?: string;
  project?: string;
  eoa_address?: string;
  recording_name?: string;
  identifiers: MemberIdentifiers;
  created_at?: string;
  updated_at?: string;
}

interface MemberFormData {
  name: string;
  email: string;
  github_id?: string;
  slack_id?: string;
  notion_id?: string;
  role?: string;
  project?: string;
  eoa_address?: string;
  recording_name?: string;
}

export default function MembersPage() {
  const router = useRouter();

  // GraphQL query for members (READ operation)
  const { data, loading, error: graphqlError, refetch } = useMembers();

  // Transform GraphQL members to REST API format
  const members: Member[] = (data?.members || []).map((gqlMember) => ({
    id: gqlMember.id, // MongoDB ObjectId from GraphQL
    name: gqlMember.name,
    email: gqlMember.email || "",
    role: gqlMember.role,
    project: gqlMember.team, // GraphQL uses 'team' instead of 'project'
    eoa_address: gqlMember.eoaAddress, // Convert camelCase to snake_case
    identifiers: {
      email: gqlMember.email,
      github: gqlMember.githubUsername,
      slack: gqlMember.slackId,
      notion: gqlMember.notionId,
    },
  }));

  const error = graphqlError?.message || null;
  
  // Modal states
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [editingMember, setEditingMember] = useState<Member | null>(null);
  const [deletingMember, setDeletingMember] = useState<Member | null>(null);
  
  // Form states
  const [formData, setFormData] = useState<MemberFormData>({
    name: "",
    email: "",
    github_id: "",
    slack_id: "",
    notion_id: "",
    role: "",
    project: "",
    eoa_address: "",
    recording_name: "",
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Open modal for creating new member
  const openCreateModal = () => {
    setEditingMember(null);
    setFormData({
      name: "",
      email: "",
      github_id: "",
      slack_id: "",
      notion_id: "",
      role: "",
      project: "",
      eoa_address: "",
      recording_name: "",
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  // Open modal for editing existing member
  const openEditModal = (member: Member) => {
    setEditingMember(member);
    
    // Extract identifiers - handle both old format (identifier_type keys) and new format (source keys)
    const getIdentifier = (source: string): string => {
      // Try source key first (new format: github, slack, notion, drive)
      if (member.identifiers && member.identifiers[source]) {
        return member.identifiers[source];
      }
      // Fallback to old format keys (identifier_type)
      if (source === "github" && member.identifiers?.username) {
        return member.identifiers.username;
      }
      if (source === "slack") {
        if (member.identifiers?.user_id) {
          return member.identifiers.user_id;
        }
        if (member.identifiers?.email) {
          return member.identifiers.email;
        }
      }
      if (source === "notion" && member.identifiers?.email) {
        return member.identifiers.email;
      }
      return "";
    };
    
    setFormData({
      name: member.name,
      email: member.email,
      github_id: getIdentifier("github"),
      slack_id: getIdentifier("slack"),
      notion_id: getIdentifier("notion"),
      role: member.role || "",
      project: member.project || "",
      eoa_address: member.eoa_address || "",
      recording_name: member.recording_name || "",
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  // Close modal
  const closeModal = () => {
    setIsModalOpen(false);
    setEditingMember(null);
    setFormError(null);
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);

    try {
      if (editingMember) {
        // Update existing member (REST API - mutations not implemented yet)
        await apiClient.updateMember(editingMember.id, formData);
      } else {
        // Create new member (REST API - mutations not implemented yet)
        await apiClient.createMember(formData);
      }
      
      // Refetch members from GraphQL
      await refetch();
      closeModal();
    } catch (err: any) {
      console.error("Error saving member:", err);
      setFormError(
        err.response?.data?.detail || err.message || "Failed to save member"
      );
    } finally {
      setSubmitting(false);
    }
  };

  // Open delete confirmation dialog
  const openDeleteDialog = (member: Member) => {
    setDeletingMember(member);
    setIsDeleteDialogOpen(true);
  };

  // Close delete confirmation dialog
  const closeDeleteDialog = () => {
    setIsDeleteDialogOpen(false);
    setDeletingMember(null);
  };

  // Handle member deletion
  const handleDelete = async () => {
    if (!deletingMember) return;

    setSubmitting(true);
    try {
      // Delete member (REST API - mutations not implemented yet)
      await apiClient.deleteMember(deletingMember.id);

      // Refetch members from GraphQL
      await refetch();
      closeDeleteDialog();
    } catch (err: any) {
      console.error("Error deleting member:", err);
      // Note: GraphQL error state is separate, this sets local error for delete operation
      alert(
        err.response?.data?.detail || err.message || "Failed to delete member"
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading members...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <UserGroupIcon className="h-8 w-8 text-blue-600" />
              Team Members
            </h1>
            <p className="text-gray-600 mt-2">
              Manage team members and their platform identifiers
            </p>
          </div>
          <button
            onClick={openCreateModal}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <PlusIcon className="h-5 w-5" />
            Add Member
          </button>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        {/* Members Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  GitHub
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Role
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Project
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {members.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-6 py-12 text-center text-gray-500"
                  >
                    No members found. Click &quot;Add Member&quot; to create
                    one.
                  </td>
                </tr>
              ) : (
                members.map((member) => (
                  <tr key={member.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <button
                        onClick={() => router.push(`/members/${member.name}`)}
                        className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline text-left"
                      >
                        {member.name}
                      </button>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {member.identifiers.github ? (
                        <a
                          href={`https://github.com/${member.identifiers.github}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-blue-600 hover:text-blue-800"
                        >
                          {member.identifiers.github}
                        </a>
                      ) : (
                        <span className="text-sm text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {member.role ? (
                        <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                          {member.role}
                        </span>
                      ) : (
                        <span className="text-sm text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-600">
                        {member.project || "-"}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button
                        onClick={() => openEditModal(member)}
                        className="text-blue-600 hover:text-blue-900 mr-4"
                      >
                        <PencilIcon className="h-5 w-5 inline" />
                      </button>
                      <button
                        onClick={() => openDeleteDialog(member)}
                        className="text-red-600 hover:text-red-900"
                      >
                        <TrashIcon className="h-5 w-5 inline" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Member count */}
        <div className="mt-4 text-sm text-gray-600">
          Total: {members.length} member{members.length !== 1 ? "s" : ""}
        </div>
      </div>

      {/* Add/Edit Member Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex justify-between items-center p-6 border-b border-gray-200">
              <h2 className="text-xl font-bold text-gray-900">
                {editingMember ? "Edit Member" : "Add New Member"}
              </h2>
              <button
                onClick={closeModal}
                className="text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>

            {/* Modal Body */}
            <form onSubmit={handleSubmit} className="p-6">
              {formError && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
                  {formError}
                </div>
              )}

              <div className="space-y-4">
                {/* Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) =>
                      setFormData({ ...formData, name: e.target.value })
                    }
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="e.g. Thomas"
                  />
                </div>

                {/* Email */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) =>
                      setFormData({ ...formData, email: e.target.value })
                    }
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="e.g. thomas@tokamak.network"
                  />
                </div>

                {/* GitHub ID */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    GitHub ID
                  </label>
                  <input
                    type="text"
                    value={formData.github_id}
                    onChange={(e) =>
                      setFormData({ ...formData, github_id: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="e.g. shinthom"
                  />
                </div>

                {/* Slack ID */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Slack ID
                  </label>
                  <input
                    type="text"
                    value={formData.slack_id}
                    onChange={(e) =>
                      setFormData({ ...formData, slack_id: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="e.g. thomas@tokamak.network or U12345678"
                  />
                </div>

                {/* Notion ID */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Notion ID
                  </label>
                  <input
                    type="text"
                    value={formData.notion_id}
                    onChange={(e) =>
                      setFormData({ ...formData, notion_id: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="e.g. thomas@tokamak.network"
                  />
                </div>

                {/* Role */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Role
                  </label>
                  <input
                    type="text"
                    value={formData.role}
                    onChange={(e) =>
                      setFormData({ ...formData, role: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="e.g. Developer, Project Lead"
                  />
                </div>

                {/* Project */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Project
                  </label>
                  <input
                    type="text"
                    value={formData.project}
                    onChange={(e) =>
                      setFormData({ ...formData, project: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="e.g. project-ooo, project-eco"
                  />
                </div>

                {/* EOA Address */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    EOA Address
                  </label>
                  <input
                    type="text"
                    value={formData.eoa_address}
                    onChange={(e) =>
                      setFormData({ ...formData, eoa_address: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
                    placeholder="e.g. 0x7f88539538ae808e45e23ff6c2b897d062616c4e"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Ethereum address for All-Thing-Eye beta access
                  </p>
                </div>

                {/* Recording Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Recording Name
                  </label>
                  <input
                    type="text"
                    value={formData.recording_name}
                    onChange={(e) =>
                      setFormData({ ...formData, recording_name: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="e.g. YEONGJU BAK for Zena"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Name displayed in meeting recordings (if different from display name)
                  </p>
                </div>
              </div>

              {/* Modal Footer */}
              <div className="flex justify-end gap-3 mt-6 pt-6 border-t border-gray-200">
                <button
                  type="button"
                  onClick={closeModal}
                  disabled={submitting}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {submitting
                    ? "Saving..."
                    : editingMember
                    ? "Update"
                    : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {isDeleteDialogOpen && deletingMember && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">
              Delete Member
            </h2>
            <p className="text-gray-600 mb-6">
              Are you sure you want to delete{" "}
              <strong>{deletingMember.name}</strong>? This action cannot be
              undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={closeDeleteDialog}
                disabled={submitting}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={submitting}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
