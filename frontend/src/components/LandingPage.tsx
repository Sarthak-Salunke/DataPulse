import { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import '../styles/landing.css';
import { useCountUp } from '../hooks/useCountUp';
import Radar from './Common/Radar';
import ShinyText from './Common/ShinyText';
import ScrollReveal from './Common/ScrollReveal';

// ── Scroll-reveal hook ─────────────────────────────────────────────
function useScrollReveal() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { el.classList.add('visible'); obs.disconnect(); } },
      { threshold: 0.15 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return ref;
}

// ── Stat card with count-up ────────────────────────────────────────
function StatCard({ target, suffix, prefix = '', label }: { target: number; suffix: string; prefix?: string; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [started, setStarted] = useState(false);
  const v = useCountUp(started ? target : 0, 1400, (target.toString().split('.')[1] ?? '').length);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setStarted(true); obs.disconnect(); } },
      { threshold: 0.3 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return (
    <div className="lp-stat" ref={ref}>
      <div className="sv">{prefix}{v.toFixed((target.toString().split('.')[1] ?? '').length)}<small>{suffix}</small></div>
      <div className="sl">{label}</div>
    </div>
  );
}

// ── Navbar ─────────────────────────────────────────────────────────
export const LandingHeader = () => {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const smoothScroll = useCallback((e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    const id = e.currentTarget.getAttribute('href')?.slice(1);
    if (id) document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  return (
    <nav className={`nav-bar${scrolled ? ' scrolled' : ''}`}>
      <div className="nav-inner">
        <Link to="/" className="brand-row">
          DataPulse
        </Link>
        <div className="nav-links">
          <a href="#how" onClick={smoothScroll}>How it works</a>
          <a href="#features" onClick={smoothScroll}>Features</a>
        </div>
        <div className="nav-actions">
          <Link to="/login"><button className="btn">Sign in</button></Link>
          <Link to="/dashboard"><button className="btn primary">View dashboard →</button></Link>
        </div>
      </div>
    </nav>
  );
};

// ── Hero ───────────────────────────────────────────────────────────
export const Hero = () => (
  <section className="hero-section">
    {/* Radar — absolute, bleeds off right edge, never blocks clicks */}
    <div className="hero-radar-wrap" aria-hidden="true">
      <Radar
        color="#4cc9c0"
        backgroundColor="#000000"
        scale={0.55}
        ringCount={8}
        spokeCount={8}
        ringThickness={0.04}
        spokeThickness={0.008}
        sweepSpeed={0.7}
        sweepWidth={2.5}
        sweepLobes={1}
        speed={0.8}
        falloff={2.5}
        brightness={0.9}
        enableMouseInteraction={false}
        mouseInfluence={0.1}
      />
    </div>
    {/* Text content sits above the radar via z-index */}
    <div className="lp-container" style={{ position: 'relative', zIndex: 1 }}>
      <div className="hero-eyebrow reveal" data-d="1">REAL-TIME FRAUD DETECTION · v1.4</div>
      <h1 className="hero-h reveal" data-d="2">
        <ShinyText
          text="Catch fraud in 38 ms,"
          color="#c2c8d6"
          shineColor="#ffffff"
          speed={3}
          delay={1.2}
          spread={100}
          direction="left"
          pauseOnHover
        />
        {' '}<em>before settlement.</em>
      </h1>
      <p className="hero-sub reveal" data-d="3">
        DataPulse scores every card swipe through Kafka and a continuously-trained ML model — flagging anomalies in the time it takes a terminal to print a receipt.
      </p>
      <div className="hero-cta reveal" data-d="4">
        <Link to="/dashboard"><button className="btn primary">View live dashboard →</button></Link>
        <button className="btn">Read the methodology</button>
      </div>
      <div className="hero-meta reveal" data-d="5">
        <span><b className="brand">23.4K</b>&nbsp; tx/s sustained</span>
        <span><b>94.3%</b>&nbsp; precision</span>
        <span><b>92.0%</b>&nbsp; recall</span>
        <span><b className="brand">38 ms</b>&nbsp; median latency</span>
      </div>
      <div className="lp-stats reveal" data-d="6">
        <StatCard target={184}  suffix="K" prefix="$" label="Capital protected · today" />
        <StatCard target={2.4}  suffix="M"             label="Transactions / day" />
        <StatCard target={0.42} suffix="%"             label="Fraud incidence rate" />
        <StatCard target={4.2}  suffix="s"             label="End-to-end stream lag" />
      </div>
    </div>
  </section>
);

// ── Stats Ticker (kept for backward compat — renders nothing extra) ──
export const StatsTicker = () => null;

// ── Pipeline section ───────────────────────────────────────────────
export const HowItWorksSection = () => {
  const ref = useScrollReveal();
  return (
    <section className="lp-section" id="how">
      <div className="lp-container">
        <div className="eyebrow sr visible">HOW IT WORKS</div>
        <h2 className="lp-s-title">A transaction's path, <em>from swipe to decision.</em></h2>
        <ScrollReveal
          as="p"
          containerClassName="lp-s-lede"
          baseOpacity={0.08}
          enableBlur={true}
          baseRotation={3}
          blurStrength={6}
          wordAnimationEnd="bottom 80%"
        >
          Every card event flows through a five-stage pipeline. The model returns a verdict before the terminal completes its handshake — fraud is blocked, not refunded.
        </ScrollReveal>
        <div className="lp-pipeline sr" ref={ref}>
          <div className="lp-pipe-flow">
            {[
              { ic: '↘', name: 'Ingest',     tech: 'Kafka',            stat: '23.4K msg/s' },
              { ic: '∿', name: 'Stream',     tech: 'Redpanda Cloud',   stat: '2.0s batch' },
              { ic: '▦', name: 'Featurise',  tech: 'Feature store',    stat: '8 ms lookup' },
              { ic: '◈', name: 'Score',      tech: 'RF v1.2 · CAPE',  stat: '38 ms verdict' },
              { ic: '→', name: 'Decide',     tech: 'Decision API',     stat: '<100ms total' },
            ].map(s => (
              <div key={s.name} className="lp-pipe-step">
                <div className="lp-pipe-icon">{s.ic}</div>
                <div className="lp-pipe-name">{s.name}</div>
                <div className="lp-pipe-tech">{s.tech}</div>
                <div className="lp-pipe-stat"><b>{s.stat.split(' ')[0]}</b> {s.stat.split(' ').slice(1).join(' ')}</div>
              </div>
            ))}
          </div>
          <div className="lp-pipe-trace">
            <div>
              <div className="lp-trace-label"><span className="lp-trace-swatch" />TRACE · NORMAL TRANSACTION</div>
              <div className="lp-trace-row" style={{ animationDelay: '80ms'  }}><span className="tt">+0 ms</span>card swipe at terminal · $42.18</div>
              <div className="lp-trace-row" style={{ animationDelay: '200ms' }}><span className="tt">+12 ms</span>kafka topic <code>tx.in</code> received</div>
              <div className="lp-trace-row" style={{ animationDelay: '320ms' }}><span className="tt">+22 ms</span>features hydrated · 38 dims</div>
              <div className="lp-trace-row ok" style={{ animationDelay: '440ms' }}><span className="tt">+38 ms</span>model verdict · <b>approved</b> (p=0.02)</div>
              <div className="lp-trace-row" style={{ animationDelay: '560ms' }}><span className="tt">+44 ms</span>response sent · receipt prints</div>
            </div>
            <div>
              <div className="lp-trace-label fraud"><span className="lp-trace-swatch fraud" />TRACE · FRAUDULENT TRANSACTION</div>
              <div className="lp-trace-row" style={{ animationDelay: '140ms' }}><span className="tt">+0 ms</span>card swipe · $487 · 1,847 km from home</div>
              <div className="lp-trace-row" style={{ animationDelay: '260ms' }}><span className="tt">+12 ms</span>kafka received · velocity check</div>
              <div className="lp-trace-row" style={{ animationDelay: '380ms' }}><span className="tt">+22 ms</span>geo + behaviour features · 4 outliers</div>
              <div className="lp-trace-row flag" style={{ animationDelay: '500ms' }}><span className="tt">+38 ms</span>model verdict · <b>FRAUD</b> (p=0.98)</div>
              <div className="lp-trace-row" style={{ animationDelay: '620ms' }}><span className="tt">+44 ms</span>decline returned · case opened · analyst pinged</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

// ── Features section ───────────────────────────────────────────────
export const FeaturesSection = () => (
  <section className="lp-section" id="features">
    <div className="lp-container">
      <div className="eyebrow">CAPABILITIES</div>
      <h2 className="lp-s-title">Three things <em>that actually move the rate.</em></h2>
      <ScrollReveal
        as="p"
        containerClassName="lp-s-lede"
        baseOpacity={0.08}
        enableBlur={true}
        baseRotation={3}
        blurStrength={6}
        wordAnimationEnd="bottom 80%"
      >
        DataPulse isn't a wrapper around a vendor model. It's a pipeline analysts can read, tune, and trust — because fraud teams need to defend their decisions, not just deliver them.
      </ScrollReveal>
      <div className="lp-features">
        <div className="lp-feature reveal" data-d="4">
          <div className="fn">01</div>
          <h3>Continuously-trained models</h3>
          <p>Random Forest retrains on the freshest 30 days of labelled events via Redpanda + Python worker. Drift is detected, not discovered.</p>
        </div>
        <div className="lp-feature reveal" data-d="5">
          <div className="fn">02</div>
          <h3>Explainable verdicts</h3>
          <p>Every flagged event carries the top SHAP feature contributions that pushed it over the threshold — so analysts can dispute, escalate, or close in seconds.</p>
        </div>
        <div className="lp-feature reveal" data-d="6">
          <div className="fn">03</div>
          <h3>Streaming, not batch</h3>
          <p>Redpanda Cloud + Python consumer with 2-second micro-batches. No nightly jobs, no after-the-fact recovery — fraud is blocked at decision time.</p>
        </div>
      </div>
    </div>
  </section>
);

// ── CTA section ────────────────────────────────────────────────────
export const CtaSection = () => (
  <section className="lp-cta" id="docs">
    <div className="lp-container">
      <h2>See it run on <em>your transaction stream.</em></h2>
      <ScrollReveal
        as="p"
        baseOpacity={0.08}
        enableBlur={true}
        baseRotation={2}
        blurStrength={5}
        wordAnimationEnd="bottom 75%"
      >
        Drop a sample CSV in or point us at your Kafka topic — we'll have a live dashboard in 20 minutes.
      </ScrollReveal>
      <div className="lp-cta-actions">
        <Link to="/dashboard"><button className="btn primary">Request a demo →</button></Link>
        <button className="btn">Read the docs</button>
      </div>
    </div>
  </section>
);

// ── Footer ─────────────────────────────────────────────────────────
export const Footer = () => (
  <footer className="lp-footer">
    <div className="lp-container">
      <div className="lp-foot-grid">
        <div>
          <div className="brand-row" style={{ marginBottom: 14 }}>
            DataPulse
          </div>
          <div style={{ color: 'var(--fg-3)', maxWidth: 260, lineHeight: 1.55 }}>
            Real-time fraud detection for card networks, issuers and payment processors.
          </div>
        </div>
        <div>
          <h4>Product</h4>
          <Link to="/dashboard">Dashboard</Link>
          <a href="#">Models</a>
          <a href="#">Pipeline</a>
          <a href="#">Pricing</a>
        </div>
        <div>
          <h4>Resources</h4>
          <a href="#">Methodology</a>
          <a href="#">Docs</a>
          <a href="#">API reference</a>
          <a href="#">Changelog</a>
        </div>
        <div>
          <h4>Company</h4>
          <a href="#">About</a>
          <a href="#">Security</a>
          <a href="#">Status</a>
          <a href="#">Contact</a>
        </div>
      </div>
      <div className="lp-foot-bottom">
        <span>© 2026 DataPulse</span>
        <span>v1.4 · streaming since 06:14:02 UTC</span>
      </div>
    </div>
  </footer>
);
