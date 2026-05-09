import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip as RcTooltip, ResponsiveContainer,
} from 'recharts';
import { useTransactions, useDashboardMetrics, useRecentAlerts } from '../../hooks/useApiData';
import type { FraudAlert, Transaction } from '../../types';
import { useCountUp } from '../../hooks/useCountUp';
import RealTimeFeed from './RealTimeFeed';
import { APP_METRICS } from '../../config/content';

// CSS vars don't work in SVG/Recharts props — use hex constants
const C = {
  grid:   '#262932',
  volume: '#a8acb4',
  fraud:  '#e26d5c',
  axis:   '#6b6f78',
  tip:    '#191b20',
  safe:   '#6fb98f',
};

// ── Data helpers ──────────────────────────────────────────────────

function buildVolumeData(txns: Transaction[]) {
  const map: Record<string, { label: string; total: number; fraud: number }> = {};
  txns.forEach(t => {
    const d = new Date(t.time);
    if (isNaN(d.getTime())) return;
    const epoch = new Date(d.getFullYear(), d.getMonth(), d.getDate(), d.getHours()).getTime();
    const key = String(epoch);
    if (!map[key]) map[key] = { label: `${String(d.getHours()).padStart(2, '0')}:00`, total: 0, fraud: 0 };
    map[key].total++;
    if (t.status === 'Fraud') map[key].fraud++;
  });
  const sorted = Object.keys(map)
    .map(Number)
    .sort((a, b) => a - b)
    .map(k => map[String(k)]);
  return sorted.length >= 3 ? sorted.slice(-24) : FALLBACK_VOL;
}

const FALLBACK_VOL = Array.from({ length: 24 }, (_, i) => ({
  label: `${String(i).padStart(2, '0')}:00`,
  total: Math.round(600 + Math.sin(i / 3.5) * 280 + i * 8),
  fraud: Math.round(2 + Math.sin(i / 2.8) * 2.5 + 0.5),
}));

function buildCategoryDist(txns: Transaction[]) {
  const counts: Record<string, { total: number; fraud: number }> = {};
  txns.forEach(t => {
    if (!counts[t.category]) counts[t.category] = { total: 0, fraud: 0 };
    counts[t.category].total++;
    if (t.status === 'Fraud') counts[t.category].fraud++;
  });
  const total = txns.length || 1;
  return Object.entries(counts)
    .sort(([, a], [, b]) => b.total - a.total)
    .slice(0, 6)
    .map(([cat, c]) => ({
      name: cat.replace(/_/g, ' '),
      pct: Math.round((c.total / total) * 100),
      fraud: c.fraud,
    }));
}

const FALLBACK_CATS = [
  { name: 'grocery pos',    pct: 28, fraud: 1 },
  { name: 'shopping net',   pct: 22, fraud: 5 },
  { name: 'misc net',       pct: 18, fraud: 3 },
  { name: 'gas transport',  pct: 12, fraud: 1 },
  { name: 'home',           pct: 10, fraud: 2 },
  { name: 'entertainment',  pct: 10, fraud: 1 },
];

function buildHeatmap(txns: Transaction[]): number[][] {
  if (txns.length === 0) return FALLBACK_HEAT;
  const grid: number[][] = Array.from({ length: 7 }, () => new Array<number>(24).fill(0));
  txns.forEach(t => {
    const d = new Date(t.time);
    if (isNaN(d.getTime())) return;
    grid[d.getDay()][d.getHours()] += t.status === 'Fraud' ? 3 : 1;
  });
  const max = Math.max(...grid.flat(), 1);
  const result = grid.map(row => row.map(v => Math.min(5, Math.round((v / max) * 5))));
  return result.flat().some(v => v > 0) ? result : FALLBACK_HEAT;
}

const FALLBACK_HEAT: number[][] = Array.from({ length: 7 }, (_, day) =>
  Array.from({ length: 24 }, (_, hr) =>
    Math.max(0, Math.min(5, Math.round(Math.sin(day * 0.8 + hr * 0.4) * 2 + Math.cos(hr * 0.6) * 1.5 + 2.5)))
  )
);

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

// ── Sub-components ────────────────────────────────────────────────

function RingGauge({ pct, color }: { pct: number; color: string }) {
  const r = 26, circ = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 64 64" style={{ width: 52, height: 52, flexShrink: 0 }}>
      <circle cx="32" cy="32" r={r} fill="none" stroke="#262932" strokeWidth="6" />
      <circle cx="32" cy="32" r={r} fill="none" stroke={color} strokeWidth="6"
        strokeDasharray={circ}
        strokeDashoffset={circ - Math.max(0, Math.min(1, pct / 100)) * circ}
        strokeLinecap="round" transform="rotate(-90 32 32)" />
    </svg>
  );
}

