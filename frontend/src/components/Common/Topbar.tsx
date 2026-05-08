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
    <header className="topbar">

      {/* ── Left: brand + divider + page title ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        <a href="/" className="brand-row" style={{ fontSize: 17, flexShrink: 0 }}>
          DataPulse
        </a>
        <span style={{ width: 1, height: 20, background: 'var(--rule-strong)', flexShrink: 0 }} />
        <div>
          {crumbs.length > 0 && (
            <div className="crumbs" style={{ marginBottom: 2 }}>
              {crumbs.map((c, i) => (
                <span key={i}>
                  {c.href ? <a href={c.href}>{c.label}</a> : <strong>{c.label}</strong>}
                  {i < crumbs.length - 1 && <span> / </span>}
                </span>
              ))}
            </div>
          )}
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg)' }}>{title}</span>
        </div>
      </div>

      {/* ── Right: extra actions + avatar + username + role + sign out ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {actions}
        {user && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div className="avatar">{user.username.slice(0, 2).toUpperCase()}</div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg)', lineHeight: 1.2 }}>
                  {user.username}
                </div>
                <div style={{
                  fontFamily: 'var(--mono)', fontSize: 10,
                  color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.06em',
                }}>
                  {user.role}
                </div>
              </div>
            </div>
            <span style={{ width: 1, height: 20, background: 'var(--rule-strong)' }} />
            <button
              className="btn ghost"
              style={{ padding: '5px 14px', fontSize: 12, letterSpacing: '0.02em' }}
              onClick={logout}
            >
              Sign out
            </button>
          </>
        )}
      </div>

    </header>
  );
}
