"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import apiClient from "@/lib/api";
import { useProjects, useMembers } from "@/graphql/hooks";
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
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface Member {
  id: string;
  name: string;
  email?: string;
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
    slack_channel_id: undefined,
    lead: undefined,
    repositories: p.repositories || [],
    repositories_synced_at: undefined,
    github_team_slug: undefined,
    drive_folders: [],
    notion_page_ids: [],
    notion_parent_page_id: undefined,
    sub_projects: [],
    member_ids: [],
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
  }));

  // Form state
  const [formData, setFormData] = useState({
    key: "",
    name: "",
    description: "",
    lead: "",
    github_team_slug: "",
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

  function openCreateModal() {
    setEditingProject(null);
    setFormData({
      key: "",
      name: "",
      description: "",
      lead: "",
      github_team_slug: "",
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
      if (editingProject) {
        // Update existing project (REST API - mutations not implemented yet)
        await apiClient.updateProject(editingProject.key, {
          name: formData.name,
          description: formData.description || undefined,
          lead: formData.lead || undefined,
          github_team_slug: formData.github_team_slug || undefined,
          // repositories are automatically synced from GitHub Teams by data collector
          drive_folders: formData.drive_folders,
          notion_parent_page_id: formData.notion_parent_page_id || undefined,
          member_ids: formData.member_ids,
          is_active: formData.is_active,
        });
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
          // repositories are automatically synced from GitHub Teams by data collector
          drive_folders: formData.drive_folders,
          notion_parent_page_id: formData.notion_parent_page_id || undefined,
          member_ids: formData.member_ids,
          is_active: formData.is_active,
        });
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
        {/* TBD Banner */}
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <svg
                className="h-5 w-5 text-yellow-400"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-yellow-700">
                <span className="font-bold">TBD (To Be Determined)</span> - This
                page is currently under development.
              </p>
            </div>
          </div>
        </div>

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
            <button
              onClick={openCreateModal}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              <PlusIcon className="h-5 w-5" />
              Add Project
            </button>
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
                    Slack Channel
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
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {project.slack_channel
                        ? `#${project.slack_channel}`
                        : "-"}
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
                        <button
                          onClick={() => openEditModal(project)}
                          className="text-indigo-600 hover:text-indigo-900"
                          title="Edit project"
                        >
                          <PencilIcon className="h-5 w-5" />
                        </button>
                        <button
                          onClick={() => handleDelete(project.key)}
                          className="text-red-600 hover:text-red-900"
                          title="Delete project"
                        >
                          <TrashIcon className="h-5 w-5" />
                        </button>
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
          <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
            <div className="relative top-20 mx-auto p-5 border w-11/12 max-w-4xl shadow-lg rounded-md bg-white">
              <div className="mt-3">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-lg font-medium text-gray-900">
                    {editingProject ? "Edit Project" : "Create New Project"}
                  </h3>
                  <button
                    onClick={() => setShowCreateModal(false)}
                    className="text-gray-400 hover:text-gray-500"
                  >
                    <span className="sr-only">Close</span>
                    <svg
                      className="h-6 w-6"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Project Name *
                    </label>
                    <input
                      type="text"
                      required
                      value={formData.name}
                      onChange={(e) =>
                        setFormData({ ...formData, name: e.target.value })
                      }
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      placeholder="Project OOO"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Description
                    </label>
                    <textarea
                      value={formData.description}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          description: e.target.value,
                        })
                      }
                      rows={3}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      placeholder="Project description..."
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        Project Lead
                      </label>
                      <input
                        type="text"
                        value={formData.lead}
                        onChange={(e) =>
                          setFormData({ ...formData, lead: e.target.value })
                        }
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                        placeholder="John Doe"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        GitHub Team Slug
                      </label>
                      <input
                        type="text"
                        value={formData.github_team_slug}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            github_team_slug: e.target.value,
                          })
                        }
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                        placeholder="project-ooo"
                      />
                    </div>
                  </div>

                  {/* GitHub Repositories */}
                  <div>
                    <div className="mb-2">
                      <label className="block text-sm font-medium text-gray-700">
                        GitHub Repositories
                      </label>
                    </div>
                    <div className="bg-blue-50 border border-blue-200 rounded-md p-3 mb-3">
                      <div className="flex items-start gap-2">
                        <svg
                          className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                          />
                        </svg>
                        <div className="flex-1">
                          <p className="text-sm text-blue-800 font-medium mb-1">
                            Repositories are automatically synced from GitHub
                            Teams
                          </p>
                          <p className="text-xs text-blue-700 mb-2">
                            Repositories are managed on{" "}
                            <a
                              href="https://github.com/orgs/tokamak-network/teams"
                              target="_blank"
                              rel="noopener noreferrer"
                              className="underline hover:text-blue-900 font-medium"
                            >
                              GitHub Teams page
                            </a>{" "}
                            for the team &quot;
                            {formData.github_team_slug || formData.key}&quot;.
                            The data collector automatically syncs repositories
                            from GitHub Teams to the database every day at
                            midnight (KST).
                          </p>
                        </div>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {formData.repositories.map((repo, index) => (
                        <span
                          key={index}
                          className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-800 rounded text-sm"
                        >
                          {repo}
                        </span>
                      ))}
                    </div>
                    {formData.repositories.length === 0 && (
                      <p className="text-xs text-gray-500 mt-2">
                        No repositories found. Add repositories to the GitHub
                        team and they will be automatically synced at midnight
                        (KST).
                      </p>
                    )}
                  </div>

                  {/* Google Drive Root Folder */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Google Drive Root Folder
                    </label>
                    <p className="text-xs text-gray-500 mb-2">
                      Enter the root folder URL or ID for this project. All
                      activities in this folder and its subfolders will be
                      associated with this project.
                    </p>
                    <div className="flex gap-2 mb-2">
                      <input
                        type="text"
                        value={newDriveFolder}
                        onChange={(e) => setNewDriveFolder(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            addDriveFolder();
                          }
                        }}
                        onBlur={addDriveFolder}
                        className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                        placeholder="https://drive.google.com/drive/folders/FOLDER_ID or folder ID"
                      />
                      <button
                        type="button"
                        onClick={addDriveFolder}
                        className="px-3 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200"
                      >
                        Add
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {formData.drive_folders.map((folder, index) => (
                        <span
                          key={index}
                          className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm"
                        >
                          <a
                            href={`https://drive.google.com/drive/folders/${folder}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:underline"
                          >
                            {folder}
                          </a>
                          <button
                            type="button"
                            onClick={() => removeDriveFolder(index)}
                            className="text-blue-600 hover:text-blue-800"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Notion Root Page */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Notion Root Page
                    </label>
                    <p className="text-xs text-gray-500 mb-2">
                      Enter the root page URL or ID for this project. All pages
                      under this root page will be associated with this project.
                    </p>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={newNotionRoot}
                        onChange={(e) => setNewNotionRoot(e.target.value)}
                        onBlur={updateNotionRoot}
                        className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                        placeholder="https://www.notion.so/workspace/Page-Title-PAGE_ID or page ID"
                      />
                    </div>
                    {formData.notion_parent_page_id && (
                      <div className="mt-2">
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-purple-100 text-purple-800 rounded text-sm">
                          <a
                            href={`https://www.notion.so/${formData.notion_parent_page_id.replace(
                              /-/g,
                              ""
                            )}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:underline"
                          >
                            {formData.notion_parent_page_id}
                          </a>
                          <button
                            type="button"
                            onClick={() => {
                              setNewNotionRoot("");
                              setFormData({
                                ...formData,
                                notion_parent_page_id: "",
                              });
                            }}
                            className="text-purple-600 hover:text-purple-800"
                          >
                            ×
                          </button>
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Project Members */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Project Members
                    </label>
                    <p className="text-xs text-gray-500 mb-2">
                      Select members who are part of this project.
                    </p>
                    <div className="relative">
                      <div className="flex gap-2 mb-2">
                        <input
                          type="text"
                          value={memberSearchTerm}
                          onChange={(e) => setMemberSearchTerm(e.target.value)}
                          onFocus={() => setShowMemberSelector(true)}
                          onBlur={() =>
                            setTimeout(() => setShowMemberSelector(false), 200)
                          }
                          className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                          placeholder="Search members..."
                        />
                      </div>
                      {showMemberSelector && filteredMembers.length > 0 && (
                        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto">
                          {filteredMembers.map((member) => (
                            <label
                              key={member.id}
                              className="flex items-center gap-2 px-4 py-2 hover:bg-gray-50 cursor-pointer"
                            >
                              <input
                                type="checkbox"
                                checked={formData.member_ids.includes(
                                  member.id
                                )}
                                onChange={() => toggleMember(member.id)}
                                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                              />
                              <span className="text-sm text-gray-900">
                                {member.name}
                              </span>
                              {member.email && (
                                <span className="text-xs text-gray-500">
                                  ({member.email})
                                </span>
                              )}
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                    {formData.member_ids.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {formData.member_ids.map((memberId) => {
                          const member = allMembers.find(
                            (m) => m.id === memberId
                          );
                          return member ? (
                            <span
                              key={memberId}
                              className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-800 rounded text-sm"
                            >
                              {member.name}
                              <button
                                type="button"
                                onClick={() => toggleMember(memberId)}
                                className="text-green-600 hover:text-green-800"
                              >
                                ×
                              </button>
                            </span>
                          ) : null;
                        })}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      checked={formData.is_active}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          is_active: e.target.checked,
                        })
                      }
                      className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                    <label className="ml-2 block text-sm text-gray-700">
                      Active
                    </label>
                  </div>

                  <div className="flex justify-end gap-3 pt-4">
                    <button
                      type="button"
                      onClick={() => setShowCreateModal(false)}
                      className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                    >
                      {editingProject ? "Update" : "Create"}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
