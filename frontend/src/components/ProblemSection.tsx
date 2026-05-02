import { useReveal } from '../hooks/useReveal';

const ProblemSection = () => {
  const { ref: textRef, isVisible: textVisible } = useReveal();
  const { ref: cardRef, isVisible: cardVisible } = useReveal(0.15);

  return (
    <section
      id="problem"
      style={{
        padding: '100px 32px',
        background: 'var(--bg-deep)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Fraud ambient glow */}
      <div style={{ position: 'absolute', top: '-100px', right: '-100px', width: '500px', height: '500px', background: 'radial-gradient(circle, rgba(255,45,85,0.06) 0%, transparent 70%)', pointerEvents: 'none' }} />
      {/* Grid bg */}
      <div style={{ position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(rgba(255,45,85,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,45,85,0.025) 1px, transparent 1px)', backgroundSize: '48px 48px', maskImage: 'radial-gradient(ellipse 70% 70% at 70% 50%, black 30%, transparent 100%)', WebkitMaskImage: 'radial-gradient(ellipse 70% 70% at 70% 50%, black 30%, transparent 100%)', pointerEvents: 'none' }} />

      <div style={{ maxWidth: '1280px', margin: '0 auto', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '80px', alignItems: 'center', position: 'relative', zIndex: 2 }}>

        {/* Left — copy */}
        <div ref={textRef} className={`reveal${textVisible ? ' visible' : ''}`}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', letterSpacing: '0.2em', textTransform: 'uppercase', color: 'var(--fraud)', opacity: 0.8, marginBottom: '16px' }}>
            The Problem
          </div>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(28px, 4vw, 44px)', fontWeight: 800, color: 'var(--text-bright)', letterSpacing: '-0.02em', lineHeight: 1.1, marginBottom: '20px' }}>
            The Hidden Cost of Delayed Fraud Detection
          </h2>
          <p style={{ fontFamily: 'var(--font-body)', fontSize: '15px', color: 'var(--text-secondary)', lineHeight: 1.75, marginBottom: '36px', maxWidth: '460px' }}>
            In the world of digital transactions, every second counts. Traditional fraud detection systems rely on batch processing that leaves a critical window of opportunity for fraudsters. By the time a flag is raised, the damage is done.
          </p>

          {/* Stats */}
          {[
            { value: '$32.39B', label: 'Global fraud losses annually', color: 'var(--fraud)' },
            { value: '$40B+', label: 'Projected losses by 2027', color: 'var(--amber)' },
            { value: '<1s', label: 'Window to catch fraud in real-time', color: 'var(--cyan)' },
          ].map(({ value, label, color }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '20px', marginBottom: '20px' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '26px', fontWeight: 600, color, minWidth: '110px', letterSpacing: '-0.02em' }}>
                {value}
              </div>
              <div style={{ fontFamily: 'var(--font-label)', fontSize: '12px', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
                {label}
              </div>
            </div>
          ))}

          {/* Pulsing fraud dot */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '8px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: 'var(--fraud)', display: 'inline-block', animation: 'pulseRed 1.4s ease-in-out infinite' }} />
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.06em' }}>
              fraud events are occurring right now
            </span>
          </div>
        </div>

        {/* Right — animated fraud alert card */}
        <div ref={cardRef} className={`reveal${cardVisible ? ' visible' : ''}`} style={{ transitionDelay: '0.15s' }}>
          {/* Stacked cards effect */}
          <div style={{ position: 'relative' }}>
            <div style={{ position: 'absolute', top: '12px', left: '12px', right: '-12px', bottom: '-12px', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--r-xl)', opacity: 0.4 }} />
            <div style={{ position: 'absolute', top: '6px', left: '6px', right: '-6px', bottom: '-6px', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--r-xl)', opacity: 0.6 }} />

            {/* Main alert card */}
            <div style={{ position: 'relative', background: 'var(--fraud-dim)', border: '1px solid var(--fraud-border)', borderLeft: '4px solid var(--fraud)', borderRadius: 'var(--r-xl)', padding: '28px', backdropFilter: 'blur(12px)' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--fraud)', letterSpacing: '0.15em', textTransform: 'uppercase', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--fraud)', display: 'inline-block', animation: 'pulseRed 1.4s ease-in-out infinite' }} />
                ALERT: High-risk transaction detected
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
                <div>
                  <div style={{ fontFamily: 'var(--font-display)', fontSize: '18px', fontWeight: 700, color: 'var(--text-bright)' }}>
                    Crypto Exchange
                  </div>
                  <div style={{ fontFamily: 'var(--font-label)', fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', marginTop: '3px' }}>
                    Finance · Card ****-1943
                  </div>
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '28px', fontWeight: 500, color: 'var(--fraud)' }}>
                  $4,500.00
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '20px' }}>
                {[['Distance', '1,204 km'], ['Confidence', '99.1%'], ['Time', '14:32:08']].map(([k, v]) => (
                  <div key={k}>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>{k}</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: k === 'Confidence' ? 'var(--fraud)' : 'var(--text-primary)', marginTop: '2px' }}>{v}</div>
                  </div>
                ))}
              </div>

              <div style={{ background: 'rgba(255,45,85,0.15)', border: '1px solid var(--fraud-border)', borderRadius: 'var(--r-sm)', padding: '8px 12px', fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--fraud)', letterSpacing: '0.06em', textAlign: 'center' }}>
                ▶ ACTION: Transaction held pending analyst review
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default ProblemSection;
