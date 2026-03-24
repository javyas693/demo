import React from 'react';
import Tooltip from './Tooltip';

function cellStyle(intel) {
  if (!intel) return { bg: 'bg-slate-100', border: 'border-slate-200', text: 'text-slate-400' };
  if (intel.enable_unwind)                              return { bg: 'bg-green-100',  border: 'border-green-300',  text: 'text-green-700'  };
  if (intel.blocking_reason?.includes('MOMENTUM'))      return { bg: 'bg-amber-100',  border: 'border-amber-300',  text: 'text-amber-700'  };
  if (intel.blocking_reason?.includes('MACRO'))         return { bg: 'bg-blue-100',   border: 'border-blue-300',   text: 'text-blue-700'   };
  return { bg: 'bg-slate-100', border: 'border-slate-200', text: 'text-slate-400' };
}

function cellTooltip(intel) {
  if (!intel) return 'No data';
  if (intel.enable_unwind) {
    return `Month ${intel.month}: Sold ${intel.shares_to_sell} shares at $${intel.cp_price?.toFixed(2)}. All signal gates passed — tax-neutral sale executed.`;
  }
  const br = intel.blocking_reason || '';
  if (br.includes('MOMENTUM')) {
    return `Month ${intel.month}: No sale — momentum score ${intel.signals?.momentum_score?.toFixed(2)} was too bullish. System protected upside by holding. Covered call ran for income.`;
  }
  if (br.includes('MACRO')) {
    return `Month ${intel.month}: No sale — market was in risk-on mode. System held position to capture potential upside. Covered call ran for income.`;
  }
  return `Month ${intel.month}: Hold`;
}

export default function DecisionTimeline({ allIntel, currentIndex }) {
  if (!allIntel || allIntel.length === 0) return null;

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Tooltip content="Each square is one month. Green = shares sold. Amber = momentum blocked the sale. Blue = macro environment blocked the sale. Click the slider above to explore any month in detail.">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider cursor-help border-b border-dashed border-slate-300">
            Decision timeline
          </span>
        </Tooltip>
        <div className="flex gap-3 ml-auto text-xs text-slate-400">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-green-100 border border-green-300 inline-block" />Sell
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-amber-100 border border-amber-300 inline-block" />Momentum block
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-blue-100 border border-blue-300 inline-block" />Macro block
          </span>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {allIntel.map((intel, i) => {
          const s = cellStyle(intel);
          const isActive = i === currentIndex - 1;
          return (
            <Tooltip key={i} content={cellTooltip(intel)} position="top">
              <div
                className={`
                  w-8 h-8 rounded flex items-center justify-center text-xs font-medium border cursor-default
                  ${s.bg} ${s.border} ${s.text}
                  ${isActive ? 'ring-2 ring-offset-1 ring-slate-500 font-bold' : ''}
                  transition-all duration-150
                `}
              >
                {intel?.month ?? i + 1}
              </div>
            </Tooltip>
          );
        })}
      </div>
    </div>
  );
}
