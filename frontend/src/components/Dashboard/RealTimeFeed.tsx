import React from 'react';
import type { Transaction } from '../../types';

const AlertCard: React.FC<{ alert: Transaction; isNew: boolean }> = ({ alert, isNew }) => (
  <div
    className={isNew ? 'animate-slide-down' : ''}
    style={{
      background: 'var(--fraud-dim)',
      border: '1px solid var(--fraud-border)',
      borderLeft: '3px solid var(--fraud)',
      borderRadius: 'var(--r-lg)',
      padding: '14px 16px',
      marginBottom: '10px',
      transition: 'border-color 0.2s',
    }}
  >
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
      <div>
        <div
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: '14px',
            fontWeight: 600,
            color: 'var(--text-bright)',
            marginBottom: '2px',
          }}
        >
          {alert.merchant}
        </div>
        <div
          style={{
            fontFamily: 'var(--font-label)',
            fontSize: '10px',
            color: 'var(--text-muted)',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
          }}
        >
          {alert.category} · {alert.customer}
        </div>
      </div>
      <div
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '20px',
          fontWeight: 500,
          color: 'var(--fraud)',
        }}
      >
        ${alert.amount.toFixed(2)}
      </div>
    </div>

    <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-secondary)', letterSpacing: '0.08em' }}>
        Distance <span style={{ color: 'var(--text-primary)' }}>{alert.distance} km</span>
      </span>
      {alert.confidence && (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-secondary)', letterSpacing: '0.08em' }}>
          Confidence <span style={{ color: 'var(--fraud)' }}>{alert.confidence.toFixed(1)}%</span>
        </span>
      )}
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-secondary)', letterSpacing: '0.08em' }}>
        Time <span style={{ color: 'var(--text-primary)' }}>{alert.time}</span>
      </span>
    </div>
  </div>
);

const AlertsFeed: React.FC<{ alerts: Transaction[] }> = ({ alerts }) => (
  <div
    style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--r-xl)',
      padding: '20px',
      display: 'flex',
      flexDirection: 'column',
      height: '420px',
    }}
  >
    {/* Panel top accent — fraud red */}
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: '2px',
        background: 'linear-gradient(90deg, var(--fraud), transparent)',
        borderRadius: 'var(--r-xl) var(--r-xl) 0 0',
        opacity: 0.5,
      }}
    />

    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
      <div
        style={{
          fontFamily: 'var(--font-label)',
          fontSize: '10px',
          fontWeight: 600,
          letterSpacing: '0.15em',
          textTransform: 'uppercase',
          color: 'var(--fraud)',
          opacity: 0.8,
        }}
      >
        Fraud Alert Feed
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: 'var(--fraud)',
            animation: 'pulseRed 1.4s ease-in-out infinite',
            display: 'inline-block',
          }}
        />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--fraud)', letterSpacing: '0.1em' }}>
          LIVE
        </span>
      </div>
    </div>

    <div style={{ flex: 1, overflowY: 'auto', paddingRight: '4px' }}>
      {alerts.length === 0 ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            fontFamily: 'var(--font-mono)',
            fontSize: '12px',
            color: 'var(--text-muted)',
          }}
        >
          Monitoring for fraud events…
        </div>
      ) : (
        alerts.map((alert, i) => (
          <AlertCard key={alert.id} alert={alert} isNew={i === 0} />
        ))
      )}
    </div>
  </div>
);

export default AlertsFeed;
