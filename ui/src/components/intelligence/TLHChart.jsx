import React from 'react';
import Tooltip from './Tooltip';

export default function TLHChart({ allIntel, currentIndex }) {
  if (!allIntel || allIntel.length === 0) return null;

  const activeIntel = allIntel[currentIndex - 1] || allIntel[allIntel.length - 1];
  const max = Math.max(...allIntel.map(m => m.tlh_inventory_after || 0), 1);
  const totalDelta = allIntel.reduce((s, m) => s + (m.tlh_delta_this_step || 0), 0);

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <Tooltip content="Tax-Loss Harvest (TLH) inventory is built up from option losses each month. It acts as a tax buffer — when shares are sold at a gain, the system uses this inventory to offset the tax bill, making the sale tax-neutral. The taller the bar, the more tax buffer has accumulated.">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider cursor-help border-b border-dashed border-slate-300">
            TLH inventory build
          </span>
        </Tooltip>
        <div className="flex items-baseline gap-2">
          <Tooltip content={`Current TLH inventory: $${Math.round(activeIntel?.tlh_inventory_after || 0).toLocaleString()}. This month generated $${Math.round(activeIntel?.tlh_delta_this_step || 0).toLocaleString()} in new TLH from option losses.`}>
            <span className="text-sm font-bold text-blue-600 cursor-help">
              ${((activeIntel?.tlh_inventory_after || 0) / 1000).toFixed(0)}k
            </span>
          </Tooltip>
          {(activeIntel?.tlh_delta_this_step || 0) > 0 && (
            <span className="text-xs text-green-500 font-medium">
              +${((activeIntel.tlh_delta_this_step) / 1000).toFixed(0)}k this month
            </span>
          )}
        </div>
      </div>

      <div className="flex gap-0.5 items-end h-14">
        {allIntel.map((intel, i) => {
          const pct      = ((intel.tlh_inventory_after || 0) / max) * 100;
          const isActive = i === currentIndex - 1;
          const hasDelta = (intel.tlh_delta_this_step || 0) > 0;
          const tip = `Month ${intel.month}: $${Math.round(intel.tlh_inventory_after || 0).toLocaleString()} total buffer${hasDelta ? ` (+$${Math.round(intel.tlh_delta_this_step).toLocaleString()} generated from option losses this month)` : ' (no new TLH generated this month)'}`;

          return (
            <Tooltip key={i} content={tip} position="top">
              <div
                className="flex-1 rounded-sm transition-all duration-150 cursor-default"
                style={{
                  height: `${Math.max(4, pct)}%`,
                  background: isActive
                    ? '#2563eb'
                    : hasDelta
                      ? '#93c5fd'
                      : '#e2e8f0',
                }}
              />
            </Tooltip>
          );
        })}
      </div>

      <div className="flex justify-between text-xs text-slate-300 mt-1.5">
        <span>M1</span>
        <Tooltip content={`Total TLH generated across all months: $${Math.round(totalDelta).toLocaleString()}. Peak inventory: $${Math.round(max).toLocaleString()}.`}>
          <span className="text-slate-400 cursor-help">
            ${(max / 1000).toFixed(0)}k peak
          </span>
        </Tooltip>
        <span>M{allIntel.length}</span>
      </div>
    </div>
  );
}
