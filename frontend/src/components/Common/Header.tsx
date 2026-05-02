import { useTheme } from '../../App';
import { ICONS } from '../../utils/constants';

const Header = () => {
  const { theme, toggleTheme } = useTheme();

  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--r-lg)',
        padding: '14px 20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '20px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: '20px',
            fontWeight: 800,
            letterSpacing: '0.04em',
          }}
        >
          <span style={{ color: 'var(--text-bright)' }}>Data</span>
          <span style={{ color: 'var(--cyan)' }}>Pulse</span>
        </div>
        <div
          style={{
            width: '1px',
            height: '20px',
            background: 'var(--border)',
          }}
        />
        <div
          style={{
            fontFamily: 'var(--font-label)',
            fontSize: '13px',
            fontWeight: 600,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--text-secondary)',
          }}
        >
          Live Fraud Detection Dashboard
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            className="pulse-red"
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: 'var(--safe)',
              display: 'inline-block',
              animation: 'healthPulse 2s ease-in-out infinite',
            }}
          />
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: 'var(--safe)',
              letterSpacing: '0.12em',
            }}
          >
            LIVE
          </span>
        </div>

        <button
          onClick={toggleTheme}
          style={{
            width: '32px',
            height: '32px',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--r-md)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: 'var(--text-secondary)',
            transition: 'border-color 0.2s, color 0.2s',
          }}
          onMouseEnter={e => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--cyan)';
            (e.currentTarget as HTMLButtonElement).style.color = 'var(--cyan)';
          }}
          onMouseLeave={e => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--border)';
            (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-secondary)';
          }}
          aria-label="Toggle theme"
        >
          {theme === 'dark'
            ? <ICONS.sun className="w-4 h-4" />
            : <ICONS.moon className="w-4 h-4" />
          }
        </button>
      </div>
    </div>
  );
};

export default Header;
