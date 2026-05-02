import React, { useEffect, useRef, useState } from 'react';
import { useReveal } from '../../hooks/useReveal';

interface PipelineNode {
  id: string;
  label: string;
  sublabel: string;
  icon: string;
  x: number;
  y: number;
}

interface PipelineEdge {
  from: string;
  to: string;
}

const NODES: PipelineNode[] = [
  { id: 'pos',       label: 'POS Terminal',  sublabel: 'Transaction source', icon: '💳', x: 60,   y: 100 },
  { id: 'kafka',     label: 'Kafka',         sublabel: 'Stream ingestion',   icon: '⚡', x: 220,  y: 100 },
  { id: 'spark',     label: 'Spark',         sublabel: 'Stream processing',  icon: '🔥', x: 380,  y: 100 },
  { id: 'ml',        label: 'ML Model',      sublabel: 'Fraud classifier',   icon: '🤖', x: 540,  y: 100 },
  { id: 'postgres',  label: 'PostgreSQL',    sublabel: 'Results store',      icon: '🗄️', x: 700,  y: 100 },
  { id: 'fastapi',   label: 'FastAPI',       sublabel: 'REST + WebSocket',   icon: '🚀', x: 860,  y: 100 },
  { id: 'react',     label: 'Dashboard',     sublabel: 'Live visualization', icon: '📊', x: 1020, y: 100 },
];

const EDGES: PipelineEdge[] = [
  { from: 'pos',      to: 'kafka'    },
  { from: 'kafka',    to: 'spark'    },
  { from: 'spark',    to: 'ml'       },
  { from: 'ml',       to: 'postgres' },
  { from: 'postgres', to: 'fastapi'  },
  { from: 'fastapi',  to: 'react'    },
];

const SVG_WIDTH = 1080;
const SVG_HEIGHT = 200;
const NODE_R = 36;
const EDGE_Y = 100;

const getNodeCenter = (id: string) => {
  const n = NODES.find(n => n.id === id)!;
  return { x: n.x, y: EDGE_Y };
};

const DataPacket: React.FC<{ edge: PipelineEdge; delay: number }> = ({ edge, delay }) => {
  const from = getNodeCenter(edge.from);
  const to   = getNodeCenter(edge.to);

  return (
    <circle r="4" cx={from.x + NODE_R} cy={EDGE_Y} fill="var(--cyan)" opacity="0.9"
      style={{ filter: 'drop-shadow(0 0 4px var(--cyan))' }}
    >
      <animateMotion dur="1.6s" begin={`${delay}s`} repeatCount="indefinite" calcMode="linear">
        <mpath/>
      </animateMotion>
      <animate attributeName="cx" from={from.x + NODE_R} to={to.x - NODE_R}
        dur="1.6s" begin={`${delay}s`} repeatCount="indefinite" calcMode="ease-in-out" />
      <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.1;0.9;1"
        dur="1.6s" begin={`${delay}s`} repeatCount="indefinite" />
    </circle>
  );
};

