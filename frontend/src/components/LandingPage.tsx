import { useState, useEffect, useRef } from 'react';
import { useTheme } from '../App';
import { ICONS } from '../utils/constants';
import { useReveal } from '../hooks/useReveal';
import LogoLoop, { type LogoItem } from './Common/LogoLoop';

// ── Smooth scroll helper ───────────────────────────────────────────────────
const scrollTo = (e: React.MouseEvent<HTMLAnchorElement>) => {
  e.preventDefault();
  const id = e.currentTarget.getAttribute('href')?.slice(1);
  if (id) document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

// ── Landing Header ─────────────────────────────────────────────────────────
export const LandingHeader = () => {
  const { theme, toggleTheme } = useTheme();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const navLinks = [
    { href: '#problem', label: 'Problem' },
    { href: '#how-it-works', label: 'How It Works' },
    { href: '#architecture', label: 'Pipeline' },
    { href: '#dashboard', label: 'Dashboard' },
  ];

  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 100,
        background: scrolled ? 'rgba(5,14,28,0.95)' : 'rgba(5,14,28,0.8)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid var(--border)',
        transition: 'background 0.3s',
      }}
    >
      <nav
        style={{
          maxWidth: '1280px',
          margin: '0 auto',
          padding: '0 32px',
          height: '64px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        {/* Logo */}
        <a
          href="#"
          style={{ textDecoration: 'none', fontFamily: 'var(--font-display)', fontSize: '22px', fontWeight: 800, letterSpacing: '0.04em' }}
        >
          <span style={{ color: 'var(--text-bright)' }}>Data</span>
          <span style={{ color: 'var(--cyan)' }}>Pulse</span>
        </a>

        {/* Nav links */}
        <div style={{ display: 'flex', gap: '32px' }}>
          {navLinks.map(({ href, label }) => (
            <a
              key={href}
              href={href}
              onClick={scrollTo}
              style={{
                fontFamily: 'var(--font-label)',
                fontSize: '13px',
                fontWeight: 600,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: 'var(--text-secondary)',
                textDecoration: 'none',
                transition: 'color 0.2s',
              }}
              onMouseEnter={e => { (e.target as HTMLAnchorElement).style.color = 'var(--cyan)'; }}
              onMouseLeave={e => { (e.target as HTMLAnchorElement).style.color = 'var(--text-secondary)'; }}
            >
              {label}
            </a>
          ))}
        </div>

        {/* Right controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--safe)', letterSpacing: '0.12em', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--safe)', display: 'inline-block', animation: 'healthPulse 2s ease-in-out infinite' }} />
            LIVE
          </span>
          <button
            onClick={toggleTheme}
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', width: '34px', height: '34px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: 'var(--text-secondary)', transition: 'color 0.2s, border-color 0.2s' }}
            onMouseEnter={e => { const b = e.currentTarget; b.style.color = 'var(--cyan)'; b.style.borderColor = 'var(--cyan)'; }}
            onMouseLeave={e => { const b = e.currentTarget; b.style.color = 'var(--text-secondary)'; b.style.borderColor = 'var(--border)'; }}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? <ICONS.sun className="w-4 h-4" /> : <ICONS.moon className="w-4 h-4" />}
          </button>
        </div>
      </nav>
    </header>
  );
};

// ── Typewriter AI assistant ────────────────────────────────────────────────
const PHRASES = [
  'Monitoring 48,291 transactions today.',
  '2,847 fraud events detected and blocked.',
  'ML model accuracy: 94.35% · Latency: 18s.',
];

const AiAssistant = () => {
  const [phraseIdx, setPhraseIdx] = useState(0);
  const [text, setText] = useState('');
  const [done, setDone] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 1800);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!visible) return;
    setText('');
    setDone(false);
    let i = 0;
    const msg = PHRASES[phraseIdx];
    const interval = setInterval(() => {
      if (i < msg.length) {
        setText(prev => prev + msg[i]);
        i++;
      } else {
        clearInterval(interval);
        setDone(true);
      }
    }, 45);
    return () => clearInterval(interval);
  }, [phraseIdx, visible]);

  useEffect(() => {
    if (!done) return;
    const t = setTimeout(() => setPhraseIdx(p => (p + 1) % PHRASES.length), 3500);
    return () => clearTimeout(t);
  }, [done]);

  if (!visible) return null;

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '40px',
        right: '40px',
        display: 'flex',
        alignItems: 'flex-end',
        gap: '12px',
      }}
    >
      <div
        style={{
          background: 'rgba(10,24,40,0.9)',
          backdropFilter: 'blur(16px)',
          border: '1px solid var(--cyan-border)',
          borderRadius: 'var(--r-xl)',
          padding: '14px 18px',
          maxWidth: '300px',
          position: 'relative',
        }}
      >
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--cyan)', letterSpacing: '0.15em', marginBottom: '6px', opacity: 0.7 }}>
          PULSE AI
        </div>
        <p
          style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-primary)', lineHeight: 1.6, minHeight: '2.5em' }}
          className={`cursor-blink${done ? ' done' : ''}`}
        >
          {text}
        </p>
        {/* Tail */}
        <div style={{ position: 'absolute', bottom: '14px', right: '-9px', width: 0, height: 0, borderTop: '8px solid transparent', borderBottom: '8px solid transparent', borderLeft: '9px solid var(--cyan-border)' }} />
      </div>
      {/* Orb */}
      <div
        style={{
          width: '52px',
          height: '52px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(0,207,255,0.25) 0%, rgba(0,207,255,0.05) 100%)',
          border: '1.5px solid var(--cyan)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          animation: 'orbPulse 2.5s ease-in-out infinite',
        }}
      >
        <span style={{ color: 'var(--cyan)', display: 'flex' }}><ICONS.shieldCheck className="w-6 h-6" /></span>
      </div>
    </div>
  );
};

