import React, { useState } from 'react';
import { CheckCircle2, XCircle, MinusCircle, ChevronDown, ChevronUp } from 'lucide-react';
import Tooltip from './Tooltip';

const HIDDEN_RULES = new Set([
  'INPUT_SNAPSHOT',
  'INVARIANT_CHECK',
  'GAIN_PER_SHARE_CALC',
  'TLH_SIZING',
  'URGENCY_SIZING',
  'FREE_SHARES_GATE',
  'SIGNAL_SUMMARY',
]);

const RULE_LABELS = {
  MOMENTUM_GATE:        'Momentum signal',
  MACRO_GATE:           'Macro environment',
  VOLATILITY_GATE:      'Volatility level',
  CLIENT_CONSTRAINT:    'Client permission',
  PRICE_TRIGGER_GATE:   'Price above trigger',
  CONCENTRATION_GATE:   'Concentration level',
  TLH_CAPACITY_GATE:    'Tax-loss buffer',
  UNREALIZED_GAIN_GATE: 'Unrealized gain check',
  SIGNAL_BLOCK:         'Signal verdict',
  FINAL_DECISION:       'Final decision',
};

const RULE_TOOLTIPS = {
  MOMENTUM_GATE:        'Checks whether the stock is strongly rallying. If momentum is above 0.5, the system holds to protect upside. Below 0.5, selling is permitted.',
  MACRO_GATE:           'Checks the broader market environment. If the market is in a risk-on phase (broad rally), the system holds the position. In neutral or cautious regimes, selling is permitted.',
  VOLATILITY_GATE:      'Checks market volatility. High volatility means uncertain execution prices, so the system defers selling. Medium or low volatility allows selling.',
  CLIENT_CONSTRAINT:    'The client\'s instruction on selling. SELL_OPTIONAL means the system decides. NO_SELL means never sell. SELL_REQUIRED means always attempt to sell.',
  PRICE_TRIGGER_GATE:   'Confirms the current price is above the minimum sell trigger (a small premium above cost basis). Prevents selling at a loss.',
  CONCENTRATION_GATE:   'Confirms the concentrated position is still large enough to warrant reducing. If it drops below 15% of the portfolio, the urgency to unwind decreases.',
  TLH_CAPACITY_GATE:    'Confirms there is enough tax-loss harvest (TLH) inventory to offset the capital gains from selling. This keeps the sale tax-neutral — no tax bill.',
  UNREALIZED_GAIN_GATE: 'Confirms the position has an unrealized gain. The TLH system is only relevant when there are gains to offset.',
  SIGNAL_BLOCK:         'Summary of which signal caused the block. The system falls back to Mode 1 (income-only via covered calls) when any signal fails.',
  FINAL_DECISION:       'The final outcome after all rules have been evaluated. Either a sell is executed, or the system holds and runs the covered call overlay for income.',
};

function humanNote(rule) {
  if (rule.rule === 'MOMENTUM_GATE') {
    const score = typeof rule.value === 'number' ? rule.value.toFixed(3) : rule.value;
    return rule.passed
      ? `Momentum ${score} — not strongly bullish, unwind allowed`
      : `Momentum ${score} — stock rallying, protecting upside`;
  }
  if (rule.rule === 'MACRO_GATE') {
    return rule.passed
      ? 'Macro environment is neutral — unwind allowed'
      : 'Market in risk-on mode — holding position to capture upside';
  }
  if (rule.rule === 'VOLATILITY_GATE') {
    return rule.passed
      ? 'Volatility is moderate — acceptable for selling'
      : 'Elevated volatility — deferring sell to protect execution quality';
  }
  if (rule.rule === 'CLIENT_CONSTRAINT') {
    if (rule.value === 'NO_SELL')       return 'Client has instructed no selling';
    if (rule.value === 'SELL_REQUIRED') return 'Client requires selling this month';
    return 'Client allows the system to decide on selling';
  }
  if (rule.rule === 'PRICE_TRIGGER_GATE') {
    const price   = typeof rule.value     === 'number' ? rule.value.toFixed(2)     : rule.value;
    const trigger = typeof rule.threshold === 'number' ? rule.threshold.toFixed(2) : rule.threshold;
    return `Current price $${price} is above the $${trigger} minimum sell trigger`;
  }
  if (rule.rule === 'CONCENTRATION_GATE') {
    const pct = typeof rule.value === 'number' ? (rule.value * 100).toFixed(1) : rule.value;
    return `Position is ${pct}% of portfolio — above the 15% concentration threshold`;
  }
  if (rule.rule === 'TLH_CAPACITY_GATE') {
    const val = typeof rule.value === 'number'
      ? `$${Math.round(rule.value).toLocaleString()}`
      : rule.value;
    return `${val} in tax-loss buffer — enough to fully offset the gains from this sale`;
  }
  if (rule.rule === 'UNREALIZED_GAIN_GATE') {
    const gain = typeof rule.value === 'number' ? rule.value.toFixed(2) : rule.value;
    return `$${gain} unrealized gain per share — position is profitable`;
  }
  if (rule.rule === 'SIGNAL_BLOCK') {
    const gate = (rule.value || '').toLowerCase();
    const name = gate === 'momentum' ? 'Momentum'
      : gate === 'macro' ? 'Macro environment'
      : 'Volatility';
    return `${name} blocked the sale — switching to income-only mode this month`;
  }
  if (rule.rule === 'FINAL_DECISION') {
    if (rule.enable_unwind) return `Sell ${rule.shares_to_sell} shares — all gates passed, tax-neutral sale executed`;
    const br = rule.blocking_reason || '';
    const reason = br.includes('MOMENTUM') ? 'momentum signal'
      : br.includes('MACRO') ? 'macro environment'
      : 'volatility';
    return `No sale this month — blocked by ${reason}. Covered call overlay running for income.`;
  }
  return rule.note || '';
}

