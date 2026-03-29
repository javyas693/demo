import { useState, useEffect, useRef } from 'react';
import { ArrowRight, Send } from 'lucide-react';

// ── Palette (dark warm theme) ────────────────────────────
const C = {
  bg:         '#181410',
  card:       '#1e1a14',
  cardBorder: '#352d1f',
  surface:    '#262016',
  gold:       '#c9a84c',
  goldDim:    '#8c7235',
  cream:      '#f0e6cc',
  muted:      '#8a7a60',
  green:      '#6ee7b7',
  red:        '#f87171',
  blue:       '#93c5fd',
};

const serif = "'Playfair Display', Georgia, serif";
const serifBody = "'Crimson Pro', Georgia, serif";

// ── Helpers ──────────────────────────────────────────────
const fmt = (v) => {
  if (v == null) return '—';
  if (v >= 1_000_000) return '$' + (v / 1_000_000).toFixed(2) + 'M';
  if (v >= 1_000) return '$' + (v / 1_000).toFixed(0) + 'K';
  return '$' + Math.round(v).toLocaleString();
};


// ── Typing indicator ─────────────────────────────────────
function TypingDots() {
  return (
    <div style={{ display: 'flex', gap: '4px', padding: '2px 0' }}>
      {[0, 1, 2].map(i => (
        <div key={i} style={{
          width: 6, height: 6, borderRadius: '50%',
          background: C.muted,
          animation: 'bounce 1.2s infinite',
          animationDelay: `${i * 0.2}s`,
        }} />
      ))}
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40% { transform: translateY(-5px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

// ── Chat onboarding card ──────────────────────────────────
function OnboardingCard({ onSimulate, error }) {
  const [messages, setMessages]       = useState([]);
  const [input, setInput]             = useState('');
  const [conversationId, setConversationId] = useState(null);
  const [isTyping, setIsTyping]       = useState(false);
  const [started, setStarted]         = useState(false);
  const bottomRef                     = useRef(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const sendMessage = async (text) => {
    if (!text.trim() || isTyping) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setIsTyping(true);
    try {
      const res = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, conversation_id: conversationId }),
      });
      const data = await res.json();
      const convId = data.conversation_id || conversationId;
      if (!conversationId) setConversationId(convId);
      setMessages(prev => [...prev, { role: 'assistant', content: data.agent_message, responseType: data.response_type }]);

      // When chatbot has everything — kick off simulation
      if (data.response_type === 'summary' && data.payload) {
        onSimulate(data.payload);
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Something went wrong. Please try again.', responseType: 'error' }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleStart = () => {
    setStarted(true);
    sendMessage('Hello');
  };

  return (
    <div style={{ background: C.bg, minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2rem 1rem' }}>
      <div style={{
        background: C.card, border: `1px solid ${C.cardBorder}`,
        borderRadius: '1.5rem', width: '100%', maxWidth: '520px',
        boxShadow: '0 24px 60px rgba(0,0,0,0.6)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{ padding: '1.75rem 2rem 1.25rem', borderBottom: `1px solid ${C.cardBorder}` }}>
          <h1 style={{ fontFamily: serif, color: C.gold, fontSize: '1.75rem', fontWeight: 700, margin: 0 }}>
            AI Advisory
          </h1>
          <p style={{ color: C.muted, marginTop: '0.35rem', fontSize: '0.85rem', lineHeight: 1.5 }}>
            Your personal advisor for managing concentrated positions.
          </p>
        </div>

        {!started ? (
          /* Welcome state */
          <div style={{ padding: '2.5rem 2rem', textAlign: 'center' }}>
            <p style={{ color: C.cream, fontSize: '1rem', lineHeight: 1.7, marginBottom: '2rem', fontFamily: serifBody }}>
              I'll ask you a few questions about your position and risk preferences, then build your personalized strategy.
            </p>
            <button onClick={handleStart} style={{
              background: C.gold, color: C.bg, border: 'none',
              borderRadius: '0.75rem', padding: '0.875rem 2rem',
              fontWeight: 700, fontSize: '0.95rem', cursor: 'pointer',
              width: '100%', transition: 'opacity 0.2s',
            }}>
              Get started →
            </button>
          </div>
        ) : (
          <>
            {/* Message thread */}
            <div style={{ padding: '1.25rem 1.5rem', overflowY: 'auto', maxHeight: '380px', display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
              {messages.map((m, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
                  <div style={{
                    maxWidth: '82%',
                    background: m.role === 'user' ? C.goldDim : C.surface,
                    border: `1px solid ${m.role === 'user' ? 'transparent' : C.cardBorder}`,
                    borderRadius: m.role === 'user' ? '1rem 1rem 0.25rem 1rem' : '1rem 1rem 1rem 0.25rem',
                    padding: '0.625rem 0.875rem',
                    color: m.role === 'user' ? C.cream : C.cream,
                    fontSize: '0.875rem', lineHeight: 1.6,
                    fontFamily: serifBody,
                  }}>
                    {m.content}
                  </div>
                </div>
              ))}
              {isTyping && (
                <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                  <div style={{ background: C.surface, border: `1px solid ${C.cardBorder}`, borderRadius: '1rem 1rem 1rem 0.25rem', padding: '0.625rem 0.875rem' }}>
                    <TypingDots />
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Input bar */}
            <div style={{ padding: '1rem 1.5rem', borderTop: `1px solid ${C.cardBorder}`, display: 'flex', gap: '0.625rem' }}>
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage(input)}
                placeholder="Type your reply…"
                disabled={isTyping}
                style={{
                  flex: 1, background: C.bg, border: `1px solid ${C.cardBorder}`,
                  borderRadius: '0.625rem', color: C.cream, padding: '0.625rem 0.875rem',
                  fontSize: '0.875rem', outline: 'none',
                  opacity: isTyping ? 0.5 : 1,
                }}
              />
              <button
                onClick={() => sendMessage(input)}
                disabled={isTyping || !input.trim()}
                style={{
                  background: input.trim() && !isTyping ? C.gold : C.cardBorder,
                  color: input.trim() && !isTyping ? C.bg : C.muted,
                  border: 'none', borderRadius: '0.625rem',
                  padding: '0 1rem', cursor: input.trim() && !isTyping ? 'pointer' : 'not-allowed',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'background 0.2s',
                }}
              >
                <Send size={16} />
              </button>
            </div>
          </>
        )}

        {error && (
          <div style={{ margin: '0 1.5rem 1rem', background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', borderRadius: '0.625rem', padding: '0.75rem 1rem', color: '#f87171', fontSize: '0.8rem' }}>
            {error}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Metric tile ──────────────────────────────────────────
function MetricTile({ label, headline, sub1, sub2, target, headlineGold }) {
  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.cardBorder}`,
      borderRadius: '1rem', padding: '1.25rem',
    }}>
      <div style={{ color: C.muted, fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>
        {label}
      </div>
      <div style={{
        color: headlineGold ? C.gold : C.cream,
        fontSize: '1.5rem', fontWeight: 700,
        fontFamily: serifBody, lineHeight: 1.2,
      }}>
        {headline}
      </div>
      {sub1 && <div style={{ color: C.green, fontSize: '0.73rem', marginTop: '0.4rem', fontWeight: 600 }}>{sub1}</div>}
      {sub2 && <div style={{ color: C.green, fontSize: '0.73rem', marginTop: '0.15rem', fontWeight: 600 }}>{sub2}</div>}
      {target && <div style={{ color: C.gold, fontSize: '0.73rem', marginTop: '0.3rem', fontWeight: 600 }}>{target}</div>}
    </div>
  );
}

// ── Login card (simulation exists) ──────────────────────
function LoginCard({ timeline, monthlyIntelligence, simulatedInputs, onNavigate }) {
  const lastState  = timeline[timeline.length - 1];
  const firstState = timeline[0];
  const lastIntel  = monthlyIntelligence[monthlyIntelligence.length - 1];

  const totalIncome = monthlyIntelligence.reduce((s, m) => s + (m.option_premium || 0), 0);
  const tlhNow      = lastIntel?.tlh_inventory_after || 0;
  const concNow     = (lastState?.concentration_pct || 0) * 100;
  const concStart   = (firstState?.concentration_pct || 0) * 100;
  const quarterAgo  = timeline[Math.max(0, timeline.length - 4)];
  const concQ       = (quarterAgo?.concentration_pct || 0) * 100 - concNow;
  const totalMonths = monthlyIntelligence.length;

  // Status sentence
  let statusSentence;
  if (lastIntel?.enable_unwind) {
    statusSentence = `Last month the strategy reduced your position and captured income. Your tax loss reserve stands at ${fmt(tlhNow)}.`;
  } else if (lastIntel?.blocking_reason?.includes('MOMENTUM')) {
    statusSentence = `Markets were favorable last month — the strategy held your position and collected covered call income instead of selling.`;
  } else if (lastIntel?.blocking_reason?.includes('MACRO')) {
    statusSentence = `A cautious market environment last month led the strategy to hold and collect income rather than sell.`;
  } else {
    statusSentence = `Your position is being actively managed. Income is accumulating and your tax loss reserve is building.`;
  }

  return (
    <div style={{ background: C.bg, minHeight: '100vh' }}>
      <div style={{ maxWidth: '960px', margin: '0 auto', padding: '3.5rem 1.5rem 4rem' }}>

        {/* Main card */}
        <div style={{
          background: C.card, border: `1px solid ${C.cardBorder}`,
          borderRadius: '1.75rem', padding: '2.5rem',
          boxShadow: '0 28px 70px rgba(0,0,0,0.55)',
        }}>
          {/* Header row */}
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '1.75rem' }}>
            <div>
              <h1 style={{ fontFamily: serif, color: C.gold, fontSize: '2rem', fontWeight: 700, margin: 0, lineHeight: 1.2 }}>
                AI Advisory
              </h1>
              <p style={{ color: C.muted, fontSize: '0.85rem', marginTop: '0.3rem' }}>
                {simulatedInputs?.ticker} · {simulatedInputs?.initial_shares?.toLocaleString()} shares · {simulatedInputs?.horizon_years}yr horizon
              </p>
            </div>
            <div style={{
              color: C.green, fontSize: '0.75rem', fontWeight: 700,
              background: 'rgba(110,231,183,0.1)', padding: '0.375rem 1rem',
              borderRadius: '2rem', border: '1px solid rgba(110,231,183,0.2)',
            }}>
              Active
            </div>
          </div>

          {/* 4 metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.875rem', marginBottom: '1.25rem' }}>
            <MetricTile
              label="Position Value"
              headline={fmt(lastState.total_portfolio_value)}
              sub1={`+${fmt(lastState.total_portfolio_value - firstState.total_portfolio_value)} since start`}
            />
            <MetricTile
              label="Income Collected"
              headline={fmt(totalIncome)}
              sub1={`across ${totalMonths} months`}
            />
            <MetricTile
              label="Tax Loss Reserve"
              headline={fmt(tlhNow)}
              sub1="ready to offset future gains"
            />
            <MetricTile
              label="Largest Position"
              headline={`${concNow.toFixed(1)}%`}
              sub1={`↓ From ${concStart.toFixed(1)}% at start`}
              sub2={concQ > 0.1 ? `↓ ${concQ.toFixed(1)}% this quarter` : undefined}
              target="◎ Target: below 15%"
              headlineGold
            />
          </div>

          {/* Status bar */}
          <div style={{
            background: C.bg, border: `1px solid ${C.cardBorder}`,
            borderRadius: '0.875rem', padding: '1rem 1.25rem',
          }}>
            <p style={{ color: '#d4c5a0', fontSize: '0.9rem', lineHeight: 1.65, margin: 0 }}>
              {statusSentence}
            </p>
          </div>

          {/* Footer nav links */}
          <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
            <button onClick={() => onNavigate('history')} style={linkBtn}>
              Full history →
            </button>
            <button onClick={() => onNavigate('projection')} style={linkBtn}>
              See projections →
            </button>
          </div>
        </div>

        {/* Acts */}
        <ActI monthlyIntelligence={monthlyIntelligence} onNavigate={onNavigate} />
        <ActII timeline={timeline} monthlyIntelligence={monthlyIntelligence} />
        <ActIII onNavigate={onNavigate} />
      </div>
    </div>
  );
}

const linkBtn = {
  background: 'transparent', border: `1px solid ${C.cardBorder}`,
  color: C.muted, borderRadius: '0.625rem',
  padding: '0.4rem 0.875rem', fontSize: '0.78rem',
  cursor: 'pointer', fontWeight: 600,
};

// ── Act I — What happened ────────────────────────────────
function ActI({ monthlyIntelligence, onNavigate }) {
  const firstSellIdx = monthlyIntelligence.findIndex(m => m.enable_unwind);
  const sellMonths   = monthlyIntelligence.filter(m => m.enable_unwind).length;
  const blockedMonths = monthlyIntelligence.filter(m => !m.enable_unwind).length;

  const largestHarvest = monthlyIntelligence.reduce((best, m, i) => {
    const prev  = i > 0 ? (monthlyIntelligence[i - 1]?.tlh_inventory_after || 0) : 0;
    const delta = (m.tlh_inventory_after || 0) - prev;
    return delta > best.delta ? { delta, i, month: m.month || i + 1 } : best;
  }, { delta: 0, i: -1, month: null });

  const moments = [];

  if (firstSellIdx >= 0) {
    moments.push({
      label: `Month ${monthlyIntelligence[firstSellIdx].month || firstSellIdx + 1}`,
      text: 'First position reduction — your unwind began.',
      accent: C.green,
    });
  }

  if (largestHarvest.i >= 0 && largestHarvest.delta > 0) {
    moments.push({
      label: `Month ${largestHarvest.month}`,
      text: `Largest single harvest — ${fmt(largestHarvest.delta)} added to your tax loss reserve.`,
      accent: C.gold,
    });
  }

  if (blockedMonths > 0) {
    moments.push({
      label: `${blockedMonths} month${blockedMonths > 1 ? 's' : ''}`,
      text: `Market conditions weren't right for selling. The strategy collected covered call income instead.`,
      accent: C.muted,
    });
  }

  if (sellMonths > 0) {
    moments.push({
      label: `${sellMonths} sale${sellMonths > 1 ? 's' : ''} total`,
      text: `Position reduced across ${sellMonths} month${sellMonths > 1 ? 's' : ''} using tax-efficient harvesting.`,
      accent: C.blue,
    });
  }

  return (
    <section style={{ marginTop: '2.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h2 style={{ fontFamily: serif, color: C.cream, fontSize: '1.2rem', fontWeight: 600, margin: 0 }}>
          What happened
        </h2>
        <button onClick={() => onNavigate('history')} style={{ ...linkBtn, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          Full history <ArrowRight size={13} />
        </button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.875rem' }}>
        {moments.map((m, i) => (
          <div key={i} style={{ background: C.card, border: `1px solid ${C.cardBorder}`, borderRadius: '1rem', padding: '1.25rem' }}>
            <div style={{ color: m.accent, fontSize: '0.73rem', fontWeight: 700, marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {m.label}
            </div>
            <div style={{ color: '#d4c5a0', fontSize: '0.875rem', lineHeight: 1.65 }}>
              {m.text}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

// ── Act II — Right now ───────────────────────────────────
function ActII({ timeline, monthlyIntelligence }) {
  const lastState = timeline[timeline.length - 1];
  const lastIntel = monthlyIntelligence[monthlyIntelligence.length - 1];
  const tlhNow    = lastIntel?.tlh_inventory_after || 0;
  const concNow   = (lastState?.concentration_pct || 0) * 100;

  let strategyStatus, strategyDetail;
  if (lastIntel?.enable_unwind) {
    strategyStatus = 'Sale executed last month';
    strategyDetail = 'Your position was reduced. Proceeds were allocated to diversified holdings.';
  } else if (lastIntel?.blocking_reason?.includes('MOMENTUM')) {
    strategyStatus = 'Strategy held — market conditions were favorable';
    strategyDetail = "The stock showed strong momentum. Selling into strength isn't the right move — the strategy waited and collected call income instead.";
  } else if (lastIntel?.blocking_reason?.includes('MACRO')) {
    strategyStatus = 'Strategy held — cautious market environment';
    strategyDetail = 'Broader market signals suggested caution. The strategy paused and collected covered call income.';
  } else {
    strategyStatus = 'Strategy is active';
    strategyDetail = 'The strategy is evaluating conditions each month and will act when the time is right.';
  }

  const items = [
    {
      label: 'Your largest position',
      value: `${concNow.toFixed(1)}% of net worth`,
      note: concNow > 25 ? 'Concentration reduction is the current priority.' : 'Approaching the target range.',
      accent: concNow > 25 ? C.red : C.green,
    },
    {
      label: 'Tax loss reserve',
      value: fmt(tlhNow),
      note: 'Available to offset gains when shares are sold — making future sales tax-neutral.',
      accent: C.gold,
    },
    {
      label: 'Strategy status',
      value: strategyStatus,
      note: strategyDetail,
      accent: C.blue,
    },
  ];

  return (
    <section style={{ marginTop: '2.5rem' }}>
      <h2 style={{ fontFamily: serif, color: C.cream, fontSize: '1.2rem', fontWeight: 600, margin: '0 0 1rem 0' }}>
        Right now
      </h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {items.map((item, i) => (
          <div key={i} style={{ background: C.card, border: `1px solid ${C.cardBorder}`, borderRadius: '1rem', padding: '1.25rem' }}>
            <div style={{ color: C.muted, fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.3rem' }}>
              {item.label}
            </div>
            <div style={{ color: item.accent, fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.3rem', fontFamily: serifBody }}>
              {item.value}
            </div>
            <div style={{ color: C.muted, fontSize: '0.82rem', lineHeight: 1.6 }}>
              {item.note}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

// ── Act III — What's ahead ───────────────────────────────
function ActIII({ onNavigate }) {
  return (
    <section style={{ marginTop: '2.5rem', marginBottom: '4rem' }}>
      <h2 style={{ fontFamily: serif, color: C.cream, fontSize: '1.2rem', fontWeight: 600, margin: '0 0 1rem 0' }}>
        What's ahead
      </h2>
      <div style={{
        background: C.card, border: `1px solid ${C.cardBorder}`,
        borderRadius: '1rem', padding: '2rem', textAlign: 'center',
      }}>
        <p style={{ color: C.muted, fontSize: '0.9rem', lineHeight: 1.7, maxWidth: '440px', margin: '0 auto' }}>
          See how your wealth could grow across three scenarios — a tough market, the expected path, and a strong market — over the next 5 to 30 years.
        </p>
        <button
          onClick={() => onNavigate('projection')}
          style={{
            marginTop: '1.5rem', background: C.gold, color: C.bg,
            border: 'none', borderRadius: '0.75rem', padding: '0.75rem 2rem',
            fontWeight: 700, fontSize: '0.875rem', cursor: 'pointer',
          }}>
          See your long-term outlook →
        </button>
      </div>
    </section>
  );
}

// ── Export ───────────────────────────────────────────────
export default function HomePage({
  timeline, monthlyIntelligence, simulatedInputs,
  inputs, setInputs, onSimulationComplete, onNavigate,
}) {
  const [error, setError] = useState(null);

  const hasSimulation = timeline && timeline.length > 0;

  const handleSimulate = async (chatPayload) => {
    setError(null);
    try {
      // Build simulation inputs from chatbot summary payload
      const lots   = chatPayload.position_lots || chatPayload.lots || [];
      const ticker = chatPayload.position_ticker || chatPayload.ticker || inputs.ticker;
      const totalShares    = lots.reduce((s, l) => s + (l.shares || 0), 0);
      const avgCostBasis   = lots.length
        ? lots.reduce((s, l) => s + (l.cost_basis || 0) * (l.shares || 0), 0) / (totalShares || 1)
        : inputs.unwind_cost_basis;
      const cash           = chatPayload.starting_cash ?? inputs.cash;
      const riskScore      = chatPayload.risk_score_final ?? inputs.risk_score;

      const merged = {
        ...inputs,
        ticker,
        initial_shares:              totalShares || inputs.initial_shares,
        unwind_cost_basis:           avgCostBasis,
        cash,
        risk_score:                  riskScore,
        total_portfolio_value:       inputs.total_portfolio_value,
        concentrated_position_value: inputs.concentrated_position_value,
      };
      setInputs(merged);

      const payload = {
        ...merged,
        horizon_months: (merged.horizon_years || 1) * 12,
        gate_overrides: {},
      };
      const res = await fetch('http://localhost:8000/api/portfolio/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Simulation failed — check that the backend is running.');
      const data = await res.json();
      onSimulationComplete(data);
    } catch (err) {
      setError(err.message);
    }
  };

  if (!hasSimulation) {
    return <OnboardingCard onSimulate={handleSimulate} error={error} />;
  }

  return (
    <LoginCard
      timeline={timeline}
      monthlyIntelligence={monthlyIntelligence}
      simulatedInputs={simulatedInputs}
      onNavigate={onNavigate}
    />
  );
}
