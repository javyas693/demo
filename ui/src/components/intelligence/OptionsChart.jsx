import React from 'react';
import Tooltip from './Tooltip';

export default function OptionsChart({ allIntel, currentIndex }) {
  if (!allIntel || allIntel.length === 0) return null;

  const activeIntel  = allIntel[currentIndex - 1] || allIntel[allIntel.length - 1];
  const max          = Math.max(...allIntel.map(m => m.option_premium || 0), 1);
  const totalPremium = allIntel.reduce((s, m) => s + (m.option_premium || 0), 0);
  const activeMonths = allIntel.filter(m => m.option_open).length;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <Tooltip content="Each month the system writes a covered call on 50% of the shares held. The option buyer pays a premium upfront — this is income the portfolio earns regardless of whether shares are sold. Taller bars = higher premium = more income generated. Premium rises as the stock price rises.">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider cursor-help border-b border-dashed border-slate-300">
            Covered call premium
          </span>
        </Tooltip>
        <div className="flex items-baseline gap-2">
          <Tooltip content={`This month's covered call premium: $${Math.round(activeIntel?.option_premium || 0).toLocaleString()}. The option is ${activeIntel?.option_open ? 'currently open' : 'closed'}.`}>
            <span className="text-sm font-bold text-green-600 cursor-help">
              ${Math.round(activeIntel?.option_premium || 0).toLocaleString()}/mo
            </span>
          </Tooltip>
          <Tooltip content={`Total premium collected across all ${activeMonths} months the covered call was active: $${Math.round(totalPremium).toLocaleString()}.`}>
            <span className="text-xs text-slate-400 cursor-help">
              ${(totalPremium / 1000).toFixed(0)}k total
            </span>
          </Tooltip>
        </div>
      </div>

      <div className="flex gap-0.5 items-end h-14">
        {allIntel.map((intel, i) => {
          const pct      = ((intel.option_premium || 0) / max) * 100;
          const isActive = i === currentIndex - 1;
          const tip = `Month ${intel.month}: $${Math.round(intel.option_premium || 0).toLocaleString()} premium collected. Option ${intel.option_open ? 'open' : 'closed'}.`;

          return (
            <Tooltip key={i} content={tip} position="top">
              <div
                className="flex-1 rounded-sm transition-all duration-150 cursor-default"
                style={{
                  height: `${Math.max(4, pct)}%`,
                  background: isActive ? '#16a34a' : '#86efac',
                }}
              />
            </Tooltip>
          );
        })}
      </div>

      <div className="flex justify-between text-xs text-slate-300 mt-1.5">
        <span>M1</span>
        <Tooltip content={`The covered call was active in ${activeMonths} of ${allIntel.length} months, generating $${Math.round(totalPremium).toLocaleString()} in total option income.`}>
          <span className="text-slate-400 cursor-help">
            {activeMonths} of {allIntel.length} months active
          </span>
        </Tooltip>
        <span>M{allIntel.length}</span>
      </div>
    </div>
  );
}
