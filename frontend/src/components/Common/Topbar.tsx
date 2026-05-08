import type { ReactNode } from 'react';
import { useAuth } from '../../context/AuthContext';

interface Crumb { label: string; href?: string; }

interface TopbarProps {
  crumbs?: Crumb[];
  title: ReactNode;
  actions?: ReactNode;
}

export default function Topbar({ crumbs = [], title, actions }: TopbarProps) {
  const { user, logout } = useAuth();

  return (
    <div className="topbar">
      <div className="title-row">
        {crumbs.length > 0 && (
          <div className="crumbs">
            {crumbs.map((c, i) => (
              <span key={i}>
                {c.href ? <a href={c.href}>{c.label}</a> : <strong>{c.label}</strong>}
                {i < crumbs.length - 1 && <span> &nbsp;/&nbsp; </span>}
              </span>
            ))}
          </div>
        )}
        <h1>{title}</h1>
      </div>

      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        {actions}
        {user && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div className="avatar" style={{ width: 28, height: 28, fontSize: 10 }}>
                {user.username.slice(0, 2).toUpperCase()}
              </div>
              <span style={{ fontSize: 13, color: 'var(--fg-2)', fontWeight: 500 }}>
                {user.username}
              </span>
            </div>
            <button
              className="btn ghost"
              style={{ padding: '4px 12px', fontSize: 12 }}
              onClick={logout}
            >
              Sign out
            </button>
          </>
        )}
      </div>
    </div>
  );
}
