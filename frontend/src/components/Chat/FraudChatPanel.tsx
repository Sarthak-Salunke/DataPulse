import React, { useState, useRef, useEffect } from 'react';
import { getAuthToken } from '../../hooks/useApiData';
import DataTable from './DataTable';
import ChartRenderer from './ChartRenderer';
import { APP_METRICS } from '../../config/content';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface UserMessage {
  role: 'user';
  text: string;
}

interface AssistantMessage {
  role: 'assistant';
  summary: string;
  sql?: string;
  rows?: Record<string, unknown>[];
  columns?: string[];
  visualization?: string;
  row_count?: number;
}

type ChatMessage = UserMessage | AssistantMessage;

interface ChatApiResponse {
  summary: string;
  sql: string;
  rows: Record<string, unknown>[];
  columns: string[];
  visualization: string;
  row_count: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function AssistantBubble({ msg }: { msg: AssistantMessage }) {
  const [showSQL, setShowSQL] = useState(false);
  const hasData =
    msg.rows && msg.columns && msg.rows.length > 0 && msg.visualization !== 'empty';

  return (
    <div
      style={{
        background: 'var(--ink-2)',
        border: '1px solid var(--rule)',
        borderRadius: '8px',
        padding: '12px 14px',
        fontSize: '13px',
        lineHeight: '1.5',
        color: 'var(--fg)',
      }}
    >
      {/* Pass 2 natural language insight */}
      <p style={{ margin: '0 0 10px', color: 'var(--fg)' }}>
        {msg.summary}
      </p>

      {/* Visualisation */}
      {hasData && msg.visualization === 'table' && (
        <DataTable rows={msg.rows!} columns={msg.columns!} />
      )}
      {hasData &&
        (msg.visualization === 'bar_chart' ||
          msg.visualization === 'line_chart') && (
          <ChartRenderer
            type={msg.visualization as 'bar_chart' | 'line_chart'}
            rows={msg.rows!}
            columns={msg.columns!}
          />
        )}
      {hasData && msg.visualization === 'stat_card' && (
        <div
          style={{
            display: 'inline-flex',
            flexDirection: 'column',
            background: 'var(--ink-1)',
            border: '1px solid var(--rule)',
            borderRadius: '8px',
            padding: '10px 18px',
            marginTop: '8px',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--mono)',
              fontSize: '9px',
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: 'var(--brand)',
              opacity: 0.7,
              marginBottom: '4px',
            }}
          >
            {msg.columns![1] ?? msg.columns![0]}
          </span>
          <span
            style={{
              fontFamily: 'var(--mono)',
              fontSize: '22px',
              fontWeight: 700,
              color: 'var(--fg)',
            }}
          >
            {String(msg.rows![0]?.[msg.columns![1]] ?? msg.rows![0]?.[msg.columns![0]] ?? '—')}
          </span>
        </div>
      )}

      {/* Footer row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          marginTop: '10px',
          flexWrap: 'wrap',
        }}
      >
        {msg.sql && (
          <button
            onClick={() => setShowSQL((s) => !s)}
            style={{
              background: 'none',
              border: '1px solid var(--rule)',
              borderRadius: '4px',
              color: 'var(--fg-3)',
              fontFamily: 'var(--mono)',
              fontSize: '10px',
              padding: '2px 8px',
              cursor: 'pointer',
              letterSpacing: '0.06em',
            }}
          >
            {showSQL ? 'Hide SQL' : 'View SQL'}
          </button>
        )}
        {msg.row_count !== undefined && (
          <span
            style={{
              fontFamily: 'var(--mono)',
              fontSize: '10px',
              color: 'var(--fg-3)',
            }}
          >
            {msg.row_count} row{msg.row_count !== 1 ? 's' : ''} returned
          </span>
        )}
      </div>

      {showSQL && msg.sql && (
        <pre
          style={{
            marginTop: '8px',
            padding: '10px',
            background: 'var(--ink-1)',
            border: '1px solid var(--rule)',
            borderRadius: '6px',
            fontFamily: 'var(--mono)',
            fontSize: '11px',
            color: 'var(--text-secondary)',
            overflowX: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {msg.sql}
        </pre>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main panel
// ─────────────────────────────────────────────────────────────────────────────

const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  'http://localhost:8000';

export default function FraudChatPanel() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const threadRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest message
  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: UserMessage = { role: 'user', text };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const token = getAuthToken();
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          message: text,
          conversation_history: messages,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail ?? `HTTP ${res.status}`);
      }

      const data: ChatApiResponse = await res.json();
      const assistantMsg: AssistantMessage = {
        role: 'assistant',
        summary: data.summary,
        sql: data.sql,
        rows: data.rows,
        columns: data.columns,
        visualization: data.visualization,
        row_count: data.row_count,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg: AssistantMessage = {
        role: 'assistant',
        summary: err instanceof Error ? err.message : 'Query failed. The analysis engine returned an error — rephrase your question or retry.',
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      {/* ── Floating toggle button ── */}
      <button
        onClick={() => setOpen((o) => !o)}
        title="Fraud Analyst Chatbot"
        className={`btn${open ? ' primary' : ''}`}
        style={{
          position: 'fixed',
          bottom: '28px',
          right: '28px',
          zIndex: 1100,
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          padding: 0,
          justifyContent: 'center',
          boxShadow: open ? '0 4px 24px var(--brand-glow)' : '0 4px 24px rgba(0,0,0,0.4)',
          fontSize: '20px',
          lineHeight: 1,
        }}
        aria-label={open ? 'Close chatbot' : 'Open fraud analyst chatbot'}
      >
        {open ? '✕' : '◈'}
      </button>

      {/* ── Slide-in chat panel ── */}
      <div
        className="panel"
        style={{
          position: 'fixed',
          top: 0,
          right: open ? 0 : '-420px',
          width: '400px',
          height: '100vh',
          zIndex: 1000,
          display: 'flex',
          flexDirection: 'column',
          borderRadius: 0,
          borderTop: 'none',
          borderBottom: 'none',
          borderRight: 'none',
          padding: 0,
          boxShadow: '-8px 0 40px rgba(0,0,0,0.5)',
          transition: 'right 0.28s var(--ease-out)',
        }}
        aria-hidden={!open}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 18px 14px',
            borderBottom: '1px solid var(--rule)',
            flexShrink: 0,
            position: 'relative',
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              height: '2px',
              background: 'linear-gradient(90deg, var(--brand), transparent)',
              opacity: 0.5,
            }}
          />
          <div
            style={{
              fontFamily: 'var(--mono)',
              fontSize: '10px',
              fontWeight: 600,
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              color: 'var(--brand)',
              opacity: 0.7,
              marginBottom: '2px',
            }}
          >
            Fraud Analyst
          </div>
          <div
            style={{
              fontFamily: 'var(--mono)',
              fontSize: '13px',
              color: 'var(--fg)',
            }}
          >
            Query your fraud data in plain language.
          </div>
        </div>

        {/* Message thread */}
        <div
          ref={threadRef}
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          {messages.length === 0 && (
            <div
              style={{
                textAlign: 'center',
                color: 'var(--fg-3)',
                fontFamily: 'var(--mono)',
                fontSize: '12px',
                marginTop: '40px',
                lineHeight: 1.8,
              }}
            >
              <div style={{ fontSize: '24px', marginBottom: '12px' }}>◈</div>
              Example queries:
              <br />
              "Which merchant has the highest fraud rate today?"
              <br />
              "Compare fraud volume this week vs last week"
              <br />
              {`Show high value frauds above $${APP_METRICS.chat.highValueFraudThreshold} in the last hour`}
            </div>
          )}

          {messages.map((msg, i) =>
            msg.role === 'user' ? (
              <div key={i} style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <div
                  style={{
                    background: 'var(--brand)',
                    color: 'var(--ink-0)',
                    borderRadius: '8px',
                    padding: '8px 12px',
                    maxWidth: '80%',
                    fontFamily: 'var(--mono)',
                    fontSize: '13px',
                    lineHeight: 1.4,
                  }}
                >
                  {msg.text}
                </div>
              </div>
            ) : (
              <div key={i} style={{ display: 'flex', justifyContent: 'flex-start' }}>
                <div style={{ maxWidth: '100%', width: '100%' }}>
                  <AssistantBubble msg={msg} />
                </div>
              </div>
            )
          )}

          {loading && (
            <div
              style={{
                display: 'flex',
                gap: '4px',
                padding: '10px 14px',
                alignItems: 'center',
              }}
            >
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    background: 'var(--brand)',
                    opacity: 0.6,
                    animation: `chatPulse 1.2s ease-in-out ${i * 0.2}s infinite`,
                  }}
                />
              ))}
              <style>{`
                @keyframes chatPulse {
                  0%, 80%, 100% { transform: scale(0.8); opacity: 0.4; }
                  40% { transform: scale(1.2); opacity: 1; }
                }
              `}</style>
            </div>
          )}
        </div>

        {/* Input bar */}
        <div
          style={{
            padding: '12px 14px',
            borderTop: '1px solid var(--rule)',
            flexShrink: 0,
            display: 'flex',
            gap: '8px',
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g. Which merchants had the highest fraud rate this week?"
            disabled={loading}
            style={{
              flex: 1,
              background: 'var(--ink-1)',
              border: '1px solid var(--rule)',
              borderRadius: '6px',
              padding: '8px 12px',
              fontFamily: 'var(--mono)',
              fontSize: '12px',
              color: 'var(--fg)',
              outline: 'none',
              opacity: loading ? 0.5 : 1,
            }}
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            style={{
              background: 'var(--brand)',
              color: 'var(--ink-0)',
              border: 'none',
              borderRadius: '6px',
              padding: '8px 14px',
              fontFamily: 'var(--mono)',
              fontSize: '11px',
              fontWeight: 600,
              letterSpacing: '0.06em',
              cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
              opacity: loading || !input.trim() ? 0.5 : 1,
              transition: 'opacity 0.15s',
            }}
          >
            Send
          </button>
        </div>
      </div>
    </>
  );
}
