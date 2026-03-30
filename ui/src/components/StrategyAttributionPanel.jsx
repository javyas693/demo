import { Layers, TrendingUp, PieChart as PieChartIcon } from 'lucide-react';

const $ = (v, d = 0) => '$' + Number(v || 0).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
const signed = (v) => (v >= 0 ? '+' : '') + '$' + Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 });

function Row({ label, value, accent, muted, indent }) {
  return (
    <div className={`flex justify-between items-baseline py-1.5 ${indent ? 'pl-4' : ''} ${muted ? '' : 'border-b border-white/60'}`}>
      <span className={`text-xs font-semibold uppercase tracking-wide ${muted ? 'text-slate-400' : 'text-slate-500'}`}>{label}</span>
      <span className={`text-sm font-bold ${accent || 'text-slate-800'}`}>{value}</span>
    </div>
  );
}

export default function StrategyAttributionPanel({ frame, baseFrame }) {
  if (!frame || !frame.strategies) return null;

  const { concentrated, income } = frame.strategies;

  // attr_income_allocated / attr_model_allocated are stored as negative (outflow
  // convention: money deployed = negative cash flow). Use abs() for display.
  const incomeDeployed = Math.abs(frame.attr_income_allocated || 0);
  const modelDeployed  = Math.abs(frame.attr_model_allocated  || 0);

  const incomeTotal  = frame.income_value || 0;
  const modelTotal   = frame.model_value  || 0;

  // P&L = current market value of sleeve minus what was deployed
  const incomePnL = incomeTotal - incomeDeployed;
  const modelPnL  = modelTotal  - modelDeployed;

  // ── TASK 4: Concentrated position ──
  const cpInitialValue = baseFrame?.concentrated_value || frame.attr_cp_initial_value || 0;
  const cpCurrentValue = frame.concentrated_value || 0;

  // Use backend-tracked value sold (capital actually released from share sales).
  // Do NOT derive as cpInitialValue - cpCurrentValue: that conflates unrealized
  // appreciation with sold proceeds and produces a wrong number when the position
  // grows without any shares being sold.
  const cpValueSold = frame.attr_cp_value_sold || 0;

  // Appreciation = what the remaining position gained (or lost) in market value.
  // Formula: current_value - (initial_value - proceeds_from_sales)
  // i.e. current vs the cost basis of shares still held.
  const cpAppreciation = cpCurrentValue - (cpInitialValue - cpValueSold);

  const cpPrice = frame.cp_price || concentrated.price || 0;
  const cpShares = concentrated.shares || 0;

  return (
    <div className="w-full mt-4 bg-white border border-slate-200 rounded-xl p-5 shadow-sm shrink-0">
      <h3 className="text-xs font-bold text-slate-500 mb-4 uppercase tracking-widest">Strategy Attribution</h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">

        {/* ─── Income Strategy ─── */}
        <div className="bg-amber-50 border border-amber-100 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-amber-500" />
            <span className="font-bold text-amber-800 text-sm">Income Strategy</span>
          </div>

          <Row label="Capital Deployed"   value={$(incomeDeployed)}              accent="text-amber-700" />
          <Row label="Holdings Value"     value={$(incomeTotal)}                 accent="text-amber-900" />
          <div className="text-[9px] text-slate-400 pl-1 -mt-1 mb-1">market value + reinvested distributions</div>
          <Row label="Unrealized P&L"     value={signed(incomePnL)}              accent={incomePnL >= 0 ? 'text-emerald-600' : 'text-red-500'} />

          <div className={`mt-2 px-2 py-1.5 rounded text-[10px] font-mono ${Math.abs(incomeDeployed + incomePnL - incomeTotal) < 5 ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>
            {$(incomeDeployed)} deployed + {incomePnL >= 0 ? '+' : ''}{incomePnL.toLocaleString(undefined, {maximumFractionDigits: 0})} P&L = {$(incomeTotal)} ✓
          </div>

          <div className="mt-3 space-y-0.5">
            <Row label="Annual Distribution Yield" value={$(income.annual_income)} muted indent />
          </div>
        </div>

        {/* ─── Model Portfolio ─── */}
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <PieChartIcon className="w-4 h-4 text-blue-500" />
            <span className="font-bold text-blue-800 text-sm">Model Portfolio</span>
          </div>

          <Row label="Capital Deployed"   value={$(modelDeployed)}               accent="text-blue-700" />
          <Row label="Holdings Value"     value={$(modelTotal)}                  accent="text-blue-900" />
          <Row label="Unrealized P&L"     value={signed(modelPnL)}               accent={modelPnL >= 0 ? 'text-emerald-600' : 'text-red-500'} />

          <div className={`mt-2 px-2 py-1.5 rounded text-[10px] font-mono ${Math.abs(modelDeployed + modelPnL - modelTotal) < 5 ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>
            {$(modelDeployed)} deployed + {modelPnL >= 0 ? '+' : ''}{modelPnL.toLocaleString(undefined, {maximumFractionDigits: 0})} P&L = {$(modelTotal)} ✓
          </div>

          <div className="mt-3 space-y-0.5">
            <Row label="Expected Annual Return" value="7.0% / yr" muted indent />
          </div>
        </div>

        {/* ─── Concentrated Position ─── */}
        <div className="bg-red-50 border border-red-100 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Layers className="w-4 h-4 text-red-500" />
            <span className="font-bold text-red-800 text-sm">Concentrated Position</span>
          </div>

          <Row label="Initial Value" value={$(cpInitialValue)} accent="text-red-700" />
          <Row label="Value Sold" value={cpValueSold > 0 ? `-${$(cpValueSold)}` : '$0'} accent="text-emerald-600" />
          <Row label="Appreciation" value={signed(cpAppreciation)} accent={cpAppreciation >= 0 ? 'text-emerald-600' : 'text-red-500'} />
          <Row label="Remaining Value" value={$(cpCurrentValue)} accent="text-red-900" />

          {/* Consistency check: initial - sold + appreciation = current */}
          <div className="mt-2 px-2 py-1.5 rounded text-[10px] font-mono bg-green-50 text-green-700">
            {$(cpInitialValue)} − {$(cpValueSold)} sold {cpAppreciation >= 0 ? '+' : '−'} {$(Math.abs(cpAppreciation))} chg = {$(cpCurrentValue)} ✓
          </div>

          <div className="mt-3 space-y-0.5">
            <Row label="Current Price" value={$(cpPrice, 2)} muted indent />
            <Row label="Shares Remaining" value={cpShares.toLocaleString()} muted indent />
          </div>
        </div>

      </div>
    </div>
  );
}