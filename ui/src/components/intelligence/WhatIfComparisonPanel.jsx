import React, { useState } from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

const GATES = [
  'MOMENTUM_GATE',
  'MACRO_GATE',
  'VOLATILITY_GATE',
  'PRICE_TRIGGER_GATE',
  'CONCENTRATION_GATE',
  'TLH_CAPACITY_GATE',
  'UNREALIZED_GAIN_GATE'
];

export default function WhatIfComparisonPanel({
  monthlyIntelligence,
  monthlyIntelligenceWhatif,
  onRunWhatIf,
  isRunning,
  onClearWhatIf
}) {
  const [toggles, setToggles] = useState({});

  const handleToggle = (gate) => {
    setToggles(prev => ({
      ...prev,
      [gate]: !prev[gate]
    }));
    if (onClearWhatIf) onClearWhatIf();
  };

  const handleRun = () => {
    if (onRunWhatIf) {
      const overrides = {};
      Object.keys(toggles).forEach(k => {
        if (toggles[k]) overrides[k] = 'suppress';
      });
      onRunWhatIf(overrides);
    }
  };

  const anyTogglesOn = Object.values(toggles).some(v => v);

  // Phase 6 polish — Blocking Gate Summary badges
  const blockingCounts = {};
  (monthlyIntelligence || []).forEach(m => {
    if (!m.blocking_reason) return;
    const match = m.blocking_reason.match(/(\w+_GATE)/);
    if (match) {
      const gate = match[1];
      blockingCounts[gate] = (blockingCounts[gate] || 0) + 1;
    }
  });
  const blockingBadges = Object.entries(blockingCounts)
    .sort((a, b) => b[1] - a[1]);  // most blocking first

  // Process data for charts
  const chartData = [];
  const len = Math.max(monthlyIntelligence?.length || 0, monthlyIntelligenceWhatif?.length || 0);

  for (let i = 0; i < len; i++) {
    const baseM = monthlyIntelligence?.[i];
    const wiM = monthlyIntelligenceWhatif?.[i];

    const dataPoint = {
      month: i + 1,
    };
    if (baseM) dataPoint.Baseline = baseM.total_portfolio_value || 0;
    if (wiM) dataPoint['What-If'] = wiM.total_portfolio_value || 0;
    if (baseM?.benchmark_value != null) dataPoint['SPY Benchmark'] = baseM.benchmark_value;

    chartData.push(dataPoint);
  }

  const formatYAxis = (val) => {
    if (val === 0) return '$0';
    if (Math.abs(val) >= 1000000) return `$${(val / 1000000).toFixed(1)}m`;
    if (Math.abs(val) >= 1000) return `$${(val / 1000).toFixed(0)}k`;
    return `$${val}`;
  };

  // Metrics calculation
  const calcMetrics = (data) => {
    if (!data || data.length === 0) return { shares: 0, conc: 0, tlh: 0, cash: 0 };
    const shares = data.reduce((sum, m) => sum + (m.shares_to_sell || 0), 0);
    // concentration_pct is already on 0-100 scale from backend
    const conc = data[data.length - 1].concentration_pct || 0;
    // TLH: net change in inventory from start to end (positive = bank grew)
    const tlh = (data[data.length - 1].tlh_inventory_after || 0) - (data[0].tlh_inventory_before || 0);
    // Cash: sum only positive cash_delta (proceeds from selling shares, not initial deployment)
    const cash = data.reduce((sum, m) => sum + Math.max(0, m.cash_delta || 0), 0);
    return { shares, conc, tlh, cash };
  };

  const baseMetrics = calcMetrics(monthlyIntelligence);
  const wiMetrics = monthlyIntelligenceWhatif ? calcMetrics(monthlyIntelligenceWhatif) : null;

  const MetricCard = ({ title, baseValue, wiValue, isBetterFunc, formatter }) => {
    let colorClass = 'text-slate-800';
    if (wiValue !== null && wiValue !== undefined) {
      const isBetter = isBetterFunc(baseValue, wiValue);
      if (isBetter === true) colorClass = 'text-green-600';
      else if (isBetter === false) colorClass = 'text-red-500';
    }

    return (
      <div className="flex-1 bg-slate-50 border border-slate-100 p-4 rounded-lg flex flex-col items-center justify-center text-center">
        <div className="text-[10px] text-slate-500 font-bold mb-2 uppercase tracking-wider h-6 flex items-end">{title}</div>
        <div className="flex items-center gap-2">
          <div className="text-lg font-bold text-slate-500">{formatter(baseValue)}</div>
          {wiValue !== null && wiValue !== undefined && (
            <>
              <div className="text-slate-300">→</div>
              <div className={`text-lg font-bold ${colorClass}`}>{formatter(wiValue)}</div>
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-6 flex flex-col gap-6 mt-2">
      <div className="border-b border-slate-100 pb-4 flex justify-between items-end">
        <div>
          <h2 className="text-sm font-bold text-slate-800 uppercase tracking-widest mb-1">What-If Comparison</h2>
          <p className="text-xs text-slate-500">Override gates and run a parallel simulation</p>
        </div>
      </div>

      {/* Blocking Gate Summary badges */}
      {blockingBadges.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Blockers</span>
          {blockingBadges.map(([gate, count]) => {
            const label = gate.replace('_GATE', '');
            const isOn = !!toggles[gate];
            return (
              <button
                key={gate}
                onClick={() => handleToggle(gate)}
                className={`px-2.5 py-1 rounded-full text-[11px] font-bold transition-colors border ${isOn
                    ? 'bg-amber-500 text-white border-amber-500'
                    : 'bg-slate-100 text-slate-600 border-slate-200 hover:border-amber-400 hover:text-amber-600'
                  }`}
              >
                {label} {count}mo
              </button>
            );
          })}
          <span className="text-[10px] text-slate-400 italic ml-1">Click to suppress</span>
        </div>
      )}

      {/* Section 1: Gate Toggles */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-4 flex-1">
          {GATES.map(gate => {
            const label = gate.replace('_GATE', '');
            const isOn = !!toggles[gate];
            return (
              <div key={gate} className="flex flex-col items-center gap-2">
                <button
                  onClick={() => handleToggle(gate)}
                  className={`w-9 h-5 rounded-full relative transition-colors ${isOn ? 'bg-amber-500' : 'bg-slate-200'}`}
                >
                  <div className={`w-3.5 h-3.5 bg-white rounded-full absolute top-0.5 transition-transform ${isOn ? 'translate-x-[18px]' : 'translate-x-1'}`} />
                </button>
                <span className="text-[9px] font-bold text-slate-500">{label}</span>
              </div>
            );
          })}
        </div>
        <button
          onClick={handleRun}
          disabled={!anyTogglesOn || isRunning}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors flex items-center gap-2 ${!anyTogglesOn || isRunning
            ? 'bg-slate-100 text-slate-400 cursor-not-allowed opacity-50'
            : 'bg-amber-500 hover:bg-amber-600 text-white shadow-sm'
            }`}
        >
          {isRunning ? (
            <><div className="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" /> Running...</>
          ) : 'Run Comparison'}
        </button>
      </div>
      <div className="text-[10px] text-slate-400 italic">CLIENT_CONSTRAINT is never overridable.</div>

      {/* Section 2: Performance Chart */}
      <div className="h-[220px] w-full mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 5, right: 5, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
            <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
            <YAxis domain={['auto', 'auto']} tickFormatter={formatYAxis} tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
            <Tooltip
              formatter={(value) => `$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
              labelFormatter={(label) => `Month ${label}`}
              contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
            />
            <Legend verticalAlign="top" align="right" iconType="circle" wrapperStyle={{ fontSize: '11px', fontWeight: 'bold' }} />
            <Line type="monotone" dataKey="Baseline" stroke="#6b7280" strokeWidth={2} dot={false} />
            {monthlyIntelligenceWhatif && (
              <Line type="monotone" dataKey="What-If" stroke="#f59e0b" strokeWidth={2} dot={false} />
            )}
            <Line type="monotone" dataKey="SPY Benchmark" stroke="#94a3b8" strokeWidth={1.5} strokeDasharray="5 4" dot={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Section 3: Four Scorecard Metrics */}
      <div className="flex gap-4 w-full mt-2">
        <MetricCard
          title="Total Shares Sold"
          baseValue={baseMetrics.shares}
          wiValue={wiMetrics?.shares}
          isBetterFunc={(b, w) => w > b ? true : w < b ? false : null}
          formatter={(v) => v.toLocaleString()}
        />
        <MetricCard
          title="Final Concentration"
          baseValue={baseMetrics.conc}
          wiValue={wiMetrics?.conc}
          isBetterFunc={(b, w) => w < b ? true : w > b ? false : null}
          // FIX: concentration_pct is already on 0-100 scale, no * 100 needed
          formatter={(v) => `${v.toFixed(1)}%`}
        />
        <MetricCard
          title="TLH Harvested"
          baseValue={baseMetrics.tlh}
          wiValue={wiMetrics?.tlh}
          isBetterFunc={(b, w) => w > b ? true : w < b ? false : null}
          formatter={(v) => formatYAxis(v)}
        />
        <MetricCard
          title="Cash from Sales"
          baseValue={baseMetrics.cash}
          wiValue={wiMetrics?.cash}
          isBetterFunc={(b, w) => w > b ? true : w < b ? false : null}
          formatter={(v) => formatYAxis(v)}
        />
      </div>
    </div>
  );
}
