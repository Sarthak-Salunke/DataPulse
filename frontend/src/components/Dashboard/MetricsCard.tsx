// ── MetricsCard — tokenised KPI card with count-up ─────────────────
import type { ReactNode } from 'react';
import { useCountUp } from '../../hooks/useCountUp';

interface Props {
  label: string;
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  delta?: number;
  invertDelta?: boolean;
  sparkline?: number[];
  accent?: 'brand' | 'amber' | 'risk' | 'safe' | 'indigo' | 'magenta';
  footnote?: ReactNode;
}

const ACCENT_VAR: Record<NonNullable<Props['accent']>, string> = {
  brand:   'var(--brand)',
  amber:   'var(--amber)',
  risk:    'var(--risk)',
  safe:    'var(--safe)',
  indigo:  'var(--indigo)',
  magenta: 'var(--magenta)',
};

export default function MetricsCard({
  label, value, prefix = '', suffix = '',
  decimals = 0, delta, invertDelta, sparkline, accent = 'brand', footnote,
}: Props) {
  const v = useCountUp(value, 1400, decimals);
  const goodDir = delta == null ? null : (invertDelta ? delta < 0 : delta > 0);
  const accentColor = ACCENT_VAR[accent];

  return (
    <div className="panel" style={{ position: 'relative', overflow: 'hidden' }}>
      <span aria-hidden style={{
        position: 'absolute', top: 0, left: 0, height: 2, width: 28,
        background: accentColor,
      }}/>
      <div className="panel-sub" style={{ marginBottom: 10, color: 'var(--fg-3)' }}>{label}</div>
      <div style={{
        fontSize: 32, fontWeight: 500, letterSpacing: '-0.025em',
        fontVariantNumeric: 'tabular-nums', lineHeight: 1,
      }}>
        {prefix}{v.toFixed(decimals)}<small style={{ fontSize: 16, color: 'var(--fg-3)', fontWeight: 400, marginLeft: 2 }}>{suffix}</small>
      </div>

      {delta != null && (
        <div style={{
          marginTop: 8, display: 'inline-flex', alignItems: 'center', gap: 6,
          fontFamily: 'var(--mono)', fontSize: 11,
          color: goodDir ? 'var(--safe)' : 'var(--risk)',
        }}>
          <span>{delta > 0 ? '▲' : '▼'}</span>{Math.abs(delta).toFixed(1)}%
          <span style={{ color: 'var(--fg-3)' }}>vs. yesterday</span>
        </div>
      )}

      {sparkline && sparkline.length > 1 && (
        <svg viewBox="0 0 200 40" style={{ width: '100%', height: 40, marginTop: 12, display: 'block' }}>
          <path
            className="draw-path"
            fill="none"
            stroke={accentColor}
            strokeWidth="1.5"
            d={sparkline.map((y, i) => {
              const x = (i / (sparkline.length - 1)) * 200;
              const min = Math.min(...sparkline), max = Math.max(...sparkline);
              const ny = max === min ? 20 : 36 - ((y - min) / (max - min)) * 32;
              return `${i === 0 ? 'M' : 'L'}${x},${ny}`;
            }).join(' ')}
          />
        </svg>
      )}

      {footnote && <div className="panel-sub" style={{ marginTop: 10 }}>{footnote}</div>}
    </div>
  );
}
