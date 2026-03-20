import React from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';

const $ = (v) => {
  const n = Number(v || 0);
  const sign = n >= 0 ? '+' : '';
  return (n === 0 || Math.abs(n) < 0.01) ? '$0.00' : `${sign}$${Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};
const $abs = (v) => `$${Number(v || 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

function Check({ pass, label, delta }) {
  return (
    <div className={`flex items-center justify-between px-3 py-1.5 rounded-lg text-xs font-semibold ${pass ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-700'}`}>
      <div className="flex items-center gap-1.5">
        {pass ? <CheckCircle2 className="w-3.5 h-3.5 text-green-500" /> : <XCircle className="w-3.5 h-3.5 text-red-500" />}
        {label}
      </div>
      <span className={`font-mono ${pass ? 'text-green-600' : 'text-red-600'}`}>
        Δ {$(delta)}
      </span>
    </div>
  );
}

function ReconRow({ label, value, dim, total, separator }) {
  return (
    <div className={`flex justify-between items-center py-1 text-xs ${separator ? 'border-t border-slate-200 pt-2 mt-1' : ''}`}>
      <span className={`font-medium ${dim ? 'text-slate-400' : 'text-slate-600'}`}>{label}</span>
      <span className={`font-mono font-bold ${total ? 'text-slate-800' : dim ? 'text-slate-400' : 'text-slate-700'}`}>{value}</span>
    </div>
  );
}

export default function ReconciliationPanel({ frame }) {
  if (!frame || !frame.reconciliation) return null;

  const recon    = frame.reconciliation;
  const details  = recon.details || {};
  const month    = frame.month || 0;

  const isBaseline = month === 0;

  return (
    <div className="w-full mt-4 bg-slate-900 border border-slate-700 rounded-xl p-5 shadow-inner shrink-0 text-slate-200">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">
          Month {month} — Reconciliation Proof
        </h3>
        <div className="flex gap-2">
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${recon.is_flow_valid ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
            {recon.is_flow_valid ? '✓ Flow Check' : '✗ Flow Check'}
          </span>
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${recon.is_sum_valid ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
            {recon.is_sum_valid ? '✓ Sum Check' : '✗ Sum Check'}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">

        {/* ── Flow Reconciliation ── */}
        <div>
          <p className="text-[10px] font-bold text-slate-500 uppercase mb-2 tracking-wider">Value Flow Proof</p>
          <div className="bg-slate-800 rounded-lg p-3 space-y-0.5">
            {isBaseline ? (
              <ReconRow label="Baseline — no prior step" value={$abs(details.start_value || frame.total_portfolio_value)} total />
            ) : (
              <>
                <ReconRow label="Start Value"           value={$abs(details.start_value)} />
                <ReconRow label="+ CP Value Change"     value={$(details.cp_change)} dim />
                <ReconRow label="+ Income Change"       value={$(details.income_change)} dim />
                <ReconRow label="+ Model Change"        value={$(details.model_change)} dim />
                <ReconRow label="+ Cash Change"         value={$(details.cash_change)} dim />
                <ReconRow label="= Reconstructed End"   value={$abs(details.reconstructed_end)} total separator />
                <ReconRow label="  Actual End"          value={$abs(details.end_value)} />
              </>
            )}
          </div>
          <div className="mt-2">
            <Check
              pass={recon.is_flow_valid}
              label={recon.is_flow_valid ? 'Every dollar accounted for' : 'Value leakage detected'}
              delta={recon.flow_delta || 0}
            />
          </div>
        </div>

        {/* ── Component Sum Check ── */}
        <div>
          <p className="text-[10px] font-bold text-slate-500 uppercase mb-2 tracking-wider">Component Sum Proof</p>
          <div className="bg-slate-800 rounded-lg p-3 space-y-0.5">
            <ReconRow label="Concentrated Position" value={$abs(details.concentrated_value || frame.concentrated_value)} />
            <ReconRow label="+ Income Strategy"     value={$abs(details.income_value || frame.income_value)} dim />
            <ReconRow label="+ Model Portfolio"     value={$abs(details.model_value || frame.model_value)} dim />
            <ReconRow label="+ Cash"                value={$abs(details.cash || frame.cash)} dim />
            <ReconRow label="= Reconstructed Total" value={$abs(details.component_sum || frame.total_portfolio_value)} total separator />
            <ReconRow label="  Actual Total"        value={$abs(details.end_value || frame.total_portfolio_value)} />
          </div>
          <div className="mt-2">
            <Check
              pass={recon.is_sum_valid}
              label={recon.is_sum_valid ? 'No double-counting detected' : 'Component mismatch detected'}
              delta={recon.sum_delta || 0}
            />
          </div>
        </div>

      </div>
    </div>
  );
}
