// ── AppShell — wraps Sidebar + main content ────────────────────────
import type { ReactNode } from 'react';
import Sidebar from './Sidebar';
import { useAuth } from '../../context/AuthContext';

interface AppShellProps {
  children: ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const { user, logout } = useAuth();
  return (
    <div className="app-shell">
      <Sidebar
        user={user ? { username: user.username, role: user.role } : undefined}
        onLogout={logout}
      />
      <main style={{ padding: '24px 32px 80px', maxWidth: 1320 }}>{children}</main>
    </div>
  );
}
