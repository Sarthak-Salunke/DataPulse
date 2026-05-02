import React, { useEffect, useState } from 'react';
import MetricsCard from './MetricsCard';
import AlertsFeed from './RealTimeFeed';
import TransactionChart from '../Charts/TransactionChart';
import CreditDebitChart from '../Charts/CreditDebitChart';
import SystemAdvicesChart from '../Charts/SystemAdvicesChart';
import type { Transaction, KPI, TransactionStatus, Toast as ToastType } from '../../types';
import { ICONS } from '../../utils/constants';
import { useDashboardMetrics, useRecentAlerts, useWebSocket } from '../../hooks/useApiData';
import type { FraudAlert } from '../../hooks/useApiData';

// ── Panel wrapper ──────────────────────────────────────────────────────────
const Panel: React.FC<{ children: React.ReactNode; className?: string; style?: React.CSSProperties }> = ({
  children,
  className,
  style,
}) => (
  <div
    className={className}
    style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--r-xl)',
      padding: '20px',
      position: 'relative',
      overflow: 'hidden',
      ...style,
    }}
  >
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: '2px',
        background: 'linear-gradient(90deg, var(--cyan), transparent)',
        opacity: 0.4,
      }}
    />
    {children}
  </div>
);

const PanelTitle: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div
    style={{
      fontFamily: 'var(--font-label)',
      fontSize: '10px',
      fontWeight: 600,
      letterSpacing: '0.15em',
      textTransform: 'uppercase',
      color: 'var(--cyan)',
      opacity: 0.7,
      marginBottom: '14px',
    }}
  >
    {children}
  </div>
);

// ── Status badge ───────────────────────────────────────────────────────────
const StatusBadge: React.FC<{ status: TransactionStatus }> = ({ status }) => {
  const isFraud = status === 'Fraud';
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        padding: '3px 8px',
        borderRadius: 'var(--r-sm)',
        fontFamily: 'var(--font-label)',
        fontSize: '10px',
        fontWeight: 600,
        letterSpacing: '0.08em',
        background: isFraud ? 'var(--fraud-dim)' : 'var(--safe-dim)',
        border: `1px solid ${isFraud ? 'var(--fraud-border)' : 'rgba(0,232,122,0.25)'}`,
        color: isFraud ? 'var(--fraud)' : 'var(--safe)',
      }}
    >
      <span
        style={{
          width: '5px',
          height: '5px',
          borderRadius: '50%',
          background: 'currentColor',
          display: 'inline-block',
        }}
      />
      {status}
    </span>
  );
};

// ── Toast ──────────────────────────────────────────────────────────────────
const Toast: React.FC<{ toast: ToastType; onRemove: (id: number) => void }> = ({ toast, onRemove }) => {
  const [exiting, setExiting] = useState(false);
  const [progress, setProgress] = useState(100);
  const isError = toast.type === 'error';
  const accentColor = isError ? 'var(--fraud)' : 'var(--safe)';

  useEffect(() => {
    const start = performance.now();
    const duration = 5000;

    const frame = (now: number) => {
      const pct = Math.max(0, 100 - ((now - start) / duration) * 100);
      setProgress(pct);
      if (pct > 0) requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);

    const dismissTimer = setTimeout(() => setExiting(true), duration);
    return () => clearTimeout(dismissTimer);
  }, []);

  useEffect(() => {
    if (exiting) {
      const t = setTimeout(() => onRemove(toast.id), 320);
      return () => clearTimeout(t);
    }
  }, [exiting, onRemove, toast.id]);

  return (
    <div
      className={exiting ? 'toast-out' : 'toast-in'}
      onClick={() => setExiting(true)}
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderLeft: `3px solid ${accentColor}`,
        borderRadius: 'var(--r-lg)',
        padding: '14px 16px',
        display: 'flex',
        gap: '12px',
        alignItems: 'flex-start',
        marginBottom: '10px',
        cursor: 'pointer',
        backdropFilter: 'blur(16px)',
        minWidth: '300px',
        maxWidth: '360px',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          width: '30px',
          height: '30px',
          background: isError ? 'var(--fraud-dim)' : 'var(--safe-dim)',
          borderRadius: 'var(--r-sm)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: accentColor,
          fontFamily: 'var(--font-mono)',
          fontSize: '14px',
          fontWeight: 700,
          flexShrink: 0,
        }}
      >
        {isError ? '!' : '✓'}
      </div>
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: '13px',
            fontWeight: 600,
            color: 'var(--text-bright)',
            marginBottom: '2px',
          }}
        >
          {toast.title}
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-secondary)' }}>
          {toast.message}
        </div>
      </div>
      {/* Progress bar */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          height: '2px',
          width: `${progress}%`,
          background: accentColor,
          transition: 'width 0.1s linear',
          borderRadius: '0 0 var(--r-lg) 0',
        }}
      />
    </div>
  );
};

