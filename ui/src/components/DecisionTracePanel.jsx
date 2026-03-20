import React, { useState } from 'react';
import { Terminal, ChevronDown, ChevronRight } from 'lucide-react';

function TraceBlock({ event }) {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <div className="border-l-2 border-slate-200 ml-3 pl-4 py-2 relative">
      <div className="absolute w-2.5 h-2.5 bg-blue-500 rounded-full -left-[6px] top-3.5 ring-4 ring-white"></div>
      
      <button 
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm font-semibold text-slate-700 hover:text-blue-600 transition-colors w-full text-left"
      >
        {expanded ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
        [{event.event}]
      </button>
      
      {expanded && event.details && (
        <pre className="mt-2 bg-slate-800 text-sky-300 p-3 rounded-lg text-xs overflow-x-auto shadow-inner border border-slate-700">
          <code>{JSON.stringify(event.details, null, 2)}</code>
        </pre>
      )}
    </div>
  );
}

export default function DecisionTracePanel({ trace }) {
  if (!trace || trace.length === 0) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 flex-1 overflow-auto">
      <div className="flex items-center gap-2 mb-4 border-b border-slate-100 pb-3">
        <Terminal className="w-5 h-5 text-slate-500" />
        <h2 className="text-sm font-semibold text-slate-700">Orchestrator Decision Trace</h2>
      </div>

      <div className="flex flex-col mt-2">
        {trace.map((evt, idx) => (
          <TraceBlock key={idx} event={evt} />
        ))}
      </div>
    </div>
  );
}
