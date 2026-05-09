// ── RealTimeFeed — table with new-row slide-in ─────────────────────
import { useEffect, useState } from 'react';
import type { Transaction } from '../../types';

interface Props { transactions: Transaction[]; }

export default function RealTimeFeed({ transactions }: Props) {
  const [seen, setSeen] = useState<Set<string>>(new Set());
  useEffect(() => {
    setSeen(prev => {
      const next = new Set(prev);
      transactions.forEach(t => next.add(t.id));
      return next;
    });
  }, [transactions]);

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <div className="panel-title">Live transaction feed <em>· 50 most recent</em></div>
          <div className="panel-sub">Live stream · authorized transaction channel</div>
        </div>
        <span className="pill"><span className="live-dot"/>LIVE</span>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Time', 'Card', 'Merchant', 'Category', 'Amount', 'Status'].map(h => (
                <th key={h} style={{
                  textAlign: 'left', padding: '0 8px 8px',
                  fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500,
                  textTransform: 'uppercase', letterSpacing: '0.06em',
                  color: 'var(--fg-3)', borderBottom: '1px solid var(--rule)',
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {transactions.length === 0 && (
              <tr>
                <td colSpan={6} style={{ ...td(), textAlign: 'center', color: 'var(--fg-3)', fontFamily: 'var(--mono)', fontSize: 11, padding: '16px 8px' }}>
                  Awaiting transaction stream — connected to live channel.
                </td>
              </tr>
            )}
            {transactions.slice(0, 12).map((t, i) => {
              const isNew = !seen.has(t.id) && i === 0;
              const isFraud = t.status === 'Fraud';
              return (
                <tr key={t.id} className={isNew ? 'row-new' : ''}>
                  <td style={td('mono')}>{t.time}</td>
                  <td style={td('mono')}>**** {String(t.customer).slice(-4)}</td>
                  <td style={td()}>{t.merchant}</td>
                  <td style={td('mono')}>{t.category}</td>
                  <td style={{ ...td('mono'), textAlign: 'right' }}>${Number(t.amount).toFixed(2)}</td>
                  <td style={td()}>
                    <span className={`tag ${isFraud ? 'fraud' : 'normal'}`}>
                      <span className="dot"/>{isFraud ? 'Flagged' : 'Approved'}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function td(kind?: 'mono'): React.CSSProperties {
  return {
    padding: 8,
    fontSize: 12,
    fontVariantNumeric: 'tabular-nums',
    fontFamily: kind === 'mono' ? 'var(--mono)' : 'var(--sans)',
    color: kind === 'mono' ? 'var(--fg-2)' : 'var(--fg)',
    borderBottom: '1px solid var(--rule)',
  };
}
