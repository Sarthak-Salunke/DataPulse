// ── CaseDetail — fraud case review page ────────────────────────────
import AppShell from '../Common/AppShell';
import Topbar from '../Common/Topbar';

interface Feature { name: string; value: string; weight: number; positive?: boolean; }
const FEATURES: Feature[] = [
  { name: 'Distance from home', value: '1,847 km',          weight: 0.31 },
  { name: 'Velocity (1h)',      value: '5 swipes / 23 min', weight: 0.24 },
  { name: 'Amount vs. card avg',value: '$487 vs. $42 · 11.6×', weight: 0.18 },
  { name: 'Merchant risk',      value: 'Electronics · CNP · 0.73', weight: 0.12 },
  { name: 'Card age',           value: '4.2y · low risk',   weight: 0.04, positive: true },
  { name: 'Cardholder tenure',  value: '7y · 3,420 swipes', weight: 0.03, positive: true },
];

export default function CaseDetail() {
  const max = Math.max(...FEATURES.map(f => f.weight));
  return (
    <AppShell>
      <Topbar
        crumbs={[
          { label: 'Risk operations', href: '/dashboard' },
          { label: 'Fraud alerts', href: '/alerts' },
          { label: 'TX-49281' },
        ]}
        title={<>Suspected card-not-present fraud <span style={{ fontFamily: 'var(--mono)', color: 'var(--fg-3)', fontSize: 14, fontWeight: 400 }}>· TX-49281</span></>}
        actions={
          <>
            <button className="btn">Previous case</button>
            <button className="btn">Next case →</button>
          </>
        }
      />

      {/* ── Verdict bar ── */}
      <div className="reveal" data-d="1" style={{
        background: 'linear-gradient(180deg, var(--risk-soft), var(--ink-1))',
        border: '1px solid var(--risk)',
        borderLeftWidth: 3,
        borderRadius: 12,
        padding: '24px 28px',
        marginBottom: 18,
        display: 'grid',
        gridTemplateColumns: 'auto 1fr auto',
        gap: 32,
        alignItems: 'center',
      }}>
        <div style={{
          width: 56, height: 56, background: 'var(--risk-soft)',
          borderRadius: 12, display: 'grid', placeItems: 'center',
          fontFamily: 'var(--mono)', fontSize: 24, color: 'var(--risk)', fontWeight: 700,
        }}>!</div>
        <div>
          <h2 style={{ margin: '0 0 4px', fontSize: 22, fontWeight: 600, color: 'var(--risk)', letterSpacing: '-0.01em' }}>
            Flagged · 98.2% confidence
          </h2>
          <div style={{ fontSize: 13, color: 'var(--fg-2)' }}>
            Velocity, geography, and merchant risk all out-of-distribution. Decline issued at +44 ms; analyst review pending.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 28 }}>
          <Stat v="$487.20"  l="Amount" />
          <Stat v="98.2%"    l="P(fraud)" color="var(--risk)" />
          <Stat v={<>38<span style={{ fontSize: 14, color: 'var(--fg-3)' }}> ms</span></>} l="Verdict latency" />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 14 }}>
        {/* Feature contributions */}
        <div className="reveal panel" data-d="2" style={{ gridColumn: 'span 8' }}>
          <div className="panel-head">
            <div>
              <div className="panel-title">Why the model flagged this <em>· feature contributions</em></div>
              <div className="panel-sub">SHAP values · top 6 of 38 features</div>
            </div>
            <div className="panel-sub">model: RF v1.2</div>
          </div>
          {FEATURES.map(f => (
            <div key={f.name} style={{
              display: 'grid', gridTemplateColumns: '180px 1fr 60px',
              gap: 12, alignItems: 'center', padding: '10px 0',
              borderBottom: '1px solid var(--rule)',
            }}>
              <div>
                <div style={{ fontSize: 13 }}>{f.name}</div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg-3)', marginTop: 2 }}>{f.value}</div>
              </div>
              <div className="bar-grow" style={{ height: 16, background: 'var(--ink-3)', borderRadius: 4, overflow: 'hidden' }}>
                <span style={{
                  display: 'block', height: '100%',
                  width: `${(f.weight / max) * 100}%`,
                  background: f.positive ? 'var(--safe)' : 'var(--risk)',
                  opacity: 0.85, borderRadius: 4,
                }}/>
              </div>
              <div style={{
                fontFamily: 'var(--mono)', fontSize: 12,
                textAlign: 'right',
                color: f.positive ? 'var(--safe)' : 'var(--risk)',
              }}>
                {f.positive ? '−' : '+'}{f.weight.toFixed(2)}
              </div>
            </div>
          ))}
        </div>

        {/* Cardholder summary */}
        <div className="reveal panel" data-d="3" style={{ gridColumn: 'span 4' }}>
          <div className="panel-head">
            <div>
              <div className="panel-title">Cardholder</div>
              <div className="panel-sub">**** **** **** 4821</div>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <KV l="Holder"     v="M. Chen" />
            <KV l="Issued"     v="2021 · 4.2y" mono />
            <KV l="Home"       v="Seattle, WA" mono />
            <KV l="Avg ticket" v="$42.18" mono />
            <KV l="Last fraud" v="Never" mono color="var(--safe)" />
            <KV l="Tenure"     v="7 yrs" mono />
          </div>
        </div>

        {/* Timeline */}
        <div className="reveal panel" data-d="4" style={{ gridColumn: 'span 12' }}>
          <div className="panel-head">
            <div className="panel-title">Case timeline</div>
            <div className="panel-sub">automated &amp; analyst events</div>
          </div>
          {[
            { t: '14:22:08', kind: 'alert',  m: <><b style={{ color: 'var(--fg)' }}>Fraud verdict</b> · TX-49281 declined at +38 ms (RF v1.2, p=0.982).</> },
            { t: '14:22:09', kind: '',       m: <>Cardholder notified via push &amp; SMS. Auto-temporary-hold placed.</> },
            { t: '14:22:10', kind: '',       m: <>Case <b style={{ color: 'var(--fg)' }}>C-7714</b> created · routed to Tier-2 / S. Marlowe.</> },
            { t: '14:24:42', kind: 'action', m: <><b style={{ color: 'var(--fg)' }}>S. Marlowe</b> opened case.</> },
            { t: '— now —', kind: '',        m: <span style={{ color: 'var(--fg)' }}>Awaiting analyst decision.</span> },
          ].map((row, i) => (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '90px 14px 1fr',
              gap: 10, padding: '6px 0',
              fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--fg-2)',
              alignItems: 'flex-start',
            }}>
              <span style={{ color: 'var(--fg-4)' }}>{row.t}</span>
              <span style={{
                width: 8, height: 8, marginTop: 6, marginLeft: 3,
                borderRadius: 4,
                background:
                  row.kind === 'alert' ? 'var(--risk)' :
                  row.kind === 'action' ? 'var(--amber)' :
                  'var(--fg-3)',
                border: '2px solid var(--ink-1)',
                boxShadow: row.kind === 'alert' ? '0 0 0 1px var(--risk)' :
                           row.kind === 'action' ? '0 0 0 1px var(--amber)' :
                           '0 0 0 1px var(--rule)',
              }}/>
              <span>{row.m}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Action bar */}
      <div className="panel reveal" data-d="5" style={{
        marginTop: 18, display: 'flex',
        alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ fontSize: 13, color: 'var(--fg-2)' }}>
          Resolve case <b style={{ color: 'var(--fg)' }}>C-7714</b>. The cardholder will be notified; the model will incorporate your label in the next training cycle.
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn ghost">Escalate to Tier 3</button>
          <button className="btn ghost">Mark false positive</button>
          <button className="btn danger">Confirm fraud · block card</button>
        </div>
      </div>
    </AppShell>
  );
}

function Stat({ v, l, color }: { v: React.ReactNode; l: string; color?: string }) {
  return (
    <div>
      <div style={{ fontSize: 26, fontWeight: 500, letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums', color: color || 'var(--fg)' }}>{v}</div>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginTop: 4 }}>{l}</div>
    </div>
  );
}

function KV({ l, v, mono, color }: { l: string; v: string; mono?: boolean; color?: string }) {
  return (
    <div>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>{l}</div>
      <div style={{
        fontSize: 14, fontWeight: 500,
        fontFamily: mono ? 'var(--mono)' : 'var(--sans)',
        color: color || 'var(--fg)',
      }}>{v}</div>
    </div>
  );
}
