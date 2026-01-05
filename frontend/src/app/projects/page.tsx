"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import apiClient from "@/lib/api";
import { useProjects, useMembers } from "@/graphql/hooks";
import { getAuthSession, isAdmin } from "@/lib/auth";
import {
  PlusIcon,
  PencilIcon,
  TrashIcon,
  FolderIcon,
} from "@heroicons/react/24/outline";

interface Project {
  id: string;
  key: string;
  name: string;
  description?: string;
  slack_channel?: string;
  slack_channel_id?: string;
  lead?: string;
  repositories: string[];
  repositories_synced_at?: string;
  github_team_slug?: string;
  drive_folders: string[];
  notion_page_ids: string[];
  notion_parent_page_id?: string;
  sub_projects: string[];
  member_ids: string[];
  members?: Member[]; // Members from GraphQL
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface Member {
  id: string;
  name: string;
  email?: string;
  role?: string;
  eoa_address?: string;
}

interface ProjectListResponse {
  total: number;
  projects: Project[];
}

export default function ProjectsPage() {
  const router = useRouter();
  const [activeOnly, setActiveOnly] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  // GraphQL queries (READ operations)
  const {
    data: projectsData,
    loading,
    error: projectsError,
    refetch: refetchProjects,
  } = useProjects({ isActive: activeOnly });
  const { data: membersData } = useMembers({ limit: 1000 });

  // Transform GraphQL data to REST API format
  const projects = (projectsData?.projects || []).map((p) => ({
    id: p.id,
    key: p.key,
    name: p.name,
    description: p.description,
    slack_channel: p.slackChannel,
    slack_channel_id: p.slackChannelId,
    lead: p.lead,
    repositories: p.repositories || [],
    repositories_synced_at: undefined,
    github_team_slug: undefined,
    drive_folders: [],
    notion_page_ids: [],
    notion_parent_page_id: undefined,
    sub_projects: [],
    // Ensure member_ids are strings
    member_ids: (p.memberIds || []).map(id => String(id)),
    // Store members from GraphQL with normalized IDs
    members: (p.members || []).map(m => ({
      ...m,
      id: String(m.id)
    })),
    is_active: p.isActive,
    created_at: "",
    updated_at: "",
  }));

  const data = {
    total: projects.length,
    projects,
  };

  const error = projectsError?.message || localError;

  // Transform GraphQL members to REST API format
  const allMembers: Member[] = (membersData?.members || []).map((m) => ({
    id: m.id,
    name: m.name,
    email: m.email,
    role: m.role,
    eoa_address: m.eoaAddress,
  }));

  // Get current user from auth session
  const currentUser = useMemo(() => {
    const session = getAuthSession();
    if (!session) return null;
    
    // Find member by EOA address
    return allMembers.find(
      (m) => m.eoa_address?.toLowerCase() === session.address.toLowerCase()
    );
  }, [allMembers]);

  // Check if current user can edit projects
  const canEditProjects = useMemo(() => {
    const session = getAuthSession();
    
    // Admin can always edit
    if (session && isAdmin(session.address)) {
      return true;
    }
    
    if (!currentUser) return false;
    
    // Check if user is Project Lead or HR
    const role = currentUser.role?.toLowerCase() || "";
    const isProjectLead = role.includes("project lead");
    const isHR = role.includes("hr") || role.includes("human resource");
    
    return isProjectLead || isHR;
  }, [currentUser]);

  // Check if current user can edit specific project
  const canEditProject = useCallback((project: Project) => {
    const session = getAuthSession();
    
    // Admin can always edit all projects
    if (session && isAdmin(session.address)) {
      return true;
    }
    
    if (!currentUser) return false;
    
    // Check if user is Project Lead or HR
    const role = currentUser.role?.toLowerCase() || "";
    const isProjectLead = role.includes("project lead");
    const isHR = role.includes("hr") || role.includes("human resource");
    
    // If user is HR, can edit all projects
    if (isHR) return true;
    
    // If user is Project Lead, can edit if they are the lead of this project
    if (isProjectLead && project.lead) {
      return currentUser.name === project.lead;
    }
    
    return false;
  }, [currentUser]);

  // Form state
  const [formData, setFormData] = useState({
    key: "",
    name: "",
    description: "",
    lead: "",
    github_team_slug: "",
    slack_channel: "",
    repositories: [] as string[],
    drive_folders: [] as string[],
    notion_parent_page_id: "",
    member_ids: [] as string[],
    is_active: true,
  });

  const [newDriveFolder, setNewDriveFolder] = useState("");
  const [newNotionRoot, setNewNotionRoot] = useState("");
  const [memberSearchTerm, setMemberSearchTerm] = useState("");
  const [showMemberSelector, setShowMemberSelector] = useState(false);
  const [leadSearchTerm, setLeadSearchTerm] = useState("");
  const [showLeadSelector, setShowLeadSelector] = useState(false);

  function openCreateModal() {
    setEditingProject(null);
    setFormData({
      key: "",
      name: "",
      description: "",
      lead: "",
      github_team_slug: "",
      slack_channel: "",
      repositories: [],
      drive_folders: [],
      notion_parent_page_id: "",
      member_ids: [],
      is_active: true,
    });
    setNewDriveFolder("");
    setNewNotionRoot("");
    setShowCreateModal(true);
  }

  function openEditModal(project: Project) {
    setEditingProject(project);
    setFormData({
      key: project.key,
      name: project.name,
      description: project.description || "",
      lead: project.lead || "",
      github_team_slug: project.github_team_slug || "",
      slack_channel: project.slack_channel || "",
      repositories: project.repositories || [],
      drive_folders: project.drive_folders || [],
      notion_parent_page_id: project.notion_parent_page_id || "",
      member_ids: project.member_ids || [],
      is_active: project.is_active,
    });
    setNewDriveFolder("");
    setNewNotionRoot(project.notion_parent_page_id || "");
    setShowCreateModal(true);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      setLocalError(null);
      
      // Find Slack channel ID from channel name
      let slack_channel_id: string | undefined = undefined;
      if (formData.slack_channel && formData.slack_channel.trim()) {
        slack_channel_id = await apiClient.findSlackChannelId(formData.slack_channel);
        if (!slack_channel_id) {
          alert(`⚠️ Warning: Slack channel "${formData.slack_channel}" not found. Project will be saved without channel ID.`);
        }
      }
      
      if (editingProject) {
        // Update existing project (REST API - mutations not implemented yet)
        await apiClient.updateProject(editingProject.key, {
          name: formData.name,
          description: formData.description || undefined,
          lead: formData.lead || undefined,
          github_team_slug: formData.github_team_slug || undefined,
          slack_channel: formData.slack_channel || undefined,
          slack_channel_id: slack_channel_id,
          // repositories are automatically synced from GitHub Teams by data collector
          drive_folders: formData.drive_folders,
          notion_parent_page_id: formData.notion_parent_page_id || undefined,
          member_ids: formData.member_ids,
          is_active: formData.is_active,
        });
        
        // Show success message for update
        alert(`✅ Project "${formData.name}" has been updated successfully!`);
      } else {
        // Generate key from name: "Project OOO" -> "project-ooo"
        const generatedKey = formData.name
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-+|-+$/g, "");
        
        // Create new project (REST API - mutations not implemented yet)
        await apiClient.createProject({
          key: generatedKey,
          name: formData.name,
          description: formData.description || undefined,
          lead: formData.lead || undefined,
          github_team_slug: formData.github_team_slug || generatedKey,
          slack_channel: formData.slack_channel || undefined,
          slack_channel_id: slack_channel_id,
          // repositories are automatically synced from GitHub Teams by data collector
          drive_folders: formData.drive_folders,
          notion_parent_page_id: formData.notion_parent_page_id || undefined,
          member_ids: formData.member_ids,
          is_active: formData.is_active,
        });
        
        // Show success message for creation
        alert(`✅ Project "${formData.name}" has been created successfully!`);
      }
      setShowCreateModal(false);

      // Refetch projects from GraphQL
      await refetchProjects();
    } catch (err: any) {
      console.error("Error saving project:", err);
      setLocalError(
        err.response?.data?.detail || err.message || "Failed to save project"
      );
    }
  }

  async function handleDelete(projectKey: string) {
    if (
      !confirm(
        `Are you sure you want to delete project "${projectKey}"? This will deactivate the project.`
      )
    ) {
      return;
    }
    try {
      setLocalError(null);
      // Delete project (REST API - mutations not implemented yet)
      await apiClient.deleteProject(projectKey);

      // Refetch projects from GraphQL
      await refetchProjects();
    } catch (err: any) {
      console.error("Error deleting project:", err);
      setLocalError(
        err.response?.data?.detail || err.message || "Failed to delete project"
      );
    }
  }

  // Extract folder ID from Drive URL
  function extractDriveFolderId(urlOrId: string): string {
    const trimmed = urlOrId.trim();
    // If it's already just an ID (no slashes), return as is
    if (!trimmed.includes("/")) {
      return trimmed;
    }
    // Extract from URL: https://drive.google.com/drive/folders/FOLDER_ID
    const match = trimmed.match(/\/folders\/([a-zA-Z0-9_-]+)/);
    return match ? match[1] : trimmed;
  }

  // Extract page ID from Notion URL
  function extractNotionPageId(urlOrId: string): string {
    const trimmed = urlOrId.trim();
    // If it's already just an ID (32 hex chars, possibly with dashes), return as is
    if (/^[a-f0-9]{32}$/i.test(trimmed.replace(/-/g, ""))) {
      return trimmed.replace(/-/g, "");
    }
    // Extract from URL: https://www.notion.so/workspace/Page-Title-PAGE_ID
    // Notion URLs can have format: https://www.notion.so/[workspace]/[title]-[32-char-id]
    const match = trimmed.match(/([a-f0-9]{32})/i);
    return match ? match[1] : trimmed;
  }

  function addDriveFolder() {
    if (newDriveFolder.trim()) {
      const folderId = extractDriveFolderId(newDriveFolder);
      if (folderId && !formData.drive_folders.includes(folderId)) {
        setFormData({
          ...formData,
          drive_folders: [...formData.drive_folders, folderId],
        });
        setNewDriveFolder("");
      }
    }
  }

  function removeDriveFolder(index: number) {
    setFormData({
      ...formData,
      drive_folders: formData.drive_folders.filter((_, i) => i !== index),
    });
  }

  function updateNotionRoot() {
    if (newNotionRoot.trim()) {
      const pageId = extractNotionPageId(newNotionRoot);
      setFormData({
        ...formData,
        notion_parent_page_id: pageId,
      });
    } else {
      setFormData({
        ...formData,
        notion_parent_page_id: "",
      });
    }
  }

  function toggleMember(memberId: string) {
    setFormData({
      ...formData,
      member_ids: formData.member_ids.includes(memberId)
        ? formData.member_ids.filter((id) => id !== memberId)
        : [...formData.member_ids, memberId],
    });
  }

  // Filter members based on search term
  const filteredMembers = allMembers.filter(
    (member) =>
    member.name.toLowerCase().includes(memberSearchTerm.toLowerCase()) ||
    member.email?.toLowerCase().includes(memberSearchTerm.toLowerCase())
  );

  // Filter members for lead selection
  const filteredLeadMembers = allMembers.filter(
    (member) =>
    member.name.toLowerCase().includes(leadSearchTerm.toLowerCase()) ||
    member.email?.toLowerCase().includes(leadSearchTerm.toLowerCase())
  );

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
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
              <FolderIcon className="h-8 w-8 text-blue-600" />
              Projects Management
            </h1>
            <p className="text-gray-600 mt-2">
              Manage project configurations and settings
        </p>
      </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={activeOnly}
                onChange={(e) => setActiveOnly(e.target.checked)}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm text-gray-700">Active only</span>
            </label>
            {canEditProjects && (
              <button
                onClick={openCreateModal}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                <PlusIcon className="h-5 w-5" />
                Add Project
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        {/* Projects Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Project
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Lead
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Repositories
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
        {data?.projects.map((project) => (
                  <tr key={project.key} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <button
                          onClick={() =>
                            router.push(`/projects/${project.key}`)
                          }
                          className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline text-left"
                        >
                  {project.name}
                        </button>
                        <div className="text-sm text-gray-500">
                          {project.key}
                        </div>
                        {project.description && (
                          <div className="text-xs text-gray-400 mt-1 line-clamp-1">
                            {project.description}
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {project.lead || "-"}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">
                        {project.repositories.length} repos
                      </div>
                      {project.repositories_synced_at && (
                        <div className="text-xs text-gray-500">
                          Synced:{" "}
                          {new Date(
                            project.repositories_synced_at
                          ).toLocaleDateString()}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          project.is_active
                            ? "bg-green-100 text-green-800"
                            : "bg-gray-100 text-gray-800"
                        }`}
                      >
                        {project.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center justify-end gap-2">
                        {canEditProject(project) && (
                          <button
                            onClick={() => openEditModal(project)}
                            className="text-indigo-600 hover:text-indigo-900"
                            title="Edit project"
                          >
                            <PencilIcon className="h-5 w-5" />
                          </button>
                        )}
                        {canEditProject(project) && (
                          <button
                            onClick={() => handleDelete(project.key)}
                            className="text-red-600 hover:text-red-900"
                            title="Delete project"
                          >
                            <TrashIcon className="h-5 w-5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data?.projects.length === 0 && (
            <div className="text-center py-12">
              <FolderIcon className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">
                No projects found
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                {activeOnly
                  ? "No active projects are configured yet."
                  : "No projects are configured yet."}
              </p>
            </div>
          )}
              </div>
              
        {/* Create/Edit Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col">
              {/* Modal Header */}
              <div className="flex justify-between items-center px-6 py-4 border-b">
                <h3 className="text-lg font-medium text-gray-900">
                  {editingProject ? "Edit Project" : "Create New Project"}
                </h3>
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="text-gray-400 hover:text-gray-500"
                >
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Modal Content - Scrollable */}
              <div className="flex-1 overflow-y-auto px-6 py-4">
                <form id="project-form" onSubmit={handleSubmit} className="space-y-4">
                  {/* Row 1: Name & Lead (Read-only) */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Project Name *
                      </label>
                      <input
                        type="text"
                        required
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                        placeholder="Project OOO"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Project Lead
                      </label>
                      <div className="block w-full rounded-md border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700">
                        {formData.lead || <span className="text-gray-400">Not set</span>}
                      </div>
                      <p className="text-xs text-gray-500 mt-1">Set in member page</p>
                    </div>
                  </div>

                  {/* Row 1.5: Slack Channel */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Slack Channel Name
                    </label>
                    <input
                      type="text"
                      value={formData.slack_channel}
                      onChange={(e) => setFormData({ ...formData, slack_channel: e.target.value })}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      placeholder="project-ooo"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Enter channel name (e.g., &quot;project-ooo&quot;). Channel ID will be automatically found and mapped.
                    </p>
                  </div>

                  {/* Row 2: GitHub Repos & Project Members */}
                  <div className="grid grid-cols-2 gap-4">
                    {/* GitHub Repositories */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        GitHub Repositories ({formData.repositories.length})
                      </label>
                      <div className="h-32 overflow-y-auto border border-gray-200 rounded-md p-2 bg-gray-50">
                        {formData.repositories.length > 0 ? (
                          <div className="space-y-1">
                            {[...formData.repositories].sort().map((repo, index) => (
                              <a
                                key={index}
                                href={`https://github.com/tokamak-network/${repo}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="block px-2 py-1 bg-white text-gray-700 rounded text-xs border border-gray-200 hover:bg-blue-50 hover:text-blue-700 truncate"
                              >
                                {repo}
                              </a>
                            ))}
                          </div>
                        ) : (
                          <p className="text-xs text-gray-400 text-center py-4">Auto-synced from GitHub Teams</p>
                        )}
                      </div>
                    </div>

                    {/* Project Members */}
                    <div className="relative">
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Project Members ({formData.member_ids.length})
                      </label>
                      <input
                        type="text"
                        value={memberSearchTerm}
                        onChange={(e) => setMemberSearchTerm(e.target.value)}
                        onFocus={() => setShowMemberSelector(true)}
                        onBlur={() => setTimeout(() => setShowMemberSelector(false), 200)}
                        className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm mb-2"
                        placeholder="Search members..."
                      />
                      {showMemberSelector && filteredMembers.length > 0 && (
                        <div className="absolute z-20 w-full bg-white border border-gray-300 rounded-md shadow-lg max-h-40 overflow-y-auto">
                          {filteredMembers.map((member) => (
                            <label key={member.id} className="flex items-center gap-2 px-3 py-2 hover:bg-gray-50 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={formData.member_ids.includes(member.id)}
                                onChange={() => toggleMember(member.id)}
                                className="rounded border-gray-300 text-primary-600"
                              />
                              <span className="text-sm">{member.name}</span>
                            </label>
                          ))}
                        </div>
                      )}
                      <div className="h-20 overflow-y-auto border border-gray-200 rounded-md p-2 bg-gray-50">
                        {formData.member_ids.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {formData.member_ids.map((memberId) => {
                              // Look up member name in allMembers list (which contains all members from DB)
                              const member = allMembers.find((m) => String(m.id) === String(memberId));
                              
                              if (!member) {
                                return (
                                  <span key={memberId} className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                                    Unknown ({String(memberId).slice(0, 8)}...)
                                    <button type="button" onClick={() => toggleMember(memberId)} className="text-gray-600 hover:text-gray-800">×</button>
                                  </span>
                                );
                              }
                              
                              return (
                                <span key={memberId} className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-800 rounded text-xs">
                                  {member.name}
                                  <button type="button" onClick={() => toggleMember(memberId)} className="text-green-600 hover:text-green-800">×</button>
                                </span>
                              );
                            })}
                          </div>
                        ) : (
                          <p className="text-xs text-gray-400 text-center py-2">No members selected</p>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Active Checkbox */}
                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      checked={formData.is_active}
                      onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                      className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                    <label className="ml-2 text-sm text-gray-700">Active</label>
                  </div>
                </form>
              </div>

              {/* Modal Footer */}
              <div className="flex justify-end gap-3 px-6 py-4 border-t bg-gray-50">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  form="project-form"
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  {editingProject ? "Update" : "Create"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
