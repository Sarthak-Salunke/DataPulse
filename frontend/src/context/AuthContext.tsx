// src/context/AuthContext.tsx
//
// Manages authentication state using httpOnly cookies.
//
// How it works:
//   1. On mount, calls GET /auth/me — if the cookie is valid the server
//      returns the user object; if not it returns 401.
//   2. login() POSTs credentials to /auth/login — the server sets the
//      httpOnly cookie directly in the response; the token never touches
//      JavaScript memory, making it immune to XSS attacks.
//   3. googleLogin() POSTs a Google ID token to /auth/google — the server
//      verifies it and sets the same httpOnly cookie.
//   4. logout() POSTs to /auth/logout — the server clears the cookie.
//
// All fetch calls include { credentials: 'include' } so the browser
// automatically attaches the cookie on every request.

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type PropsWithChildren,
} from 'react';
import { setAuthToken, getAuthToken } from '../hooks/useApiData';

// ============================================================================
// Types
// ============================================================================

interface User {
  username: string;
  role: string;
}

interface AuthState {
  user: User | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  googleLogin: (credential: string) => Promise<void>;
  logout: () => Promise<void>;
}

// ============================================================================
// Context
// ============================================================================

const AuthContext = createContext<AuthState | undefined>(undefined);

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}

// ============================================================================
// Provider
// ============================================================================

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount: verify session via cookie OR stored Bearer token.
  useEffect(() => {
    const headers: Record<string, string> = {};
    const token = getAuthToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    fetch(`${API}/auth/me`, { credentials: 'include', headers })
      .then(res => (res.ok ? res.json() : null))
      .then((data: User | null) => setUser(data))
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as { detail?: string }).detail || 'Login failed');
    }
    const data: User & { token?: string } = await res.json();
    if (data.token) setAuthToken(data.token);
    setUser({ username: data.username, role: data.role });
  }, []);

  const googleLogin = useCallback(async (credential: string) => {
    const res = await fetch(`${API}/auth/google`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as { detail?: string }).detail || 'Google sign-in failed');
    }
    const data: User & { token?: string } = await res.json();
    if (data.token) setAuthToken(data.token);
    setUser({ username: data.username, role: data.role });
  }, []);

  const logout = useCallback(async () => {
    await fetch(`${API}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    }).catch(() => {});
    setAuthToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, googleLogin, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
