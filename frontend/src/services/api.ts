// src/services/api.ts

import {
  Transaction,
  DashboardMetrics,
  FraudAlert,
  CustomerDetails,
  TransactionStatement,
  ApiResponse,
  ApiError,
  PaginatedResponse,
  FilterOptions,
  PaginationParams,
} from '../types';

// ============================================================================
// Configuration
// ============================================================================

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000') + '/api';

// ============================================================================
// HTTP Client Helper
// ============================================================================

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<ApiResponse<T>> {
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
        ...options,
      });

      if (!response.ok) {
        const error: ApiError = {
          message: `HTTP ${response.status}: ${response.statusText}`,
          status: response.status,
        };
        throw error;
      }

      const data = await response.json();
      return {
        data,
        success: true,
      };
    } catch (error) {
      console.error('API Request Error:', error);
      const apiError: ApiError = {
        message: error instanceof Error ? error.message : 'Unknown error occurred',
        status: (error as ApiError).status,
      };
      return {
        data: null as T,
        success: false,
        error: apiError,
      };
    }
  }

  async get<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, body?: unknown): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  async put<T>(endpoint: string, body?: unknown): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(body),
    });
  }

  async delete<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }
}

const apiClient = new ApiClient(API_BASE_URL);

// ============================================================================
// API Service Functions
// ============================================================================

export const apiService = {
  // --------------------------------------------------------------------------
  // Health Check
  // --------------------------------------------------------------------------
  async healthCheck(): Promise<ApiResponse<{ status: string; time: string }>> {
    return apiClient.get('/health');
  },

  // --------------------------------------------------------------------------
  // Dashboard Metrics
  // --------------------------------------------------------------------------
  async getDashboardMetrics(): Promise<ApiResponse<DashboardMetrics>> {
    return apiClient.get('/dashboard/metrics');
  },

  // --------------------------------------------------------------------------
  // Transactions
  // --------------------------------------------------------------------------
  async getTransactions(
    filters?: FilterOptions,
    pagination?: PaginationParams
  ): Promise<ApiResponse<PaginatedResponse<Transaction>>> {
    const params = new URLSearchParams();

    if (pagination) {
      params.append('page', pagination.page.toString());
      params.append('limit', pagination.limit.toString());
      if (pagination.sortBy) params.append('sortBy', pagination.sortBy);
      if (pagination.sortOrder) params.append('sortOrder', pagination.sortOrder);
    }

    if (filters) {
      if (filters.status) params.append('status', filters.status);
      if (filters.dateFrom) params.append('dateFrom', filters.dateFrom);
      if (filters.dateTo) params.append('dateTo', filters.dateTo);
      if (filters.minAmount) params.append('minAmount', filters.minAmount.toString());
      if (filters.maxAmount) params.append('maxAmount', filters.maxAmount.toString());
      if (filters.merchant) params.append('merchant', filters.merchant);
      if (filters.category) params.append('category', filters.category);
    }

    const queryString = params.toString();
    const endpoint = queryString ? `/transactions?${queryString}` : '/transactions';

    return apiClient.get(endpoint);
  },

  // --------------------------------------------------------------------------
  // Fraud Alerts
  // --------------------------------------------------------------------------
  async getFraudAlerts(limit: number = 10): Promise<ApiResponse<FraudAlert[]>> {
    return apiClient.get(`/fraud/alerts?limit=${limit}`);
  },

  // --------------------------------------------------------------------------
  // Customer Information
  // --------------------------------------------------------------------------
  async getCustomerDetails(ccNum: string): Promise<ApiResponse<CustomerDetails>> {
    return apiClient.get(`/customer/${ccNum}`);
  },

  async getCustomerStatement(ccNum: string): Promise<ApiResponse<TransactionStatement[]>> {
    return apiClient.get(`/statement/${ccNum}`);
  },
};

// ============================================================================
// Mock Data Generator (for development without backend)
// ============================================================================

export const mockApi = {
  async getDashboardMetrics(): Promise<ApiResponse<DashboardMetrics>> {
    return {
      data: {
        totalTransactions: 15234,
        fraudDetected: 127,
        fraudRate: 0.83,
        accuracy: 98.7,
      },
      success: true,
    };
  },

  async getRecentTransactions(count: number = 10): Promise<ApiResponse<Transaction[]>> {
    const transactions: Transaction[] = Array.from({ length: count }, (_, i) => ({
      id: `TXN${Date.now() - i * 1000}`,
      time: new Date(Date.now() - i * 60000).toISOString(),
      customer: `CUSTOMER_${Math.floor(Math.random() * 1000)}`,
      merchant: ['Amazon', 'Walmart', 'Target', 'Best Buy', 'Starbucks'][Math.floor(Math.random() * 5)],
      category: ['Shopping', 'Food', 'Gas', 'Entertainment'][Math.floor(Math.random() * 4)],
      amount: Math.random() * 500,
      distance: Math.random() * 100,
      status: Math.random() > 0.9 ? 'Fraud' : 'Normal',
      confidence: Math.random() * 100,
    }));

    return {
      data: transactions,
      success: true,
    };
  },
};

export default apiService;