// ── Transaction detail modal ───────────────────────────────────────────────
const TransactionDetailModal: React.FC<{
  transaction: Transaction | null;
  onClose: () => void;
}> = ({ transaction, onClose }) => {
  if (!transaction) return null;
  const isFraud = transaction.status === 'Fraud';

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.7)',
        backdropFilter: 'blur(8px)',
        zIndex: 50,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--r-xl)',
          width: '100%',
          maxWidth: '420px',
          margin: '16px',
          animation: 'slideDown 0.3s ease-out forwards',
        }}
        onClick={e => e.stopPropagation()}
      >
        <div
          style={{
            padding: '20px 24px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: '16px', fontWeight: 700, color: 'var(--text-bright)' }}>
              Transaction Details
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
              {transaction.id}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', padding: '4px' }}
          >
            <ICONS.x className="w-5 h-5" />
          </button>
        </div>

        <div style={{ padding: '20px 24px' }}>
          <div
            style={{
              padding: '16px',
              borderRadius: 'var(--r-lg)',
              marginBottom: '16px',
              textAlign: 'center',
              background: isFraud ? 'var(--fraud-dim)' : 'var(--safe-dim)',
              border: `1px solid ${isFraud ? 'var(--fraud-border)' : 'rgba(0,232,122,0.25)'}`,
            }}
          >
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '28px', fontWeight: 600, color: isFraud ? 'var(--fraud)' : 'var(--safe)' }}>
              ${transaction.amount.toFixed(2)}
            </div>
            <StatusBadge status={transaction.status} />
          </div>

          {[
            ['Time', transaction.time],
            ['Merchant', transaction.merchant],
            ['Category', transaction.category],
            ['Customer', transaction.customer],
            ['Distance', `${transaction.distance} km`],
            ...(isFraud && transaction.confidence ? [['Confidence', `${transaction.confidence.toFixed(1)}%`]] : []),
          ].map(([label, val]) => (
            <div
              key={label}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '8px 0',
                borderBottom: '1px solid var(--border)',
              }}
            >
              <span style={{ fontFamily: 'var(--font-label)', fontSize: '12px', color: 'var(--text-secondary)', letterSpacing: '0.06em' }}>
                {label}
              </span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-primary)' }}>{val}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ── Transaction feed ───────────────────────────────────────────────────────