// ── Dashboard mockup (mini wireframe for hero) ─────────────────────────────
const DashboardMockup = () => (
  <div
    style={{
      background: 'var(--bg-deep)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--r-xl)',
      padding: '16px',
      fontFamily: 'var(--font-mono)',
      fontSize: '10px',
      color: 'var(--text-secondary)',
      userSelect: 'none',
    }}
  >
    {/* Topbar */}
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', padding: '8px 12px', background: 'var(--bg-surface)', borderRadius: 'var(--r-md)', border: '1px solid var(--border)' }}>
      <span style={{ fontFamily: 'var(--font-display)', fontWeight: 800, color: 'var(--cyan)', fontSize: '13px' }}>Data<span style={{ color: 'var(--text-bright)' }}>Pulse</span></span>
      <span style={{ color: 'var(--safe)', letterSpacing: '0.1em' }}>● LIVE</span>
    </div>
    {/* KPI row */}
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '8px', marginBottom: '10px' }}>
      {[['48,291', 'var(--cyan)'], ['2,847', 'var(--fraud)'], ['45,444', 'var(--safe)'], ['94.3%', 'var(--text-bright)']].map(([v, c], i) => (
        <div key={i} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', padding: '10px 10px 8px', position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '1.5px', background: `linear-gradient(90deg, ${c}, transparent)`, opacity: 0.6 }} />
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '15px', fontWeight: 600, color: c as string }}>{v}</div>
        </div>
      ))}
    </div>
    {/* Chart bars + alert feed */}
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 90px', gap: '8px' }}>
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', padding: '10px', height: '64px', display: 'flex', alignItems: 'flex-end', gap: '3px' }}>
        {[30, 48, 36, 60, 42, 68, 50, 72, 58, 80].map((h, i) => (
          <div key={i} style={{ flex: 1, borderRadius: '2px 2px 0 0', background: `rgba(0,207,255,${0.15 + h / 300})`, height: `${h}%`, border: '1px solid var(--cyan-border)' }} />
        ))}
      </div>
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--fraud-border)', borderLeft: '2px solid var(--fraud)', borderRadius: 'var(--r-md)', padding: '8px' }}>
        <div style={{ color: 'var(--fraud)', marginBottom: '4px', letterSpacing: '0.08em' }}>FRAUD</div>
        {['$1,248', '$4,500', '$892'].map((a, i) => (
          <div key={i} style={{ color: 'var(--fraud)', opacity: 1 - i * 0.25, fontSize: '10px', marginBottom: '2px', fontFamily: 'var(--font-mono)' }}>{a}</div>
        ))}
      </div>
    </div>
  </div>
);

