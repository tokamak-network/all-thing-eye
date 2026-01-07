"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { api as apiClient } from "@/lib/api";
import { useMembers, useProjects, useDeactivateMember, useReactivateMember } from "@/graphql/hooks";
import {
  UserGroupIcon,
  PlusIcon,
  PencilIcon,
  TrashIcon,
  XMarkIcon,
  UserMinusIcon,
  UserPlusIcon,
  UsersIcon,
  ArchiveBoxIcon,
} from "@heroicons/react/24/outline";

interface MemberIdentifiers {
  email?: string;
  github?: string;
  slack?: string;
  notion?: string;
  drive?: string;
  [key: string]: string | undefined;
}

interface Member {
  id: string;
  name: string;
  email: string;
  role?: string;
  project?: string;
  projectKeys?: string[];
  eoa_address?: string;
  recording_name?: string;
  identifiers: MemberIdentifiers;
  created_at?: string;
  updated_at?: string;
  isActive?: boolean;
  resignedAt?: string;
  resignationReason?: string;
}

interface MemberFormData {
  name: string;
  email: string;
  github_id?: string;
  slack_id?: string;
  notion_id?: string;
  role?: string;
  project?: string;
  projectKeys?: string[];
  eoa_address?: string;
  recording_name?: string;
  // Employment status (for edit modal)
  isActive?: boolean;
  resignationReason?: string;
}

type TabType = "active" | "inactive";

