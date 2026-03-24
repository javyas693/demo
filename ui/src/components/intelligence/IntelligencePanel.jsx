import React from 'react';
import Tooltip from './Tooltip';
import DecisionTimeline from './DecisionTimeline';
import SignalGaugePanel from './SignalGaugePanel';
import DecisionTracePanel2 from './DecisionTracePanel2';
import TLHChart from './TLHChart';
import OptionsChart from './OptionsChart';
import WhatIfComparisonPanel from './WhatIfComparisonPanel';

function MetricCard({ label, value, sub, valueClass, tooltip }) {
  return (
    <Tooltip content={tooltip}>
      <div className="bg-slate-50 rounded-lg p-3 border border-slate-100 cursor-help h-full">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">{label}</div>
        <div className={`text-xl font-bold text-slate-800 ${valueClass || ''}`}>{value}</div>
        <div className="text-xs text-slate-400 mt-0.5">{sub}</div>
      </div>
    </Tooltip>
  );
}

export default function IntelligencePanel({ intel, allIntel, allIntelWhatif, gateOverrides, currentIndex, onRunWhatIf, isWhatIfRunning, onClearWhatIf }) {
  if (!allIntel || allIntel.length === 0) return null;

  const tlhPeak      = Math.max(...allIntel.map(m => m.tlh_inventory_after || 0));
  const totalPremium = allIntel.reduce((s, m) => s + (m.option_premium || 0), 0);
  const sellMonths   = allIntel.filter(m => m.enable_unwind).length;
  const allClean     = allIntel.every(m => m.reconciliation_valid !== false);
  const activeMonth  = intel?.month ?? currentIndex;

  return (
    <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-5 flex flex-col gap-6">

      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-700">Decision intelligence</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            {allIntel.length}-month run · {sellMonths} sell events · use the slider above to explore each month
          </p>
        </div>
        <Tooltip content={allClean ? 'All monthly reconciliation checks passed — every portfolio value, cash flow, and TLH balance was verified to balance correctly. No accounting errors detected.' : 'One or more months failed reconciliation — check the reconciliation panel below for details.'}>
          <span className={`text-xs font-bold px-2.5 py-1 rounded-full border cursor-help ${
            allClean
              ? 'bg-green-50 text-green-700 border-green-200'
              : 'bg-red-50 text-red-700 border-red-200'
          }`}>
            {allClean ? 'Reconciliation clean' : 'Reconciliation issues'}
          </span>
        </Tooltip>
      </div>

      {/* Summary metrics */}
      <div className="grid grid-cols-4 gap-3">
        <MetricCard
          label="TLH stockpile"
          value={`$${(tlhPeak / 1000).toFixed(0)}k`}
          sub="accumulated, ready to deploy"
          tooltip="Tax-Loss Harvest (TLH) inventory accumulated from option losses over the simulation. This acts as a tax buffer — when shares are sold, gains are offset by this inventory, making the sale tax-neutral (no tax bill). The larger this number, the more capacity for future tax-neutral sells."
        />
        <MetricCard
          label="Option income"
          value={`$${(totalPremium / 1000).toFixed(0)}k`}
          sub={`${allIntel.length} consecutive months`}
          tooltip="Total covered call premium income collected across all months. Each month the system writes a covered call on 50% of held shares and collects the premium upfront. This income runs every month regardless of whether shares are sold — it's the system working for you even during hold periods."
        />
        <MetricCard
          label="Sell months"
          value={sellMonths}
          sub={`of ${allIntel.length} total months`}
          tooltip="Number of months where the system executed a tax-neutral share sale. Sales only occur when all signal gates pass (momentum not bullish, macro not risk-on, volatility acceptable) AND sufficient TLH inventory exists to offset the gains. In months without a sale, the covered call overlay generates income instead."
        />
        <MetricCard
          label="Current month"
          value={`M${activeMonth}`}
          sub={intel?.enable_unwind ? 'sell executed' : intel?.blocking_reason?.includes('MOMENTUM') ? 'momentum block' : 'macro block'}
          tooltip="The month currently selected on the slider. The signal state and decision trace below reflect this specific month's evaluation. Move the slider to explore any month in the simulation."
        />
      </div>

      {/* Decision timeline */}
      <DecisionTimeline allIntel={allIntel} currentIndex={currentIndex} />

      {/* What-If Comparison */}
      <WhatIfComparisonPanel
        monthlyIntelligence={allIntel}
        monthlyIntelligenceWhatif={allIntelWhatif}
        gateOverrides={gateOverrides}
        onRunWhatIf={onRunWhatIf}
        isRunning={isWhatIfRunning}
        onClearWhatIf={onClearWhatIf}
      />

      {/* Signals and trace side by side — items-start prevents unequal stretch when trace expands */}
      <div className="grid grid-cols-2 gap-8 items-start pt-4 border-t border-slate-100">
        <div className="min-h-[220px]">
          <SignalGaugePanel intel={intel} />
        </div>
        <div className="min-h-[220px]">
          <DecisionTracePanel2 intel={intel} />
        </div>
      </div>

      {/* TLH and options charts side by side */}
      <div className="grid grid-cols-2 gap-8 pt-2 border-t border-slate-100">
        <TLHChart allIntel={allIntel} currentIndex={currentIndex} />
        <OptionsChart allIntel={allIntel} currentIndex={currentIndex} />
      </div>

    </div>
  );
}