// ── Hero ───────────────────────────────────────────────────────────────────
export const Hero = () => {
  const mockupRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onScroll = () => {
      if (!mockupRef.current) return;
      const y = window.scrollY;
      mockupRef.current.style.transform = `translateY(${y * -0.28}px)`;
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <section
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        position: 'relative',
        overflow: 'hidden',
        padding: '80px 32px 60px',
      }}
    >
      {/* Grid background */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage: 'linear-gradient(rgba(0,207,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(0,207,255,0.04) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
          maskImage: 'radial-gradient(ellipse 80% 60% at 50% 40%, black 40%, transparent 100%)',
          WebkitMaskImage: 'radial-gradient(ellipse 80% 60% at 50% 40%, black 40%, transparent 100%)',
          pointerEvents: 'none',
        }}
      />
      {/* Cyan glow blob */}
      <div style={{ position: 'absolute', width: '600px', height: '600px', background: 'radial-gradient(circle, rgba(0,207,255,0.07) 0%, transparent 70%)', top: '-120px', left: '-120px', pointerEvents: 'none' }} />
      {/* Fraud glow blob */}
      <div style={{ position: 'absolute', width: '400px', height: '400px', background: 'radial-gradient(circle, rgba(255,45,85,0.05) 0%, transparent 70%)', bottom: 0, right: '-60px', pointerEvents: 'none' }} />

      <div style={{ maxWidth: '1280px', margin: '0 auto', width: '100%', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '80px', alignItems: 'center', position: 'relative', zIndex: 2 }}>
        {/* Left — copy */}
        <div>
          <div
            className="stagger-load delay-100"
            style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', letterSpacing: '0.2em', textTransform: 'uppercase', color: 'var(--cyan)', opacity: 0.7, marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px' }}
          >
            <span style={{ display: 'block', width: '32px', height: '1px', background: 'var(--cyan)', opacity: 0.5 }} />
            Real-Time Fraud Detection · 2025
          </div>

          <h1
            className="stagger-load delay-200"
            style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(52px, 7vw, 88px)', fontWeight: 800, lineHeight: 0.95, letterSpacing: '-0.02em', color: 'var(--text-bright)', marginBottom: '24px' }}
          >
            Data<span style={{ color: 'var(--cyan)', display: 'block' }}>Pulse</span>
          </h1>

          <p
            className="stagger-load delay-300"
            style={{ fontFamily: 'var(--font-label)', fontSize: '18px', fontWeight: 400, color: 'var(--text-secondary)', letterSpacing: '0.04em', maxWidth: '460px', marginBottom: '16px' }}
          >
            Real-time fraud intelligence & visualization
          </p>

          <p
            className="stagger-load delay-400"
            style={{ fontFamily: 'var(--font-body)', fontSize: '15px', color: 'var(--text-secondary)', maxWidth: '420px', lineHeight: 1.7, marginBottom: '40px' }}
          >
            Every transaction analysed in under 20 seconds. A Random Forest ML model trained on historical patterns flags fraud with 94.35% accuracy — surfaced in a live command-center dashboard.
          </p>

          <a
            href="#dashboard"
            onClick={scrollTo}
            className="stagger-load delay-500"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '10px',
              padding: '14px 28px',
              background: 'var(--cyan)',
              color: '#000',
              fontFamily: 'var(--font-display)',
              fontSize: '15px',
              fontWeight: 700,
              borderRadius: 'var(--r-md)',
              textDecoration: 'none',
              letterSpacing: '0.04em',
              position: 'relative',
              overflow: 'hidden',
              transition: 'transform 0.2s, box-shadow 0.2s',
            }}
            onMouseEnter={e => {
              const el = e.currentTarget;
              el.style.transform = 'translateY(-2px)';
              el.style.boxShadow = '0 8px 32px rgba(0,207,255,0.3)';
              const shimmer = el.querySelector('.shimmer') as HTMLElement;
              if (shimmer) shimmer.style.animation = 'shimmerSweep 0.7s ease forwards';
            }}
            onMouseLeave={e => {
              const el = e.currentTarget;
              el.style.transform = 'translateY(0)';
              el.style.boxShadow = 'none';
              const shimmer = el.querySelector('.shimmer') as HTMLElement;
              if (shimmer) shimmer.style.animation = 'none';
            }}
          >
            <span className="shimmer" style={{ position: 'absolute', inset: 0, background: 'linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.25) 50%, transparent 60%)', transform: 'translateX(-100%)' }} />
            <span style={{ position: 'relative', zIndex: 1 }}>Launch Dashboard</span>
            <span style={{ position: 'relative', zIndex: 1, display: 'flex' }}><ICONS.arrowRight className="w-4 h-4" /></span>
          </a>
        </div>

        {/* Right — mockup */}
        <div ref={mockupRef} className="stagger-load delay-600" style={{ willChange: 'transform' }}>
          <DashboardMockup />
        </div>
      </div>

      {/* Bottom gradient fade */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '120px', background: 'linear-gradient(to bottom, transparent, var(--bg-void))', pointerEvents: 'none' }} />

      <AiAssistant />
    </section>
  );
};

