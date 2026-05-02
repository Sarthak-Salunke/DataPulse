import React, { useState, useEffect, useRef } from 'react';
import type { KPI } from '../../types';

interface KPICardProps extends KPI {
  accentColor?: string;
}

const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);

const AnimatedCounter: React.FC<{ value: string }> = ({ value }) => {
  const [display, setDisplay] = useState('0');
  const frameRef = useRef<number>(0);
  const startRef = useRef<number>(0);

  const raw = parseFloat(value.replace(/[,%]/g, ''));
  const suffix = value.match(/%/) ? '%' : '';
  const hasDecimal = value.includes('.');
  const decimals = hasDecimal ? value.split('.')[1].replace('%', '').length : 0;

  useEffect(() => {
    startRef.current = performance.now();
    const duration = 1800;

    const step = (now: number) => {
      const t = Math.min((now - startRef.current) / duration, 1);
      const val = easeOutCubic(t) * raw;
      setDisplay(
        hasDecimal ? val.toFixed(decimals) : Math.floor(val).toLocaleString()
      );
      if (t < 1) frameRef.current = requestAnimationFrame(step);
    };

    frameRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frameRef.current);
  }, [raw, hasDecimal, decimals]);

  return <>{display}{suffix}</>;
};

const KPICard: React.FC<KPICardProps> = ({
  title,
  value,
  details,
  change,
  changeType,
  accentColor,
}) => {
  const accent = accentColor ?? 'var(--cyan)';
  const isFraud = title.toLowerCase().includes('fraud');
  const valueColor = isFraud ? 'var(--fraud)' : changeType === 'increase' ? 'var(--text-bright)' : 'var(--text-bright)';
  const trendColor = changeType === 'increase' ? 'var(--safe)' : 'var(--fraud)';
  const trendPrefix = changeType === 'increase' ? '↑' : '↓';

  return (
    <div
      className="card-hover"
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--r-lg)',
        padding: '20px 24px',
        position: 'relative',
        overflow: 'hidden',
        height: '100%',
      }}
    >
      {/* Top accent gradient line */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '2px',
          background: `linear-gradient(90deg, ${accent}, transparent)`,
          opacity: 0.6,
        }}
      />

      <div
        style={{
          fontFamily: 'var(--font-label)',
          fontSize: '11px',
          fontWeight: 600,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          color: 'var(--text-secondary)',
          marginBottom: '10px',
        }}
      >
        {title}
      </div>

      <div
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '34px',
          fontWeight: 500,
          color: valueColor,
          lineHeight: 1,
          letterSpacing: '-0.02em',
          marginBottom: '8px',
        }}
      >
        <AnimatedCounter value={value} />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            color: 'var(--text-muted)',
          }}
        >
          {details}
        </span>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            color: trendColor,
            display: 'flex',
            alignItems: 'center',
            gap: '3px',
          }}
        >
          {trendPrefix} {change}
        </span>
      </div>
    </div>
  );
};

export default KPICard;
