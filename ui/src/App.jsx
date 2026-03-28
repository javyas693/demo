import { useState } from 'react';
import HomePage from './components/HomePage';
import HistoryTab from './components/HistoryTab';
import ProjectionTab from './components/ProjectionTab';
import { Settings } from 'lucide-react';
import StrategyTab from './components/StrategyTab';

export default function App() {
  const [activePage, setActivePage] = useState('home');
  const [showSettings, setShowSettings] = useState(false);
  const [globalError, setGlobalError] = useState(null);

  const [timeline, setTimeline] = useState(null);
  const [timelineSeries, setTimelineSeries] = useState(null);
  const [simulatedInputs, setSimulatedInputs] = useState(null);
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
    ticker: 'AAPL',
    initial_shares: 8000,
    unwind_cost_basis: 15.0,
    horizon_years: 1,
    gate_overrides: {},
  });

  const handleRunWhatIf = async (gateOverrides) => {
    setIsWhatIfRunning(true);
    setGlobalError(null);
    try {
      const payload = {
        ...(simulatedInputs || inputs),
        gate_overrides: gateOverrides,
        horizon_months: (inputs.horizon_years || 1) * 12,
      };
      const response = await fetch('http://localhost:8000/api/portfolio/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error('Simulation failed');
      const data = await response.json();
      setMonthlyIntelligenceWhatif(data.monthly_intelligence_whatif || null);
    } catch (err) {
      setGlobalError(err.message || 'Failed to run what-if simulation');
    } finally {
      setIsWhatIfRunning(false);
    }
  };

  const handleSimulationComplete = (timelineData) => {
    setTimeline(timelineData.timeline);
    setTimelineSeries(timelineData.timeline_series);
    setMonthlyIntelligence(timelineData.monthly_intelligence || []);
    setMonthlyIntelligenceWhatif(null);
    setSimulatedInputs({ ...inputs });
    // Stay on home — the login card will now render with data
  };

  const isHomePage = activePage === 'home';

  return (
    <div className="min-h-screen flex flex-col" style={isHomePage ? { background: '#181410' } : { background: '#f8fafc' }}>

      {/* Nav header — shown on History and Projections pages */}
      {!isHomePage && (
        <header className="sticky top-0 z-50 bg-white border-b border-slate-200 px-6 py-2.5 flex items-center justify-between shadow-sm">
          <button
            onClick={() => setActivePage('home')}
            className="text-sm font-semibold text-slate-500 hover:text-slate-800 transition-colors"
          >
            ← Home
          </button>
          <nav className="flex space-x-1 bg-slate-100 p-1 rounded-lg">
            <button
              onClick={() => setActivePage('history')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activePage === 'history' ? 'bg-white shadow-sm text-blue-700' : 'text-slate-600 hover:text-slate-900'}`}
            >
              History
            </button>
            <button
              onClick={() => setActivePage('projection')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activePage === 'projection' ? 'bg-white shadow-sm text-blue-700' : 'text-slate-600 hover:text-slate-900'}`}
            >
              Projections
            </button>
          </nav>
          <button
            onClick={() => setShowSettings(s => !s)}
            title="Configure inputs"
            className="text-slate-400 hover:text-slate-600 transition-colors"
          >
            <Settings className="w-5 h-5" />
          </button>
        </header>
      )}

      {/* Minimal dark nav on home page */}
      {isHomePage && timeline && (
        <header style={{ position: 'sticky', top: 0, zIndex: 50, background: 'rgba(24,20,16,0.95)', borderBottom: '1px solid #352d1f', padding: '0.625rem 1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', backdropFilter: 'blur(8px)' }}>
          <span style={{ fontFamily: "'Playfair Display', Georgia, serif", color: '#c9a84c', fontSize: '1rem', fontWeight: 700 }}>
            AI Advisory
          </span>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {['history', 'projection'].map(page => (
              <button key={page} onClick={() => setActivePage(page)} style={{ background: 'transparent', border: '1px solid #352d1f', color: '#8a7a60', borderRadius: '0.5rem', padding: '0.35rem 0.875rem', fontSize: '0.78rem', cursor: 'pointer', fontWeight: 600, textTransform: 'capitalize' }}>
                {page === 'projection' ? 'Projections' : 'History'}
              </button>
            ))}
            <button onClick={() => setShowSettings(s => !s)} style={{ background: 'transparent', border: '1px solid #352d1f', color: '#8a7a60', borderRadius: '0.5rem', padding: '0.35rem 0.5rem', fontSize: '0.78rem', cursor: 'pointer' }} title="Configure inputs">
              <Settings size={14} />
            </button>
          </div>
        </header>
      )}

      {/* Settings panel (dev access to strategy inputs) */}
      {showSettings && (
        <div className="fixed inset-0 z-[100] flex">
          <div className="absolute inset-0 bg-black/50" onClick={() => setShowSettings(false)} />
          <div className="relative ml-auto w-full max-w-xl bg-white h-full overflow-y-auto shadow-2xl">
            <div className="p-4 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-700">Strategy Configuration</h2>
              <button onClick={() => setShowSettings(false)} className="text-slate-400 hover:text-slate-600 text-sm">✕ Close</button>
            </div>
            <div className="p-4">
              <StrategyTab
                onError={setGlobalError}
                inputs={inputs}
                setInputs={setInputs}
                onSimulationComplete={(data) => { handleSimulationComplete(data); setShowSettings(false); }}
                onSimulationStart={() => setMonthlyIntelligenceWhatif(null)}
              />
            </div>
          </div>
        </div>
      )}

      {globalError && (
        <div className="bg-red-50 border-l-4 border-red-500 p-3 mx-6 mt-3 rounded text-sm text-red-700 flex justify-between">
          <span>{globalError}</span>
          <button onClick={() => setGlobalError(null)} className="ml-4 text-red-400 hover:text-red-600">✕</button>
        </div>
      )}

      <main className="flex-1">
        {activePage === 'home' && (
          <HomePage
            timeline={timeline}
            monthlyIntelligence={monthlyIntelligence}
            simulatedInputs={simulatedInputs}
            inputs={inputs}
            setInputs={setInputs}
            onSimulationComplete={handleSimulationComplete}
            onNavigate={setActivePage}
          />
        )}
        {activePage === 'history' && (
          <div className="p-6">
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
          </div>
        )}
        {activePage === 'projection' && (
          <div className="p-6">
            <ProjectionTab
              simulatedInputs={simulatedInputs}
              onError={setGlobalError}
            />
          </div>
        )}
      </main>
    </div>
  );
}