// ── Stats Ticker ───────────────────────────────────────────────────────────
const useCountUp = (target: number, duration = 1800) => {
  const [count, setCount] = useState(0);
  const { ref, isVisible } = useReveal(0.3);
  const started = useRef(false);

  useEffect(() => {
    if (!isVisible || started.current) return;
    started.current = true;
    const startTime = performance.now();
    const step = (now: number) => {
      const t = Math.min((now - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setCount(Math.floor(eased * target));
      if (t < 1) requestAnimationFrame(step);
      else setCount(target);
    };
    requestAnimationFrame(step);
  }, [isVisible, target, duration]);

  return { ref, count };
};

const StatItem: React.FC<{ value: number; suffix: string; label: string; note: string }> = ({ value, suffix, label, note }) => {
  const { ref, count } = useCountUp(value);
  return (
    <div ref={ref} style={{ textAlign: 'center', padding: '0 32px' }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'clamp(36px, 5vw, 52px)', fontWeight: 500, color: 'var(--text-bright)', letterSpacing: '-0.02em', lineHeight: 1 }}>
        {count.toLocaleString()}{suffix}
      </div>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: '16px', fontWeight: 700, color: 'var(--cyan)', marginTop: '8px', letterSpacing: '-0.01em' }}>
        {label}
      </div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px', letterSpacing: '0.06em' }}>
        {note}
      </div>
    </div>
  );
};

// ── Tech-stack logo items ──────────────────────────────────────────────────
const TechLabel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <span
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '10px',
      fontFamily: 'var(--font-mono)',
      fontSize: '13px',
      letterSpacing: '0.08em',
      color: 'var(--text-secondary)',
      whiteSpace: 'nowrap',
    }}
  >
    <span
      style={{
        width: '5px',
        height: '5px',
        borderRadius: '50%',
        background: 'var(--cyan)',
        opacity: 0.5,
        display: 'inline-block',
        flexShrink: 0,
      }}
    />
    {children}
  </span>
);

const TECH_LOGOS: LogoItem[] = [
  { node: <TechLabel>Apache Kafka</TechLabel>,  title: 'Apache Kafka'  },
  { node: <TechLabel>Apache Spark</TechLabel>,  title: 'Apache Spark'  },
  { node: <TechLabel>PostgreSQL</TechLabel>,    title: 'PostgreSQL'    },
  { node: <TechLabel>TimescaleDB</TechLabel>,   title: 'TimescaleDB'   },
  { node: <TechLabel>FastAPI</TechLabel>,       title: 'FastAPI'       },
  { node: <TechLabel>React</TechLabel>,         title: 'React'         },
  { node: <TechLabel>scikit-learn</TechLabel>,  title: 'scikit-learn'  },
];

export const StatsTicker = () => (
  <section style={{ padding: '64px 32px', background: 'var(--bg-deep)', borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)', overflow: 'hidden' }}>
    <div style={{ maxWidth: '1280px', margin: '0 auto' }}>
      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '0', marginBottom: '48px', position: 'relative' }}>
        <div style={{ position: 'absolute', top: '10%', bottom: '10%', left: '33.33%', width: '1px', background: 'var(--border)' }} />
        <div style={{ position: 'absolute', top: '10%', bottom: '10%', left: '66.66%', width: '1px', background: 'var(--border)' }} />
        <StatItem value={94} suffix="%" label="Model Accuracy" note="Random Forest · trained on 1M+ samples" />
        <StatItem value={20} suffix="s" label="Detection Latency" note="End-to-end pipeline · Kafka → Dashboard" />
        <StatItem value={92} suffix="%" label="Fraud Recall" note="True positive rate across all categories" />
      </div>

      {/* Logo loop strip */}
      <div style={{ borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)', padding: '0' }}>
        <LogoLoop
          logos={TECH_LOGOS}
          speed={70}
          direction="left"
          logoHeight={60}
          gap={60}
          hoverSpeed={0}
          fadeOut
          scaleOnHover
          ariaLabel="Technology stack"
        />
      </div>
    </div>
  </section>
);

