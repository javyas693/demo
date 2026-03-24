import React, { useState, useEffect, useRef } from 'react';
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

export default function HistoryTab({ onError, timeline, timelineSeries, monthlyIntelligence, monthlyIntelligenceWhatif, inputs, onRunWhatIf, isWhatIfRunning, onClearWhatIf }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [speed, setSpeed] = useState(1);
  const timerRef = useRef(null);

  // Reset playback and auto-start when new timeline arrives
  useEffect(() => {
    setCurrentIndex(0);
    if (timeline && timeline.length > 0) {
      setIsPlaying(true);
    }
  }, [timeline]);

  // Playback Engine
  useEffect(() => {
    if (isPlaying && timeline && timeline.length > 0) {
      timerRef.current = setInterval(() => {
        setCurrentIndex((prev) => {
          if (prev >= timeline.length - 1) {
            setIsPlaying(false);
            return prev;
          }
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

  // No simulation run yet
  if (!timeline || timeline.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-4 py-24">
        <BarChart3 className="w-16 h-16 opacity-20" />
        <p className="text-lg font-medium">Run a simulation to see results</p>
        <p className="text-sm text-slate-400">Go to the <span className="text-blue-600 font-semibold">Strategy Input</span> tab and click Run Simulation.</p>
      </div>
    );
  }

  const baseState = timeline[0];
  const state = timeline[currentIndex];
  const intel = monthlyIntelligence?.[currentIndex - 1] || null;
  const horizonMonths = (inputs?.horizon_years || 1) * 12;

  const portfolioDelta = state.total_portfolio_value - baseState.total_portfolio_value;

  const dynamicSummary = {
    capital_released: timeline.slice(0, currentIndex + 1).reduce((sum, f) => sum + (f.capital_released_this_step || 0), 0),
    allocation_to_income: timeline.slice(0, currentIndex + 1).reduce((sum, f) => sum + (f.allocation_to_income_this_step || 0), 0),
    allocation_to_model: timeline.slice(0, currentIndex + 1).reduce((sum, f) => sum + (f.allocation_to_model_this_step || 0), 0),
    true_final_ecosystem_value: state.total_portfolio_value
  };

  const monthSummary = {
    month: state.month || currentIndex,
    shares_sold: state.strategies?.concentrated?.shares_sold || 0,
    capital_released: state.capital_released_this_step || 0,
    to_income: state.allocation_to_income_this_step || 0,
    to_model: state.allocation_to_model_this_step || 0,
  };

  const hasTrace = state.decision_trace && state.decision_trace.length > 0;

  return (
    <div className="w-full h-full flex flex-col gap-4">

      {/* Playback Controls */}
      <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={togglePlay}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-4 py-2.5 rounded-xl shadow-md transition-colors"
          >
            {isPlaying ? (
              <><Pause className="w-4 h-4" fill="currentColor" /> Pause</>
            ) : (
              <><RefreshCcw className="w-4 h-4" /> Run Simulation</>
            )}
          </button>
          <div className="flex items-center gap-2 ml-4 border-l border-slate-200 pl-4">
            <span className="text-xs font-bold text-slate-400 uppercase">Speed</span>
            <select
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
              className="w-20 rounded border-slate-300 shadow-sm text-sm p-1"
            >
              <option value={0.5}>0.5x</option>
              <option value={1}>1x</option>
              <option value={2}>2x</option>
              <option value={5}>5x</option>
              <option value={10}>10x</option>
            </select>
          </div>
        </div>

        <div className="flex-1 px-4 max-w-2xl w-full">
          <div className="flex justify-between text-xs text-slate-400 font-bold mb-2 uppercase tracking-wider">
            <span>Starting Portfolio</span>
            <span className="text-blue-600 px-3 py-1 bg-blue-50 rounded-full">
              Month {state.month || currentIndex} of {horizonMonths}
            </span>
            <span>Horizon: {inputs?.horizon_years || 1} Years</span>
          </div>
          <input
            type="range"
            min="0" max={timeline.length - 1}
            value={currentIndex}
            onChange={(e) => { setIsPlaying(false); setCurrentIndex(Number(e.target.value)); }}
            className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
          />
        </div>
      </div>

      {/* Portfolio Metrics Header */}
      <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4 flex gap-4 divide-x divide-slate-100">
        <div className="flex-1 px-4">
          <span className="text-xs font-bold text-slate-400 uppercase">Portfolio Value</span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-lg font-bold text-slate-800">${state.total_portfolio_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
            <span className={`text-xs font-bold ${portfolioDelta >= 0 ? 'text-green-600' : 'text-red-500'}`}>
              {portfolioDelta >= 0 ? '+' : ''}${portfolioDelta.toLocaleString(undefined, { maximumFractionDigits: 0 })} since start
            </span>
          </div>
        </div>
        <div className="flex-1 px-4">
          <span className="text-xs font-bold text-slate-400 uppercase">Concentration</span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-lg font-bold text-slate-800">{state.concentration_pct.toFixed(1)}%</span>
            <span className={`text-xs font-bold ${state.concentration_pct <= baseState.concentration_pct ? 'text-green-600' : 'text-red-500'}`}>
              {state.concentration_pct > baseState.concentration_pct ? '+' : ''}
              {(state.concentration_pct - baseState.concentration_pct).toFixed(1)}%
            </span>
          </div>
        </div>
        <div className="flex-1 px-4">
          <span className="text-xs font-bold text-slate-400 uppercase">Annual Income</span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-lg font-bold text-slate-800">${(state.strategies?.income?.annual_income || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
            <span className={`text-xs font-bold ${(state.strategies?.income?.annual_income || 0) >= (baseState.strategies?.income?.annual_income || 0) ? 'text-green-600' : 'text-red-500'}`}>
              {(state.strategies?.income?.annual_income || 0) >= (baseState.strategies?.income?.annual_income || 0) ? '+' : ''}
              ${((state.strategies?.income?.annual_income || 0) - (baseState.strategies?.income?.annual_income || 0)).toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </span>
          </div>
        </div>
        <div className="flex-1 px-4">
          <span className="text-xs font-bold text-slate-400 uppercase">Target Risk Score</span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-lg font-bold text-slate-800">{inputs?.risk_score || 50}</span>
          </div>
        </div>
      </div>

      {/* Month Step Summary Bar */}
      <div className="bg-slate-800 text-slate-200 text-xs px-5 py-3 rounded-xl flex gap-6 items-center font-mono shadow-inner border border-slate-700 flex-wrap">
        <span className="font-bold text-white">Month {monthSummary.month}:</span>
        <span>Shares Sold: <span className="text-amber-300 font-bold">{monthSummary.shares_sold}</span></span>
        <span>Capital Released: <span className="text-green-400 font-bold">${monthSummary.capital_released.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span></span>
        <span className="border-l border-slate-600 pl-4">→ Income: <span className="text-sky-300 font-bold">${monthSummary.to_income.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span></span>
        <span>→ Model: <span className="text-blue-400 font-bold">${monthSummary.to_model.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span></span>
      </div>

      {/* 3-Panel Visual Suite */}
      <div className="flex-1 flex gap-4 h-full relative">
        <CurrentStatePanel state={baseState} />
        <TransformationPanel summary={dynamicSummary} trace={state.decision_trace || []} />
        <ProjectedStatePanel state={state} initialState={baseState} />
      </div>

      <StrategyAttributionPanel frame={state} baseFrame={baseState} />
      <HoldingsPanel frame={state} />
      <ReconciliationPanel frame={state} />

      <SimulationCharts timeline={timeline} timelineSeries={timelineSeries} currentIndex={currentIndex} />

      {hasTrace && <DecisionTracePanel trace={state.decision_trace} />}

      {/* Intelligence Panel — reads monthly_intelligence from simulate response */}
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

    </div>
  );
}
