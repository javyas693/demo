import React from 'react';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Legend
} from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-white border border-slate-200 shadow-lg rounded-xl p-3 text-sm z-50 min-w-[200px]">
        <p className="font-bold text-slate-800 mb-2 border-b border-slate-100 pb-1">Month {data.month}</p>
        <div className="space-y-1">
          <p className="font-semibold text-slate-700">Total: ${Math.round(data.total_portfolio_value).toLocaleString()}</p>
          {data.benchmark_value != null && (
            <p className="text-slate-400 text-xs">SPY Benchmark: ${Math.round(data.benchmark_value).toLocaleString()}</p>
          )}
          <div className="pt-2 border-t border-slate-100 mt-2">
            <p className="text-xs font-bold text-slate-400 uppercase mb-1">Concentrated Position</p>
            <div className="bg-slate-50 p-1.5 rounded text-xs space-y-0.5 border border-slate-100">
              <p className="flex justify-between"><span className="text-slate-500">Shares held:</span> <span className="font-mono">{data.shares.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span></p>
              <p className="flex justify-between"><span className="text-slate-500">Price used:</span> <span className="font-mono">${data.cp_price.toFixed(2)}</span></p>
              <p className="flex justify-between font-bold text-amber-700 mt-1 pt-1 border-t border-slate-200"><span className="text-amber-800">Computed value:</span> <span>${Math.round(data.concentrated_value).toLocaleString()}</span></p>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-100 mt-2">
            <p className="text-xs font-bold text-slate-400 uppercase">Other Holdings</p>
            <p className="flex justify-between text-sky-700"><span className="text-sky-600">Income:</span> <span>${Math.round(data.income_value).toLocaleString()}</span></p>
            <p className="flex justify-between text-blue-700"><span className="text-blue-600">Model:</span> <span>${Math.round(data.model_value).toLocaleString()}</span></p>
            <p className="flex justify-between text-slate-600"><span className="text-slate-500">Cash:</span> <span>${Math.round(data.cash).toLocaleString()}</span></p>
          </div>
          <div className="pt-2 border-t border-slate-100 mt-2">
            <p className="text-xs font-bold text-slate-400 uppercase">This Step Generated</p>
            <p className="text-emerald-600">Income Gen: +${Math.round(data.income_generated_this_step).toLocaleString()}</p>
            <p className="text-indigo-600">Model Growth: +${Math.round(data.model_growth_this_step).toLocaleString()}</p>
          </div>
        </div>
      </div>
    );
  }
  return null;
};

export default function SimulationCharts({ timeline, timelineSeries, currentIndex }) {
  if (!timeline || timeline.length === 0) return null;

  // The playback sync uses currentIndex. We read the corresponding month from timeline.
  const currentMonth = timeline[currentIndex]?.month;

  return (
    <div className="w-full flex justify-center py-4">
      <div className="w-full grid grid-cols-1 xl:grid-cols-2 gap-4">

        {/* Module 1: Total Portfolio Line */}
        <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4 flex flex-col items-center">
          <h3 className="text-sm font-bold text-slate-700 mb-4 w-full text-center">Total Portfolio Value</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeline} margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(val) => `$${(val / 1000)}k`} />
                <Tooltip content={<CustomTooltip />} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '11px' }} verticalAlign="top" align="right" />
                <ReferenceLine x={currentMonth} stroke="#3b82f6" strokeDasharray="3 3" />
                <Line type="monotone" dataKey="total_portfolio_value" name="Portfolio" stroke="#2563eb" strokeWidth={2} dot={false} activeDot={{ r: 6 }} />
                <Line type="monotone" dataKey="benchmark_value" name="SPY Benchmark" stroke="#94a3b8" strokeWidth={1.5} strokeDasharray="5 4" dot={false} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Module 2: Strategy Breakdown (Stacked Area) */}
        <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4 flex flex-col items-center">
          <h3 className="text-sm font-bold text-slate-700 mb-4 w-full text-center">Portfolio Composition</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timeline} margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(val) => `$${(val / 1000)}k`} />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine x={currentMonth} stroke="#3b82f6" strokeDasharray="3 3" />
                <Area type="monotone" dataKey="cash" stackId="1" stroke="#94a3b8" fill="#cbd5e1" />
                <Area type="monotone" dataKey="model_value" stackId="1" stroke="#3b82f6" fill="#93c5fd" />
                <Area type="monotone" dataKey="income_value" stackId="1" stroke="#0ea5e9" fill="#7dd3fc" />
                <Area type="monotone" dataKey="concentrated_value" stackId="1" stroke="#f59e0b" fill="#fcd34d" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Module 3: Value Creation Chart (Multi-line) */}
        <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4 flex flex-col items-center">
          <h3 className="text-sm font-bold text-slate-700 mb-4 w-full text-center">Value Creation (Cumulative)</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeline} margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(val) => `$${(val / 1000).toFixed(1)}k`} />
                <Tooltip content={<CustomTooltip />} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
                <ReferenceLine x={currentMonth} stroke="#3b82f6" strokeDasharray="3 3" />
                <Line type="monotone" name="Income Gen" dataKey="cumulative_income_generated" stroke="#10b981" strokeWidth={2} dot={false} />
                <Line type="monotone" name="Model Growth" dataKey="model_growth_to_date" stroke="#6366f1" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Module 4: Monthly Attribution (Grouped Bar) */}
        <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4 flex flex-col items-center">
          <h3 className="text-sm font-bold text-slate-700 mb-4 w-full text-center">Monthly Attribution</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={timeline} margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(val) => `$${Math.round(val)}`} />
                <Tooltip content={<CustomTooltip />} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
                <ReferenceLine x={currentMonth} stroke="#3b82f6" strokeDasharray="3 3" />
                <Bar name="Income Gen This Step" dataKey="income_generated_this_step" fill="#10b981" radius={[2, 2, 0, 0]} />
                <Bar name="Model Growth This Step" dataKey="model_growth_this_step" fill="#6366f1" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>
    </div>
  );
}
