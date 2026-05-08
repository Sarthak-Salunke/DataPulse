import React, { useEffect, useRef, useMemo } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import './ScrollReveal.css';

gsap.registerPlugin(ScrollTrigger);

// ── Props ─────────────────────────────────────────────────────────
interface ScrollRevealProps {
  children:             React.ReactNode;
  scrollContainerRef?:  React.RefObject<HTMLElement>;
  /** HTML element to render as the outer wrapper (default: 'h2') */
  as?:                  keyof React.JSX.IntrinsicElements;
  enableBlur?:          boolean;
  baseOpacity?:         number;
  baseRotation?:        number;
  blurStrength?:        number;
  containerClassName?:  string;
  textClassName?:       string;
  rotationEnd?:         string;
  wordAnimationEnd?:    string;
}

// ── Component ─────────────────────────────────────────────────────
const ScrollReveal = ({
  children,
  scrollContainerRef,
  as                = 'h2',
  enableBlur        = true,
  baseOpacity       = 0.1,
  baseRotation      = 3,
  blurStrength      = 4,
  containerClassName = '',
  textClassName     = '',
  rotationEnd       = 'bottom bottom',
  wordAnimationEnd  = 'bottom bottom',
}: ScrollRevealProps) => {
  const containerRef = useRef<HTMLElement>(null);

  // Split plain-string children into individual <span class="word"> elements.
  // Non-string children are rendered as-is (no animation split).
  const splitText = useMemo(() => {
    const text = typeof children === 'string' ? children : '';
    return text.split(/(\s+)/).map((word, index) => {
      if (/^\s+$/.test(word)) return word;
      return (
        <span className="word" key={index}>
          {word}
        </span>
      );
    });
  }, [children]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const scroller =
      scrollContainerRef?.current ? scrollContainerRef.current : window;

    // gsap.context scopes all ScrollTriggers to this element — safe cleanup
    const ctx = gsap.context(() => {
      gsap.fromTo(
        el,
        { transformOrigin: '0% 50%', rotate: baseRotation },
        {
          ease: 'none',
          rotate: 0,
          scrollTrigger: {
            trigger: el,
            scroller,
            start: 'top bottom',
            end:   rotationEnd,
            scrub: true,
          },
        }
      );

      const wordEls = el.querySelectorAll('.word');

      gsap.fromTo(
        wordEls,
        { opacity: baseOpacity, willChange: 'opacity' },
        {
          ease:    'none',
          opacity: 1,
          stagger: 0.05,
          scrollTrigger: {
            trigger: el,
            scroller,
            start: 'top bottom-=20%',
            end:   wordAnimationEnd,
            scrub: true,
          },
        }
      );

      if (enableBlur) {
        gsap.fromTo(
          wordEls,
          { filter: `blur(${blurStrength}px)` },
          {
            ease:   'none',
            filter: 'blur(0px)',
            stagger: 0.05,
            scrollTrigger: {
              trigger: el,
              scroller,
              start: 'top bottom-=20%',
              end:   wordAnimationEnd,
              scrub: true,
            },
          }
        );
      }
    }, el);

    return () => ctx.revert();
  }, [
    scrollContainerRef, enableBlur, baseRotation, baseOpacity,
    rotationEnd, wordAnimationEnd, blurStrength,
  ]);

  // Polymorphic render — inner element is always <span> so it nests
  // safely inside any outer tag (including <p>).
  const Tag = as as React.ElementType;

  return (
    <Tag
      ref={containerRef}
      className={`scroll-reveal ${containerClassName}`.trim()}
    >
      <span className={`scroll-reveal-text ${textClassName}`.trim()}>
        {typeof children === 'string' ? splitText : children}
      </span>
    </Tag>
  );
};

export default ScrollReveal;