export default function MembersPage() {
  const router = useRouter();

  // Tab state
  const [activeTab, setActiveTab] = useState<TabType>("active");

  // GraphQL query for active members
  const { 
    data: activeData, 
    loading: activeLoading, 
    error: activeError, 
    refetch: refetchActive 
  } = useMembers({ includeInactive: false });

  // GraphQL query for inactive members (only fetch when on inactive tab)
  const { 
    data: inactiveData, 
    loading: inactiveLoading, 
    error: inactiveError, 
    refetch: refetchInactive 
  } = useMembers({ includeInactive: true });

  // GraphQL mutations for member status
  const [deactivateMember, { loading: deactivating }] = useDeactivateMember();
  const [reactivateMember, { loading: reactivating }] = useReactivateMember();

  // GraphQL query for projects
  const { data: projectsData } = useProjects({ isActive: true });
  const projects = useMemo(
    () => projectsData?.projects || [],
    [projectsData?.projects]
  );

  // Transform GraphQL members to local format
  const transformMembers = (gqlMembers: any[]): Member[] => {
    return gqlMembers.map((gqlMember) => ({
      id: gqlMember.id,
      name: gqlMember.name,
      email: gqlMember.email || "",
      role: gqlMember.role,
      project:
        gqlMember.projectKeys && gqlMember.projectKeys.length > 0
          ? gqlMember.projectKeys.join(", ")
          : gqlMember.team || "",
      projectKeys: gqlMember.projectKeys || [],
      eoa_address: gqlMember.eoaAddress,
      identifiers: {
        email: gqlMember.email,
        github: gqlMember.githubUsername,
        slack: gqlMember.slackId,
        notion: gqlMember.notionId,
      },
      isActive: gqlMember.isActive ?? true,
      resignedAt: gqlMember.resignedAt,
      resignationReason: gqlMember.resignationReason,
    }));
  };

  // Filter members by active status
  const activeMembers = useMemo(() => {
    const allMembers = transformMembers(activeData?.members || []);
    return allMembers.filter(m => m.isActive !== false);
  }, [activeData]);

  const inactiveMembers = useMemo(() => {
    const allMembers = transformMembers(inactiveData?.members || []);
    return allMembers.filter(m => m.isActive === false);
  }, [inactiveData]);

  const currentMembers = activeTab === "active" ? activeMembers : inactiveMembers;
  const loading = activeTab === "active" ? activeLoading : inactiveLoading;
  const error = activeTab === "active" ? activeError?.message : inactiveError?.message;

  // Refetch both queries
  const refetchAll = async () => {
    await Promise.all([refetchActive(), refetchInactive()]);
  };

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
    projectKeys: [],
    eoa_address: "",
    recording_name: "",
    isActive: true,
    resignationReason: "",
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
      projectKeys: [],
      eoa_address: "",
      recording_name: "",
      isActive: true,
      resignationReason: "",
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  // Open modal for editing existing member
  const openEditModal = (member: Member) => {
    setEditingMember(member);

    const getIdentifier = (source: string): string => {
      if (member.identifiers && member.identifiers[source]) {
        return member.identifiers[source];
      }
      if (source === "github" && member.identifiers?.username) {
        return member.identifiers.username;
      }
      if (source === "slack") {
        if (member.identifiers?.user_id) return member.identifiers.user_id;
        if (member.identifiers?.email) return member.identifiers.email;
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
      projectKeys: member.projectKeys || [],
      eoa_address: member.eoa_address || "",
      recording_name: member.recording_name || "",
      isActive: member.isActive ?? true,
      resignationReason: member.resignationReason || "",
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
      const submitData = {
        ...formData,
        projects: formData.projectKeys || [],
      };
      delete (submitData as any).projectKeys;
      delete (submitData as any).isActive;
      delete (submitData as any).resignationReason;

      if (editingMember) {
        // Check if status changed
        const wasActive = editingMember.isActive ?? true;
        const isNowActive = formData.isActive ?? true;

        // Update member data first
        await apiClient.updateMember(editingMember.id, submitData);

        // Handle status change via mutation
        if (wasActive && !isNowActive) {
          // Deactivating member
          await deactivateMember({
            variables: {
              memberId: editingMember.id,
              resignationReason: formData.resignationReason || undefined,
            },
          });
        } else if (!wasActive && isNowActive) {
          // Reactivating member
          await reactivateMember({
            variables: {
              memberId: editingMember.id,
            },
          });
        }
      } else {
        // Create new member
        await apiClient.createMember(submitData);
      }

      await refetchAll();
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

  // Handle quick reactivation from inactive tab
  const handleQuickReactivate = async (member: Member) => {
    if (!confirm(`${member.name}님을 재활성화하시겠습니까?`)) return;

    try {
      const result = await reactivateMember({
        variables: { memberId: member.id },
      });

      if (result.data?.reactivateMember.success) {
        await refetchAll();
      } else {
        alert(result.data?.reactivateMember.message || "Failed to reactivate member");
      }
    } catch (err: any) {
      console.error("Error reactivating member:", err);
      alert(err.message || "Failed to reactivate member");
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
      await apiClient.deleteMember(deletingMember.id);
      await refetchAll();
      closeDeleteDialog();
    } catch (err: any) {
      console.error("Error deleting member:", err);
      alert(err.response?.data?.detail || err.message || "Failed to delete member");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading && currentMembers.length === 0) {
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
        <div className="flex justify-between items-center mb-6">
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

        {/* Tabs */}
        <div className="border-b border-gray-200 mb-6">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab("active")}
              className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "active"
                  ? "border-blue-500 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
            >
              <UsersIcon className="h-5 w-5" />
              Active Members
              <span className={`ml-2 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                activeTab === "active" 
                  ? "bg-blue-100 text-blue-600" 
                  : "bg-gray-100 text-gray-600"
              }`}>
                {activeMembers.length}
              </span>
            </button>
            <button
              onClick={() => setActiveTab("inactive")}
              className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "inactive"
                  ? "border-gray-500 text-gray-700"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
            >
              <ArchiveBoxIcon className="h-5 w-5" />
              Inactive Members
              <span className={`ml-2 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                activeTab === "inactive" 
                  ? "bg-gray-200 text-gray-700" 
                  : "bg-gray-100 text-gray-600"
              }`}>
                {inactiveMembers.length}
              </span>
            </button>
          </nav>
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
                {activeTab === "inactive" && (
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Resigned
                  </th>
                )}
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {currentMembers.length === 0 ? (
                <tr>
                  <td
                    colSpan={activeTab === "inactive" ? 6 : 5}
                    className="px-6 py-12 text-center text-gray-500"
                  >
                    {activeTab === "active" 
                      ? 'No active members found. Click "Add Member" to create one.'
                      : "No inactive members."}
                  </td>
                </tr>
              ) : (
                currentMembers.map((member) => (
                  <tr 
                    key={member.id} 
                    className={`hover:bg-gray-50 ${activeTab === "inactive" ? "bg-gray-50" : ""}`}
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <button
                        onClick={() => router.push(`/members/${member.name}`)}
                        className={`text-sm font-medium hover:underline text-left ${
                          activeTab === "active"
                            ? "text-blue-600 hover:text-blue-800"
                            : "text-gray-600 hover:text-gray-800"
                        }`}
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
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {(() => {
                          let projectKeys: string[] = [];
                          if (member.projectKeys && member.projectKeys.length > 0) {
                            projectKeys = member.projectKeys;
                          } else if (member.project) {
                            projectKeys = member.project.split(",").map((p) => p.trim()).filter(Boolean);
                          }

                          // Filter to only show active projects
                          const activeProjectKeys = projectKeys.filter((pk) => 
                            projects.some((p) => p.key === pk)
                          );

                          if (activeProjectKeys.length > 0) {
                            return activeProjectKeys.map((projectKey, idx) => {
                              const project = projects.find((p) => p.key === projectKey);
                              return (
                                <span
                                  key={idx}
                                  className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                                >
                                  {project ? project.name : projectKey}
                                </span>
                              );
                            });
                          }
                          return <span className="text-sm text-gray-400">-</span>;
                        })()}
                      </div>
                    </td>
                    {activeTab === "inactive" && (
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div>
                          {member.resignedAt && (
                            <div className="text-sm text-gray-600">
                              {new Date(member.resignedAt).toLocaleDateString("ko-KR")}
                            </div>
                          )}
                          {member.resignationReason && (
                            <div className="text-xs text-gray-400 mt-0.5 max-w-[150px] truncate" title={member.resignationReason}>
                              {member.resignationReason}
                            </div>
                          )}
                        </div>
                      </td>
                    )}
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button
                        onClick={() => openEditModal(member)}
                        className="text-blue-600 hover:text-blue-900 mr-3"
                        title="Edit"
                      >
                        <PencilIcon className="h-5 w-5 inline" />
                      </button>
                      {activeTab === "inactive" && (
                        <button
                          onClick={() => handleQuickReactivate(member)}
                          className="text-green-600 hover:text-green-900 mr-3"
                          title="Reactivate"
                          disabled={reactivating}
                        >
                          <UserPlusIcon className="h-5 w-5 inline" />
                        </button>
                      )}
                      <button
                        onClick={() => openDeleteDialog(member)}
                        className="text-red-600 hover:text-red-900"
                        title="Delete"
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
          {activeTab === "active" 
            ? `${activeMembers.length} active member${activeMembers.length !== 1 ? "s" : ""}`
            : `${inactiveMembers.length} inactive member${inactiveMembers.length !== 1 ? "s" : ""}`}
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
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
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
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
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
                    onChange={(e) => setFormData({ ...formData, github_id: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="e.g. shinthom"
                  />
                </div>

                {/* Role */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Role
                  </label>
                  <select
                    value={formData.role}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="">Select a role</option>
                    <option value="Project Lead">Project Lead</option>
                    <option value="External Contributor">External Contributor</option>
                  </select>
                </div>

                {/* Project */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Projects
                  </label>
                  <div className="border border-gray-300 rounded-lg p-3 max-h-48 overflow-y-auto bg-white">
                    {projects.length > 0 ? (
                      <div className="space-y-2">
                        {projects.map((project) => {
                          const isSelected = (formData.projectKeys || []).includes(project.key);
                          return (
                            <label
                              key={project.key}
                              className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-2 rounded"
                            >
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={(e) => {
                                  const currentKeys = formData.projectKeys || [];
                                  if (e.target.checked) {
                                    setFormData({ ...formData, projectKeys: [...currentKeys, project.key] });
                                  } else {
                                    setFormData({ ...formData, projectKeys: currentKeys.filter((k) => k !== project.key) });
                                  }
                                }}
                                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                              />
                              <span className="text-sm text-gray-700">{project.name}</span>
                            </label>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-400 text-center py-2">No projects available</p>
                    )}
                  </div>
                  {formData.projectKeys && formData.projectKeys.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {formData.projectKeys.map((projectKey) => {
                        const project = projects.find((p) => p.key === projectKey);
                        return (
                          <span
                            key={projectKey}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                          >
                            {project ? project.name : projectKey}
                            <button
                              type="button"
                              onClick={() => {
                                setFormData({
                                  ...formData,
                                  projectKeys: (formData.projectKeys || []).filter((k) => k !== projectKey),
                                });
                              }}
                              className="text-blue-600 hover:text-blue-800"
                            >
                              ×
                            </button>
                          </span>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* EOA Address */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    EOA Address
                  </label>
                  <input
                    type="text"
                    value={formData.eoa_address}
                    onChange={(e) => setFormData({ ...formData, eoa_address: e.target.value })}
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
                    onChange={(e) => setFormData({ ...formData, recording_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="e.g. YEONGJU BAK for Zena"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Name displayed in meeting recordings (if different from display name)
                  </p>
                </div>

                {/* Employment Status Section - Only for editing existing members */}
                {editingMember && (
                  <div className="border-t border-gray-200 pt-4 mt-6">
                    <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                      <UserMinusIcon className="h-5 w-5 text-gray-500" />
                      Employment Status
                    </h3>
                    
                    {/* Status Toggle */}
                    <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div>
                        <div className="font-medium text-gray-900">
                          {formData.isActive ? "Active" : "Inactive (Resigned)"}
                        </div>
                        <div className="text-sm text-gray-500">
                          {formData.isActive 
                            ? "Member is currently active" 
                            : "Member has been marked as resigned"}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setFormData({ ...formData, isActive: !formData.isActive })}
                        className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                          formData.isActive ? "bg-green-500" : "bg-gray-300"
                        }`}
                      >
                        <span
                          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                            formData.isActive ? "translate-x-5" : "translate-x-0"
                          }`}
                        />
                      </button>
                    </div>

                    {/* Resignation Reason - Only show when inactive */}
                    {!formData.isActive && (
                      <div className="mt-3">
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Resignation Reason (optional)
                        </label>
                        <textarea
                          value={formData.resignationReason}
                          onChange={(e) => setFormData({ ...formData, resignationReason: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                          rows={2}
                          placeholder="e.g., Left for another opportunity"
                        />
                        {editingMember.resignedAt && (
                          <p className="mt-1 text-xs text-gray-500">
                            Resigned on: {new Date(editingMember.resignedAt).toLocaleDateString("ko-KR")}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Modal Footer */}
              <div className="flex justify-end gap-3 mt-6 pt-6 border-t border-gray-200">
                <button
                  type="button"
                  onClick={closeModal}
                  disabled={submitting || deactivating || reactivating}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || deactivating || reactivating}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {submitting || deactivating || reactivating
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
              Are you sure you want to delete <strong>{deletingMember.name}</strong>? 
              This action cannot be undone.
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
