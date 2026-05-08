// ── Sidebar — full app shell sidebar ──────────────────────────────
import type { ReactNode } from 'react';

type NavId =
  | 'overview' | 'alerts' | 'transactions' | 'customers' | 'merchants'
  | 'pipeline' | 'models' | 'rules' | 'audit';

interface NavItemProps {
  id: NavId; label: string; href?: string;
  count?: ReactNode; alert?: boolean;
  active?: NavId;
}
function NavItem({ id, label, href = '#', count, alert, active }: NavItemProps) {
  const isActive = active === id;
  return (
    <a className={`nav-item${isActive ? ' active' : ''}${alert ? ' alert' : ''}`} href={href}>
      <span className="ic">●</span>
      {label}
      {count != null && <span className="count">{count}</span>}
    </a>
  );
}

interface SidebarProps {
  active?: NavId;
  user?: { username: string; role: string };
  onLogout?: () => void;
}

export default function Sidebar({ active = 'overview', user, onLogout }: SidebarProps) {
  return (
    <aside className="side">
      <a className="brand-row" href="/">
        <div className="brand-mark">D</div>DataPulse
      </a>

      <nav className="nav-group">
        <div className="nav-label">Monitoring</div>
        <NavItem id="overview"     label="Overview"      active={active} href="/dashboard" />
        <NavItem id="alerts"       label="Fraud alerts"  active={active} href="/alerts" count="12" alert />
        <NavItem id="transactions" label="Transactions"  active={active} href="/tx" count="23.4K" />
        <NavItem id="customers"    label="Customers"     active={active} href="/customers" />
        <NavItem id="merchants"    label="Merchants"     active={active} href="/merchants" />
      </nav>

      <nav className="nav-group">
        <div className="nav-label">System</div>
        <NavItem id="pipeline" label="Pipeline" active={active} />
        <NavItem id="models"   label="Models"   active={active} />
        <NavItem id="rules"    label="Rules"    active={active} />
        <NavItem id="audit"    label="Audit log" active={active} />
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
