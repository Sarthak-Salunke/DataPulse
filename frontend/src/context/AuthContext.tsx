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
//   3. logout() POSTs to /auth/logout — the server clears the cookie.
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

// ============================================================================
// Types
// ============================================================================

interface User {
  username: string;
  role: string;
}

interface AuthState {
  user: User | null;
  isLoading: boolean;   // true while the initial /auth/me check is in-flight
  login: (username: string, password: string) => Promise<void>;
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

  // On mount: check if a valid cookie session already exists.
  // This restores the session after a page refresh without re-entering credentials.
  useEffect(() => {
    fetch(`${API}/auth/me`, { credentials: 'include' })
      .then(res => (res.ok ? res.json() : null))
      .then((data: User | null) => setUser(data))
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      credentials: 'include',         // receive the Set-Cookie header
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as { detail?: string }).detail || 'Login failed');
    }

    const data: User = await res.json();
    setUser(data);
  }, []);

  const logout = useCallback(async () => {
    await fetch(`${API}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    }).catch(() => {});   // best-effort — clear local state regardless
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
