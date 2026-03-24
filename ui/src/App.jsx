import React, { useState } from 'react';
import StrategyTab from './components/StrategyTab';
import HistoryTab from './components/HistoryTab';
import ProjectionTab from './components/ProjectionTab';
import { Activity, BarChart3, TrendingUp, CheckCircle2 } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('strategy');
  const [globalError, setGlobalError] = useState(null);

  // Global timeline storage — shared between tabs
  const [timeline, setTimeline] = useState(null);
  const [timelineSeries, setTimelineSeries] = useState(null);
  const [simulatedInputs, setSimulatedInputs] = useState(null);
  // 1. Add state alongside timeline
  const [monthlyIntelligence, setMonthlyIntelligence] = useState([]);
  const [monthlyIntelligenceWhatif, setMonthlyIntelligenceWhatif] = useState(null);
  const [isWhatIfRunning, setIsWhatIfRunning] = useState(false);

  const [inputs, setInputs] = useState({
    total_portfolio_value: 1250000,
    concentrated_position_value: 1200000,
    cash: 50000,
    income_portfolio_value: 0,
    model_portfolio_value: 0,
    tlh_inventory: 250000,
    risk_score: 50,
    income_preference: 50,
    ticker: "AAPL",
    initial_shares: 8000,
    unwind_cost_basis: 15.0,
    horizon_years: 1,
    gate_overrides: {}
  });
  const handleRunWhatIf = async (gateOverrides) => {
    console.log("[DEBUG] gate_overrides being sent:", JSON.stringify(gateOverrides));
    setIsWhatIfRunning(true);
    setGlobalError(null);
    try {
      const payload = {
        ...(simulatedInputs || inputs),
        gate_overrides: gateOverrides,
        horizon_months: (inputs.horizon_years || 1) * 12
      };
      const response = await fetch('http://localhost:8000/api/portfolio/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Simulation failed`);
      }

      const data = await response.json();
      console.log("[DEBUG] What-If payload:", payload);
      console.log("[DEBUG] What-If API returned:", data.monthly_intelligence_whatif);
      setMonthlyIntelligenceWhatif(data.monthly_intelligence_whatif || null);
    } catch (err) {
      console.error(err);
      setGlobalError(err.message || 'Failed to run what-if simulation');
    } finally {
      setIsWhatIfRunning(false);
    }
  };

  // 2. Capture it in handleSimulationComplete
  const handleSimulationComplete = (timelineData) => {
    setTimeline(timelineData.timeline);
    setTimelineSeries(timelineData.timeline_series);
    setMonthlyIntelligence(timelineData.monthly_intelligence || []);
    setMonthlyIntelligenceWhatif(null);
    setSimulatedInputs({ ...inputs });
    setActiveTab('history');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="sticky top-0 z-50 bg-white border-b border-slate-200 px-6 py-2.5 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-2">
          <Activity className="text-blue-600 w-6 h-6" />
          <h1 className="text-xl font-semibold tracking-tight text-slate-800">
            AI Advisory
            <span className="text-sm font-normal text-slate-500 ml-2">Portfolio Orchestrator V1</span>
          </h1>
        </div>
        <nav className="flex space-x-1 bg-slate-100 p-1 rounded-lg">
          <button
            onClick={() => setActiveTab('strategy')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'strategy' ? 'bg-white shadow-sm text-blue-700' : 'text-slate-600 hover:text-slate-900'}`}
          >
            Strategy Input
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${activeTab === 'history' ? 'bg-white shadow-sm text-blue-700' : 'text-slate-600 hover:text-slate-900'}`}
          >
            Historical Performance
            {timeline && (
              <span className="w-2 h-2 rounded-full bg-green-500 inline-block" title="Simulation ready" />
            )}
          </button>
          <button
            onClick={() => setActiveTab('projection')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'projection' ? 'bg-white shadow-sm text-blue-700' : 'text-slate-600 hover:text-slate-900'}`}
          >
            Projections
          </button>
        </nav>
      </header>

      {globalError && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 mx-6 mt-4 rounded shadow-sm">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-red-700 font-medium">System unavailable</p>
              <p className="text-sm text-red-600 mt-1">{globalError}</p>
            </div>
            <div className="ml-auto pl-3">
              <div className="-mx-1.5 -my-1.5">
                <button
                  onClick={() => setGlobalError(null)}
                  className="inline-flex rounded-md p-1.5 text-red-500 hover:bg-red-100 focus:outline-none"
                >
                  <span className="sr-only">Dismiss</span>
                  <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <main className="flex-1 overflow-auto p-6 flex flex-col items-center">
        <div className="w-full max-w-7xl h-full flex flex-col">
          {activeTab === 'strategy' && (
            <StrategyTab
              onError={setGlobalError}
              inputs={inputs}
              setInputs={setInputs}
              onSimulationComplete={handleSimulationComplete}
              onSimulationStart={() => setMonthlyIntelligenceWhatif(null)}
            />
          )}
          {activeTab === 'history' && (
            // 3. Pass it to HistoryTab
            <HistoryTab
              onError={setGlobalError}
              timeline={timeline}
              timelineSeries={timelineSeries}
              monthlyIntelligence={monthlyIntelligence}
              monthlyIntelligenceWhatif={monthlyIntelligenceWhatif}
              inputs={simulatedInputs || inputs}
              onRunWhatIf={handleRunWhatIf}
              isWhatIfRunning={isWhatIfRunning}
              onClearWhatIf={() => setMonthlyIntelligenceWhatif(null)}
            />
          )}
          {activeTab === 'projection' && <ProjectionTab onError={setGlobalError} />}
        </div>
      </main>
    </div>
  );
}