export default function DecisionTracePanel2({ intel }) {
  const [expanded, setExpanded] = useState(false);

  if (!intel) {
    return (
      <div className="flex flex-col gap-2">
        <Tooltip content="The decision trace shows every rule the system evaluated this month, in order, with a plain-English explanation of what it checked and why it passed or blocked.">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider cursor-help border-b border-dashed border-slate-300">
            Decision trace
          </span>
        </Tooltip>
        <p className="text-xs text-slate-300 italic">Move the slider to a month to see the trace</p>
      </div>
    );
  }

  const trace = (intel.decision_trace || []).filter(r => !HIDDEN_RULES.has(r.rule));

  if (trace.length === 0) {
    return (
      <div className="flex flex-col gap-2">
        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Decision trace</span>
        <p className="text-xs text-slate-400 italic">No trace data for this month</p>
      </div>
    );
  }

  const visible = expanded ? trace : trace.slice(0, 4);

  return (
    <div className="flex flex-col">
      <Tooltip content="The decision trace shows every rule the system evaluated this month, in order, with a plain-English explanation of what it checked and why it passed or blocked.">
        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 cursor-help border-b border-dashed border-slate-300 self-start">
          Decision trace — month {intel.month}
        </span>
      </Tooltip>

      <div className="flex flex-col mt-1">
        {visible.map((rule, i) => {
          const isFinal = rule.rule === 'FINAL_DECISION';
          const label   = RULE_LABELS[rule.rule] || rule.rule;
          const note    = humanNote(rule);
          const tip     = RULE_TOOLTIPS[rule.rule];

          const icon = isFinal
            ? <MinusCircle className="w-3.5 h-3.5 text-slate-400 flex-shrink-0 mt-0.5" />
            : rule.passed
              ? <CheckCircle2 className="w-3.5 h-3.5 text-green-500 flex-shrink-0 mt-0.5" />
              : <XCircle className="w-3.5 h-3.5 text-amber-500 flex-shrink-0 mt-0.5" />;

          return (
            <div
              key={i}
              className={`flex items-start gap-2.5 py-2 border-b border-slate-100 last:border-0 ${isFinal ? 'opacity-75' : ''}`}
            >
              {icon}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Tooltip content={tip} position="right">
                    <span className="text-xs font-semibold text-slate-700 cursor-help border-b border-dashed border-slate-200">
                      {label}
                    </span>
                  </Tooltip>
                  {!isFinal && (
                    <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                      rule.passed
                        ? 'bg-green-50 text-green-700'
                        : 'bg-amber-50 text-amber-700'
                    }`}>
                      {rule.passed ? 'Pass' : 'Block'}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">{note}</p>
              </div>
            </div>
          );
        })}
      </div>

      {trace.length > 4 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs text-blue-500 hover:text-blue-700 mt-2 self-start transition-colors"
        >
          {expanded
            ? <><ChevronUp className="w-3 h-3" /> Show less</>
            : <><ChevronDown className="w-3 h-3" /> {trace.length - 4} more rules</>
          }
        </button>
      )}
    </div>
  );
}
