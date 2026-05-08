import { useState, useEffect, createContext, useContext, type PropsWithChildren } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { queryClient } from './lib/queryClient';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginPage from './components/Auth/LoginPage';
import { LandingHeader, Hero, HowItWorksSection, FeaturesSection, CtaSection, Footer } from './components/LandingPage';
import AppShell from './components/Common/AppShell';
import Dashboard from './components/Dashboard/Dashboard';
import CaseDetail from './components/Cases/CaseDetail';
import FraudChatPanel from './components/Chat/FraudChatPanel';

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

// ── ProtectedRoute — redirects to /login if not authenticated ──────────────
function ProtectedRoute({ children }: PropsWithChildren) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div style={{
        minHeight: '100vh',
        background: 'var(--ink-0)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'var(--mono)',
        fontSize: '13px',
        color: 'var(--fg-3)',
      }}>
        Initialising…
      </div>
    );
  }

  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;

  return <>{children}</>;
}

// ── Landing page (public) ──────────────────────────────────────────────────
function LandingPage() {
  return (
    <ThemeProvider>
      <div style={{ background: 'var(--ink-0)', color: 'var(--fg)', minHeight: '100vh' }}>
        <LandingHeader />
        <main>
          <Hero />
          <HowItWorksSection />
          <FeaturesSection />
          <CtaSection />
        </main>
        <Footer />
        {/* Single fixed fade — covers every section uniformly as you scroll */}
        <div className="lp-page-fade" aria-hidden="true" />
      </div>
    </ThemeProvider>
  );
}

// ── Dashboard page (protected) ─────────────────────────────────────────────
function DashboardPage() {
  return (
    <ThemeProvider>
      <AppShell active="overview">
        <Dashboard />
      </AppShell>
      <FraudChatPanel />
    </ThemeProvider>
  );
}

// ── App ────────────────────────────────────────────────────────────────────
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/cases/:id"
              element={
                <ProtectedRoute>
                  <ThemeProvider>
                    <CaseDetail />
                  </ThemeProvider>
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}

export default App;
