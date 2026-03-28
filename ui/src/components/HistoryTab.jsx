import { useState, useEffect, useRef } from 'react';
import { Pause, RefreshCcw, BarChart3 } from 'lucide-react';
import CurrentStatePanel from './CurrentStatePanel';
import TransformationPanel from './TransformationPanel';
import ProjectedStatePanel from './ProjectedStatePanel';
import DecisionTracePanel from './DecisionTracePanel';
import StrategyAttributionPanel from './StrategyAttributionPanel';
import ReconciliationPanel from './ReconciliationPanel';
import HoldingsPanel from './HoldingsPanel';
import SimulationCharts from './SimulationCharts';
import IntelligencePanel from './intelligence/IntelligencePanel';

const SECTIONS = [
  { id: 'performance',  label: 'Performance' },
  { id: 'month',        label: 'Month by Month' },
  { id: 'tax-income',   label: 'Tax & Income' },
  { id: 'deep-dive',    label: 'Deep Dive' },
];

export default function HistoryTab({ timeline, timelineSeries, monthlyIntelligence, monthlyIntelligenceWhatif, inputs, onRunWhatIf, isWhatIfRunning, onClearWhatIf }) {
  const [isPlaying, setIsPlaying]     = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [speed, setSpeed]             = useState(1);
  const [activeSection, setActiveSection] = useState('performance');
  const timerRef = useRef(null);
  const sectionRefs = {
    performance: useRef(null),
    month:       useRef(null),
    'tax-income': useRef(null),
    'deep-dive':  useRef(null),
  };

  useEffect(() => {
    setCurrentIndex(0);
    if (timeline && timeline.length > 0) setIsPlaying(true);
  }, [timeline]);

  useEffect(() => {
    if (isPlaying && timeline && timeline.length > 0) {
      timerRef.current = setInterval(() => {
        setCurrentIndex(prev => {
          if (prev >= timeline.length - 1) { setIsPlaying(false); return prev; }
          return prev + 1;
        });
      }, 1000 / speed);
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [isPlaying, speed, timeline]);

  const togglePlay = () => {
    if (currentIndex >= (timeline?.length ?? 1) - 1) setCurrentIndex(0);
    setIsPlaying(!isPlaying);
  };

  const scrollTo = (id) => {
    setActiveSection(id);
    sectionRefs[id]?.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  if (!timeline || timeline.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-4 py-24">
        <BarChart3 className="w-16 h-16 opacity-20" />
        <p className="text-lg font-medium">No simulation data yet</p>
        <p className="text-sm text-slate-400">Go back to <span className="text-blue-600 font-semibold">Home</span> and analyze your position first.</p>
      </div>
    );
  }

  const baseState  = timeline[0];
  const state      = timeline[currentIndex];
  const intel      = monthlyIntelligence?.[currentIndex - 1] || null;
  const horizonMonths = (inputs?.horizon_years || 1) * 12;

  const portfolioDelta = state.total_portfolio_value - baseState.total_portfolio_value;

  const dynamicSummary = {
    capital_released:      timeline.slice(0, currentIndex + 1).reduce((s, f) => s + (f.capital_released_this_step || 0), 0),
    allocation_to_income:  timeline.slice(0, currentIndex + 1).reduce((s, f) => s + (f.allocation_to_income_this_step || 0), 0),
    allocation_to_model:   timeline.slice(0, currentIndex + 1).reduce((s, f) => s + (f.allocation_to_model_this_step || 0), 0),
    true_final_ecosystem_value: state.total_portfolio_value,
  };

  const monthSummary = {
    month:            state.month || currentIndex,
    shares_sold:      state.strategies?.concentrated?.shares_sold || 0,
    capital_released: state.capital_released_this_step || 0,
    to_income:        state.allocation_to_income_this_step || 0,
    to_model:         state.allocation_to_model_this_step || 0,
  };

  const hasTrace = state.decision_trace && state.decision_trace.length > 0;
  const fmt = v => '$' + Math.round(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });

  return (
    <div className="w-full flex flex-col gap-0 max-w-7xl mx-auto">

      {/* ── Sticky playback bar ── */}
      <div className="sticky top-0 z-30 bg-white border border-slate-200 shadow-sm rounded-xl p-4 mb-4 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={togglePlay}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-4 py-2.5 rounded-xl shadow-md transition-colors"
          >
            {isPlaying
              ? <><Pause className="w-4 h-4" fill="currentColor" /> Pause</>
              : <><RefreshCcw className="w-4 h-4" /> Replay</>}
          </button>
          <div className="flex items-center gap-2 ml-4 border-l border-slate-200 pl-4">
            <span className="text-xs font-bold text-slate-400 uppercase">Speed</span>
            <select
              value={speed}
              onChange={e => setSpeed(Number(e.target.value))}
              className="w-20 rounded border-slate-300 shadow-sm text-sm p-1"
            >
              <option value={0.5}>0.5×</option>
              <option value={1}>1×</option>
              <option value={2}>2×</option>
              <option value={5}>5×</option>
              <option value={10}>10×</option>
            </select>
          </div>
        </div>

        <div className="flex-1 px-4 max-w-2xl w-full">
          <div className="flex justify-between text-xs text-slate-400 font-bold mb-2 uppercase tracking-wider">
            <span>Start</span>
            <span className="text-blue-600 px-3 py-1 bg-blue-50 rounded-full">
              Month {state.month || currentIndex} of {horizonMonths}
            </span>
            <span>{inputs?.horizon_years || 1}yr horizon</span>
          </div>
          <input
            type="range" min="0" max={timeline.length - 1} value={currentIndex}
            onChange={e => { setIsPlaying(false); setCurrentIndex(Number(e.target.value)); }}
            className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
          />
        </div>
      </div>

      {/* ── Section nav ── */}
      <div className="sticky top-[72px] z-20 bg-white border border-slate-200 rounded-xl shadow-sm mb-4">
        <div className="flex">
          {SECTIONS.map((s, i) => (
            <button
              key={s.id}
              onClick={() => scrollTo(s.id)}
              className={`flex-1 py-3 text-sm font-semibold transition-colors
                ${i === 0 ? 'rounded-l-xl' : ''}
                ${i === SECTIONS.length - 1 ? 'rounded-r-xl' : ''}
                ${activeSection === s.id
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-500 hover:text-slate-800 hover:bg-slate-50'}`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* ══ Section 1: Performance ══ */}
      <section ref={sectionRefs.performance} className="scroll-mt-36 flex flex-col gap-4 mb-8">
        <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">Performance</h2>

        {/* Portfolio snapshot */}
        <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4 grid grid-cols-2 md:grid-cols-4 divide-x divide-slate-100">
          <div className="px-4">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wide">Portfolio value</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-lg font-bold text-slate-800">{fmt(state.total_portfolio_value)}</span>
              <span className={`text-xs font-bold ${portfolioDelta >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                {portfolioDelta >= 0 ? '+' : ''}{fmt(portfolioDelta)} since start
              </span>
            </div>
          </div>
          <div className="px-4">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wide">Concentration risk</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-lg font-bold text-slate-800">{(state.concentration_pct * 100).toFixed(1)}%</span>
              <span className={`text-xs font-bold ${state.concentration_pct <= baseState.concentration_pct ? 'text-green-600' : 'text-red-500'}`}>
                {state.concentration_pct > baseState.concentration_pct ? '+' : ''}
                {((state.concentration_pct - baseState.concentration_pct) * 100).toFixed(1)}%
              </span>
            </div>
          </div>
          <div className="px-4">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wide">Income yield</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-lg font-bold text-slate-800">{fmt(state.strategies?.income?.annual_income || 0)}</span>
              <span className={`text-xs font-bold ${(state.strategies?.income?.annual_income || 0) >= (baseState.strategies?.income?.annual_income || 0) ? 'text-green-600' : 'text-red-500'}`}>
                {(state.strategies?.income?.annual_income || 0) >= (baseState.strategies?.income?.annual_income || 0) ? '+' : ''}
                {fmt((state.strategies?.income?.annual_income || 0) - (baseState.strategies?.income?.annual_income || 0))}
              </span>
            </div>
          </div>
          <div className="px-4">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wide">Risk preference</span>
            <div className="mt-1">
              <span className="text-lg font-bold text-slate-800">{inputs?.risk_score || 50}</span>
              <span className="text-xs text-slate-400 ml-1">/ 100</span>
            </div>
          </div>
        </div>

        <SimulationCharts timeline={timeline} timelineSeries={timelineSeries} currentIndex={currentIndex} />
      </section>

      {/* ══ Section 2: Month by Month ══ */}
      <section ref={sectionRefs.month} className="scroll-mt-36 flex flex-col gap-4 mb-8">
        <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">Month by Month</h2>

        {/* Plain English month summary */}
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-2">Month {monthSummary.month} summary</p>
          {monthSummary.shares_sold > 0 ? (
            <p className="text-sm text-slate-700 leading-relaxed">
              <span className="font-semibold text-green-700">{monthSummary.shares_sold.toLocaleString()} shares reduced.</span>{' '}
              {fmt(monthSummary.capital_released)} freed up and put to work
              {monthSummary.to_income > 0 && <> — <span className="text-sky-700 font-semibold">{fmt(monthSummary.to_income)} into income strategy</span></>}
              {monthSummary.to_model > 0 && <> and <span className="text-blue-700 font-semibold">{fmt(monthSummary.to_model)} into diversified holdings</span></>}.
            </p>
          ) : (
            <p className="text-sm text-slate-700 leading-relaxed">
              {intel?.blocking_reason?.includes('MOMENTUM')
                ? 'The stock showed strong momentum this month — the strategy held and collected covered call income instead of selling.'
                : intel?.blocking_reason?.includes('MACRO')
                ? 'A cautious market environment this month — the strategy held your position and collected covered call income.'
                : 'No shares were sold this month. The strategy continued collecting income from covered calls.'}
            </p>
          )}
        </div>

        {/* Intelligence panel (signals, decision trace, what-if) */}
        <IntelligencePanel
          intel={intel}
          allIntel={monthlyIntelligence || []}
          allIntelWhatif={monthlyIntelligenceWhatif}
          gateOverrides={inputs?.gate_overrides}
          currentIndex={currentIndex}
          onRunWhatIf={onRunWhatIf}
          isWhatIfRunning={isWhatIfRunning}
          onClearWhatIf={onClearWhatIf}
        />
      </section>

      {/* ══ Section 3: Tax & Income ══ */}
      <section ref={sectionRefs['tax-income']} className="scroll-mt-36 flex flex-col gap-4 mb-8">
        <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">Tax & Income</h2>
        {/* TLH and options charts live inside IntelligencePanel above, but the StrategyAttribution panel has tax context */}
        <StrategyAttributionPanel frame={state} baseFrame={baseState} />
      </section>

      {/* ══ Section 4: Deep Dive ══ */}
      <section ref={sectionRefs['deep-dive']} className="scroll-mt-36 flex flex-col gap-4 mb-8">
        <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">Deep Dive</h2>

        <div className="flex gap-4">
          <CurrentStatePanel state={baseState} />
          <TransformationPanel summary={dynamicSummary} trace={state.decision_trace || []} />
          <ProjectedStatePanel state={state} initialState={baseState} />
        </div>

        <HoldingsPanel frame={state} />
        <ReconciliationPanel frame={state} />
        {hasTrace && <DecisionTracePanel trace={state.decision_trace} />}
      </section>

    </div>
  );
}
