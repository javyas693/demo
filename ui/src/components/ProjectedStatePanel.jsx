import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

const COLORS = ['#ef4444', '#f59e0b', '#3b82f6'];

export default function ProjectedStatePanel({ state, initialState }) {
  if (!state) return null;

  // TASK 4: strict flat fields only
  const total = state.total_portfolio_value || 0;
  const concentration = state.concentration_pct || 0;
  const concentrated = state.concentrated_value || 0;
  const income = state.income_value || 0;
  const model = state.model_value || 0;

  // TASK 6: change from start
  const baseConcentrated = initialState?.concentrated_value || 0;
  const baseIncome = initialState?.income_value || 0;
  const baseModel = initialState?.model_value || 0;

  const deltaConcentrated = concentrated - baseConcentrated;
  const deltaIncome = income - baseIncome;
  const deltaModel = model - baseModel;

  // TASK 5: Normalize pie chart to proportions of total
  const data = [
    { name: 'Concentrated', value: total > 0 ? concentrated / total : 0 },
    { name: 'Income', value: total > 0 ? income / total : 0 },
    { name: 'Model', value: total > 0 ? model / total : 0 },
  ].filter(d => d.value > 0);

  const concentrationDelta = (concentration - (initialState?.concentration_pct || 0)).toFixed(1);

  return (
    <div className="flex-1 bg-white border border-blue-200 rounded-xl shadow-md ring-1 ring-blue-50 flex flex-col p-5 relative z-10">
      <h3 className="font-semibold text-blue-900 border-b border-blue-100 pb-2 mb-4">Current Portfolio</h3>
      
      <div className="flex flex-col gap-4 flex-1">
        {/* Top KPIs */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-widest">ECOSYSTEM</span>
            <p className="text-lg font-bold text-slate-800">${total.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</p>
          </div>
          <div className="bg-blue-50 p-3 rounded-lg border border-blue-100">
            <span className="text-xs font-semibold text-blue-600 uppercase tracking-widest">CONCENTRATION</span>
            <div className="flex items-center gap-2">
               <p className="text-lg font-bold text-blue-800">{concentration.toFixed(1)}%</p>
               <span className={`text-xs font-bold ${Number(concentrationDelta) > 0 ? 'text-red-500 bg-red-50' : 'text-green-600 bg-green-100'} px-1.5 py-0.5 rounded-full`}>
                 {Number(concentrationDelta) > 0 ? '+' : ''}{concentrationDelta}%
               </span>
            </div>
          </div>
        </div>
        
        {/* TASK 5: Normalized pie chart */}
        <div className="h-48 w-full mt-2 relative">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={data} innerRadius={50} outerRadius={80} paddingAngle={2} dataKey="value">
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(val) => `${(val * 100).toFixed(1)}%`} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* TASK 4: Strict flat field values */}
        <div className="space-y-2 text-sm mt-auto">
          <div className="flex justify-between items-center px-2 py-1 bg-red-50 text-red-800 rounded">
            <span>Concentrated</span>
            <span className="font-semibold">${concentrated.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span>
          </div>
          <div className="flex justify-between items-center px-2 py-1 bg-blue-50 text-blue-800 rounded">
            <span>Model Core</span>
            <span className="font-semibold text-green-600">${model.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span>
          </div>
          <div className="flex justify-between items-center px-2 py-1 bg-amber-50 text-amber-800 rounded">
            <span>Income Strats</span>
            <span className="font-semibold text-green-600">${income.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span>
          </div>
        </div>

        {/* TASK 6: Change from start deltas */}
        <div className="border-t border-slate-100 pt-3 mt-1">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Change From Start</p>
          <div className="space-y-1 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-500">Concentrated</span>
              <span className={`font-semibold ${deltaConcentrated <= 0 ? 'text-green-600' : 'text-red-500'}`}>
                {deltaConcentrated >= 0 ? '+' : ''}${deltaConcentrated.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Income</span>
              <span className={`font-semibold ${deltaIncome >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                {deltaIncome >= 0 ? '+' : ''}${deltaIncome.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Model</span>
              <span className={`font-semibold ${deltaModel >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                {deltaModel >= 0 ? '+' : ''}${deltaModel.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
