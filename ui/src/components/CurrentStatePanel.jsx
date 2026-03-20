import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

const COLORS = ['#ef4444', '#f59e0b', '#3b82f6', '#10b981'];

export default function CurrentStatePanel({ state }) {
  if (!state) return null;
  
  const total = state.total_portfolio_value || 0;
  const concentration = state.concentration_pct || 0;
  const concentrated = state.concentrated_value || 0;
  const income = state.income_value || 0;
  const model = state.model_value || 0;
  const cash = state.cash || 0;

  const data = [
    { name: 'Concentrated', value: concentrated },
    { name: 'Income', value: income },
    { name: 'Model', value: model },
  ];

  return (
    <div className="flex-1 bg-white border border-slate-200 rounded-xl shadow-sm flex flex-col p-5 relative z-10">
      <h3 className="font-semibold text-slate-800 border-b border-slate-100 pb-2 mb-4">Starting Portfolio</h3>
      
      <div className="flex flex-col gap-4 flex-1">
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-widest">ECOSYSTEM</span>
            <p className="text-lg font-bold text-slate-800">${total.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</p>
          </div>
          <div className="bg-red-50 p-3 rounded-lg border border-red-100">
            <span className="text-xs font-semibold text-red-500 uppercase tracking-widest">CONCENTRATION</span>
            <p className="text-lg font-bold text-red-700">{concentration.toFixed(1)}%</p>
          </div>
        </div>
        
        <div className="h-48 w-full mt-2 relative">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={data} innerRadius={50} outerRadius={80} paddingAngle={2} dataKey="value">
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(val) => `$${val.toLocaleString()}`} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="space-y-2 text-sm mt-auto">
          <div className="flex justify-between items-center px-2 py-1 bg-red-50 text-red-800 rounded">
            <span>Concentrated</span>
            <span className="font-semibold">${concentrated.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span>
          </div>
          <div className="flex justify-between items-center px-2 py-1 bg-blue-50 text-blue-800 rounded">
            <span>Model Core</span>
            <span className="font-semibold">${model.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span>
          </div>
          <div className="flex justify-between items-center px-2 py-1 bg-amber-50 text-amber-800 rounded">
            <span>Income Strats</span>
            <span className="font-semibold">${income.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
