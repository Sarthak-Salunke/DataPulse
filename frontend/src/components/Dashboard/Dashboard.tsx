// ── Dashboard — full redesign matching design/DataPulse Dashboard Redesign.html ──
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip as RcTooltip, ResponsiveContainer,
} from 'recharts';
import { useTransactions, useDashboardMetrics, useRecentAlerts } from '../../hooks/useApiData';
import type { FraudAlert, Transaction } from '../../types';
import { useCountUp } from '../../hooks/useCountUp';
import RealTimeFeed from './RealTimeFeed';

// CSS vars don't work in SVG/Recharts props — use hex constants
const C = {
  grid:   '#262932',
  volume: '#a8acb4',
  fraud:  '#e26d5c',
  axis:   '#6b6f78',
  tip:    '#191b20',
  accent: '#f0b35a',
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
  { name: 'grocery pos', pct: 28, fraud: 1 },
  { name: 'shopping net', pct: 22, fraud: 5 },
  { name: 'misc net', pct: 18, fraud: 3 },
  { name: 'gas transport', pct: 12, fraud: 1 },
  { name: 'home', pct: 10, fraud: 2 },
  { name: 'entertainment', pct: 10, fraud: 1 },
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
  const hasData = result.flat().some(v => v > 0);
  return hasData ? result : FALLBACK_HEAT;
}

const FALLBACK_HEAT: number[][] = Array.from({ length: 7 }, (_, day) =>
  Array.from({ length: 24 }, (_, hr) =>
    Math.max(0, Math.min(5, Math.round(Math.sin(day * 0.8 + hr * 0.4) * 2 + Math.cos(hr * 0.6) * 1.5 + 2.5)))
  )
);

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

// ── Inline sub-components ─────────────────────────────────────────

