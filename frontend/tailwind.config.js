/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        'bg-void':    '#020810',
        'bg-deep':    '#050E1C',
        'bg-surface': '#0A1828',
        'bg-elevated':'#0F2038',
        'bg-card':    '#0D1E34',
        'dp-cyan':    '#00CFFF',
        'dp-fraud':   '#FF2D55',
        'dp-safe':    '#00E87A',
        'dp-amber':   '#FFB319',
      },
      fontFamily: {
        display: ['Syne', 'sans-serif'],
        mono:    ['JetBrains Mono', 'monospace'],
        body:    ['Barlow', 'sans-serif'],
        label:   ['Barlow Condensed', 'sans-serif'],
      },
      borderRadius: {
        sm: '4px',
        md: '8px',
        lg: '12px',
        xl: '16px',
      },
      animation: {
        'slide-down':  'slideRowIn 0.35s ease forwards',
        'toast-in':    'toastIn 0.38s cubic-bezier(0.22,0.61,0.36,1) forwards',
        'toast-out':   'toastOut 0.3s ease forwards',
        'health-green':'healthPulse 2s ease-in-out infinite',
        'health-red':  'healthPulseRed 0.8s ease-in-out infinite',
        'pulse-red':   'pulseRed 1.4s ease-in-out infinite',
        'marquee':     'marqueeScroll 14s linear infinite',
        'orb-pulse':   'orbPulse 2.5s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
