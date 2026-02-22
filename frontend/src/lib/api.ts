/**
 * API Client for All-Thing-Eye Backend
 */

import axios, { AxiosInstance } from "axios";
import { getToken, getAuthHeader, isTokenValid, clearToken } from "./jwt";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: `${API_BASE_URL}/api/v1`,
      headers: {
        "Content-Type": "application/json",
      },
      timeout: 30000,
    });

    // Request interceptor to add JWT token
    this.client.interceptors.request.use(
      (config) => {
        // Add JWT token to all requests (except /auth/login)
        if (!config.url?.includes("/auth/login")) {
          const authHeader = getAuthHeader();
          if (authHeader) {
            config.headers.Authorization = authHeader;
          }
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        // Handle 401 Unauthorized - clear token and redirect to login
        if (error.response?.status === 401) {
          console.warn("🔒 Authentication failed - clearing token");
          clearToken();
          if (typeof window !== "undefined") {
            window.location.href = "/login";
          }
        }
        console.error("API Error:", error.response?.data || error.message);
        return Promise.reject(error);
      }
    );
  }

  // Members API
  async getMembers(params?: { limit?: number; offset?: number }) {
    const response = await this.client.get("/members", { params });
    return response.data;
  }

  async getMemberDetail(memberId: number) {
    const response = await this.client.get(`/members/${memberId}`);
    return response.data;
  }

  async createMember(memberData: {
    name: string;
    email: string;
    github_id?: string;
    slack_id?: string;
    notion_id?: string;
    role?: string;
    project?: string;
    projects?: string[];
    eoa_address?: string;
    recording_name?: string;
  }) {
    const response = await this.client.post("/members", memberData);
    return response.data;
  }

  async updateMember(
    memberId: string,
    memberData: {
      name?: string;
      email?: string;
      github_id?: string;
      slack_id?: string;
      notion_id?: string;
      role?: string;
      project?: string;
      projects?: string[];
      eoa_address?: string;
      recording_name?: string;
    }
  ) {
    const response = await this.client.patch(
      `/members/${memberId}`,
      memberData
    );
    return response.data;
  }

  async deleteMember(memberId: string) {
    const response = await this.client.delete(`/members/${memberId}`);
    return response.data;
  }

  async getMemberDetailById(memberId: string) {
    const response = await this.client.get(`/members/${memberId}`);
    return response.data;
  }

  async getMemberActivities(
    memberId: string,
    params?: {
      source_type?: string;
      activity_type?: string;
      start_date?: string;
      end_date?: string;
      limit?: number;
      offset?: number;
    }
  ) {
    const response = await this.client.get(`/members/${memberId}/activities`, {
      params,
    });
    return response.data;
  }

  async generateMemberSummary(
    memberId: string,
    params?: {
      start_date?: string;
      end_date?: string;
    }
  ) {
    const response = await this.client.post(`/members/${memberId}/summary`, params || {});
    return response.data;
  }

  // Activities API
  async getActivities(params?: {
    source_type?: string;
    activity_type?: string;
    member_id?: number;
    member_name?: string; // Filter by member name (for recordings and daily analysis, filters by participant)
    keyword?: string; // Search keyword (searches in titles, content, messages)
    project_key?: string; // Filter by project key (filters activities by project repositories, channels, folders, etc.)
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  }) {
    const response = await this.client.get("/activities", { params });
    return response.data;
  }

  async getActivitiesSummary(params?: {
    source_type?: string;
    start_date?: string;
    end_date?: string;
  }) {
    const response = await this.client.get("/activities/summary", { params });
    return response.data;
  }

  async getActivityTypes(params?: { source_type?: string }) {
    const response = await this.client.get("/activities/types", { params });
    return response.data;
  }

  // Projects API
  async getProjects() {
    const response = await this.client.get("/projects");
    return response.data;
  }

  async getProjectDetail(projectKey: string) {
    const response = await this.client.get(`/projects/${projectKey}`);
    return response.data;
  }

  async getProjectMembers(projectKey: string) {
    const response = await this.client.get(`/projects/${projectKey}/members`);
    return response.data;
  }

  // Projects Management API (CRUD operations)
  // Note: These endpoints use the projects-management router which is mounted at /api/v1
  // The router itself defines /projects, so the full path is /api/v1/projects
  async getProjectsManagement(activeOnly: boolean = false) {
    // Use a different endpoint path - check if projects-management has a separate prefix
    // Actually, projects_management router is mounted at /api/v1, and it defines /projects
    // So we need to check the actual route structure
    // Let's use the management endpoints directly
    const response = await this.client.get("/projects-management/projects", {
      params: { active_only: activeOnly },
    });
    return response.data;
  }

  async getProjectManagement(projectKey: string) {
    const response = await this.client.get(`/projects-management/projects/${projectKey}`);
    return response.data;
  }

  async createProject(projectData: {
    key: string;
    name: string;
    description?: string;
    slack_channel?: string;
    slack_channel_id?: string;
    lead?: string;
    github_team_slug?: string;
    repositories?: string[];
    drive_folders?: string[];
    notion_page_ids?: string[];
    notion_parent_page_id?: string;
    sub_projects?: string[];
    member_ids?: string[];
    is_active?: boolean;
  }) {
    const response = await this.client.post("/projects-management/projects", projectData);
    return response.data;
  }

  async updateProject(
    projectKey: string,
    projectData: {
      name?: string;
      description?: string;
      slack_channel?: string;
      slack_channel_id?: string;
      lead?: string;
      github_team_slug?: string;
      repositories?: string[];
      drive_folders?: string[];
      notion_page_ids?: string[];
      notion_parent_page_id?: string;
      sub_projects?: string[];
      member_ids?: string[];
      is_active?: boolean;
    }
  ) {
    const response = await this.client.put(`/projects-management/projects/${projectKey}`, projectData);
    return response.data;
  }

  async deleteProject(projectKey: string) {
    const response = await this.client.delete(`/projects-management/projects/${projectKey}`);
    return response.data;
  }

  async syncProjectRepositories(projectKey: string) {
    const response = await this.client.post(`/projects-management/projects/${projectKey}/sync-repositories`);
    return response.data;
  }

  // Grant Reports Management
  async getGrantReports(projectKey: string) {
    const response = await this.client.get(`/projects-management/projects/${projectKey}/grant-reports`);
    return response.data;
  }

  async addGrantReport(
    projectKey: string,
    reportData: {
      title: string;
      year: number;
      quarter: number;
      drive_url: string;
      file_name?: string;
    }
  ) {
    const response = await this.client.post(`/projects-management/projects/${projectKey}/grant-reports`, reportData);
    return response.data;
  }

  async updateGrantReport(
    projectKey: string,
    reportId: string,
    reportData: {
      title: string;
      year: number;
      quarter: number;
      drive_url: string;
      file_name?: string;
    }
  ) {
    const response = await this.client.put(`/projects-management/projects/${projectKey}/grant-reports/${reportId}`, reportData);
    return response.data;
  }

  async deleteGrantReport(projectKey: string, reportId: string) {
    const response = await this.client.delete(`/projects-management/projects/${projectKey}/grant-reports/${reportId}`);
    return response.data;
  }

  // Grant Report Summary API
  async summarizeGrantReport(projectKey: string, reportId: string, forceRefresh: boolean = false) {
    const response = await this.client.post(
      `/projects-management/projects/${projectKey}/grant-reports/${reportId}/summarize`,
      null,
      { params: { force_refresh: forceRefresh }, timeout: 180000 } // 3 min timeout for AI
    );
    return response.data;
  }

  async getProjectSummary(projectKey: string, forceRefresh: boolean = false) {
    const response = await this.client.get(
      `/projects-management/projects/${projectKey}/grant-reports/summary`,
      { 
        params: { force_refresh: forceRefresh },
        timeout: 180000 // 3 min timeout for AI
      }
    );
    return response.data;
  }

  // Drive Folder API
  async getDriveFolderFiles(folderId: string) {
    const response = await this.client.get(`/projects-management/drive/folder/${folderId}/files`);
    return response.data;
  }

  async findSlackChannelId(channelName: string): Promise<string | undefined> {
    if (!channelName || !channelName.trim()) {
      return undefined;
    }
    
    try {
      // Query slack_channels collection via database API
      const response = await this.client.get(
        `/database/collections/slack_channels/documents`,
        {
          params: {
            limit: 100,
            filter: JSON.stringify({
              name: { $regex: channelName.trim(), $options: "i" }
            })
          }
        }
      );
      
      const channels = response.data?.documents || [];
      if (channels.length > 0) {
        // Return channel_id or slack_id
        return channels[0].channel_id || channels[0].slack_id;
      }
      
      return undefined;
    } catch (error) {
      console.error("Error finding Slack channel ID:", error);
      return undefined;
    }
  }

  // Export API
  async getTables() {
    const response = await this.client.get("/exports/tables");
    return response.data;
  }

  getExportTableCsvUrl(
    source: string,
    table: string,
    limit?: number,
    startDate?: string,
    endDate?: string
  ) {
    const queryParams = new URLSearchParams();
    if (limit) queryParams.append("limit", limit.toString());
    if (startDate) queryParams.append("start_date", startDate);
    if (endDate) queryParams.append("end_date", endDate);

    const params = queryParams.toString() ? `?${queryParams.toString()}` : "";
    return `${API_BASE_URL}/api/v1/exports/tables/${source}/${table}/csv${params}`;
  }

  getExportMembersUrl(format: "csv" | "json" = "csv") {
    return `${API_BASE_URL}/api/v1/exports/members?format=${format}`;
  }

  getExportActivitiesUrl(
    format: "csv" | "json" = "csv",
    params?: {
      source_type?: string;
      activity_type?: string;
      start_date?: string;
      end_date?: string;
      project_key?: string;
      member_name?: string;
      limit?: number;
    }
  ) {
    const queryParams = new URLSearchParams();
    queryParams.append("format", format);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== "") {
          queryParams.append(key, value.toString());
        }
      });
    }
    return `${API_BASE_URL}/api/v1/exports/activities?${queryParams.toString()}`;
  }

  getExportProjectUrl(
    projectKey: string,
    format: "csv" | "json" = "csv",
    dataType: "all" | "slack" | "github" | "google_drive" = "all"
  ) {
    return `${API_BASE_URL}/api/v1/exports/projects/${projectKey}?format=${format}&data_type=${dataType}`;
  }

  async exportBulkTables(
    tables: Array<{ source: string; table: string }>,
    startDate?: string,
    endDate?: string,
    format: "csv" | "json" | "toon" = "csv"
  ) {
    const payload: any = {
      tables,
      format,
    };
    if (startDate) payload.start_date = startDate;
    if (endDate) payload.end_date = endDate;

    const response = await this.client.post("/exports/bulk", payload, {
      responseType: "blob",
    });
    return response.data;
  }

  // Database viewer API
  async getDatabaseCollections() {
    const response = await this.client.get("/database/collections");
    return response.data;
  }

  async getDatabaseStats() {
    const response = await this.client.get("/database/stats");
    return response.data;
  }

  async getCollectionSchema(collectionName: string) {
    const response = await this.client.get(
      `/database/collections/${collectionName}/schema`
    );
    return response.data;
  }

  async getCollectionDocuments(
    collectionName: string,
    page: number = 1,
    limit: number = 30,
    search?: string
  ) {
    const response = await this.client.get(
      `/database/collections/${collectionName}/documents`,
      { params: { page, limit, search } }
    );
    return response.data;
  }

  async getCollectionSample(collectionName: string, limit: number = 10) {
    const response = await this.client.get(
      `/database/collections/${collectionName}/sample`,
      { params: { limit } }
    );
    return response.data;
  }

  async getCollectionStats(collectionName: string) {
    const response = await this.client.get(
      `/database/collections/${collectionName}/stats`
    );
    return response.data;
  }

  async getLastCollected() {
    const response = await this.client.get("/database/last-collected");
    return response.data;
  }

  // Unified statistics API
  async getAppStats() {
    const response = await this.client.get("/stats/summary");
    return response.data;
  }

  // Code statistics API (GitHub commits)
  async getCodeStats(startDate?: string, endDate?: string) {
    const params: { start_date?: string; end_date?: string } = {};
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    const response = await this.client.get("/stats/code-changes", { params });
    return response.data;
  }

  async getMemberCommits(memberName: string, startDate?: string, endDate?: string) {
    const params: Record<string, string> = { member_name: memberName };
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    const response = await this.client.get("/stats/member-commits", { params });
    return response.data;
  }

  // Authentication API
  async login(address: string, message: string, signature: string) {
    const response = await this.client.post("/auth/login", {
      address,
      message,
      signature,
    });
    return response.data;
  }

  async verifyToken(token: string) {
    const response = await this.client.post("/auth/verify", { token });
    return response.data;
  }

  async getAdmins() {
    const response = await this.client.get("/auth/admins");
    return response.data;
  }

  async checkAdmin(address: string) {
    const response = await this.client.get(`/auth/check-admin/${address}`);
    return response.data;
  }

  // Generic get method for custom endpoints
  async get<T = any>(endpoint: string, params?: any): Promise<T> {
    const response = await this.client.get(endpoint, { params });
    return response.data;
  }

  // Translation API
  async translateText(
    text: string,
    targetLanguage: string = "ko",
    sourceLanguage?: string
  ) {
    const response = await this.client.post("/ai/translate", {
      text,
      target_language: targetLanguage,
      source_language: sourceLanguage,
    });
    return response.data;
  }

  // AI Processed Data API - Meetings
  async getMeetings(params?: {
    search?: string;
    participant?: string;
    template?: string;
    limit?: number;
    offset?: number;
  }) {
    const response = await this.client.get("/ai/meetings", { params });
    return response.data;
  }

  async getMeetingDetail(meetingId: string) {
    const response = await this.client.get(`/ai/meetings/${meetingId}`);
    return response.data;
  }

  async getMeetingAnalysis(meetingId: string, template: string) {
    const response = await this.client.get(
      `/ai/meetings/${meetingId}/analysis/${template}`
    );
    return response.data;
  }

  async getFailedRecordings(params?: { limit?: number; offset?: number }) {
    const response = await this.client.get("/ai/failed-recordings", { params });
    return response.data;
  }

  async getAiStats() {
    const response = await this.client.get("/ai/stats");
    return response.data;
  }

  // Recordings Daily Analysis API
  async getRecordingsDaily(params?: {
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  }) {
    const response = await this.client.get("/ai/recordings-daily", { params });
    return response.data;
  }

  async getRecordingsDailyByDate(date: string) {
    const response = await this.client.get(`/ai/recordings-daily/${date}`);
    return response.data;
  }

  // Custom Export API
  async getCustomExportPreview(params: {
    selected_members?: string[];
    start_date?: string;
    end_date?: string;
    project?: string;
    selected_fields?: string[];
    limit?: number;
    offset?: number;
  }) {
    const response = await this.client.post("/custom-export/preview", params);
    return response.data;
  }

  async getCustomExportMembers() {
    const response = await this.client.get("/custom-export/members");
    return response.data;
  }

  async getCustomExportCollections() {
    const response = await this.client.get("/custom-export/collections");
    return response.data;
  }

  /**
   * Fetch custom export data as JSON (for AI analysis)
   */
  async fetchCustomExportData(params: {
    selected_members?: string[];
    start_date?: string;
    end_date?: string;
    project?: string;
    selected_fields?: string[];
    sources?: string[];
    limit?: number;
    offset?: number;
  }) {
    const response = await this.client.post("/custom-export/preview", {
      ...params,
      limit: params.limit || 500,  // Higher limit for AI analysis
      offset: params.offset || 0,
    });
    return response.data;
  }

  async downloadCustomExport(
    params: {
      selected_members?: string[];
      start_date?: string;
      end_date?: string;
      project?: string;
      selected_fields?: string[];
    },
    format: "csv" | "json" | "toon" = "csv"
  ) {
    const response = await this.client.post(
      `/custom-export/export?format=${format}`,
      params,
      { responseType: "blob" }
    );
    return response.data;
  }

  async downloadCustomExportCsv(params: {
    selected_members?: string[];
    start_date?: string;
    end_date?: string;
    project?: string;
    selected_fields?: string[];
  }) {
    return this.downloadCustomExport(params, "csv");
  }

  async exportCollection(
    collection: { source: string; collection: string },
    format: "csv" | "json" | "toon" = "csv",
    startDate?: string,
    endDate?: string,
    limit?: number
  ) {
    // Increase timeout for large collection exports (3 minutes)
    const response = await this.client.post(
      "/custom-export/collection",
      {
        collections: [collection],
        format,
        start_date: startDate,
        end_date: endDate,
        limit,
      },
      { 
        responseType: "blob",
        timeout: 180000 // 3 minutes for large single collection exports
      }
    );
    return response.data;
  }

  async exportCollectionsBulk(
    collections: Array<{ source: string; collection: string }>,
    format: "csv" | "json" | "toon" = "csv",
    startDate?: string,
    endDate?: string,
    limit?: number
  ) {
    // Increase timeout for bulk exports (5 minutes)
    const response = await this.client.post(
      "/custom-export/collections/bulk",
      {
        collections,
        format,
        start_date: startDate,
        end_date: endDate,
        limit,
      },
      { 
        responseType: "blob",
        timeout: 300000 // 5 minutes for large bulk exports
      }
    );
    return response.data;
  }

  async exportMembers(format: "csv" | "json" | "toon" = "csv") {
    const response = await this.client.get(
      `/custom-export/members?format=${format}`,
      { responseType: "blob" }
    );
    return response.data;
  }

  // Tokamak AI API
  private getAIClient(): AxiosInstance {
    const AI_API_BASE_URL =
      process.env.NEXT_PUBLIC_AI_API_URL || "https://api.ai.tokamak.network";
    
    const aiClient = axios.create({
      baseURL: AI_API_BASE_URL,
      headers: {
        "Content-Type": "application/json",
      },
      timeout: 60000, // 60 seconds for AI responses
    });

    // Add authentication header
    aiClient.interceptors.request.use(
      (config) => {
        // Try API key first (from environment variable)
        const apiKey = process.env.NEXT_PUBLIC_AI_API_KEY;
        if (apiKey) {
          config.headers["X-API-Key"] = apiKey;
        } else {
          // Fallback to JWT token if API key not available
          const authHeader = getAuthHeader();
          if (authHeader) {
            config.headers.Authorization = authHeader;
          }
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    return aiClient;
  }

  /**
   * Chat with AI assistant (via backend proxy)
   * @param messages Array of chat messages
   * @param model Optional model name (defaults to server default)
   * @param context Optional context data
   */
  async chatWithAI(
    messages: Array<{ role: "user" | "assistant" | "system"; content: string }>,
    model?: string,
    context?: Record<string, any>
  ) {
    // Use backend proxy instead of direct API call
    const requestBody: any = {
      messages: messages.map((msg) => ({
        role: msg.role,
        content: msg.content,
      })),
    };

    if (model) {
      requestBody.model = model;
    }

    if (context) {
      requestBody.context = context;
    }

    // Debug: Log the full URL
    const fullUrl = `${this.client.defaults.baseURL}/ai/chat`;
    console.log("🔍 Calling AI API at:", fullUrl, "Method: POST");
    console.log("📦 Request body:", requestBody);

    const response = await this.client.post("/ai/chat", requestBody);
    return response.data;
  }

  /**
   * Generate text using AI (via backend proxy)
   * @param prompt Text prompt
   * @param model Optional model name
   * @param context Optional context data
   */
  async generateWithAI(
    prompt: string,
    model?: string,
    context?: Record<string, any>
  ) {
    // Use backend proxy instead of direct API call
    const requestBody: any = {
      prompt,
    };

    if (model) {
      requestBody.model = model;
    }

    if (context) {
      requestBody.context = context;
    }

    const response = await this.client.post("/ai/generate", requestBody);
    return response.data;
  }

  /**
   * List available AI models (via backend proxy)
   */
  async listAIModels() {
    // Use backend proxy instead of direct API call
    const response = await this.client.get("/ai/models");
    return response.data;
  }

  // ============================================================================
  // MCP (Model Context Protocol) API
  // ============================================================================

  /**
   * List available MCP resources
   */
  async listMCPResources() {
    const response = await this.client.get("/mcp/resources");
    return response.data;
  }

  /**
   * Read an MCP resource
   */
  async readMCPResource(resourcePath: string) {
    const response = await this.client.get(`/mcp/resources/${resourcePath}`);
    return response.data;
  }

  /**
   * List available MCP tools
   */
  async listMCPTools() {
    const response = await this.client.get("/mcp/tools");
    return response.data;
  }

  /**
   * Call an MCP tool
   */
  async callMCPTool(name: string, args: Record<string, any> = {}) {
    const response = await this.client.post("/mcp/tools/call", {
      name,
      arguments: args,
    });
    return response.data;
  }

  /**
   * List available MCP prompts
   */
  async listMCPPrompts() {
    const response = await this.client.get("/mcp/prompts");
    return response.data;
  }

  /**
   * Get an MCP prompt with arguments
   */
  async getMCPPrompt(name: string, args: Record<string, string> = {}) {
    const response = await this.client.post("/mcp/prompts/get", {
      name,
      arguments: args,
    });
    return response.data;
  }

  /**
   * Chat with AI using MCP context injection
   * This automatically fetches relevant data based on the conversation
   */
  async chatWithMCPContext(
    messages: Array<{ role: string; content: string }>,
    model?: string,
    contextHints?: Record<string, any>,
    signal?: AbortSignal
  ) {
    const isDev = process.env.NODE_ENV === "development";
    const endpoint = isDev ? "/mcp/chat/test" : "/mcp/chat";
    
    const response = await this.client.post(endpoint, {
      messages,
      model,
      context_hints: contextHints,
    }, { signal });
    return response.data;
  }

  /**
   * Chat with MCP Agent - True Function Calling Agent
   * AI decides which tools to call and iterates until it has enough information
   */
  async chatWithAgent(
    messages: Array<{ role: string; content: string }>,
    model?: string,
    maxIterations?: number,
    signal?: AbortSignal
  ) {
    // Use test endpoint in development (no auth required)
    // Use regular endpoint in production (requires auth)
    const isDev = process.env.NODE_ENV === "development";
    const endpoint = isDev ? "/mcp/agent/test" : "/mcp/agent";
    
    console.log(`🤖 Agent API call to ${endpoint}`);
    console.log(`   Messages: ${messages.length}, Model: ${model}`);
    
    const response = await this.client.post(endpoint, {
      messages,
      model,
      max_iterations: maxIterations || 10,
    }, { signal });
    
    console.log(`🤖 Agent API response:`, response.data);
    return response.data;
  }

  /**
   * List available agent tools
   */
  async listAgentTools() {
    const response = await this.client.get("/mcp/agent/tools");
    return response.data;
  }

  // ============================================
  // Reports API
  // ============================================

  /**
   * Generate a biweekly ecosystem report
   */
  async generateReport(
    startDate: string,
    endDate: string,
    useAi: boolean = true
  ): Promise<{
    content: string;
    metadata: {
      start_date: string;
      end_date: string;
      use_ai: boolean;
      generated_at: string;
      stats: {
        total_commits: number;
        total_repos: number;
        total_prs: number;
        staked_ton: number;
        market_cap: number;
      };
    };
  }> {
    const response = await this.client.post("/reports/generate", {
      start_date: startDate,
      end_date: endDate,
      use_ai: useAi,
    });
    return response.data;
  }

  /**
   * Get preset date ranges for report generation
   */
  async getReportPresets(): Promise<{
    presets: Array<{
      name: string;
      start_date: string;
      end_date: string;
    }>;
  }> {
    const response = await this.client.get("/reports/presets");
    return response.data;
  }
  // ============================================
  // Weekly Output Schedules API
  // ============================================

  async getWeeklyOutputSchedules(activeOnly?: boolean) {
    const params: { active_only?: boolean } = {};
    if (activeOnly !== undefined) params.active_only = activeOnly;
    const response = await this.client.get("/weekly-output/schedules", { params });
    return response.data;
  }

  async getWeeklyOutputSchedule(id: string) {
    const response = await this.client.get(`/weekly-output/schedules/${id}`);
    return response.data;
  }

  async createWeeklyOutputSchedule(data: {
    name: string;
    channel_id: string;
    channel_name: string;
    member_ids: string[];
    thread_schedule: { day_of_week: string; hour: number; minute: number };
    reminder_schedule: { day_of_week: string; hour: number; minute: number };
    final_schedule: { day_of_week: string; hour: number; minute: number };
    thread_message?: string | null;
    reminder_message?: string | null;
    final_message?: string | null;
    is_active?: boolean;
  }) {
    const response = await this.client.post("/weekly-output/schedules", data);
    return response.data;
  }

  async updateWeeklyOutputSchedule(
    id: string,
    data: {
      name?: string;
      channel_id?: string;
      channel_name?: string;
      member_ids?: string[];
      thread_schedule?: { day_of_week: string; hour: number; minute: number };
      reminder_schedule?: { day_of_week: string; hour: number; minute: number };
      final_schedule?: { day_of_week: string; hour: number; minute: number };
      thread_message?: string | null;
      reminder_message?: string | null;
      final_message?: string | null;
      is_active?: boolean;
    }
  ) {
    const response = await this.client.put(`/weekly-output/schedules/${id}`, data);
    return response.data;
  }

  async deleteWeeklyOutputSchedule(id: string) {
    const response = await this.client.delete(`/weekly-output/schedules/${id}`);
    return response.data;
  }

  async getMembersWithSlack() {
    const response = await this.client.get("/weekly-output/members-with-slack");
    return response.data;
  }

  // Onboarding API
  async sendWelcomeMessage(memberId: string, force: boolean = false) {
    const response = await this.client.post("/onboarding/send-welcome", {
      member_id: memberId,
      force,
    });
    return response.data;
  }
}

export const api = new ApiClient();
export default api;
