import React from 'react';
import { ArrowRight, CheckCircle2 } from 'lucide-react';

export default function TransformationPanel({ summary, trace }) {
  const capital_released = Math.abs(summary.capital_released || 0);
  const allocation_to_income = Math.abs(summary.allocation_to_income || 0);
  const allocation_to_model = Math.abs(summary.allocation_to_model || 0);
  const total_deployed = allocation_to_income + allocation_to_model;

  return (
    <div className="flex-1 flex flex-col items-center justify-center relative z-0 px-2 py-8">

      {/* TASK 7: Single direction arrow connector */}
      <div className="absolute top-1/2 left-0 w-full h-0.5 bg-slate-200 -z-10 transform -translate-y-1/2"></div>

      <div className="bg-white rounded-full p-3 shadow border border-slate-200 z-10 mb-6">
        <ArrowRight className="w-6 h-6 text-blue-500" />
      </div>

      {/* TASK 3: Renamed + restructured middle panel */}
      <div className="bg-emerald-50 border border-emerald-100 rounded-xl shadow-sm w-full p-4 flex flex-col items-center z-10 relative">
        <div className="absolute -top-3 bg-emerald-100 text-emerald-800 text-[10px] font-bold px-2 py-1 rounded-full uppercase tracking-wider">
          Capital Deployed to Strategies
        </div>

        <p className="text-3xl font-black text-emerald-600 mt-2 mb-0">${total_deployed.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</p>
        <p className="text-[10px] text-slate-400 mb-1">net deployed to date (income + model)</p>
        <p className="text-[10px] text-slate-400 mb-3">${capital_released.toLocaleString(undefined, { maximumFractionDigits: 0 })} released from CP · includes cash &amp; option income</p>

        <div className="w-full flex justify-between items-center gap-2">
           <div className="flex flex-col items-center bg-white p-2 rounded shadow-sm border border-slate-100 w-1/2">
             <span className="text-[10px] font-bold text-slate-400 uppercase">→ To Income</span>
             <span className="text-sm font-bold text-amber-600">${allocation_to_income.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span>
           </div>

           <div className="flex flex-col items-center bg-white p-2 rounded shadow-sm border border-slate-100 w-1/2">
             <span className="text-[10px] font-bold text-slate-400 uppercase">→ To Core MP</span>
             <span className="text-sm font-bold text-blue-600">${allocation_to_model.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span>
           </div>
        </div>
      </div>
      
      <div className="mt-6 flex flex-col gap-2 w-full">
         <div className="flex items-center gap-2 text-xs text-slate-500 bg-white p-2 border border-slate-100 rounded shadow-sm">
           <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
           <span>Tax-Neutral Liquidation Passed</span>
         </div>
         <div className="flex items-center gap-2 text-xs text-slate-500 bg-white p-2 border border-slate-100 rounded shadow-sm">
           <ArrowRight className="w-4 h-4 text-blue-400 flex-shrink-0" />
           <span>Risk Constraints Executed</span>
         </div>
      </div>

    </div>
  );
}
