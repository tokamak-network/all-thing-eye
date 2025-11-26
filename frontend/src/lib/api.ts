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
        if (!config.url?.includes('/auth/login')) {
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
          console.warn('🔒 Authentication failed - clearing token');
          clearToken();
          if (typeof window !== 'undefined') {
            window.location.href = '/login';
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

  async getMemberActivities(
    memberId: number,
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

  async createMember(memberData: {
    name: string;
    email: string;
    github_id?: string;
    slack_id?: string;
    notion_id?: string;
    role?: string;
    project?: string;
  }) {
    const response = await this.client.post("/members", memberData);
    return response.data;
  }

  async updateMember(memberId: string, memberData: {
    name?: string;
    email?: string;
    github_id?: string;
    slack_id?: string;
    notion_id?: string;
    role?: string;
    project?: string;
  }) {
    const response = await this.client.patch(`/members/${memberId}`, memberData);
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

  // Activities API
  async getActivities(params?: {
    source_type?: string;
    activity_type?: string;
    member_id?: number;
    member_name?: string; // Filter by member name
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
      limit?: number;
    }
  ) {
    const queryParams = new URLSearchParams();
    queryParams.append("format", format);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
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
}

export const api = new ApiClient();
export default api;