const ArchitectureDiagram: React.FC = () => {
  const { ref, isVisible } = useReveal(0.15);
  const [drawn, setDrawn] = useState(false);
  const prevVisible = useRef(false);

  useEffect(() => {
    if (isVisible && !prevVisible.current) {
      prevVisible.current = true;
      setTimeout(() => setDrawn(true), 100);
    }
  }, [isVisible]);

  return (
    <section
      id="architecture"
      style={{ padding: '100px 32px', background: 'var(--bg-deep)', borderTop: '1px solid var(--border)' }}
    >
      <div style={{ maxWidth: '1280px', margin: '0 auto' }}>
        {/* Header */}
        <div
          ref={ref}
          className={`reveal${isVisible ? ' visible' : ''}`}
          style={{ textAlign: 'center', marginBottom: '64px' }}
        >
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', letterSpacing: '0.2em', textTransform: 'uppercase', color: 'var(--cyan)', opacity: 0.7, marginBottom: '12px' }}>
            Architecture
          </div>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(28px, 4vw, 44px)', fontWeight: 800, color: 'var(--text-bright)', letterSpacing: '-0.02em', marginBottom: '16px' }}>
            The Pipeline
          </h2>
          <p style={{ fontFamily: 'var(--font-body)', fontSize: '16px', color: 'var(--text-secondary)', maxWidth: '520px', margin: '0 auto', lineHeight: 1.7 }}>
            Follow a transaction from swipe to screen — through Kafka, Spark, and a Random Forest ML classifier — in under 20 seconds.
          </p>
        </div>

        {/* Diagram container */}
        <div
          style={{
            background: 'rgba(10,24,40,0.6)',
            backdropFilter: 'blur(12px)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--r-xl)',
            padding: '40px 32px',
            overflowX: 'auto',
          }}
        >
          <svg
            viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
            width="100%"
            style={{ overflow: 'visible', minWidth: '680px' }}
          >
            <defs>
              <filter id="glow-cyan">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Edges (draw-in lines) */}
            {EDGES.map((edge, i) => {
              const from = getNodeCenter(edge.from);
              const to   = getNodeCenter(edge.to);
              const x1 = from.x + NODE_R;
              const x2 = to.x - NODE_R;
              const totalLen = x2 - x1;

              return (
                <g key={`${edge.from}-${edge.to}`}>
                  {/* Track line */}
                  <line x1={x1} y1={EDGE_Y} x2={x2} y2={EDGE_Y}
                    stroke="var(--border)" strokeWidth="1.5" />
                  {/* Animated fill line */}
                  <line x1={x1} y1={EDGE_Y} x2={x2} y2={EDGE_Y}
                    stroke="var(--cyan)"
                    strokeWidth="1.5"
                    strokeDasharray={totalLen}
                    strokeDashoffset={drawn ? 0 : totalLen}
                    style={{
                      transition: `stroke-dashoffset 0.7s ease ${i * 0.15}s`,
                      opacity: 0.6,
                    }}
                  />
                  {/* Arrowhead */}
                  <polygon
                    points={`${x2},${EDGE_Y - 5} ${x2 + 8},${EDGE_Y} ${x2},${EDGE_Y + 5}`}
                    fill="var(--cyan)"
                    opacity={drawn ? 0.6 : 0}
                    style={{ transition: `opacity 0.3s ease ${i * 0.15 + 0.65}s` }}
                  />
                </g>
              );
            })}

            {/* Animated data packets */}
            {drawn && EDGES.map((edge, i) => (
              <DataPacket key={`pkt-${edge.from}`} edge={edge} delay={i * 0.28} />
            ))}

            {/* Nodes */}
            {NODES.map((node, i) => (
              <g key={node.id}
                style={{
                  opacity: drawn ? 1 : 0,
                  transform: drawn ? 'scale(1)' : 'scale(0.6)',
                  transformOrigin: `${node.x}px ${EDGE_Y}px`,
                  transition: `opacity 0.4s ease ${i * 0.12}s, transform 0.4s ease ${i * 0.12}s`,
                }}
              >
                {/* Outer ring */}
                <circle cx={node.x} cy={EDGE_Y} r={NODE_R + 4}
                  fill="none"
                  stroke="var(--cyan)"
                  strokeWidth="0.5"
                  opacity="0.2"
                />
                {/* Node circle */}
                <circle cx={node.x} cy={EDGE_Y} r={NODE_R}
                  fill="var(--bg-elevated)"
                  stroke="var(--cyan-border)"
                  strokeWidth="1.5"
                  filter={i === NODES.length - 1 ? 'url(#glow-cyan)' : undefined}
                />
                {/* Icon */}
                <text x={node.x} y={EDGE_Y + 7} textAnchor="middle" fontSize="22" style={{ fontFamily: 'var(--font-body)' }}>
                  {node.icon}
                </text>
                {/* Label */}
                <text x={node.x} y={EDGE_Y + NODE_R + 18}
                  textAnchor="middle"
                  fill="var(--text-bright)"
                  fontSize="11"
                  fontFamily="var(--font-display)"
                  fontWeight="700"
                >
                  {node.label}
                </text>
                {/* Sub-label */}
                <text x={node.x} y={EDGE_Y + NODE_R + 32}
                  textAnchor="middle"
                  fill="var(--text-muted)"
                  fontSize="9"
                  fontFamily="var(--font-mono)"
                  letterSpacing="0.04em"
                >
                  {node.sublabel}
                </text>
              </g>
            ))}
          </svg>
        </div>

        {/* Latency callout */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: '40px', marginTop: '32px', flexWrap: 'wrap' }}>
          {[
            { label: 'Kafka Throughput', value: '23K msg/s' },
            { label: 'Spark Batch', value: '2s' },
            { label: 'End-to-End', value: '<20s' },
            { label: 'Model Accuracy', value: '94.35%' },
          ].map(({ label, value }) => (
            <div key={label} style={{ textAlign: 'center' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '20px', fontWeight: 500, color: 'var(--cyan)', letterSpacing: '-0.01em' }}>{value}</div>
              <div style={{ fontFamily: 'var(--font-label)', fontSize: '11px', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginTop: '3px' }}>{label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default ArchitectureDiagram;
