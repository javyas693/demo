import React from 'react';
import Tooltip from './Tooltip';

const MACRO_MAP = {
  risk_on:  { label: 'Risk-on',  color: '#3b82f6', pct: 80 },
  neutral:  { label: 'Neutral',  color: '#94a3b8', pct: 45 },
  risk_off: { label: 'Risk-off', color: '#22c55e', pct: 20 },
};

const VOL_MAP = {
  high:   { label: 'High',   pct: 85, color: '#f59e0b' },
  medium: { label: 'Medium', pct: 50, color: '#94a3b8' },
  low:    { label: 'Low',    pct: 20, color: '#22c55e' },
};

const SIGNAL_TOOLTIPS = {
  momentum: (score, passed) => passed
    ? `Momentum score is ${score?.toFixed(3)}. The threshold is 0.5 — scores below this mean the stock is not strongly rallying, so the system allows selling. This month: sell is permitted.`
    : `Momentum score is ${score?.toFixed(3)}. The threshold is 0.5 — scores above this mean the stock is strongly bullish. The system protects upside by not selling during rallies. This month: sale blocked.`,

  macro: (regime, passed) => passed
    ? `Macro regime is "${regime}" — the broader market environment is neutral or cautious. The system allows selling when macro is not in risk-on mode.`
    : `Macro regime is "${regime}" — the market is in a risk-on phase, meaning broad assets are rallying. The system holds the position to capture potential upside. Sale blocked.`,

  volatility: (level, passed) => passed
    ? `Volatility is "${level}" — within acceptable range. The system allows selling when volatility is not extreme.`
    : `Volatility is "${level}" — elevated market turbulence detected. The system defers selling to protect execution quality. Sale blocked.`,

  decision: (enable, reason, shares) => enable
    ? `All signal gates passed this month. The system executed a tax-neutral sale of ${shares} shares. Gains were fully offset by the tax-loss harvest (TLH) inventory.`
    : `One or more signal gates blocked the sale. The covered call overlay continued running to generate option premium income. No shares were sold.`,
};

function Gauge({ label, pct, color, display, subtext, showThreshold, thresholdPct, tooltip }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <Tooltip content={tooltip} position="right">
          <span className="text-xs text-slate-500 cursor-help border-b border-dashed border-slate-200">{label}</span>
        </Tooltip>
        <span className="text-xs font-semibold text-slate-700">{display}</span>
      </div>
      <div className="relative h-1.5 bg-slate-100 rounded-full overflow-visible">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${Math.max(3, Math.min(100, pct))}%`, background: color }}
        />
        {showThreshold && (
          <div
            className="absolute top-1/2 -translate-y-1/2 w-px h-3 bg-slate-300"
            style={{ left: `${thresholdPct}%` }}
            title="Block threshold at 0.5"
          />
        )}
      </div>
      {subtext && (
        <span className="text-xs text-slate-300 leading-none">{subtext}</span>
      )}
    </div>
  );
}

export default function SignalGaugePanel({ intel }) {
  if (!intel?.signals) {
    return (
      <div className="flex flex-col gap-2">
        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Signal state</span>
        <p className="text-xs text-slate-300 italic">Move the slider to a month to see signals</p>
      </div>
    );
  }

  const { momentum_score, macro_regime, volatility_level } = intel.signals;

  const momPct   = Math.round(((momentum_score + 1) / 2) * 100);
  const momColor = momentum_score >= 0.5 ? '#f59e0b' : momentum_score >= 0 ? '#94a3b8' : '#3b82f6';
  const momPass  = momentum_score <= 0.5;

  const macro = MACRO_MAP[macro_regime] || MACRO_MAP.neutral;
  const vol   = VOL_MAP[volatility_level]  || VOL_MAP.medium;
  const volPass = volatility_level !== 'high';

  const blockReason = intel.blocking_reason || '';
  const blockedBy = blockReason.includes('MOMENTUM') ? 'momentum too bullish'
    : blockReason.includes('MACRO') ? 'macro risk-on'
    : blockReason.includes('VOLATILITY') ? 'high volatility'
    : null;

  return (
    <div className="flex flex-col gap-4">
      <Tooltip content="Signals are market indicators the system evaluates each month before deciding whether to sell shares. All three must pass for a sale to occur. If any signal blocks, the system switches to income-only mode using covered calls.">
        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider cursor-help border-b border-dashed border-slate-300">
          Signal state — month {intel.month}
        </span>
      </Tooltip>

      <Gauge
        label="Momentum"
        pct={momPct}
        color={momColor}
        display={momentum_score?.toFixed(3)}
        subtext={momPass ? 'Not bullish — allows selling' : 'Strongly bullish — blocks selling'}
        showThreshold
        thresholdPct={75}
        tooltip={SIGNAL_TOOLTIPS.momentum(momentum_score, momPass)}
      />

      <Gauge
        label="Macro environment"
        pct={macro.pct}
        color={macro.color}
        display={macro.label}
        subtext={macro_regime === 'risk_on' ? 'Risk-on — blocks selling' : 'Neutral or cautious — allows selling'}
        showThreshold={false}
        tooltip={SIGNAL_TOOLTIPS.macro(macro_regime, macro_regime !== 'risk_on')}
      />

      <Gauge
        label="Volatility"
        pct={vol.pct}
        color={vol.color}
        display={vol.label}
        subtext={!volPass ? 'High vol — blocks selling' : 'Acceptable — allows selling'}
        showThreshold={false}
        tooltip={SIGNAL_TOOLTIPS.volatility(volatility_level, volPass)}
      />

      <Tooltip content={SIGNAL_TOOLTIPS.decision(intel.enable_unwind, blockReason, intel.shares_to_sell)}>
        <div className="pt-3 border-t border-slate-100 flex items-center justify-between w-full cursor-help">
          <span className="text-xs text-slate-400">This month's decision</span>
          {intel.enable_unwind ? (
            <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-green-50 text-green-700 border border-green-200">
              Sell {intel.shares_to_sell} shares
            </span>
          ) : (
            <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
              Hold — {blockedBy || 'blocked'}
            </span>
          )}
        </div>
      </Tooltip>
    </div>
  );
}
