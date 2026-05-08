// ── Sidebar ─────────────────────────────────────────────────────────
interface SidebarProps {
  user?: { username: string; role: string };
  onLogout?: () => void;
}

export default function Sidebar({ user, onLogout }: SidebarProps) {
  return (
    <aside className="side">
      <a className="brand-row" href="/">
        DataPulse
      </a>

      <nav className="nav-group">
        <div className="nav-label">Monitoring</div>
        <a className="nav-item active" href="/dashboard">
          <span className="ic">●</span>Overview
        </a>
      </nav>

      {user && (
        <div className="side-foot">
          <div className="avatar">{user.username.slice(0, 2).toUpperCase()}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ color: 'var(--fg)', fontSize: 12, fontWeight: 500 }}>{user.username}</div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              {user.role}
            </div>
          </div>
          {onLogout && (
            <button className="btn ghost" style={{ padding: '4px 8px', fontSize: 11 }} onClick={onLogout}>
              Out
            </button>
          )}
        </div>
      )}
    </aside>
  );
}
