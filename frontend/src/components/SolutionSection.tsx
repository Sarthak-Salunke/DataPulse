import { useState, useEffect, useRef } from 'react';

const STEPS = [
  {
    num: '01',
    title: 'Card Swipe',
    icon: '💳',
    description: 'A customer initiates a transaction. The raw event — card number, merchant, amount, location — is captured at the point of sale and published to the stream.',
    detail: ['Sub-millisecond capture', 'POS terminal integration', 'Raw event payload'],
  },
  {
    num: '02',
    title: 'Apache Kafka',
    icon: '⚡',
    description: 'The transaction event is published to a Kafka topic. Kafka acts as the high-throughput message broker, decoupling ingestion from processing and guaranteeing delivery.',
    detail: ['23K messages/second', 'Durable log retention', 'Topic partitioning'],
  },
  {
    num: '03',
    title: 'Apache Spark',
    icon: '🔥',
    description: 'Spark Streaming consumes the Kafka topic in micro-batches every 2 seconds. Feature engineering runs in-flight: distance from home, transaction velocity, amount z-score.',
    detail: ['2-second micro-batches', 'Feature engineering', 'In-memory processing'],
  },
  {
    num: '04',
    title: 'ML Model',
    icon: '🤖',
    description: 'The engineered feature vector is scored by a pre-trained Random Forest classifier. Predictions above the fraud threshold trigger an alert. Model accuracy: 94.35%.',
    detail: ['Random Forest classifier', '94.35% accuracy · 92% recall', 'Threshold: 0.5 confidence'],
  },
  {
    num: '05',
    title: 'Live Dashboard',
    icon: '📊',
    description: 'Results are written to PostgreSQL and pushed to the React dashboard via a FastAPI WebSocket. Fraud alerts appear within 20 seconds of the original swipe.',
    detail: ['PostgreSQL + TimescaleDB', 'FastAPI WebSocket', '<20s end-to-end latency'],
  },
];

const HowItWorks = () => {
  const [activeStep, setActiveStep] = useState(0);
  const stepRefs = useRef<(HTMLDivElement | null)[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observers: IntersectionObserver[] = [];

    stepRefs.current.forEach((el, i) => {
      if (!el) return;
      const obs = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) setActiveStep(i);
        },
        { threshold: 0.5, rootMargin: '-20% 0px -20% 0px' }
      );
      obs.observe(el);
      observers.push(obs);
    });

    return () => observers.forEach(o => o.disconnect());
  }, []);

  const step = STEPS[activeStep];

  return (
    <section
      id="how-it-works"
      ref={containerRef}
      style={{ background: 'var(--bg-void)', borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}
    >
      <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '0 32px', display: 'grid', gridTemplateColumns: '1fr 1fr', minHeight: '100vh' }}>

        {/* Left — sticky progress panel */}
        <div style={{ position: 'sticky', top: '80px', height: 'fit-content', padding: '80px 60px 80px 0', alignSelf: 'start' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', letterSpacing: '0.2em', textTransform: 'uppercase', color: 'var(--cyan)', opacity: 0.7, marginBottom: '16px' }}>
            How It Works
          </div>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(28px, 3.5vw, 40px)', fontWeight: 800, color: 'var(--text-bright)', letterSpacing: '-0.02em', lineHeight: 1.1, marginBottom: '40px' }}>
            From Swipe to<br />
            <span style={{ color: 'var(--cyan)' }}>Alert in 20s</span>
          </h2>

          {/* Step progress list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
            {STEPS.map((s, i) => {
              const isActive = i === activeStep;
              const isPast = i < activeStep;
              return (
                <div
                  key={i}
                  onClick={() => {
                    stepRefs.current[i]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                  }}
                  style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '12px 0', cursor: 'pointer', borderLeft: `3px solid ${isActive ? 'var(--cyan)' : 'var(--border)'}`, paddingLeft: '16px', transition: 'border-color 0.3s', marginLeft: '-3px' }}
                >
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', letterSpacing: '0.1em', color: isActive ? 'var(--cyan)' : isPast ? 'var(--text-muted)' : 'var(--text-muted)', minWidth: '28px' }}>
                    {s.num}
                  </div>
                  <div style={{ fontFamily: 'var(--font-display)', fontSize: '15px', fontWeight: isActive ? 700 : 500, color: isActive ? 'var(--text-bright)' : isPast ? 'var(--text-muted)' : 'var(--text-secondary)', transition: 'color 0.3s' }}>
                    {s.title}
                  </div>
                  {isActive && (
                    <div style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--cyan)', letterSpacing: '0.1em' }}>
                      ←
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Active step detail card */}
          <div
            key={activeStep}
            style={{
              marginTop: '32px',
              background: 'var(--bg-surface)',
              border: '1px solid var(--cyan-border)',
              borderRadius: 'var(--r-xl)',
              padding: '24px',
              position: 'relative',
              overflow: 'hidden',
              animation: 'staggerFadeUp 0.4s ease forwards',
            }}
          >
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '2px', background: 'linear-gradient(90deg, var(--cyan), transparent)', opacity: 0.5 }} />
            <div style={{ fontSize: '28px', marginBottom: '12px' }}>{step.icon}</div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: '18px', fontWeight: 700, color: 'var(--text-bright)', marginBottom: '10px' }}>
              {step.title}
            </div>
            <p style={{ fontFamily: 'var(--font-body)', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: '16px' }}>
              {step.description}
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {step.detail.map(d => (
                <div key={d} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '4px', height: '4px', borderRadius: '50%', background: 'var(--cyan)', display: 'inline-block', opacity: 0.7 }} />
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.04em' }}>{d}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right — scrollable step sections */}
        <div style={{ padding: '80px 0 80px 60px', borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column' }}>
          {STEPS.map((s, i) => (
            <div
              key={i}
              ref={el => { stepRefs.current[i] = el; }}
              style={{ minHeight: '100vh', display: 'flex', alignItems: 'center' }}
            >
              <div style={{ padding: '40px 0', width: '100%' }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '48px', color: 'var(--border)', fontWeight: 300, marginBottom: '-8px', lineHeight: 1 }}>
                  {s.num}
                </div>
                <div style={{ fontSize: '48px', marginBottom: '20px' }}>{s.icon}</div>
                <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '32px', fontWeight: 800, color: i === activeStep ? 'var(--text-bright)' : 'var(--text-secondary)', letterSpacing: '-0.02em', marginBottom: '16px', transition: 'color 0.4s' }}>
                  {s.title}
                </h3>
                <p style={{ fontFamily: 'var(--font-body)', fontSize: '16px', color: 'var(--text-secondary)', lineHeight: 1.75, maxWidth: '400px', marginBottom: '24px' }}>
                  {s.description}
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {s.detail.map(d => (
                    <span
                      key={d}
                      style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', padding: '5px 12px', background: i === activeStep ? 'var(--cyan-dim)' : 'var(--bg-surface)', border: `1px solid ${i === activeStep ? 'var(--cyan-border)' : 'var(--border)'}`, borderRadius: 'var(--r-sm)', color: i === activeStep ? 'var(--cyan)' : 'var(--text-muted)', letterSpacing: '0.06em', transition: 'all 0.4s' }}
                    >
                      {d}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default HowItWorks;
