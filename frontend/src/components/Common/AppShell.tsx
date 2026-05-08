import type { ReactNode } from 'react';
import Topbar from './Topbar';

interface AppShellProps {
  children: ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  return (
    <div className="app-shell-full">
      <Topbar title="Overview" />
      <main style={{ padding: '24px 32px 80px' }}>{children}</main>
    </div>
  );
}
