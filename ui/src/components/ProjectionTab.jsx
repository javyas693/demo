<<<<<<< HEAD
import React, { useState, useCallback } from 'react';
=======
import { useState, useCallback } from 'react';
>>>>>>> main
import { runProjection } from '../api';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, BarChart, Bar, CartesianGrid, ReferenceLine,
} from 'recharts';
import { TrendingUp, ChevronDown, ChevronUp } from 'lucide-react';

// ── Formatters ─────────────────────────────────────────────────────────
const fmt = (v) => {
  if (v == null) return '—';
  if (v >= 1_000_000) return '$' + (v / 1_000_000).toFixed(1) + 'M';
  if (v >= 1_000)     return '$' + (v / 1_000).toFixed(0) + 'K';
  return '$' + Math.round(v).toLocaleString();
};
const fmtFull = (v) =>
  '$' + Math.round(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
const pct = (v) => (v == null ? '—' : v.toFixed(1) + '%');

// ── Tooltip ────────────────────────────────────────────────────────────
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-slate-200 shadow-lg rounded-xl p-3 text-sm z-50 min-w-[180px]">
      <p className="font-bold text-slate-800 mb-2 border-b border-slate-100 pb-1">{label}</p>
      <div className="space-y-1">
        {payload
<<<<<<< HEAD
          .filter(p => p.name !== 'p90 (bull)' && p.name !== 'p10 (bear)')
=======
          .filter(p => p.name !== 'Strong market' && p.name !== 'Tough market')
>>>>>>> main
          .map((p, i) => (
            <div key={i} className="flex justify-between gap-4">
              <span className="text-slate-500">{p.name}</span>
              <span className="font-semibold text-slate-800">{fmt(p.value)}</span>
            </div>
          ))}
      </div>
    </div>
  );
}

// ── Slider row ─────────────────────────────────────────────────────────
function SliderRow({ label, value, min, max, step = 1, onChange, format = v => v }) {
  return (
    <div className="flex items-center gap-3 mb-3">
      <label className="text-sm text-slate-500 w-52 shrink-0">{label}</label>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="flex-1 accent-blue-600" />
      <span className="text-sm font-semibold text-slate-700 w-14 text-right">
        {format(value)}
      </span>
    </div>
  );
}

