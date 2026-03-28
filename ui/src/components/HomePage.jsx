import { useState } from 'react';
import { ArrowRight } from 'lucide-react';

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

// ── Field input (dark styled) ────────────────────────────
function Field({ label, type, value, onChange, placeholder }) {
  return (
    <div>
      <label style={{
        color: C.muted, fontSize: '0.7rem', fontWeight: 700,
        display: 'block', marginBottom: '0.375rem',
        textTransform: 'uppercase', letterSpacing: '0.07em',
      }}>
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          background: C.bg, border: `1px solid ${C.cardBorder}`,
          borderRadius: '0.625rem', color: C.cream,
          padding: '0.625rem 0.875rem', width: '100%',
          fontSize: '0.9rem', outline: 'none', boxSizing: 'border-box',
        }}
      />
    </div>
  );
}

// ── Onboarding card (no simulation yet) ─────────────────
function OnboardingCard({ inputs, setInputs, onSimulate, loading, error }) {
  return (
    <div style={{ background: C.bg, minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2rem 1rem' }}>
      <div style={{
        background: C.card, border: `1px solid ${C.cardBorder}`,
        borderRadius: '1.5rem', width: '100%', maxWidth: '480px',
        padding: '2.5rem', boxShadow: '0 24px 60px rgba(0,0,0,0.6)',
      }}>
        <div style={{ marginBottom: '2rem' }}>
          <h1 style={{ fontFamily: serif, color: C.gold, fontSize: '1.875rem', fontWeight: 700, margin: 0 }}>
            AI Advisory
          </h1>
          <p style={{ color: C.muted, marginTop: '0.5rem', fontSize: '0.9rem', lineHeight: 1.6 }}>
            Tell us about your position and we'll build your personalized strategy.
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Field label="Stock ticker" type="text" value={inputs.ticker}
              onChange={v => setInputs(p => ({ ...p, ticker: v.toUpperCase() }))} placeholder="AAPL" />
            <Field label="Shares held" type="number" value={inputs.initial_shares}
              onChange={v => setInputs(p => ({ ...p, initial_shares: v === '' ? '' : Number(v) }))} placeholder="8000" />
          </div>
          <Field label="Cost basis per share ($)" type="number" value={inputs.unwind_cost_basis}
            onChange={v => setInputs(p => ({ ...p, unwind_cost_basis: v === '' ? '' : Number(v) }))} placeholder="15.00" />
          <Field label="Total portfolio value ($)" type="number" value={inputs.total_portfolio_value}
            onChange={v => setInputs(p => ({ ...p, total_portfolio_value: v === '' ? '' : Number(v), concentrated_position_value: v === '' ? '' : Number(v) - (p.cash || 50000) }))}
            placeholder="1250000" />
          <Field label="Existing tax losses ($)" type="number" value={inputs.tlh_inventory}
            onChange={v => setInputs(p => ({ ...p, tlh_inventory: v === '' ? '' : Number(v) }))} placeholder="250000" />
          <Field label="Investment horizon (years)" type="number" value={inputs.horizon_years}
            onChange={v => setInputs(p => ({ ...p, horizon_years: v === '' ? '' : Number(v) }))} placeholder="3" />
        </div>

        {error && (
          <div style={{ marginTop: '1rem', background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', borderRadius: '0.625rem', padding: '0.75rem 1rem', color: '#f87171', fontSize: '0.8rem' }}>
            {error}
          </div>
        )}

        <button
          onClick={onSimulate}
          disabled={loading}
          style={{
            background: loading ? C.cardBorder : C.gold,
            color: loading ? C.muted : C.bg,
            borderRadius: '0.75rem', marginTop: '1.75rem', width: '100%',
            padding: '0.875rem', fontWeight: 700, fontSize: '0.925rem',
            cursor: loading ? 'not-allowed' : 'pointer', border: 'none',
            transition: 'background 0.2s',
          }}>
          {loading ? 'Analyzing your position…' : 'Analyze my position →'}
        </button>
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
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  const hasSimulation = timeline && timeline.length > 0;

  const handleSimulate = async () => {
    setLoading(true);
    setError(null);
    try {
      const numericFields = ['initial_shares','unwind_cost_basis','cash','tlh_inventory',
        'total_portfolio_value','concentrated_position_value','income_portfolio_value','model_portfolio_value','horizon_years'];
      const coerced = { ...inputs };
      numericFields.forEach(k => { if (coerced[k] === '') coerced[k] = 0; });
      const payload = {
        ...coerced,
        horizon_months: (coerced.horizon_years || 1) * 12,
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
    } finally {
      setLoading(false);
    }
  };

  if (!hasSimulation) {
    return <OnboardingCard inputs={inputs} setInputs={setInputs} onSimulate={handleSimulate} loading={loading} error={error} />;
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