function RingGauge({ pct, color }: { pct: number; color: string }) {
  const r = 26, circ = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 64 64" style={{ width: 56, height: 56, flexShrink: 0 }}>
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
        width: 32, height: 32, borderRadius: 6, background: 'var(--risk-soft)',
        color: 'var(--risk)', display: 'grid', placeItems: 'center',
        fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 600,
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

  const rawTotal  = metrics?.totalTransactions ?? 23400;
  const rawFraud  = metrics?.fraudDetected     ?? 47;
  const rawRate   = metrics?.fraudRate         ?? 0.42;
  const rawAcc    = metrics?.accuracy          ?? 94.3;

  const fraudRate  = useCountUp(rawRate,   1600, 2);
  const accuracy   = useCountUp(rawAcc,    1400, 1);
  const txTotal    = useCountUp(rawTotal,  1800, 0);
  const fraudCount = useCountUp(rawFraud,  1400, 0);

  const volumeData = buildVolumeData(transactions);
  const heatmap    = buildHeatmap(transactions);
  const catDist    = buildCategoryDist(transactions);
  const catRows    = catDist.length > 0 ? catDist : FALLBACK_CATS;
  const sparkFraud = volumeData.map(d => d.fraud);
  const capitalK   = ((rawFraud * 3900) / 1000).toFixed(1);

  return (
    <>
      {/* ── Hero ──────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 14, marginBottom: 14 }}>
        {/* Fraud rate card */}
        <div className="panel reveal" data-d="1" style={{
          position: 'relative', overflow: 'hidden', padding: '24px 28px',
          background: 'linear-gradient(180deg, var(--ink-1), var(--ink-0))',
          borderColor: 'var(--rule-strong)',
        }}>
          <div className="panel-sub" style={{
            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14,
            color: 'var(--risk)', textTransform: 'uppercase', letterSpacing: '0.04em',
          }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--risk)', display: 'inline-block' }}/>
            FRAUD INCIDENCE RATE · ROLLING 1H
          </div>
          <div style={{
            fontSize: 64, fontWeight: 500, letterSpacing: '-0.04em',
            fontVariantNumeric: 'tabular-nums', lineHeight: 1,
          }}>
            {fraudRate.toFixed(2)}
            <span style={{ fontSize: 28, color: 'var(--fg-3)', fontWeight: 400, marginLeft: 4 }}>%</span>
          </div>
          <div style={{ marginTop: 10, color: 'var(--fg-2)', fontSize: 13, display: 'flex', alignItems: 'baseline', gap: 14 }}>
            {Math.round(fraudCount)} of {Math.round(txTotal).toLocaleString()} transactions flagged
            <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--risk)' }}>
              ↑ +0.08 pp vs prior hour
            </span>
          </div>
          {/* Inline sparkline */}
          <svg style={{ position: 'absolute', right: 28, bottom: 24, width: 220, height: 70 }}
               viewBox="0 0 280 80" preserveAspectRatio="none" aria-hidden>
            <defs>
              <linearGradient id="heroFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#e26d5c" stopOpacity="0.3"/>
                <stop offset="100%" stopColor="#e26d5c" stopOpacity="0"/>
              </linearGradient>
            </defs>
            {(() => {
              const pts = sparkFraud.length >= 2 ? sparkFraud : [2,3,2,4,3,5,4,6,5,7,6,8,7,9,8,10];
              const min = Math.min(...pts), max = Math.max(...pts, min + 1);
              const xs = pts.map((_, i) => (i / (pts.length - 1)) * 280);
              const ys = pts.map(v => 70 - ((v - min) / (max - min)) * 58);
              const line = pts.map((_, i) => `${i === 0 ? 'M' : 'L'}${xs[i]},${ys[i]}`).join(' ');
              return (
                <>
                  <path d={`${line} L${xs[xs.length-1]},80 L0,80 Z`} fill="url(#heroFill)"/>
                  <path d={line} fill="none" stroke="#e26d5c" strokeWidth="1.5"/>
                  <circle cx={xs[xs.length-1]} cy={ys[ys.length-1]} r="3" fill="#e26d5c"/>
                </>
              );
            })()}
          </svg>
        </div>

        {/* Mini-stats column */}
        <div style={{ display: 'grid', gridTemplateRows: '1fr 1fr', gap: 14 }}>
          <div className="panel reveal" data-d="2" style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 18px',
          }}>
            <div>
              <div className="panel-sub" style={{ textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Model confidence</div>
              <div style={{ fontSize: 26, fontWeight: 500, letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums', lineHeight: 1.1 }}>
                {accuracy.toFixed(1)}<small style={{ fontSize: 13, color: 'var(--fg-3)', marginLeft: 2 }}>%</small>
              </div>
              <div className="panel-sub" style={{ marginTop: 4 }}>precision · recall 92.0%</div>
            </div>
            <RingGauge pct={accuracy} color={C.safe} />
          </div>
          <div className="panel reveal" data-d="3" style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 18px',
          }}>
            <div>
              <div className="panel-sub" style={{ textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Capital at risk · today</div>
              <div style={{ fontSize: 26, fontWeight: 500, letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums', lineHeight: 1.1 }}>
                ${capitalK}<small style={{ fontSize: 13, color: 'var(--fg-3)', marginLeft: 2 }}>K</small>
              </div>
              <div className="panel-sub" style={{ marginTop: 4 }}>across {rawFraud} incidents</div>
            </div>
            <RingGauge pct={Math.min(100, (rawFraud / 200) * 100 + 15)} color={C.fraud} />
          </div>
        </div>
      </div>

      {/* ── KPI strip ─────────────────────────────────────────── */}
      <div className="reveal" data-d="4" style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        background: 'var(--ink-1)', border: '1px solid var(--rule)',
        borderRadius: 12, marginBottom: 18, overflow: 'hidden',
      }}>
        {([
          { label: 'Throughput', value: `${Math.round(rawTotal / 1440)}/min`, meta: '↑ 4.2% vs 24h avg', good: true },
          { label: 'Fraud detected', value: String(rawFraud), meta: `+${Math.round(rawFraud * 0.2)} last hour`, good: false },
          { label: 'False positives', value: String(Math.max(1, Math.round(rawFraud * 0.06))), meta: '↓ 2 last hour', good: true },
          { label: 'Median latency', value: '38 ms', meta: 'P99 · 142 ms', good: null as boolean | null },
        ] as { label: string; value: string; meta: string; good: boolean | null }[]).map((k, i) => (
          <div key={k.label} style={{
            padding: '18px 22px',
            borderRight: i < 3 ? '1px solid var(--rule)' : 'none',
          }}>
            <div className="panel-sub" style={{ textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>{k.label}</div>
            <div style={{ fontSize: 24, fontWeight: 500, letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums', lineHeight: 1.1 }}>
              {k.value}
            </div>
            <div style={{ marginTop: 6, fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg-3)' }}>
              <span style={{
                padding: '1px 6px', borderRadius: 3, fontSize: 10,
                color: k.good === true ? 'var(--safe)' : k.good === false ? 'var(--risk)' : 'var(--fg-3)',
                background: k.good === true ? 'var(--safe-soft)' : k.good === false ? 'var(--risk-soft)' : 'transparent',
              }}>{k.meta}</span>
            </div>
          </div>
        ))}
      </div>

      {/* ── Main grid ─────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 14 }}>

        {/* Volume chart — col 8 */}
        <div className="panel reveal" data-d="5" style={{ gridColumn: 'span 8' }}>
          <div className="panel-head">
            <div>
              <div className="panel-title">Transaction volume <em>vs. flagged events</em></div>
              <div className="panel-sub">past 24 hours · hourly buckets</div>
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

        {/* Fraud alerts feed — col 4 */}
        <div className="panel reveal" data-d="6" style={{ gridColumn: 'span 4' }}>
          <div className="panel-head">
            <div className="panel-title">Fraud alerts <em>· live</em></div>
            <span className="pill"><span className="live-dot"/>LIVE</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 292, overflowY: 'auto' }}>
            {alerts.length === 0
              ? <div style={{ color: 'var(--fg-3)', fontFamily: 'var(--mono)', fontSize: 12, padding: '8px 0' }}>No active alerts</div>
              : alerts.map((a, i) => <AlertCard key={a.transNum ?? a.transaction_id ?? i} a={a}/>)
            }
          </div>
        </div>

        {/* Real-time feed table — col 8 */}
        <div className="reveal" data-d="7" style={{ gridColumn: 'span 8' }}>
          <RealTimeFeed transactions={transactions.slice(0, 50)}/>
        </div>

        {/* Pipeline health — col 4 */}
        <div className="panel reveal" data-d="8" style={{ gridColumn: 'span 4' }}>
          <div className="panel-head">
            <div className="panel-title">Pipeline health</div>
            <span className="pill"><span className="live-dot"/>LIVE</span>
          </div>
          {([
            { name: 'Kafka ingest',  v: 92, label: '23.4K msg/s', ok: true },
            { name: 'Sklearn model', v: 76, label: '2.0s batch',  ok: true },
            { name: 'Feature store', v: 64, label: '8 ms lookup', ok: true },
            { name: 'Decision API',  v: 48, label: '38 ms',       ok: false },
          ] as { name: string; v: number; label: string; ok: boolean }[]).map((row, i, arr) => (
            <div key={row.name} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '10px 0',
              borderBottom: i < arr.length - 1 ? '1px solid var(--rule)' : 'none',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', flexShrink: 0, background: row.ok ? C.safe : C.accent, display: 'inline-block' }}/>
                {row.name}
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg-2)' }}>{row.label}</div>
                <div style={{ width: 80, height: 3, background: 'var(--ink-3)', borderRadius: 2, overflow: 'hidden', marginTop: 4 }}>
                  <span style={{ display: 'block', height: '100%', width: `${row.v}%`, background: C.safe, borderRadius: 2 }}/>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Risk heatmap — col 8 */}
        <div className="panel reveal" data-d="9" style={{ gridColumn: 'span 8' }}>
          <div className="panel-head">
            <div>
              <div className="panel-title">Risk heatmap <em>· hour × day</em></div>
              <div className="panel-sub">fraud event density by weekday and hour of day</div>
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

        {/* Category distribution — col 4 */}
        <div className="panel reveal" data-d="10" style={{ gridColumn: 'span 4' }}>
          <div className="panel-head">
            <div className="panel-title">Top categories</div>
            <div className="panel-sub">by transaction volume</div>
          </div>
          {catRows.map((cat, i) => (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '1fr auto',
              alignItems: 'center', gap: 10,
              padding: '8px 0',
              borderBottom: i < catRows.length - 1 ? '1px solid var(--rule)' : 'none',
            }}>
              <div>
                <div style={{ fontSize: 13, marginBottom: 4, textTransform: 'capitalize' }}>{cat.name}</div>
                <div style={{ height: 4, background: 'var(--ink-3)', borderRadius: 2, overflow: 'hidden' }}>
                  <span style={{ display: 'block', height: '100%', width: `${cat.pct}%`, background: cat.fraud > 2 ? C.fraud : C.accent, borderRadius: 2 }}/>
                </div>
              </div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg-2)', width: 44, textAlign: 'right' }}>
                {cat.pct}%
              </div>
            </div>
          ))}
        </div>

      </div>
    </>
  );
}