// ── Metric card ────────────────────────────────────────────────────────
function MetricCard({ label, value, sub, accent }) {
  return (
    <div className="bg-slate-50 border border-slate-100 rounded-xl p-4">
      <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1">{label}</p>
      <p className={`text-xl font-bold ${accent || 'text-slate-800'}`}>{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  );
}

const TARGET_OPTIONS = [
  { label: 'No target', value: null },
  { label: '25%', value: 0.25 },
  { label: '20%', value: 0.20 },
  { label: '15%', value: 0.15 },
  { label: '10%', value: 0.10 },
];

export default function ProjectionTab({ simulatedInputs, onError }) {
  const [horizonYears, setHorizonYears]           = useState(20);
  const [targetConcentration, setTargetConcentration] = useState(0.15);
  const [spreadYears, setSpreadYears]             = useState(5);
  const [incomePreference, setIncomePreference]   = useState(50);
  const [cpReturn, setCpReturn]                   = useState(null);
  const [incomeReturn, setIncomeReturn]           = useState(7);
  const [modelReturn, setModelReturn]             = useState(8);
  const [taxRate, setTaxRate]                     = useState(20);
  const [showAdvanced, setShowAdvanced]           = useState(false);
  const [result, setResult]                       = useState(null);
  const [loading, setLoading]                     = useState(false);

  const cp     = simulatedInputs?.concentrated_position_value || 1_200_000;
  const shares = simulatedInputs?.initial_shares || 8_000;
  const price  = cp / shares;

  const run = useCallback(async () => {
    setLoading(true);
    setResult(null);
    const payload = {
      cp_value:                 cp,
      income_value:             simulatedInputs?.income_portfolio_value || 0,
      model_value:              simulatedInputs?.model_portfolio_value  || 0,
      cash:                     simulatedInputs?.cash || 0,
      cost_basis:               simulatedInputs?.unwind_cost_basis || 15,
      current_cp_price:         price,
      ticker:                   simulatedInputs?.ticker || 'SPY',
      horizon_years:            horizonYears,
      income_preference:        incomePreference / 100,
      target_concentration_pct: targetConcentration,
      spread_years:             spreadYears,
      return_assumptions: {
        ...(cpReturn !== null ? { cp_annual_return: cpReturn / 100 } : {}),
        income_annual_return: incomeReturn / 100,
        model_annual_return:  modelReturn  / 100,
        tax_rate:             taxRate      / 100,
      },
    };
    const res = await runProjection(payload);
    if (res.error) onError?.(res.error);
    else setResult(res.data);
    setLoading(false);
  }, [simulatedInputs, horizonYears, targetConcentration, spreadYears,
      incomePreference, cpReturn, incomeReturn, modelReturn, taxRate]);

  const chartData = result
    ? [{ year: 'Today', total: cp, cp, income: 0, model: 0, cpPct: 96 },
       ...result.annual_snapshots.map(s => ({
         year:   `Yr ${s.year}`,
         total:  s.total_p50,
         p10:    s.total_p10,
         p90:    s.total_p90,
         cp:     s.cp_p50,
         income: s.income_p50,
         model:  s.model_p50,
         cpPct:  s.cp_remaining_pct,
         tax:    s.cumulative_tax_paid_p50,
       }))]
    : [];

  const finalYear = result?.annual_snapshots?.[result.annual_snapshots.length - 1];
  const a = result?.assumptions_used;

  if (!simulatedInputs) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-4 py-24">
        <TrendingUp className="w-16 h-16 opacity-20" />
        <p className="text-lg font-medium">Run a simulation first</p>
        <p className="text-sm text-slate-400">
<<<<<<< HEAD
          Go to the <span className="text-blue-600 font-semibold">Strategy Input</span> tab
          and click Run Simulation, then return here.
=======
          Go back to <span className="text-blue-600 font-semibold">Home</span> and analyze your position first.
>>>>>>> main
        </p>
      </div>
    );
  }

  return (
    <div className="w-full flex flex-col gap-4">

      {/* ── Input panel ── */}
      <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-5">
<<<<<<< HEAD
        <h3 className="text-sm font-bold text-slate-700 mb-4">Projection inputs</h3>

        <SliderRow label="Projection horizon" value={horizonYears} min={5} max={30}
          onChange={setHorizonYears} format={v => `${v} yrs`} />
        <SliderRow label="Unwind target" value={unwindPct} min={10} max={100} step={5}
          onChange={setUnwindPct} format={v => `${v}%`} />
        <SliderRow label="Spread over" value={unwindYears} min={1}
          max={Math.min(15, horizonYears)}
          onChange={setUnwindYears} format={v => `${v} yrs`} />
        <SliderRow label="Proceeds → income" value={incomePreference} min={0} max={100}
=======
        <h3 className="text-sm font-bold text-slate-700 mb-4">Adjust your outlook</h3>

        <SliderRow label="How far ahead to model" value={horizonYears} min={5} max={30}
          onChange={setHorizonYears} format={v => `${v} yrs`} />

        {/* Target concentration pill selector */}
        <div className="flex items-center gap-3 mb-3">
          <label className="text-sm text-slate-500 w-52 shrink-0">Reduce concentration to</label>
          <div className="flex gap-2 flex-wrap">
            {TARGET_OPTIONS.map(opt => (
              <button
                key={String(opt.value)}
                onClick={() => setTargetConcentration(opt.value)}
                className={`px-3 py-1 rounded-full text-sm font-semibold border transition-colors ${
                  targetConcentration === opt.value
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-slate-600 border-slate-300 hover:border-blue-400'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {targetConcentration !== null && (
          <SliderRow label="Glide path (years to get there)" value={spreadYears} min={1}
            max={Math.min(15, horizonYears)}
            onChange={setSpreadYears} format={v => `${v} yrs`} />
        )}

        <SliderRow label="Proceeds allocated to income" value={incomePreference} min={0} max={100}
>>>>>>> main
          step={10} onChange={setIncomePreference} format={v => `${v}%`} />

        <div className="bg-blue-50 border border-blue-100 rounded-lg px-4 py-2.5
          text-sm text-blue-800 mb-4">
          {targetConcentration !== null
            ? <>Selling each year to bring concentration below{' '}
                <span className="font-bold">{(targetConcentration * 100).toFixed(0)}%</span>{' '}
                over a <span className="font-bold">{spreadYears}-year</span> glide path —{' '}
                reinvesting proceeds per your {incomePreference}% income preference.</>
            : <>No target set — position held as-is for the full {horizonYears}-year horizon.</>
          }
        </div>

        <button onClick={() => setShowAdvanced(o => !o)}
          className="flex items-center gap-1.5 text-xs font-semibold text-slate-500
            hover:text-slate-700 mb-3 transition-colors">
          {showAdvanced
            ? <ChevronUp className="w-3.5 h-3.5" />
            : <ChevronDown className="w-3.5 h-3.5" />}
<<<<<<< HEAD
          Return assumptions (advanced)
=======
          Growth rate assumptions (advanced)
>>>>>>> main
        </button>

        {showAdvanced && (
          <div className="border-t border-slate-100 pt-4 mb-4">
            <SliderRow
              label={cpReturn === null ? 'CP return (auto-fitted)' : 'CP return (override)'}
              value={cpReturn ?? 12} min={4} max={20} step={1}
              onChange={v => setCpReturn(v)} format={v => `${v}%`} />
            {cpReturn !== null && (
              <button onClick={() => setCpReturn(null)}
                className="text-xs text-blue-600 hover:underline mb-3 -mt-2 block">
                Reset to fitted value
              </button>
            )}
            <SliderRow label="Income annual return" value={incomeReturn} min={2} max={15}
              step={1} onChange={setIncomeReturn} format={v => `${v}%`} />
            <SliderRow label="Model annual return" value={modelReturn} min={2} max={15}
              step={1} onChange={setModelReturn} format={v => `${v}%`} />
            <SliderRow label="Capital gains tax" value={taxRate} min={0} max={40}
              step={1} onChange={setTaxRate} format={v => `${v}%`} />
          </div>
        )}

        <button onClick={run} disabled={loading}
          className={`flex items-center gap-2 text-sm font-semibold px-5 py-2.5
            rounded-xl shadow-md transition-colors
            ${loading
              ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700 text-white'}`}>
          <TrendingUp className="w-4 h-4" />
          {loading ? 'Running…' : 'Run projection'}
        </button>
      </div>

      {result && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
<<<<<<< HEAD
            <MetricCard label={`Year ${horizonYears} median`}
              value={fmtFull(finalYear?.total_p50)} accent="text-blue-700" />
            <MetricCard label="Bear case (p10)"
              value={fmtFull(finalYear?.total_p10)} accent="text-red-600"
              sub={`Year ${horizonYears}`} />
            <MetricCard label="Bull case (p90)"
              value={fmtFull(finalYear?.total_p90)} accent="text-emerald-600"
              sub={`Year ${horizonYears}`} />
            <MetricCard label="Tax paid (median)"
=======
            <MetricCard label={`Year ${horizonYears} expected`}
              value={fmtFull(finalYear?.total_p50)} accent="text-blue-700" />
            <MetricCard label="Tough market"
              value={fmtFull(finalYear?.total_p10)} accent="text-red-600"
              sub={`Year ${horizonYears}`} />
            <MetricCard label="Strong market"
              value={fmtFull(finalYear?.total_p90)} accent="text-emerald-600"
              sub={`Year ${horizonYears}`} />
            <MetricCard label="Tax paid (expected)"
>>>>>>> main
              value={fmtFull(finalYear?.cumulative_tax_paid_p50)} accent="text-amber-700" />
          </div>

          {/* Assumptions strip */}
          {a && (
            <div className="bg-slate-50 border border-slate-100 rounded-xl px-4 py-2.5
              flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
              <span>
<<<<<<< HEAD
                <span className="font-semibold text-slate-700">
                  {simulatedInputs?.ticker}
                </span>{' '}
                CP: {(a.cp_annual_return * 100).toFixed(1)}% return /
                {(a.cp_annual_vol * 100).toFixed(1)}% vol{' '}
                <span className="text-slate-400">({a.cp_assumptions_source})</span>
              </span>
              <span>Income:{' '}
                <span className="font-semibold text-slate-700">
                  {(a.income_annual_return * 100).toFixed(1)}%
                </span>
              </span>
              <span>Model:{' '}
                <span className="font-semibold text-slate-700">
                  {(a.model_annual_return * 100).toFixed(1)}%
                </span>
              </span>
              <span>Tax:{' '}
                <span className="font-semibold text-slate-700">
                  {(a.tax_rate * 100).toFixed(0)}%
                </span>
              </span>
              <span>Paths:{' '}
                <span className="font-semibold text-slate-700">
                  {result.simulations_run.toLocaleString()}
                </span>
=======
                <span className="font-semibold text-slate-700">{simulatedInputs?.ticker}</span>{' '}
                {(a.cp_annual_return * 100).toFixed(1)}% annual return · {(a.cp_annual_vol * 100).toFixed(1)}% volatility{' '}
                <span className="text-slate-400">({a.cp_assumptions_source})</span>
              </span>
              <span>Income strategy:{' '}
                <span className="font-semibold text-slate-700">{(a.income_annual_return * 100).toFixed(1)}%/yr</span>
              </span>
              <span>Diversified holdings:{' '}
                <span className="font-semibold text-slate-700">{(a.model_annual_return * 100).toFixed(1)}%/yr</span>
              </span>
              <span>Capital gains tax:{' '}
                <span className="font-semibold text-slate-700">{(a.tax_rate * 100).toFixed(0)}%</span>
              </span>
              <span>Simulations run:{' '}
                <span className="font-semibold text-slate-700">{result.simulations_run.toLocaleString()}</span>
>>>>>>> main
              </span>
            </div>
          )}

          {/* Total portfolio fan chart */}
          <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4">
            <h3 className="text-sm font-bold text-slate-700 mb-1">
<<<<<<< HEAD
              Total portfolio — percentile fan
            </h3>
            <p className="text-xs text-slate-400 mb-3">
              Shaded region = 10th–90th percentile spread across 1,000 paths
            </p>
            <div className="flex flex-wrap gap-4 mb-3 text-xs text-slate-500">
              {[
                { cls: 'bg-blue-600',   label: 'Total p50' },
                { cls: 'bg-teal-600',   label: 'CP p50' },
                { cls: 'bg-amber-500',  label: 'Income p50' },
                { cls: 'bg-violet-500', label: 'Model p50' },
=======
              Total portfolio value over time
            </h3>
            <p className="text-xs text-slate-400 mb-3">
              Shaded band = range across 1,000 simulated market scenarios
            </p>
            <div className="flex flex-wrap gap-4 mb-3 text-xs text-slate-500">
              {[
                { cls: 'bg-blue-600',   label: 'Expected path' },
                { cls: 'bg-teal-600',   label: 'Concentrated position' },
                { cls: 'bg-amber-500',  label: 'Income strategy' },
                { cls: 'bg-violet-500', label: 'Diversified holdings' },
>>>>>>> main
              ].map(l => (
                <span key={l.label} className="flex items-center gap-1.5">
                  <span className={`w-2.5 h-2.5 rounded-sm ${l.cls}`} />
                  {l.label}
                </span>
              ))}
            </div>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}
                  margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="year" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                  <YAxis tickFormatter={fmt} tick={{ fontSize: 11, fill: '#94a3b8' }}
                    width={62} />
                  <Tooltip content={<CustomTooltip />} />
                  <Line dataKey="p90" stroke="rgba(37,99,235,0.15)" strokeWidth={1}
<<<<<<< HEAD
                    dot={false} name="p90 (bull)" />
                  <Line dataKey="p10" stroke="rgba(37,99,235,0.15)" strokeWidth={1}
                    dot={false} name="p10 (bear)" />
                  <Line dataKey="total" stroke="#2563eb" strokeWidth={2.5}
                    dot={false} name="Total p50" />
                  <Line dataKey="cp" stroke="#0f766e" strokeWidth={1.5}
                    dot={false} strokeDasharray="4 3" name="CP p50" />
                  <Line dataKey="income" stroke="#d97706" strokeWidth={1.5}
                    dot={false} name="Income p50" />
                  <Line dataKey="model" stroke="#7c3aed" strokeWidth={1.5}
                    dot={false} name="Model p50" />
=======
                    dot={false} name="Strong market" />
                  <Line dataKey="p10" stroke="rgba(37,99,235,0.15)" strokeWidth={1}
                    dot={false} name="Tough market" />
                  <Line dataKey="total" stroke="#2563eb" strokeWidth={2.5}
                    dot={false} name="Expected path" />
                  <Line dataKey="cp" stroke="#0f766e" strokeWidth={1.5}
                    dot={false} strokeDasharray="4 3" name="Concentrated position" />
                  <Line dataKey="income" stroke="#d97706" strokeWidth={1.5}
                    dot={false} name="Income strategy" />
                  <Line dataKey="model" stroke="#7c3aed" strokeWidth={1.5}
                    dot={false} name="Diversified holdings" />
>>>>>>> main
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Sleeve breakdown + concentration */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4">
              <h3 className="text-sm font-bold text-slate-700 mb-4">
<<<<<<< HEAD
                Sleeve breakdown — median
=======
                Where your wealth sits — expected path
>>>>>>> main
              </h3>
              <div className="h-56 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData.slice(1)}
                    margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="year" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                    <YAxis tickFormatter={fmt} tick={{ fontSize: 10, fill: '#94a3b8' }}
                      width={56} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="cp"     stackId="a" fill="#5eead4" name="CP" />
                    <Bar dataKey="income" stackId="a" fill="#fbbf24" name="Income" />
                    <Bar dataKey="model"  stackId="a" fill="#a78bfa" name="Model"
                      radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4">
              <h3 className="text-sm font-bold text-slate-700 mb-1">
<<<<<<< HEAD
                CP concentration over time
              </h3>
              <p className="text-xs text-slate-400 mb-4">
                Dashed line = 15% diversification target
=======
                Concentration reducing over time
              </h3>
              <p className="text-xs text-slate-400 mb-4">
                Dashed line = 15% target
>>>>>>> main
              </p>
              <div className="h-56 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData}
                    margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="year" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                    <YAxis domain={[0, 100]} tickFormatter={v => v + '%'}
                      tick={{ fontSize: 10, fill: '#94a3b8' }} width={40} />
                    <Tooltip formatter={v => v != null ? v.toFixed(1) + '%' : '—'} />
                    <ReferenceLine y={15} stroke="#ef4444" strokeDasharray="4 2"
                      label={{ value: '15% target', fontSize: 10,
                        fill: '#ef4444', position: 'insideRight' }} />
                    <Area dataKey="cpPct" stroke="#f97316" fill="rgba(249,115,22,0.08)"
                      strokeWidth={2} dot={false} name="CP %" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Annual table */}
          <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4">
<<<<<<< HEAD
            <h3 className="text-sm font-bold text-slate-700 mb-4">Annual snapshot</h3>
=======
            <h3 className="text-sm font-bold text-slate-700 mb-4">Year by year breakdown</h3>
>>>>>>> main
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-100">
<<<<<<< HEAD
                    {['Year','Bear (p10)','Median','Bull (p90)',
                      'CP','Income','Model','CP %','Tax paid'].map(h => (
=======
                    {['Year','Tough market','Expected','Strong market',
                      'Your position','Income','Diversified','Concentration','Tax paid'].map(h => (
>>>>>>> main
                      <th key={h} className="px-3 py-2 text-right font-bold text-slate-400
                        uppercase tracking-widest whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.annual_snapshots.map((s, i) => (
                    <tr key={s.year}
                      className={`border-b border-slate-50
                        ${i % 2 === 1 ? 'bg-slate-50' : ''}`}>
                      <td className="px-3 py-2 text-right font-bold text-slate-700">
                        {s.year}
                      </td>
                      <td className="px-3 py-2 text-right text-red-600 font-semibold">
                        {fmt(s.total_p10)}</td>
                      <td className="px-3 py-2 text-right text-blue-700 font-semibold">
                        {fmt(s.total_p50)}</td>
                      <td className="px-3 py-2 text-right text-emerald-600 font-semibold">
                        {fmt(s.total_p90)}</td>
                      <td className="px-3 py-2 text-right text-slate-600">
                        {fmt(s.cp_p50)}</td>
                      <td className="px-3 py-2 text-right text-amber-700">
                        {fmt(s.income_p50)}</td>
                      <td className="px-3 py-2 text-right text-violet-600">
                        {fmt(s.model_p50)}</td>
                      <td className={`px-3 py-2 text-right font-bold
                        ${s.cp_remaining_pct > 50
                          ? 'text-red-500' : 'text-emerald-600'}`}>
                        {pct(s.cp_remaining_pct)}
                      </td>
                      <td className="px-3 py-2 text-right text-slate-400">
                        {fmt(s.cumulative_tax_paid_p50)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
