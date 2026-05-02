export type Theme = 'light' | 'dark';
export type TransactionStatus = 'Normal' | 'Fraud';

export interface Transaction {
  id: string;
  time: string;
  customer: string;
  merchant: string;
  category: string;
  amount: number;
  distance: number;
  status: TransactionStatus;
  confidence?: number;
  type?: string;
}

export interface KPI {
  title: string;
  value: string;
  details: string;
  change: string;
  changeType: 'increase' | 'decrease';
}

export interface Toast {
  id: number;
  title: string;
  message: string;
  type: 'error' | 'success';
}

export interface DashboardMetrics {
  totalTransactions: number;
  fraudDetected: number;
  fraudRate: number;
  accuracy: number;
}

export interface FraudAlert {
  timestamp: string;
  ccNum: string;
  amount: number;
  merchant: string;
  confidence: number;
  transNum?: string;
  transaction_id?: string;
  customer_name?: string;
  merchant_name?: string;
  category?: string;
  distance?: number;
  transaction_type?: string;
}

export interface CustomerDetails {
  ccNum: string;
  name?: string;
  email?: string;
}

export interface TransactionStatement {
  id: string;
  date: string;
  amount: number;
  merchant: string;
  status: TransactionStatus;
}

export interface ApiResponse<T> {
  data: T;
  success: boolean;
  error?: ApiError;
}

export interface ApiError {
  message: string;
  status?: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}

export interface FilterOptions {
  status?: string;
  dateFrom?: string;
  dateTo?: string;
  minAmount?: number;
  maxAmount?: number;
  merchant?: string;
  category?: string;
}

export interface PaginationParams {
  page: number;
  limit: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}