// ── CTA section ────────────────────────────────────────────────────────────
export const CtaSection = () => {
  const { ref, isVisible } = useReveal();

  return (
    <section
      ref={ref}
      className={`reveal${isVisible ? ' visible' : ''}`}
      style={{ padding: '100px 32px', background: 'var(--bg-deep)', position: 'relative', overflow: 'hidden', textAlign: 'center' }}
    >
      {/* Background glow */}
      <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: '600px', height: '300px', background: 'radial-gradient(ellipse, rgba(0,207,255,0.08) 0%, transparent 70%)', pointerEvents: 'none' }} />
      {/* Scrolling faint data (decorative) */}
      <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', opacity: 0.03, pointerEvents: 'none', fontFamily: 'var(--font-mono)', fontSize: '10px', lineHeight: 1.8, color: 'var(--cyan)', whiteSpace: 'nowrap' }}>
        {Array.from({ length: 20 }, (_, i) => (
          <div key={i} style={{ animation: `marqueeScroll ${14 + i * 2}s linear infinite`, display: 'inline-block' }}>
            TX-0094 FRAUD $1,248.00 · TX-0095 NORMAL $42.99 · TX-0096 FRAUD $4,500.00 · TX-0097 NORMAL $87.32 · TX-0098 NORMAL $19.99 &nbsp;&nbsp;&nbsp;
            TX-0094 FRAUD $1,248.00 · TX-0095 NORMAL $42.99 · TX-0096 FRAUD $4,500.00 · TX-0097 NORMAL $87.32 · TX-0098 NORMAL $19.99 &nbsp;&nbsp;&nbsp;
          </div>
        ))}
      </div>

      <div style={{ position: 'relative', zIndex: 2 }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', letterSpacing: '0.2em', textTransform: 'uppercase', color: 'var(--cyan)', opacity: 0.7, marginBottom: '16px' }}>
          Ready to monitor
        </div>
        <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(32px, 5vw, 56px)', fontWeight: 800, color: 'var(--text-bright)', letterSpacing: '-0.02em', marginBottom: '16px' }}>
          Launch the Live Dashboard
        </h2>
        <p style={{ fontFamily: 'var(--font-body)', fontSize: '16px', color: 'var(--text-secondary)', maxWidth: '480px', margin: '0 auto 40px', lineHeight: 1.7 }}>
          Watch transactions flow in real-time. Every fraud event surfaces instantly with confidence scores, merchant data, and geolocation context.
        </p>
        <a
          href="#dashboard"
          onClick={scrollTo}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '10px',
            padding: '16px 36px',
            background: 'var(--cyan)',
            color: '#000',
            fontFamily: 'var(--font-display)',
            fontSize: '16px',
            fontWeight: 700,
            borderRadius: 'var(--r-md)',
            textDecoration: 'none',
            letterSpacing: '0.04em',
            position: 'relative',
            overflow: 'hidden',
            transition: 'transform 0.2s, box-shadow 0.2s',
            animation: 'orbPulse 3s ease-in-out infinite',
          }}
          onMouseEnter={e => {
            const el = e.currentTarget;
            el.style.transform = 'translateY(-2px)';
            el.style.boxShadow = '0 12px 40px rgba(0,207,255,0.35)';
          }}
          onMouseLeave={e => {
            const el = e.currentTarget;
            el.style.transform = 'translateY(0)';
            el.style.boxShadow = 'none';
          }}
        >
          <span>View Live Dashboard</span>
          <ICONS.arrowRight className="w-5 h-5" />
        </a>
      </div>
    </section>
  );
};

// ── Footer ─────────────────────────────────────────────────────────────────
export const Footer = () => (
  <footer
    style={{
      padding: '40px 32px',
      borderTop: '1px solid var(--border)',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      flexWrap: 'wrap',
      gap: '16px',
      maxWidth: '1280px',
      margin: '0 auto',
    }}
  >
    <div style={{ fontFamily: 'var(--font-display)', fontSize: '18px', fontWeight: 800 }}>
      <span style={{ color: 'var(--text-bright)' }}>Data</span>
      <span style={{ color: 'var(--cyan)' }}>Pulse</span>
    </div>
    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.08em' }}>
      Design Brief v1.0 · Cyber-Noir Terminal · React + Recharts
    </div>
    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.06em' }}>
      © {new Date().getFullYear()} DataPulse · Fraud Detection Demo
    </div>
  </footer>
);
