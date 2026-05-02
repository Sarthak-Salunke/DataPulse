import { ICONS } from '../utils/constants';
import { useReveal } from '../hooks/useReveal';

const FEATURES = [
  {
    icon: ICONS.activity,
    title: 'Real-Time Analytics',
    description: 'Monitor transactions, fraud rates, and model performance as they happen. Sub-second pipeline latency keeps your view current.',
    tag: 'Live',
    tagColor: 'var(--fraud)',
  },
  {
    icon: ICONS.alert,
    title: 'Instant Fraud Alerts',
    description: 'Every transaction flagged by the ML model surfaces immediately in the alert feed with confidence score, merchant, and distance context.',
    tag: 'Critical',
    tagColor: 'var(--amber)',
  },
  {
    icon: ICONS.shieldCheck,
    title: 'Model Performance Tracking',
    description: 'Track accuracy and recall metrics continuously. Know when your model drifts before it costs you.',
    tag: 'ML',
    tagColor: 'var(--cyan)',
  },
  {
    icon: ICONS.server,
    title: 'System Health Monitor',
    description: 'All backend components — Kafka, Spark, PostgreSQL, ML Model — visible at a glance with live latency indicators.',
    tag: 'Infra',
    tagColor: 'var(--cyan)',
  },
  {
    icon: ICONS.trendingUp,
    title: 'Interactive Charts',
    description: 'Area charts, bar charts, and category breakdowns let analysts drill into patterns and emerging fraud clusters.',
    tag: 'Analytics',
    tagColor: 'var(--safe)',
  },
  {
    icon: ICONS.code,
    title: 'Developer-First Stack',
    description: 'Built on Kafka, Spark, FastAPI, and React — production-ready architecture you can extend, fork, or deploy.',
    tag: 'Open',
    tagColor: 'var(--text-secondary)',
  },
];

interface FeatureCardProps {
  icon: React.ElementType;
  title: string;
  description: string;
  tag: string;
  tagColor: string;
  delay: number;
  isVisible: boolean;
}

const FeatureCard: React.FC<FeatureCardProps> = ({ icon: Icon, title, description, tag, tagColor, delay, isVisible }) => (
  <div
    className="reveal card-hover"
    style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--r-xl)',
      padding: '28px',
      position: 'relative',
      overflow: 'hidden',
      opacity: isVisible ? 1 : 0,
      transform: isVisible ? 'translateY(0)' : 'translateY(28px)',
      transition: `opacity 0.55s ease ${delay}ms, transform 0.55s ease ${delay}ms`,
    }}
  >
    {/* Top accent */}
    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '2px', background: `linear-gradient(90deg, ${tagColor}, transparent)`, opacity: 0.5 }} />

    {/* Icon */}
    <div
      style={{
        width: '44px',
        height: '44px',
        borderRadius: 'var(--r-lg)',
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: '16px',
        color: tagColor,
      }}
    >
      <Icon className="w-5 h-5" />
    </div>

    {/* Tag */}
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
      <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '17px', fontWeight: 700, color: 'var(--text-bright)', letterSpacing: '-0.01em' }}>
        {title}
      </h3>
      <span style={{ fontFamily: 'var(--font-label)', fontSize: '10px', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: tagColor, background: `${tagColor}1A`, border: `1px solid ${tagColor}40`, borderRadius: 'var(--r-sm)', padding: '2px 8px', flexShrink: 0, marginLeft: '8px' }}>
        {tag}
      </span>
    </div>

    <p style={{ fontFamily: 'var(--font-body)', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.65 }}>
      {description}
    </p>
  </div>
);

const FeaturesGrid = () => {
  const { ref, isVisible } = useReveal(0.05);

  return (
    <section
      id="features"
      style={{ padding: '100px 32px', background: 'var(--bg-void)' }}
    >
      <div style={{ maxWidth: '1280px', margin: '0 auto' }}>
        <div
          ref={ref}
          className={`reveal${isVisible ? ' visible' : ''}`}
          style={{ textAlign: 'center', marginBottom: '64px' }}
        >
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', letterSpacing: '0.2em', textTransform: 'uppercase', color: 'var(--cyan)', opacity: 0.7, marginBottom: '12px' }}>
            Capabilities
          </div>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(28px, 4vw, 44px)', fontWeight: 800, color: 'var(--text-bright)', letterSpacing: '-0.02em', marginBottom: '16px' }}>
            A Powerful, All-in-One<br />
            <span style={{ color: 'var(--cyan)' }}>Command Center</span>
          </h2>
          <p style={{ fontFamily: 'var(--font-body)', fontSize: '16px', color: 'var(--text-secondary)', maxWidth: '520px', margin: '0 auto', lineHeight: 1.7 }}>
            DataPulse provides every tool a fraud analyst needs — from live feeds to historical trend analysis — in a single precision-built interface.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
          {FEATURES.map((f, i) => (
            <FeatureCard
              key={f.title}
              {...f}
              delay={i * 80}
              isVisible={isVisible}
            />
          ))}
        </div>
      </div>
    </section>
  );
};

export default FeaturesGrid;
