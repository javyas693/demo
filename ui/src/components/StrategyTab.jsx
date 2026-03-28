import React, { useState } from 'react';
import { simulatePortfolio } from '../api';
import { Settings, Play } from 'lucide-react';

export default function StrategyTab({ onError, inputs, setInputs, onSimulationComplete, onSimulationStart }) {
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setInputs(prev => ({ ...prev, [name]: value === '' ? '' : (isNaN(Number(value)) ? value : Number(value)) }));
  };

  const handleSimulate = async () => {
    if (onSimulationStart) onSimulationStart();
    setLoading(true);
    onError(null);
    const numericFields = ['initial_shares','unwind_cost_basis','cash','tlh_inventory',
      'total_portfolio_value','concentrated_position_value','income_portfolio_value','model_portfolio_value'];
    const coerced = { ...inputs };
    numericFields.forEach(k => { if (coerced[k] === '') coerced[k] = 0; });
    const { data, error } = await simulatePortfolio(coerced);
    if (error) {
      onError(error);
      setLoading(false);
      return;
    }
    onSimulationComplete(data);
    setLoading(false);
  };

  return (
    <div className="w-full max-w-xl mx-auto flex flex-col gap-6">
      
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div className="flex items-center gap-2 mb-5 border-b border-slate-100 pb-4">
          <Settings className="w-5 h-5 text-slate-500" />
          <h2 className="text-lg font-semibold text-slate-700">Strategy Configuration</h2>
        </div>

        <div className="space-y-5">

          {/* Risk + Income sliders */}
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1">Risk Score (1-100)</label>
            <div className="flex items-center gap-3">
              <input type="range" name="risk_score" min="1" max="100" value={inputs.risk_score} onChange={handleChange} className="flex-1 accent-blue-600" />
              <span className="text-sm font-bold text-slate-700 w-8 text-right">{inputs.risk_score}</span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1">Income Preference (%)</label>
            <div className="flex items-center gap-3">
              <input type="range" name="income_preference" min="0" max="100" value={inputs.income_preference} onChange={handleChange} className="flex-1 accent-blue-600" />
              <span className="text-sm font-bold text-slate-700 w-8 text-right">{inputs.income_preference}%</span>
            </div>
          </div>

          {/* Two-col grid for the rest */}
          <div className="grid grid-cols-2 gap-4 pt-3 border-t border-slate-100">
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1">Horizon</label>
              <select name="horizon_years" value={inputs.horizon_years || 1} onChange={handleChange} className="w-full rounded-lg border-slate-300 shadow-sm text-sm p-2 bg-white border">
                <option value={1}>1 Year</option>
                <option value={3}>3 Years</option>
                <option value={5}>5 Years</option>
                <option value={10}>10 Years</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1">Ticker</label>
              <input type="text" name="ticker" value={inputs.ticker} onChange={handleChange} className="w-full rounded-lg border-slate-300 shadow-sm text-sm px-3 py-2 border uppercase" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1">Shares</label>
              <input type="number" name="initial_shares" value={inputs.initial_shares} onChange={handleChange} className="w-full rounded-lg border-slate-300 shadow-sm text-sm px-3 py-2 border" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1">Cost Basis ($)</label>
              <input type="number" name="unwind_cost_basis" value={inputs.unwind_cost_basis} onChange={handleChange} className="w-full rounded-lg border-slate-300 shadow-sm text-sm px-3 py-2 border" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1">Starting Cash ($)</label>
              <input type="number" name="cash" value={inputs.cash} onChange={handleChange} className="w-full rounded-lg border-slate-300 shadow-sm text-sm px-3 py-2 border" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1">TLH Inventory ($)</label>
              <input type="number" name="tlh_inventory" value={inputs.tlh_inventory} onChange={handleChange} className="w-full rounded-lg border-slate-300 shadow-sm text-sm px-3 py-2 border" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1">Portfolio Value ($)</label>
              <input type="number" name="total_portfolio_value" value={inputs.total_portfolio_value} onChange={handleChange} className="w-full rounded-lg border-slate-300 shadow-sm text-sm px-3 py-2 border" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1">Concentrated Value ($)</label>
              <input type="number" name="concentrated_position_value" value={inputs.concentrated_position_value} onChange={handleChange} className="w-full rounded-lg border-slate-300 shadow-sm text-sm px-3 py-2 border" />
            </div>
          </div>

          <button 
            onClick={handleSimulate}
            disabled={loading}
            className="w-full mt-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-4 rounded-xl flex items-center justify-center gap-2 transition-all disabled:opacity-50 shadow-md"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                Simulating Horizon...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Run Simulation
              </>
            )}
          </button>
        </div>
      </div>

      {/* Confirmation callout after simulation */}
      {!loading && (
        <div className="text-center text-xs text-slate-400 font-medium">
          After running, switch to the <span className="text-blue-600 font-semibold">Historical Performance</span> tab to see the full playback.
        </div>
      )}

    </div>
  );
}
