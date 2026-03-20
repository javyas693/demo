import React from 'react';
import { Briefcase } from 'lucide-react';

export default function HoldingsPanel({ frame }) {
  if (!frame || !frame.strategies) return null;

  const incomeHoldings = frame.strategies.income?.holdings || {};
  const modelHoldings = frame.strategies.model?.holdings || {};

  const renderHoldingsTable = (holdings, title, accentColor) => {
    const symbols = Object.keys(holdings);
    if (symbols.length === 0) return null;

    return (
      <div className="flex-1">
        <h4 className={`text-xs font-bold uppercase mb-2 ${accentColor}`}>{title}</h4>
        <div className="bg-slate-50 border border-slate-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-slate-500 bg-slate-100 uppercase border-b border-slate-200">
              <tr>
                <th className="px-3 py-2">Symbol</th>
                <th className="px-3 py-2 text-right">Shares</th>
              </tr>
            </thead>
            <tbody>
              {symbols.map((symbol, idx) => (
                <tr key={symbol} className="border-b border-slate-100 last:border-0">
                  <td className="px-3 py-2 font-medium text-slate-700">{symbol}</td>
                  <td className="px-3 py-2 text-right font-mono text-slate-600">
                    {holdings[symbol].toLocaleString(undefined, { maximumFractionDigits: 3 })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <div className="w-full mt-4 bg-white border border-slate-200 rounded-xl p-5 shadow-sm shrink-0">
      <div className="flex items-center gap-2 mb-4">
        <Briefcase className="w-4 h-4 text-slate-500" />
        <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest">Holdings per Timestep</h3>
      </div>
      <div className="flex flex-col md:flex-row gap-6">
        {renderHoldingsTable(incomeHoldings, "Income Strategy Holdings", "text-amber-600")}
        {renderHoldingsTable(modelHoldings, "Model Portfolio Holdings", "text-blue-600")}
      </div>
    </div>
  );
}
