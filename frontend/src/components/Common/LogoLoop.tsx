import React, { useRef, useEffect } from 'react';

// ── Types ──────────────────────────────────────────────────────────────────
export interface LogoItem {
  node?: React.ReactNode;
  src?: string;
  alt?: string;
  title?: string;
  href?: string;
}

interface LogoLoopProps {
  logos: LogoItem[];
  speed?: number;
  direction?: 'left' | 'right' | 'up' | 'down';
  width?: number | string;
  logoHeight?: number;
  gap?: number;
  hoverSpeed?: number;
  fadeOut?: boolean;
  fadeOutColor?: string;
  scaleOnHover?: boolean;
  renderItem?: (item: LogoItem, key: React.Key) => React.ReactNode;
  ariaLabel?: string;
  className?: string;
  style?: React.CSSProperties;
}

// ── Component ──────────────────────────────────────────────────────────────
const LogoLoop: React.FC<LogoLoopProps> = ({
  logos,
  speed = 120,
  direction = 'left',
  width = '100%',
  logoHeight = 28,
  gap = 32,
  hoverSpeed = 0,
  fadeOut = false,
  fadeOutColor,
  scaleOnHover = false,
  renderItem,
  ariaLabel = 'Partner logos',
  className,
  style,
}) => {
  const trackRef     = useRef<HTMLDivElement>(null);
  const posRef       = useRef(0);
  const lastTimeRef  = useRef<number | null>(null);
  const rafRef       = useRef<number>(0);
  const hoveredRef   = useRef(false);

  const isHorizontal = direction === 'left' || direction === 'right';
  // sign: negative = left/up (content moves left), positive = right/down
  const sign = direction === 'left' || direction === 'up' ? -1 : 1;

  // ── Animation loop ─────────────────────────────────────────────────────
  // Key design decisions:
  //  • Each copy has trailing padding = gap so seam gap equals item gap
  //  • step = scrollWidth/2 (or scrollHeight/2) — read every frame, always correct
  //  • "while" normalization handles any drift, not just one step at a time
  useEffect(() => {
    posRef.current = 0;
    lastTimeRef.current = null;

    const animate = (time: number) => {
      if (lastTimeRef.current === null) lastTimeRef.current = time;
      const dt = Math.min((time - lastTimeRef.current) / 1000, 0.05);
      lastTimeRef.current = time;

      const currentSpeed = hoveredRef.current ? (hoverSpeed ?? 0) : speed;
      posRef.current += sign * currentSpeed * dt;

      if (trackRef.current) {
        const step = isHorizontal
          ? trackRef.current.scrollWidth / 2
          : trackRef.current.scrollHeight / 2;

        if (step > 1) {
          // Normalize — while loop handles any multi-step drift
          if (sign < 0) {
            while (posRef.current <= -step) posRef.current += step;
          } else {
            while (posRef.current >= 0) posRef.current -= step;
          }
        }

        trackRef.current.style.transform = isHorizontal
          ? `translateX(${posRef.current}px)`
          : `translateY(${posRef.current}px)`;
      }

      rafRef.current = requestAnimationFrame(animate);
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => {
      cancelAnimationFrame(rafRef.current);
      lastTimeRef.current = null;
    };
  }, [speed, hoverSpeed, sign, isHorizontal]);

  // ── Item renderer ──────────────────────────────────────────────────────
  const renderOne = (item: LogoItem, key: React.Key): React.ReactNode => {
    if (renderItem) return renderItem(item, key);

    const inner = item.src ? (
      <img
        src={item.src}
        alt={item.alt ?? item.title ?? ''}
        style={{ height: logoHeight, width: 'auto', objectFit: 'contain', display: 'block' }}
      />
    ) : (
      <div style={{ height: logoHeight, display: 'flex', alignItems: 'center' }}>
        {item.node}
      </div>
    );

    const itemEl = (
      <div
        title={item.title}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          transition: scaleOnHover ? 'transform 0.2s ease' : undefined,
          cursor: item.href ? 'pointer' : 'default',
        }}
        onMouseEnter={scaleOnHover
          ? e => { (e.currentTarget as HTMLDivElement).style.transform = 'scale(1.1)'; }
          : undefined}
        onMouseLeave={scaleOnHover
          ? e => { (e.currentTarget as HTMLDivElement).style.transform = 'scale(1)'; }
          : undefined}
      >
        {inner}
      </div>
    );

    if (item.href) {
      return (
        <a
          key={key}
          href={item.href}
          target="_blank"
          rel="noopener noreferrer"
          style={{ display: 'flex', alignItems: 'center', textDecoration: 'none', flexShrink: 0 }}
        >
          {itemEl}
        </a>
      );
    }

    return <React.Fragment key={key}>{itemEl}</React.Fragment>;
  };

  // ── Copy style ─────────────────────────────────────────────────────────
  // Trailing padding (not gap on the track) creates the seam gap so that
  // scrollWidth / 2 == one copy's apparent width including the trailing space.
  // This means the loop step is always exactly one copy width.
  const copyStyle: React.CSSProperties = isHorizontal
    ? {
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        gap: `${gap}px`,
        flexShrink: 0,
        paddingRight: `${gap}px`,   // trailing gap → seam is seamless
      }
    : {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: `${gap}px`,
        flexShrink: 0,
        paddingBottom: `${gap}px`,  // trailing gap → seam is seamless
      };

  // ── Fade mask ──────────────────────────────────────────────────────────
  const fadePx = '80px';
  let maskImage: string | undefined;
  if (fadeOut) {
    if (fadeOutColor) {
      maskImage = isHorizontal
        ? `linear-gradient(to right, ${fadeOutColor}, transparent ${fadePx}, transparent calc(100% - ${fadePx}), ${fadeOutColor})`
        : `linear-gradient(to bottom, ${fadeOutColor}, transparent ${fadePx}, transparent calc(100% - ${fadePx}), ${fadeOutColor})`;
    } else {
      maskImage = isHorizontal
        ? `linear-gradient(to right, transparent, black ${fadePx}, black calc(100% - ${fadePx}), transparent)`
        : `linear-gradient(to bottom, transparent, black ${fadePx}, black calc(100% - ${fadePx}), transparent)`;
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <div
      role="region"
      aria-label={ariaLabel}
      className={className}
      style={{
        width: typeof width === 'number' ? `${width}px` : width,
        overflow: 'hidden',
        position: 'relative',
        ...(maskImage ? { maskImage, WebkitMaskImage: maskImage } : {}),
        ...style,
      }}
      onMouseEnter={() => { hoveredRef.current = true; }}
      onMouseLeave={() => { hoveredRef.current = false; }}
    >
      {/* Track — two identical copies for seamless wrap.
          No gap on the track itself; each copy carries trailing padding. */}
      <div
        ref={trackRef}
        style={{
          display: 'flex',
          flexDirection: isHorizontal ? 'row' : 'column',
          alignItems: 'center',
          willChange: 'transform',
        }}
      >
        <div style={copyStyle}>
          {logos.map((item, i) => renderOne(item, `a-${i}`))}
        </div>
        <div style={copyStyle} aria-hidden="true">
          {logos.map((item, i) => renderOne(item, `b-${i}`))}
        </div>
      </div>
    </div>
  );
};

export default LogoLoop;