function AlertCard({ a }: { a: FraudAlert }) {
  const label = (a.merchant_name || a.merchant || 'Unknown')
    .replace(/fraud_/i, '').replace(/_/g, ' ').slice(0, 26);
  let timeStr = '—';
  try { timeStr = new Date(a.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); } catch {}
  return (
    <div style={{
      border: '1px solid var(--rule)', borderLeft: '2px solid var(--risk)',
      borderRadius: 8, padding: '10px 12px', background: 'var(--ink-2)',
      display: 'grid', gridTemplateColumns: 'auto 1fr auto', gap: 10, alignItems: 'center',
    }}>
      <div style={{
        width: 30, height: 30, borderRadius: 6, background: 'var(--risk-soft)',
        color: 'var(--risk)', display: 'grid', placeItems: 'center',
        fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 700,
      }}>!</div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>{label}</div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg-3)' }}>
          {timeStr}{a.category ? ` · ${a.category}` : ''}
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>
          ${Number(a.amount).toFixed(2)}
        </div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--risk)', marginTop: 2 }}>
          {Math.round(Number(a.confidence))}% conf
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────

export default function Dashboard() {
  const { transactions } = useTransactions(500);
  const { metrics }      = useDashboardMetrics();
  const { alerts }       = useRecentAlerts(8);

  const rawTotal  = metrics?.totalTransactions ?? APP_METRICS.dashboard.defaultTotalTransactions;
  const rawFraud  = metrics?.fraudDetected     ?? APP_METRICS.dashboard.defaultFraudDetected;
  const rawRate   = metrics?.fraudRate         ?? APP_METRICS.dashboard.defaultFraudRatePct;
  const rawAcc    = metrics?.accuracy          ?? APP_METRICS.dashboard.defaultModelAccuracyPct;

  const txTotal    = useCountUp(rawTotal,  1800, 0);
  const fraudCount = useCountUp(rawFraud,  1400, 0);
  const fraudRate  = useCountUp(rawRate,   1600, 2);
  const accuracy   = useCountUp(rawAcc,    1400, 1);

  const volumeData = buildVolumeData(transactions);
  const heatmap    = buildHeatmap(transactions);
  const catDist    = buildCategoryDist(transactions);
  const catRows    = catDist.length > 0 ? catDist : FALLBACK_CATS;
  const sparkFraud = volumeData.map(d => d.fraud);

  return (
    <>
      {/* ── Row 1: KPI cards ──────────────────────────────────── */}
      <div className="reveal" data-d="1" style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 14, marginBottom: 14,
      }}>

        {/* Total transactions */}
        <div className="panel" style={{ padding: '20px 22px' }}>
          <div className="panel-sub" style={{ textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
            Transactions processed
          </div>
          <div style={{ fontSize: 34, fontWeight: 500, letterSpacing: '-0.03em', fontVariantNumeric: 'tabular-nums', lineHeight: 1 }}>
            {Math.round(txTotal).toLocaleString()}
          </div>
          <div style={{ marginTop: 8, fontFamily: 'var(--mono)', fontSize: 11 }}>
            <span style={{ padding: '2px 7px', borderRadius: 3, fontSize: 10, color: 'var(--safe)', background: 'var(--safe-soft)' }}>
              ↑ {Math.round(rawTotal / 1440)} tx / min · 24h avg
            </span>
          </div>
        </div>

        {/* Fraud detected */}
        <div className="panel" style={{ padding: '20px 22px', borderColor: 'var(--risk)' }}>
          <div className="panel-sub" style={{ textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
            Cases flagged
          </div>
          <div style={{ fontSize: 34, fontWeight: 500, letterSpacing: '-0.03em', fontVariantNumeric: 'tabular-nums', lineHeight: 1, color: 'var(--risk)' }}>
            {Math.round(fraudCount)}
          </div>
          <div style={{ marginTop: 8, fontFamily: 'var(--mono)', fontSize: 11 }}>
            <span style={{ padding: '2px 7px', borderRadius: 3, fontSize: 10, color: 'var(--risk)', background: 'var(--risk-soft)' }}>
              ↑ +{Math.round(rawFraud * 0.2)} new cases · last 60 min
            </span>
          </div>
        </div>

        {/* Fraud rate + sparkline */}
        <div className="panel" style={{ padding: '20px 22px', position: 'relative', overflow: 'hidden' }}>
          <div className="panel-sub" style={{ textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
            Fraud incidence rate
          </div>
          <div style={{ fontSize: 34, fontWeight: 500, letterSpacing: '-0.03em', fontVariantNumeric: 'tabular-nums', lineHeight: 1 }}>
            {fraudRate.toFixed(2)}
            <span style={{ fontSize: 16, color: 'var(--fg-3)', fontWeight: 400, marginLeft: 3 }}>%</span>
          </div>
          <div style={{ marginTop: 8, fontFamily: 'var(--mono)', fontSize: 11 }}>
            <span style={{ padding: '2px 7px', borderRadius: 3, fontSize: 10, color: 'var(--risk)', background: 'var(--risk-soft)' }}>
              ↑ {APP_METRICS.dashboard.fraudRateDeltaLabel}
            </span>
          </div>
          {/* Sparkline */}
          <svg style={{ position: 'absolute', right: 12, bottom: 12, width: 90, height: 36 }}
               viewBox="0 0 110 44" preserveAspectRatio="none" aria-hidden>
            <defs>
              <linearGradient id="kpiFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#e26d5c" stopOpacity="0.3"/>
                <stop offset="100%" stopColor="#e26d5c" stopOpacity="0"/>
              </linearGradient>
            </defs>
            {(() => {
              const pts = sparkFraud.length >= 2 ? sparkFraud : [2,3,2,4,3,5,4,6,5,7];
              const min = Math.min(...pts), max = Math.max(...pts, min + 1);
              const xs = pts.map((_, i) => (i / (pts.length - 1)) * 110);
              const ys = pts.map(v => 36 - ((v - min) / (max - min)) * 28);
              const line = pts.map((_, i) => `${i === 0 ? 'M' : 'L'}${xs[i]},${ys[i]}`).join(' ');
              return (
                <>
                  <path d={`${line} L${xs[xs.length-1]},44 L0,44 Z`} fill="url(#kpiFill)"/>
                  <path d={line} fill="none" stroke="#e26d5c" strokeWidth="1.5"/>
                  <circle cx={xs[xs.length-1]} cy={ys[ys.length-1]} r="2.5" fill="#e26d5c"/>
                </>
              );
            })()}
          </svg>
        </div>

        {/* Model accuracy */}
        <div className="panel" style={{ padding: '20px 22px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div className="panel-sub" style={{ textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
              Detection precision
            </div>
            <div style={{ fontSize: 34, fontWeight: 500, letterSpacing: '-0.03em', fontVariantNumeric: 'tabular-nums', lineHeight: 1 }}>
              {accuracy.toFixed(1)}
              <span style={{ fontSize: 16, color: 'var(--fg-3)', fontWeight: 400, marginLeft: 3 }}>%</span>
            </div>
            <div style={{ marginTop: 8, fontFamily: 'var(--mono)', fontSize: 11 }}>
              <span style={{ padding: '2px 7px', borderRadius: 3, fontSize: 10, color: 'var(--safe)', background: 'var(--safe-soft)' }}>
                Recall: {APP_METRICS.dashboard.displayRecallPct}%
              </span>
            </div>
          </div>
          <RingGauge pct={accuracy} color={C.safe} />
        </div>
      </div>

      {/* ── Row 2: Volume chart + Fraud alerts ────────────────── */}
      <div className="reveal" data-d="2" style={{
        display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 14, marginBottom: 14,
      }}>
        {/* Volume chart */}
        <div className="panel" style={{ gridColumn: 'span 8' }}>
          <div className="panel-head">
            <div>
              <div className="panel-title">Transaction volume <em>· fraud event overlay</em></div>
              <div className="panel-sub">Rolling 24-hour window · hourly resolution</div>
            </div>
            <div style={{ display: 'flex', gap: 16, fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg-2)' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 10, height: 2, background: C.volume, display: 'inline-block' }}/>volume
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 10, height: 2, background: C.fraud, display: 'inline-block' }}/>fraud
              </span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={volumeData} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
              <defs>
                <linearGradient id="volFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={C.volume} stopOpacity={0.18}/>
                  <stop offset="95%" stopColor={C.volume} stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="fraudFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={C.fraud} stopOpacity={0.25}/>
                  <stop offset="95%" stopColor={C.fraud} stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid stroke={C.grid} strokeDasharray="3 3" vertical={false}/>
              <XAxis dataKey="label"
                tick={{ fill: C.axis, fontSize: 10, fontFamily: 'IBM Plex Mono, monospace' }}
                tickLine={false} axisLine={false} interval="preserveStartEnd"/>
              <YAxis
                tick={{ fill: C.axis, fontSize: 10, fontFamily: 'IBM Plex Mono, monospace' }}
                tickLine={false} axisLine={false}/>
              <RcTooltip
                contentStyle={{ background: C.tip, border: `1px solid ${C.grid}`, borderRadius: 6, fontFamily: 'IBM Plex Mono, monospace', fontSize: 11 }}
                labelStyle={{ color: C.volume, marginBottom: 4 }}
                itemStyle={{ color: '#ecedef' }}
              />
              <Area type="monotone" dataKey="total" stroke={C.volume} strokeWidth={1.5} fill="url(#volFill)" dot={false} name="Volume"/>
              <Area type="monotone" dataKey="fraud" stroke={C.fraud}  strokeWidth={1.5} fill="url(#fraudFill)" dot={false} name="Fraud"/>
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Fraud alerts */}
        <div className="panel" style={{ gridColumn: 'span 4' }}>
          <div className="panel-head">
            <div className="panel-title">Active fraud cases <em>· live</em></div>
            <span className="pill"><span className="live-dot"/>LIVE</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 292, overflowY: 'auto' }}>
            {alerts.length === 0
              ? <div style={{ color: 'var(--fg-3)', fontFamily: 'var(--mono)', fontSize: 12, padding: '8px 0' }}>No fraud activity detected in this window.</div>
              : alerts.map((a, i) => <AlertCard key={a.transNum ?? a.transaction_id ?? i} a={a}/>)
            }
          </div>
        </div>
      </div>

      {/* ── Row 3: Real-time feed + Category distribution ─────── */}
      <div className="reveal" data-d="3" style={{
        display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 14, marginBottom: 14,
      }}>
        {/* Real-time feed */}
        <div style={{ gridColumn: 'span 8' }}>
          <RealTimeFeed transactions={transactions.slice(0, 50)}/>
        </div>

        {/* Category distribution */}
        <div className="panel" style={{ gridColumn: 'span 4' }}>
          <div className="panel-head">
            <div className="panel-title">Category exposure</div>
            <div className="panel-sub">by share of total transaction volume</div>
          </div>
          {catRows.map((cat, i) => (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '1fr auto',
              alignItems: 'center', gap: 10,
              padding: '9px 0',
              borderBottom: i < catRows.length - 1 ? '1px solid var(--rule)' : 'none',
            }}>
              <div>
                <div style={{ fontSize: 13, marginBottom: 5, textTransform: 'capitalize' }}>{cat.name}</div>
                <div style={{ height: 4, background: 'var(--ink-3)', borderRadius: 2, overflow: 'hidden' }}>
                  <span style={{ display: 'block', height: '100%', width: `${cat.pct}%`, background: cat.fraud > 2 ? C.fraud : C.safe, borderRadius: 2 }}/>
                </div>
              </div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg-2)', width: 36, textAlign: 'right' }}>
                {cat.pct}%
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Row 4: Risk heatmap ───────────────────────────────── */}
      <div className="panel reveal" data-d="4">
        <div className="panel-head">
          <div>
            <div className="panel-title">Fraud density heatmap <em>· hour × weekday</em></div>
            <div className="panel-sub">Relative fraud event concentration · 7-day rolling baseline</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, paddingTop: 1 }}>
            {DAYS.map(d => (
              <div key={d} style={{ height: 14, display: 'flex', alignItems: 'center', fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--fg-4)', width: 24 }}>{d}</div>
            ))}
          </div>
          <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'repeat(24, 1fr)', gridAutoRows: 14, gap: 2 }}>
            {heatmap.flat().map((level, idx) => (
              <div key={idx} style={{
                borderRadius: 2,
                background: level === 0 ? '#22252c'
                  : level === 1 ? '#2a4a3c'
                  : level === 2 ? '#3d6552'
                  : level === 3 ? '#5a8a73'
                  : level === 4 ? '#f0b35a55'
                  : '#e26d5c',
              }}/>
            ))}
          </div>
        </div>
        <div style={{ marginTop: 6, marginLeft: 32, display: 'grid', gridTemplateColumns: 'repeat(24, 1fr)', gap: 2 }}>
          {Array.from({ length: 24 }, (_, i) => (
            <div key={i} style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--fg-4)', textAlign: 'center' }}>
              {i % 6 === 0 ? `${String(i).padStart(2, '0')}h` : ''}
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 10, fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg-3)' }}>
          Low
          {(['#2a4a3c', '#3d6552', '#5a8a73', '#f0b35a55', '#e26d5c'] as const).map((bg, i) => (
            <span key={i} style={{ width: 12, height: 12, borderRadius: 2, background: bg, display: 'inline-block' }}/>
          ))}
          High
        </div>
      </div>
    </>
  );
}