const TransactionFeed: React.FC<{
  transactions: Transaction[];
  onRowClick: (tx: Transaction) => void;
}> = ({ transactions, onRowClick }) => (
  <Panel style={{ height: '380px', display: 'flex', flexDirection: 'column' }}>
    <PanelTitle>Live Transaction Feed — last 20</PanelTitle>
    <div style={{ overflowX: 'auto', flex: 1 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {['Time', 'Merchant', 'Amount', 'Status'].map(h => (
              <th
                key={h}
                style={{
                  padding: '6px 8px',
                  fontFamily: 'var(--font-label)',
                  fontSize: '10px',
                  fontWeight: 600,
                  letterSpacing: '0.12em',
                  textTransform: 'uppercase',
                  color: 'var(--text-muted)',
                  textAlign: 'left',
                  borderBottom: '1px solid var(--border)',
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {transactions.map((tx, i) => (
            <tr
              key={tx.id}
              onClick={() => onRowClick(tx)}
              className={i === 0 ? 'animate-slide-down' : ''}
              style={{
                borderBottom: '1px solid rgba(0,207,255,0.04)',
                cursor: 'pointer',
                transition: 'background 0.15s',
                background: tx.status === 'Fraud' && i === 0 ? 'rgba(255,45,85,0.06)' : 'transparent',
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLTableRowElement).style.background = 'var(--bg-elevated)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLTableRowElement).style.background = 'transparent'; }}
            >
              <td style={{ padding: '9px 8px', fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)' }}>
                {tx.time}
              </td>
              <td style={{ padding: '9px 8px', fontFamily: 'var(--font-body)', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>
                {tx.merchant}
              </td>
              <td style={{ padding: '9px 8px', fontFamily: 'var(--font-mono)', fontSize: '13px', color: 'var(--text-primary)' }}>
                ${tx.amount.toFixed(2)}
              </td>
              <td style={{ padding: '9px 8px' }}>
                <StatusBadge status={tx.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </Panel>
);

// ── System health ──────────────────────────────────────────────────────────
const SystemHealth: React.FC = () => {
  const services = [
    { name: 'PostgreSQL', stat: '12ms', online: true },
    { name: 'Kafka', stat: '23K msg/s', online: true },
    { name: 'Spark', stat: '2s batch', online: true },
    { name: 'ML Model v1.2', stat: '94.3%', online: true },
  ];

  return (
    <Panel>
      <PanelTitle>System Health</PanelTitle>
      {services.map(svc => (
        <div
          key={svc.name}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '10px 0',
            borderBottom: '1px solid rgba(0,207,255,0.05)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: svc.online ? 'var(--safe)' : 'var(--fraud)',
                display: 'inline-block',
                animation: svc.online
                  ? 'healthPulse 2s ease-in-out infinite'
                  : 'healthPulseRed 0.8s ease-in-out infinite',
              }}
            />
            <span style={{ fontFamily: 'var(--font-label)', fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', letterSpacing: '0.04em' }}>
              {svc.name}
            </span>
          </div>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--cyan)' }}>
            {svc.stat}
          </span>
        </div>
      ))}
    </Panel>
  );
};

// ── Activity log ───────────────────────────────────────────────────────────
const ActivityLog: React.FC<{ logs: { time: string; message: string }[] }> = ({ logs }) => (
  <Panel>
    <PanelTitle>Activity Log</PanelTitle>
    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', lineHeight: 2.2 }}>
      {logs.length === 0 ? (
        <span style={{ color: 'var(--text-muted)' }}>Awaiting activity…</span>
      ) : (
        logs.map((log, i) => (
          <div key={i}>
            <span style={{ color: i === 0 ? 'var(--cyan)' : 'var(--text-muted)' }}>
              [{log.time}]
            </span>{' '}
            <span style={{ color: 'var(--text-secondary)' }}>{log.message}</span>
          </div>
        ))
      )}
    </div>
  </Panel>
);

// ── Mock data helpers ──────────────────────────────────────────────────────
const MERCHANTS = ['Amazon', 'Walmart', 'Apple', 'Starbucks', 'Netflix', 'ExxonMobil', 'Costco', 'Best Buy'];
const CATEGORIES = ['Shopping', 'Grocery', 'Electronics', 'Coffee', 'Streaming', 'Gas', 'Wholesale', 'Retail'];
let txCounter = 1000;

const generateTransaction = (): Transaction => {
  const idx = Math.floor(Math.random() * MERCHANTS.length);
  const isFraud = Math.random() < 0.05;
  const amount = isFraud ? Math.random() * 400 + 100 : Math.random() * 150 + 5;
  return {
    id: `TX${++txCounter}`,
    time: new Date().toLocaleTimeString(),
    customer: `**** **** **** ${String(Math.floor(Math.random() * 9000) + 1000)}`,
    merchant: MERCHANTS[idx],
    category: CATEGORIES[idx],
    amount: parseFloat(amount.toFixed(2)),
    distance: Math.floor(Math.random() * 2000),
    status: isFraud ? 'Fraud' : 'Normal',
    confidence: isFraud ? parseFloat((Math.random() * 12 + 87).toFixed(2)) : undefined,
  };
};

const convertAlertToTransaction = (alert: FraudAlert): Transaction => ({
  id: alert.transNum ?? `API-${Date.now()}`,
  time: new Date(alert.timestamp).toLocaleTimeString(),
  customer: alert.ccNum ?? 'Unknown',
  merchant: alert.merchant ?? 'Unknown',
  category: alert.category ?? 'Unknown',
  amount: alert.amount,
  distance: alert.distance ?? 0,
  status: 'Fraud' as TransactionStatus,
  confidence: alert.confidence,
});

// ── Dashboard ──────────────────────────────────────────────────────────────
const Dashboard: React.FC = () => {
  const { metrics: apiMetrics, loading: metricsLoading } = useDashboardMetrics(5000);
  const { alerts: apiAlerts } = useRecentAlerts(10, 3000);
  const { lastMessage } = useWebSocket();

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [alerts, setAlerts] = useState<Transaction[]>([]);
  const [activityLog, setActivityLog] = useState<{ time: string; message: string }[]>([]);
  const [toasts, setToasts] = useState<ToastType[]>([]);
  const [selectedTx, setSelectedTx] = useState<Transaction | null>(null);

  const addToast = (toast: Omit<ToastType, 'id'>) =>
    setToasts(prev => [...prev.slice(-2), { ...toast, id: Date.now() }]);

  const removeToast = (id: number) =>
    setToasts(prev => prev.filter(t => t.id !== id));

  // WebSocket real-time fraud alerts
  useEffect(() => {
    if (!lastMessage) return;
    if (lastMessage.type === 'fraud_alert' && lastMessage.data) {
      const alert = convertAlertToTransaction(lastMessage.data as FraudAlert);
      setAlerts(prev => [alert, ...prev].slice(0, 10));
      setTransactions(prev => [alert, ...prev].slice(0, 20));
      addToast({ title: 'Fraud Detected', message: `${alert.merchant} · $${alert.amount.toFixed(2)} · ${alert.id}`, type: 'error' });
      setActivityLog(prev => [{ time: alert.time, message: `FRAUD detected: ${alert.id} — $${alert.amount.toFixed(2)}` }, ...prev].slice(0, 8));
    }
  }, [lastMessage]);

  // Sync KPIs from API metrics
  useEffect(() => {
    if (!apiMetrics) return;
    setKpis([
      { title: 'Total Today', value: apiMetrics.totalTransactions.toLocaleString(), details: 'All processed', change: '+2.1%', changeType: 'increase' },
      { title: 'Fraud Detected', value: `${apiMetrics.fraudDetected}`, details: `${apiMetrics.fraudRate.toFixed(2)}% of total`, change: '+5.4%', changeType: 'increase' },
      { title: 'Normal Transactions', value: (apiMetrics.totalTransactions - apiMetrics.fraudDetected).toLocaleString(), details: `${(100 - apiMetrics.fraudRate).toFixed(2)}% of total`, change: '+1.8%', changeType: 'increase' },
      { title: 'Model Accuracy', value: `${apiMetrics.accuracy.toFixed(2)}%`, details: 'Recall: 92.0%', change: '-0.2%', changeType: 'decrease' },
    ]);
  }, [apiMetrics]);

  // Sync alerts from API
  useEffect(() => {
    if (!apiAlerts?.length) return;
    const converted = apiAlerts.map(convertAlertToTransaction);
    setAlerts(converted);
  }, [apiAlerts]);

  // Mock data fallback
  useEffect(() => {
    if (metricsLoading || apiMetrics) return;

    const initial = Array.from({ length: 10 }, generateTransaction);
    setTransactions(initial);

    const interval = setInterval(() => {
      const tx = generateTransaction();
      setTransactions(prev => [tx, ...prev].slice(0, 20));

      if (tx.status === 'Fraud') {
        setAlerts(prev => [tx, ...prev].slice(0, 10));
        setActivityLog(prev => [
          { time: tx.time, message: `FRAUD detected: ${tx.id} — $${tx.amount.toFixed(2)}` },
          ...prev,
        ].slice(0, 8));
        addToast({ title: 'Fraud Detected', message: `${tx.merchant} · $${tx.amount.toFixed(2)}`, type: 'error' });
      } else if (Math.random() > 0.6) {
        setActivityLog(prev => [
          { time: tx.time, message: `Batch processed: ${tx.id}` },
          ...prev,
        ].slice(0, 8));
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [metricsLoading, apiMetrics]);

  // KPIs from mock transactions
  useEffect(() => {
    if (apiMetrics || transactions.length === 0) return;
    const total = 1247 + transactions.length;
    const fraud = 47 + transactions.filter(t => t.status === 'Fraud').length;
    const normal = total - fraud;
    setKpis([
      { title: 'Total Today', value: total.toLocaleString(), details: 'All processed', change: '+2.1%', changeType: 'increase' },
      { title: 'Fraud Detected', value: `${fraud}`, details: `${((fraud / total) * 100).toFixed(2)}% of total`, change: '+5.4%', changeType: 'increase' },
      { title: 'Normal Transactions', value: normal.toLocaleString(), details: `${((normal / total) * 100).toFixed(2)}% of total`, change: '+1.8%', changeType: 'increase' },
      { title: 'Model Accuracy', value: '94.35%', details: 'Recall: 92.0%', change: '-0.2%', changeType: 'decrease' },
    ]);
  }, [transactions, apiMetrics]);

  const kpiAccents = ['var(--cyan)', 'var(--fraud)', 'var(--safe)', 'var(--amber)'];

  return (
    <div style={{ position: 'relative' }}>
      {/* Toast container — fixed bottom-right */}
      <div style={{ position: 'fixed', bottom: '24px', right: '24px', zIndex: 60 }}>
        {toasts.map(toast => (
          <Toast key={toast.id} toast={toast} onRemove={removeToast} />
        ))}
      </div>

      <TransactionDetailModal transaction={selectedTx} onClose={() => setSelectedTx(null)} />

      {/* API unavailable notice */}
      {!metricsLoading && !apiMetrics && (
        <div
          style={{
            background: 'var(--amber-dim)',
            border: '1px solid rgba(255,179,25,0.25)',
            borderRadius: 'var(--r-md)',
            padding: '10px 16px',
            marginBottom: '16px',
            fontFamily: 'var(--font-mono)',
            fontSize: '12px',
            color: 'var(--amber)',
          }}
        >
          ◆ Using simulated data — backend API not reachable
        </div>
      )}

      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px', marginBottom: '16px' }}>
        {kpis.map((kpi, i) => (
          <MetricsCard key={kpi.title} {...kpi} accentColor={kpiAccents[i]} />
        ))}
      </div>

      {/* Main 2-col layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '14px' }}>
        {/* Left column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', minWidth: 0 }}>
          <TransactionFeed transactions={transactions} onRowClick={setSelectedTx} />

          <Panel>
            <PanelTitle>Transactions Over Time</PanelTitle>
            <TransactionChart />
          </Panel>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
            <Panel>
              <PanelTitle>Credit / Debit Split</PanelTitle>
              <CreditDebitChart />
            </Panel>
            <ActivityLog logs={activityLog} />
          </div>
        </div>

        {/* Right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <AlertsFeed alerts={alerts} />
          <SystemHealth />
          <Panel>
            <PanelTitle>System Advisories</PanelTitle>
            <SystemAdvicesChart />
          </Panel>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
