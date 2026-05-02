import { useState, useEffect, createContext, useContext, type PropsWithChildren } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { queryClient } from './lib/queryClient';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginPage from './components/Auth/LoginPage';
import { LandingHeader, Hero, StatsTicker, CtaSection, Footer } from './components/LandingPage';
import ProblemSection from './components/ProblemSection';
import HowItWorks from './components/SolutionSection';
import FeaturesGrid from './components/VerifiableComputeSection';
import ArchitectureDiagram from './components/Pipeline/ArchitectureDiagram';
import Header from './components/Common/Header';
import Dashboard from './components/Dashboard/Dashboard';

// ── Theme context ──────────────────────────────────────────────────────────
type Theme = 'dark' | 'light';

interface ThemeCtx {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeCtx | undefined>(undefined);

export const useTheme = (): ThemeCtx => {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider');
  return ctx;
};

const ThemeProvider = ({ children }: PropsWithChildren) => {
  const [theme, setTheme] = useState<Theme>('dark');

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'light') {
      root.classList.add('light');
    } else {
      root.classList.remove('light');
    }
  }, [theme]);

  const toggleTheme = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'));

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

// ── Auth-gated app content ─────────────────────────────────────────────────
// Separated so it can call useAuth() which requires being inside AuthProvider.
function AppContent() {
  const { user, isLoading, logout } = useAuth();

  // While the initial /auth/me check is in-flight, show nothing to avoid
  // flashing the login page for users who are already authenticated.
  if (isLoading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          background: 'var(--bg-void)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: 'var(--font-mono)',
          fontSize: '13px',
          color: 'var(--text-muted)',
        }}
      >
        Initialising…
      </div>
    );
  }

  if (!user) return <LoginPage />;

  return (
    <ThemeProvider>
      <div style={{ background: 'var(--bg-void)', color: 'var(--text-primary)', minHeight: '100vh' }}>

        {/* ── Slim user bar ── */}
        <div
          style={{
            position: 'fixed',
            top: 0, right: 0,
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            padding: '6px 16px',
            background: 'var(--bg-elevated)',
            borderBottom: '1px solid var(--border)',
            borderLeft: '1px solid var(--border)',
            borderBottomLeftRadius: 'var(--r-lg)',
          }}
        >
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-secondary)' }}>
            {user.username}
          </span>
          <span style={{ fontFamily: 'var(--font-label)', fontSize: '9px', color: 'var(--cyan)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            {user.role}
          </span>
          <button
            onClick={logout}
            style={{
              background: 'none',
              border: '1px solid var(--border)',
              borderRadius: 'var(--r-sm)',
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-label)',
              fontSize: '10px',
              padding: '2px 8px',
              cursor: 'pointer',
              letterSpacing: '0.06em',
            }}
          >
            Sign out
          </button>
        </div>

        {/* ── Landing nav ── */}
        <LandingHeader />

        <main>
          {/* ── Hero ── */}
          <Hero />

          {/* ── Stats ticker ── */}
          <StatsTicker />

          {/* ── The Problem ── */}
          <ProblemSection />

          {/* ── How It Works (pinned scroll steps) ── */}
          <HowItWorks />

          {/* ── Features grid ── */}
          <FeaturesGrid />

          {/* ── Architecture pipeline ── */}
          <ArchitectureDiagram />

          {/* ── CTA ── */}
          <CtaSection />

          {/* ── Live Dashboard ── */}
          <section
            id="dashboard"
            style={{
              padding: '80px 32px 100px',
              background: 'var(--bg-void)',
              borderTop: '1px solid var(--border)',
            }}
          >
            <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
              <Header />
              <Dashboard />
            </div>
          </section>
        </main>

        {/* ── Footer ── */}
        <Footer />
      </div>
    </ThemeProvider>
  );
}

// ── App ────────────────────────────────────────────────────────────────────
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}

export default App;
