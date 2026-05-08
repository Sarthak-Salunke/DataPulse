// ── Topbar — breadcrumbs + title + actions slot ────────────────────
import type { ReactNode } from 'react';

interface Crumb { label: string; href?: string; }

interface TopbarProps {
  crumbs?: Crumb[];
  title: ReactNode;
  actions?: ReactNode;
}

export default function Topbar({ crumbs = [], title, actions }: TopbarProps) {
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
      {actions && <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>{actions}</div>}
    </div>
  );
}
