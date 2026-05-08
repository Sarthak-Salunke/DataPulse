// ── LoginPage — Google OAuth + username/password fallback ───────────
import { useState, type FormEvent } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { GoogleLogin } from '@react-oauth/google';
import { useAuth } from '../../context/AuthContext';

export default function LoginPage() {
  const { login, googleLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: Location })?.from?.pathname ?? '/dashboard';

  const [username, setUsername] = useState('');
  const [password, setPassword]   = useState('');
  const [error, setError]         = useState<string | null>(null);
  const [loading, setLoading]     = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleSuccess(credential: string) {
    setError(null);
    setLoading(true);
    try {
      await googleLogin(credential);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Google sign-in failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
      {/* Left: form */}
      <div style={{ padding: '32px 48px', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <a className="brand-row" href="/"><div className="brand-mark">D</div>DataPulse</a>
          <span className="pill"><span className="live-dot"/>v1.4 · us-east-1</span>
        </div>

        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ width: '100%', maxWidth: 380 }}>
            <div className="reveal" data-d="1" style={{
              fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--brand)',
              textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 16,
            }}>SIGN IN</div>
            <h1 className="reveal" data-d="2" style={{
              fontSize: 38, fontWeight: 500, letterSpacing: '-0.025em',
              lineHeight: 1.05, margin: '0 0 12px',
            }}>
              Welcome back, <em className="italic-em" style={{
                background: 'linear-gradient(120deg, var(--brand), var(--indigo))',
                WebkitBackgroundClip: 'text', backgroundClip: 'text', WebkitTextFillColor: 'transparent',
              }}>analyst.</em>
            </h1>
            <p className="reveal" data-d="3" style={{ color: 'var(--fg-2)', fontSize: 14, marginBottom: 32 }}>
              Use your work account to access the live fraud dashboard.
            </p>

            {/* Google OAuth button */}
            <div className="reveal" data-d="4" style={{ marginBottom: 24 }}>
              <GoogleLogin
                onSuccess={({ credential }) => credential && handleGoogleSuccess(credential)}
                onError={() => setError('Google sign-in failed — try again')}
                theme="filled_black"
                shape="rectangular"
                text="continue_with"
                size="large"
                width="380"
              />
            </div>

            <div className="reveal" data-d="5" style={{
              display: 'flex', alignItems: 'center', gap: 14,
              fontFamily: 'var(--mono)', fontSize: 10,
              color: 'var(--fg-4)', textTransform: 'uppercase', letterSpacing: '0.1em',
              margin: '24px 0',
            }}>
              <span style={{ flex: 1, height: 1, background: 'var(--rule)' }}/>
              Or with username
              <span style={{ flex: 1, height: 1, background: 'var(--rule)' }}/>
            </div>

            <form onSubmit={handleSubmit} className="reveal" data-d="6">
              <Field label="Username" id="username">
                <input
                  type="text"
                  id="username"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  placeholder="admin"
                  autoComplete="username"
                />
              </Field>
              <Field label="Password" id="pw">
                <input
                  type="password"
                  id="pw"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••••"
                  autoComplete="current-password"
                />
              </Field>

              {error && (
                <div style={{
                  padding: '8px 12px', borderRadius: 6, marginBottom: 12,
                  background: 'var(--risk-soft)', color: 'var(--risk)',
                  fontSize: 12, border: '1px solid var(--risk)',
                }}>{error}</div>
              )}

              <button type="submit" disabled={loading} style={{
                width: '100%', padding: 13,
                background: 'linear-gradient(180deg, var(--brand-2), var(--brand))',
                color: 'var(--ink-0)', border: '1px solid var(--brand)',
                borderRadius: 10, fontSize: 14, fontWeight: 600,
                fontFamily: 'var(--sans)', cursor: 'pointer',
                opacity: loading ? 0.7 : 1,
              }}>{loading ? 'Signing in…' : 'Sign in →'}</button>
            </form>
          </div>
        </div>
      </div>

      {/* Right: testimonial */}
      <div style={{
        background: 'var(--ink-1)',
        borderLeft: '1px solid var(--rule)',
        padding: '32px 48px',
        display: 'flex', flexDirection: 'column', justifyContent: 'center',
        position: 'relative', overflow: 'hidden',
      }}>
        <div className="reveal" data-d="3" style={{ maxWidth: 480, position: 'relative', zIndex: 1 }}>
          <div style={{
            fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg-3)',
            textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 24,
          }}>FROM THE FIELD</div>
          <blockquote style={{
            margin: 0, fontFamily: 'var(--serif)', fontStyle: 'italic',
            fontSize: 30, lineHeight: 1.3, letterSpacing: '-0.01em', fontWeight: 500,
          }}>
            <span style={{ color: 'var(--brand)', marginRight: 4 }}>"</span>
            The verdicts arrive before the receipt prints. We stopped writing post-mortem reports — there's nothing to bury anymore.
          </blockquote>
          <div style={{ marginTop: 24, fontFamily: 'var(--mono)', fontSize: 12 }}>
            H. Okafor<br/>
            <span style={{ color: 'var(--fg-3)' }}>VP, Fraud Operations · Tier-1 issuer</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return (
    <>
      <label htmlFor={id} style={{
        display: 'block', fontFamily: 'var(--mono)', fontSize: 10,
        color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.06em',
        marginBottom: 6,
      }}>{label}</label>
      <div style={{ marginBottom: 14 }}>
        {children && <style>{`
          input[type="text"], input[type="password"] {
            width: 100%; padding: 12px 14px;
            background: var(--ink-1); border: 1px solid var(--rule-strong);
            border-radius: 10px; color: var(--fg);
            font-size: 14px; font-family: var(--sans);
          }
          input:focus { outline: none; border-color: var(--brand);
            box-shadow: 0 0 0 3px var(--brand-soft); }
        `}</style>}
        {children}
      </div>
    </>
  );
}
