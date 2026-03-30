"use client"

import * as React from "react"
import { Activity, HelpCircle, Layers } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Slider } from "@/components/ui/slider"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { MetricCard } from "@/components/ui/metric-card"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid,
    Tooltip as RechartsTooltip, Legend, ResponsiveContainer,
    BarChart, Bar, LabelList,
} from "recharts"
import {
    simulateConcentratedPosition,
    postFrontierPropose,
    postMPSimulate,
    postAnchorIncomeSimulate,
    patchProfile,
    FrontierProposalResponse,
} from "@/lib/api"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const formatCurrency = (num: number, compact = true) =>
    new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        notation: compact ? "compact" : "standard",
        maximumFractionDigits: 1,
    }).format(num)

const getTodayStr = () => new Date().toISOString().split("T")[0]
const getTenYearsAgoStr = () => {
    const d = new Date()
    d.setFullYear(d.getFullYear() - 10)
    return d.toISOString().split("T")[0]
}

// ---------------------------------------------------------------------------
// Shared inner tab list styling
// ---------------------------------------------------------------------------
const INNER_TAB_LIST = "w-full justify-start rounded-none border-b border-zinc-200 dark:border-zinc-800 bg-transparent p-0 overflow-x-auto flex-nowrap scrollbar-none"
const INNER_TAB_TRIGGER = "rounded-none border-b-2 border-transparent data-[state=active]:border-indigo-600 dark:data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 pb-2 pt-2 whitespace-nowrap text-sm"

// ---------------------------------------------------------------------------
// Reusable empty state
// ---------------------------------------------------------------------------
function EmptyState({ message }: { message: string }) {
    return (
        <div className="flex flex-col items-center justify-center py-16 px-4 text-center border border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl bg-zinc-50/50 dark:bg-zinc-900/20">
            <Activity className="h-8 w-8 text-zinc-300 mb-4" />
            <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">No results yet.</h3>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-sm">{message}</p>
        </div>
    )
}

// ---------------------------------------------------------------------------
// Future tab placeholder
// ---------------------------------------------------------------------------
function FuturePlaceholder() {
    return (
        <div className="flex flex-col items-center justify-center py-16 px-4 text-center border border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl bg-zinc-50/50 dark:bg-zinc-900/20">
            <h3 className="text-xl font-medium text-zinc-900 dark:text-zinc-100 mb-2">Future Scenario Modeling</h3>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-sm">
                Monte Carlo projections will appear here.
            </p>
        </div>
    )
}

// ---------------------------------------------------------------------------
// Shared input field class
// ---------------------------------------------------------------------------
const INPUT_CLS = "flex h-10 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 dark:border-zinc-800 dark:bg-zinc-950 dark:placeholder:text-zinc-400 dark:focus-visible:ring-indigo-400 text-zinc-900 dark:text-zinc-100"

// ===========================================================================
// CP Engine Tab
// ===========================================================================
function CPStrategy() {
    // --- state ---
    const [inputSymbol, setInputSymbol] = React.useState("AAPL")
    const [inputShares, setInputShares] = React.useState<number | "">(1200)
    const [inputCostBasis, setInputCostBasis] = React.useState<number | "">(185.25)
    const [inputStartingCash, setInputStartingCash] = React.useState<number | "">(0)
    const [inputTlhInventory, setInputTlhInventory] = React.useState<number | "">(50000)
    const [inputMaxSharesPerMonth, setInputMaxSharesPerMonth] = React.useState<number | "">(200)

    const [startDate, setStartDate] = React.useState(getTenYearsAgoStr())
    const [endDate, setEndDate] = React.useState(getTodayStr())
    const [cpStartDateDisplay, setCpStartDateDisplay] = React.useState("")
    const [cpEndDateDisplay, setCpEndDateDisplay] = React.useState("")

    const [strategyMode, setStrategyMode] = React.useState<"harvest" | "tax_neutral">("harvest")
    const [coveredPct, setCoveredPct] = React.useState(50)
    const [targetDelta, setTargetDelta] = React.useState(0.20)
    const [targetDteDays, setTargetDteDays] = React.useState(30)
    const [profitCaptureTarget, setProfitCaptureTarget] = React.useState(50)
    const [stopLossMultiple, setStopLossMultiple] = React.useState(3.0)

    const [cpSimData, setCpSimData] = React.useState<any>(null)
    const [cpIsSimulating, setCpIsSimulating] = React.useState(false)
    const [cpLastRunRef, setCpLastRunRef] = React.useState<{ start: string; end: string } | null>(null)
    const [innerTab, setInnerTab] = React.useState("input")

    // date display sync
    React.useEffect(() => {
        if (startDate.includes("-")) {
            const [y, m, d] = startDate.split("-")
            setCpStartDateDisplay(`${m}-${d}-${y}`)
        }
    }, [startDate])
    React.useEffect(() => {
        if (endDate.includes("-")) {
            const [y, m, d] = endDate.split("-")
            setCpEndDateDisplay(`${m}-${d}-${y}`)
        }
    }, [endDate])

    const handleRunSimulation = async () => {
        setCpIsSimulating(true)
        setCpSimData(null)
        try {
            await patchProfile({
                positions: [{
                    symbol: inputSymbol || "AAPL",
                    shares: Number(inputShares) || 0,
                    cost_basis: Number(inputCostBasis) || 0,
                    sleeve: "core",
                }],
            })
            const res = await simulateConcentratedPosition({
                strategy: "COVERED_CALL",
                core: {
                    ticker: inputSymbol || "AAPL",
                    initial_shares: Number(inputShares) || 0,
                    cost_basis: Number(inputCostBasis) || 0,
                    starting_cash: Number(inputStartingCash) || 0,
                    start_date: startDate,
                    end_date: endDate,
                },
                covered_call: {
                    coverage_pct: coveredPct,
                    target_delta: targetDelta,
                    target_dte_days: targetDteDays,
                    profit_capture_pct: profitCaptureTarget / 100.0,
                },
                strategy_mode: strategyMode,
                share_reduction_trigger_pct: 0,
                tlh: {
                    harvest_trigger_pct: stopLossMultiple,
                    max_shares_per_month: Number(inputMaxSharesPerMonth) || 200,
                    mode: strategyMode,
                },
                tax: { tax_mode: "OFF" },
            })
            setCpSimData(res)
            setCpLastRunRef({ start: startDate, end: endDate })
            setInnerTab("history")
        } catch (e) {
            console.error("CP simulation failed", e)
        } finally {
            setCpIsSimulating(false)
        }
    }

    return (
        <Tabs value={innerTab} onValueChange={setInnerTab} className="w-full mt-4">
            <TabsList className={INNER_TAB_LIST}>
                <TabsTrigger value="input" className={INNER_TAB_TRIGGER}>1. Input</TabsTrigger>
                <TabsTrigger value="history" className={INNER_TAB_TRIGGER}>2. History</TabsTrigger>
                <TabsTrigger value="future" className={INNER_TAB_TRIGGER}>3. Future</TabsTrigger>
            </TabsList>

            {/* ---- INPUT ---- */}
            <TabsContent value="input" className="pt-6 space-y-6 outline-none">
                <Card className="border-indigo-100 dark:border-indigo-900/30 shadow-sm">
                    <CardHeader className="bg-indigo-50/50 dark:bg-indigo-900/20 pb-4">
                        <CardTitle className="text-base text-indigo-900 dark:text-indigo-100">Portfolio Inputs</CardTitle>
                    </CardHeader>
                    <CardContent className="p-6 space-y-6">
                        <div className="flex flex-col md:flex-row gap-4 items-end">
                            {[
                                { label: "Symbol", value: inputSymbol, setter: (v: any) => setInputSymbol(v), type: "text" },
                                { label: "Shares", value: inputShares, setter: (v: any) => setInputShares(v === "" ? "" : Number(v)), type: "number" },
                                { label: "Cost Basis", value: inputCostBasis, setter: (v: any) => setInputCostBasis(v === "" ? "" : Number(v)), type: "number" },
                                { label: "Starting Cash", value: inputStartingCash, setter: (v: any) => setInputStartingCash(v === "" ? "" : Number(v)), type: "number" },
                                { label: "TLH Inventory", value: inputTlhInventory, setter: (v: any) => setInputTlhInventory(v === "" ? "" : Number(v)), type: "number" },
                            ].map(({ label, value, setter, type }) => (
                                <div key={label} className="space-y-2 flex-1">
                                    <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{label}</label>
                                    <input type={type} value={value} onChange={e => setter(e.target.value)} className={INPUT_CLS} />
                                </div>
                            ))}
                        </div>

                        <div className="flex flex-col md:flex-row gap-4 border-t border-zinc-100 dark:border-zinc-800 pt-5">
                            <div className="space-y-2 flex-1">
                                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Start Date (MM-DD-YYYY)</label>
                                <input type="text" placeholder="MM-DD-YYYY" value={cpStartDateDisplay}
                                    onChange={e => {
                                        const val = e.target.value; setCpStartDateDisplay(val)
                                        const parts = val.split("-")
                                        if (parts.length === 3 && parts[2]?.length === 4 && parts[0]?.length === 2 && parts[1]?.length === 2)
                                            setStartDate(`${parts[2]}-${parts[0]}-${parts[1]}`)
                                    }}
                                    className={INPUT_CLS} />
                            </div>
                            <div className="space-y-2 flex-1">
                                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">End Date (MM-DD-YYYY)</label>
                                <input type="text" placeholder="MM-DD-YYYY" value={cpEndDateDisplay}
                                    onChange={e => {
                                        const val = e.target.value; setCpEndDateDisplay(val)
                                        const parts = val.split("-")
                                        if (parts.length === 3 && parts[2]?.length === 4 && parts[0]?.length === 2 && parts[1]?.length === 2)
                                            setEndDate(`${parts[2]}-${parts[0]}-${parts[1]}`)
                                    }}
                                    className={INPUT_CLS} />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Strategy Mode</label>
                            <div className="flex bg-zinc-100 dark:bg-zinc-900 p-1 rounded-lg w-full max-w-lg border border-zinc-200 dark:border-zinc-800">
                                {(["harvest", "tax_neutral"] as const).map(mode => (
                                    <button key={mode} onClick={() => setStrategyMode(mode)}
                                        className={`flex-1 text-sm font-medium py-1.5 rounded-md transition-all ${strategyMode === mode ? "bg-white dark:bg-zinc-800 shadow-sm text-zinc-900 dark:text-zinc-100" : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"}`}>
                                        {mode === "harvest" ? "Harvest & Hold (TLH)" : "Tax-Neutral Sell"}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 border-t border-zinc-100 dark:border-zinc-800 pt-5">
                            {[
                                { label: "Coverage %", value: coveredPct, min: 0, max: 100, step: 10, setter: setCoveredPct, display: `${coveredPct}%` },
                                { label: "Target Delta", value: targetDelta, min: 0.05, max: 0.50, step: 0.05, setter: setTargetDelta, display: targetDelta.toFixed(2) },
                                { label: "Option Duration (Days)", value: targetDteDays, min: 14, max: 90, step: 7, setter: setTargetDteDays, display: `${targetDteDays}d` },
                                { label: "Profit Capture %", value: profitCaptureTarget, min: 0, max: 100, step: 5, setter: setProfitCaptureTarget, display: `${profitCaptureTarget}%` },
                                { label: "Stop Loss Multiple", value: stopLossMultiple, min: 1.0, max: 5.0, step: 0.5, setter: setStopLossMultiple, display: `${stopLossMultiple}x` },
                            ].map(({ label, value, min, max, step, setter, display }) => (
                                <div key={label} className="space-y-3">
                                    <div className="flex justify-between items-center text-sm font-medium">
                                        <span>{label}</span>
                                        <span>{display}</span>
                                    </div>
                                    <Slider value={[value]} min={min} max={max} step={step} onValueChange={v => setter(v[0] as any)} />
                                </div>
                            ))}
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Max Shares / Month</label>
                                <input type="number" value={inputMaxSharesPerMonth}
                                    onChange={e => setInputMaxSharesPerMonth(e.target.value === "" ? "" : Number(e.target.value))}
                                    className={`${INPUT_CLS} max-w-[160px]`} />
                            </div>
                        </div>

                        <Button onClick={handleRunSimulation}
                            disabled={cpIsSimulating || !inputShares || Number(inputShares) <= 0 || startDate > endDate}
                            className="bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-50">
                            {cpIsSimulating ? "Simulating..." : "Run Simulation"}
                        </Button>
                    </CardContent>
                </Card>
            </TabsContent>

            {/* ---- HISTORY ---- */}
            <TabsContent value="history" className="pt-8 space-y-6 outline-none">
                {!cpSimData ? (
                    <EmptyState message="Configure inputs and run a simulation to see historical performance." />
                ) : (
                    <div className="space-y-8 animate-in fade-in zoom-in-95 duration-300">
                        <div className="flex items-center justify-between px-2">
                            <h4 className="flex flex-col py-1">
                                <span className="text-sm font-medium flex items-center gap-2">
                                    Simulation Results
                                    <Badge variant="secondary" className="text-[10px] bg-zinc-100 dark:bg-zinc-800 font-normal">Deterministic Unwind</Badge>
                                </span>
                                {cpLastRunRef && (
                                    <span className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                                        Simulation: {cpLastRunRef.start} → {cpLastRunRef.end}
                                    </span>
                                )}
                            </h4>
                        </div>

                        {/* Chart */}
                        <div className="h-[300px] w-full bg-white dark:bg-zinc-950 border border-zinc-100 dark:border-zinc-800 rounded-xl p-4">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={cpSimData.time_series}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e4e4e7" />
                                    <XAxis dataKey="Date" tickFormatter={v => new Date(v).toLocaleDateString()} minTickGap={30} fontSize={12} stroke="#a1a1aa" />
                                    <YAxis yAxisId="left" orientation="left" tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} fontSize={12} stroke="#a1a1aa" />
                                    <YAxis yAxisId="right" orientation="right" fontSize={12} stroke="#a1a1aa" />
                                    <RechartsTooltip
                                        labelFormatter={v => new Date(v).toLocaleDateString()}
                                        formatter={(value: any, name: any) => [
                                            name === "Shares" ? value : `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
                                            String(name).replace("_", " "),
                                        ]}
                                    />
                                    <Legend />
                                    <Line yAxisId="left" type="monotone" dataKey="Price" stroke="#a855f7" dot={false} strokeWidth={2} />
                                    <Line yAxisId="right" type="stepAfter" dataKey="Shares" stroke="#3b82f6" dot={false} strokeWidth={2} />
                                    <Line yAxisId="left" type="monotone" dataKey="Cash" stroke="#10b981" dot={false} strokeWidth={2} />
                                    <Line yAxisId="left" type="monotone" dataKey="Portfolio_Value" stroke="#6366f1" dot={false} strokeWidth={2} />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>

                        {/* 5 Metric Cards */}
                        <div className="grid grid-cols-5 gap-3 w-full">
                            {[
                                { label: "Shares Sold", value: String(cpSimData.summary.shares_sold || 0), color: "text-zinc-900 dark:text-zinc-100" },
                                { label: "Cash", value: formatCurrency(cpSimData.summary.final_cash || 0), color: "text-emerald-600 dark:text-emerald-400" },
                                { label: "Net Option Result", value: formatCurrency(cpSimData.summary.net_option_result || cpSimData.summary.realized_option_pnl || 0), color: (cpSimData.summary.net_option_result || 0) < 0 ? "text-red-600 dark:text-red-500" : "text-green-600 dark:text-green-500" },
                                { label: "Total Return", value: `${(cpSimData.summary.total_return_pct || 0).toFixed(2)}%`, color: (cpSimData.summary.total_return_pct || 0) >= 0 ? "text-green-600 dark:text-green-500" : "text-red-600 dark:text-red-500" },
                            ].map(({ label, value, color }) => (
                                <div key={label} className="bg-white dark:bg-zinc-950 rounded-xl border border-zinc-200 dark:border-zinc-800 p-3 h-[90px] flex flex-col justify-between">
                                    <div className="text-[11px] text-zinc-500 uppercase tracking-wide">{label}</div>
                                    <div className={`font-semibold leading-none truncate tabular-nums text-[clamp(16px,1.8vw,22px)] ${color}`}>{value}</div>
                                </div>
                            ))}
                            {/* Assignment Risk */}
                            <div className="bg-white dark:bg-zinc-950 rounded-xl border border-zinc-200 dark:border-zinc-800 p-3 h-[90px] flex flex-col justify-between">
                                <div className="text-[11px] text-zinc-500 uppercase tracking-wide">Assignment Risk</div>
                                <div className="flex flex-col">
                                    <div className={`font-semibold text-sm truncate ${targetDelta <= 0.20 ? "text-green-600 dark:text-green-500" : targetDelta <= 0.30 ? "text-amber-500 dark:text-amber-400" : "text-red-600 dark:text-red-500"}`}>
                                        {targetDelta <= 0.20 ? "LOW" : targetDelta <= 0.30 ? "MEDIUM" : "HIGH"}
                                    </div>
                                    <div className="text-[10px] text-zinc-400">~{(targetDelta * 100).toFixed(0)}% probability</div>
                                </div>
                            </div>
                        </div>

                        {/* Tax Loss Inventory */}
                        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 overflow-hidden">
                            <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50 flex items-center justify-between">
                                <h3 className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">Tax Loss Inventory</h3>
                                <Badge className="text-xs bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400">
                                    {strategyMode === "harvest" ? "HARVEST_MODE" : "TAX_NEUTRAL_MODE"}
                                </Badge>
                            </div>
                            <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-6">
                                {[
                                    { label: "TLH Available", value: `$${(cpSimData.summary.tax_loss_inventory || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, color: "text-zinc-900 dark:text-zinc-100" },
                                    { label: "TLH Used", value: `$${(cpSimData.summary.tlh_used || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, color: "text-zinc-900 dark:text-zinc-100" },
                                    { label: "TLH Remaining", value: `$${(cpSimData.summary.tlh_inventory_remaining || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, color: "text-emerald-600 dark:text-emerald-400" },
                                ].map(({ label, value, color }) => (
                                    <div key={label} className="space-y-1">
                                        <span className="text-xs font-medium text-zinc-500">{label}</span>
                                        <div className={`text-lg font-semibold ${color}`}>{value}</div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Tax Utilization */}
                        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 overflow-hidden">
                            <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50">
                                <h3 className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">Tax Utilization</h3>
                            </div>
                            <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-6">
                                <div className="space-y-1">
                                    <span className="text-xs font-medium text-zinc-500">Gain Per Share</span>
                                    <div className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                                        ${(cpSimData.summary.gain_per_share || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                                    </div>
                                </div>
                                <div className="space-y-1">
                                    <span className="text-xs font-medium text-zinc-500">Potential Tax Savings</span>
                                    <div className="text-lg font-semibold text-emerald-600 dark:text-emerald-400">
                                        ${(Math.max(0, cpSimData.summary.tlh_inventory_remaining || 0) * 0.37).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                    </div>
                                </div>
                                <div className="space-y-1">
                                    <span className="text-xs font-medium text-zinc-500">Tax-Neutral Shares</span>
                                    <div className="text-lg font-semibold text-indigo-600 dark:text-indigo-400">
                                        {Math.floor(cpSimData.summary.tax_neutral_shares_available || 0).toLocaleString()} <span className="text-xs text-zinc-500 font-normal">shares</span>
                                    </div>
                                </div>
                            </div>
                            <div className="px-4 py-3 bg-indigo-50/50 dark:bg-indigo-900/20 border-t border-indigo-100 dark:border-indigo-900/50 text-sm text-indigo-700 dark:text-indigo-400 text-center font-medium">
                                You can sell up to {Math.floor(cpSimData.summary.tax_neutral_shares_available || 0).toLocaleString()} shares tax-free
                            </div>
                        </div>

                        {/* Yearly Tax Ledger + Bar Chart */}
                        {cpSimData.summary.yearly_tax_ledger && Object.keys(cpSimData.summary.yearly_tax_ledger).length > 0 && (
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 overflow-hidden flex flex-col">
                                    <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50">
                                        <h3 className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">Yearly Tax Report</h3>
                                    </div>
                                    <div className="flex-1 overflow-auto max-h-[350px]">
                                        <Table>
                                            <TableHeader className="bg-zinc-50/50 dark:bg-zinc-900/20 sticky top-0 backdrop-blur-sm z-10">
                                                <TableRow>
                                                    <TableHead className="w-[80px]">Year</TableHead>
                                                    <TableHead className="text-right">Option Income</TableHead>
                                                    <TableHead className="text-right text-rose-600 dark:text-rose-500">Option Losses</TableHead>
                                                    <TableHead className="text-right">Net Capital Result</TableHead>
                                                    <TableHead className="text-right text-indigo-600 dark:text-indigo-400">TLH Generated</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {Object.entries(cpSimData.summary.yearly_tax_ledger)
                                                    .sort(([y1], [y2]) => Number(y1) - Number(y2))
                                                    .map(([year, data]: [string, any]) => (
                                                        <TableRow key={year}>
                                                            <TableCell className="font-medium text-xs">{year}</TableCell>
                                                            <TableCell className="text-xs text-right">${data.option_income.toLocaleString(undefined, { maximumFractionDigits: 0 })}</TableCell>
                                                            <TableCell className="text-xs text-right text-rose-600 dark:text-rose-400">${data.option_losses.toLocaleString(undefined, { maximumFractionDigits: 0 })}</TableCell>
                                                            <TableCell className={`text-xs text-right font-medium ${data.net_capital_result < 0 ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`}>
                                                                {data.net_capital_result < 0 ? "-" : ""}${Math.abs(data.net_capital_result).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                                            </TableCell>
                                                            <TableCell className="text-xs text-right font-medium text-indigo-600 dark:text-indigo-400">${data.tlh_generated.toLocaleString(undefined, { maximumFractionDigits: 0 })}</TableCell>
                                                        </TableRow>
                                                    ))}
                                                <TableRow className="bg-zinc-50 dark:bg-zinc-900/50 border-t-2 border-zinc-200 dark:border-zinc-800">
                                                    <TableCell className="font-bold text-xs">Total</TableCell>
                                                    <TableCell className="font-bold text-xs text-right">${Object.values(cpSimData.summary.yearly_tax_ledger).reduce((a: number, v: any) => a + v.option_income, 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</TableCell>
                                                    <TableCell className="font-bold text-xs text-right text-rose-600 dark:text-rose-500">${Object.values(cpSimData.summary.yearly_tax_ledger).reduce((a: number, v: any) => a + v.option_losses, 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</TableCell>
                                                    <TableCell className="font-bold text-xs text-right">${Object.values(cpSimData.summary.yearly_tax_ledger).reduce((a: number, v: any) => a + v.net_capital_result, 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</TableCell>
                                                    <TableCell className="font-bold text-xs text-right text-indigo-600 dark:text-indigo-500">${(cpSimData.summary.tax_loss_inventory || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</TableCell>
                                                </TableRow>
                                            </TableBody>
                                        </Table>
                                    </div>
                                </div>

                                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 overflow-hidden flex flex-col min-h-[350px]">
                                    <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50">
                                        <h3 className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">Income vs TLH Generation</h3>
                                        <p className="text-xs text-zinc-500 mt-1">
                                            Strategy generated ${(cpSimData.summary.option_income || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })} income and ${(cpSimData.summary.tax_loss_inventory || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })} tax losses over the period.
                                        </p>
                                    </div>
                                    <div className="p-4 flex-1 w-full h-full min-h-[300px]">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart
                                                data={Object.entries(cpSimData.summary.yearly_tax_ledger)
                                                    .sort(([y1], [y2]) => Number(y1) - Number(y2))
                                                    .map(([year, data]: [string, any]) => ({
                                                        year,
                                                        "Income Generated": data.option_income,
                                                        "Tax Loss Generated": data.tlh_generated,
                                                        Net: data.net_capital_result,
                                                    }))}
                                                margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e4e4e7" />
                                                <XAxis dataKey="year" fontSize={12} stroke="#a1a1aa" />
                                                <YAxis tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} fontSize={12} stroke="#a1a1aa" />
                                                <RechartsTooltip
                                                    formatter={(value: any, name: any) => [`$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, name]}
                                                    cursor={{ fill: "rgba(230,230,230,0.1)" }}
                                                />
                                                <Legend />
                                                <Bar dataKey="Income Generated" fill="#10b981" radius={[4, 4, 0, 0]}>
                                                    <LabelList dataKey="Income Generated" position="top" formatter={(v: any) => v > 0 ? `$${(v / 1000).toFixed(0)}k` : ""} fill="#10b981" fontSize={10} />
                                                </Bar>
                                                <Bar dataKey="Tax Loss Generated" fill="#6366f1" radius={[4, 4, 0, 0]}>
                                                    <LabelList dataKey="Tax Loss Generated" position="top" formatter={(v: any) => v > 0 ? `$${(v / 1000).toFixed(0)}k` : ""} fill="#6366f1" fontSize={10} />
                                                </Bar>
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Audit Log */}
                        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 overflow-hidden">
                            <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50">
                                <h3 className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">Audit Log</h3>
                            </div>
                            <div className="max-h-[300px] overflow-auto">
                                <Table>
                                    <TableHeader className="bg-zinc-50/50 dark:bg-zinc-900/20 sticky top-0 backdrop-blur-sm">
                                        <TableRow>
                                            <TableHead className="w-[100px]">Date</TableHead>
                                            <TableHead>Event</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {cpSimData.summary.audit_log?.map((log: string, i: number) => {
                                            const parts = log.split(" | ")
                                            return (
                                                <TableRow key={i}>
                                                    <TableCell className="font-medium text-xs whitespace-nowrap align-top">{parts[0]}</TableCell>
                                                    <TableCell className="text-xs text-zinc-600 dark:text-zinc-400 whitespace-pre-wrap align-top">{parts.slice(1).join(" | ")}</TableCell>
                                                </TableRow>
                                            )
                                        })}
                                        {(!cpSimData.summary.audit_log || cpSimData.summary.audit_log.length === 0) && (
                                            <TableRow>
                                                <TableCell colSpan={2} className="text-center py-6 text-zinc-500">No events recorded</TableCell>
                                            </TableRow>
                                        )}
                                    </TableBody>
                                </Table>
                            </div>
                        </div>
                    </div>
                )}
            </TabsContent>

            <TabsContent value="future" className="pt-8 outline-none"><FuturePlaceholder /></TabsContent>
        </Tabs>
    )
}

// ===========================================================================
// MP Engine Tab
// ===========================================================================
function MPStrategy() {
    const [mpCapital, setMpCapital] = React.useState<number | "">(500000)
    const [mpRiskTarget, setMpRiskTarget] = React.useState(65)
    const [mpStartDate, setMpStartDate] = React.useState(getTenYearsAgoStr())
    const [mpEndDate, setMpEndDate] = React.useState(getTodayStr())
    const [mpStartDateDisplay, setMpStartDateDisplay] = React.useState("")
    const [mpEndDateDisplay, setMpEndDateDisplay] = React.useState("")

    const [mpAllocations, setMpAllocations] = React.useState<FrontierProposalResponse | null>(null)
    const [mpSimData, setMpSimData] = React.useState<any>(null)
    const [mpIsLoading, setMpIsLoading] = React.useState(false)
    const [mpLastRunRef, setMpLastRunRef] = React.useState<{ start: string; end: string } | null>(null)
    const [innerTab, setInnerTab] = React.useState("input")

    React.useEffect(() => {
        if (mpStartDate.includes("-")) { const [y, m, d] = mpStartDate.split("-"); setMpStartDateDisplay(`${m}-${d}-${y}`) }
    }, [mpStartDate])
    React.useEffect(() => {
        if (mpEndDate.includes("-")) { const [y, m, d] = mpEndDate.split("-"); setMpEndDateDisplay(`${m}-${d}-${y}`) }
    }, [mpEndDate])

    const handleGenerate = async () => {
        setMpIsLoading(true)
        setMpSimData(null)
        try {
            const res = await postFrontierPropose(mpRiskTarget)
            setMpAllocations(res)
            if (mpCapital) {
                const simRes = await postMPSimulate({
                    target_weights: res.target_weights,
                    initial_capital: Number(mpCapital),
                    start_date: mpStartDate,
                    end_date: mpEndDate,
                })
                setMpSimData(simRes)
                setMpLastRunRef({ start: mpStartDate, end: mpEndDate })
                setInnerTab("history")
            }
        } catch (e) {
            console.error("MP generate failed", e)
        } finally {
            setMpIsLoading(false)
        }
    }

    return (
        <Tabs value={innerTab} onValueChange={setInnerTab} className="w-full mt-4">
            <TabsList className={INNER_TAB_LIST}>
                <TabsTrigger value="input" className={INNER_TAB_TRIGGER}>1. Input</TabsTrigger>
                <TabsTrigger value="history" className={INNER_TAB_TRIGGER}>2. History</TabsTrigger>
                <TabsTrigger value="future" className={INNER_TAB_TRIGGER}>3. Future</TabsTrigger>
            </TabsList>

            {/* ---- INPUT ---- */}
            <TabsContent value="input" className="pt-6 space-y-6 outline-none">
                <Card className="border-indigo-100 dark:border-indigo-900/30 shadow-sm">
                    <CardHeader>
                        <CardTitle className="text-base">Managed Portfolio (MP) Strategy</CardTitle>
                        <CardDescription>Configure target risk for your managed portfolio.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Initial Capital</label>
                            <div className="relative">
                                <div className="absolute left-3 top-2.5 text-zinc-500 text-sm pointer-events-none">$</div>
                                <input type="text" value={mpCapital}
                                    onChange={e => { const v = e.target.value.replace(/[^0-9.]/g, ""); setMpCapital(v === "" ? "" : Number(v)) }}
                                    className={`${INPUT_CLS} pl-7`} />
                            </div>
                        </div>

                        <div className="space-y-3">
                            <div className="flex justify-between items-center text-sm font-medium">
                                <span>MP Risk Target (1–100)</span>
                                <span>{mpRiskTarget}</span>
                            </div>
                            <Slider value={[mpRiskTarget]} min={1} max={100} step={1} onValueChange={v => setMpRiskTarget(v[0])} />
                        </div>

                        <div className="space-y-3">
                            <div className="text-sm font-medium">Simulation Period</div>
                            <div className="flex gap-4">
                                {[
                                    { label: "Start (MM-DD-YYYY)", display: mpStartDateDisplay, setDisplay: setMpStartDateDisplay, setInternal: setMpStartDate },
                                    { label: "End (MM-DD-YYYY)", display: mpEndDateDisplay, setDisplay: setMpEndDateDisplay, setInternal: setMpEndDate },
                                ].map(({ label, display, setDisplay, setInternal }) => (
                                    <div key={label} className="space-y-1.5 flex-1">
                                        <span className="text-xs text-zinc-500 font-medium">{label}</span>
                                        <input type="text" placeholder="MM-DD-YYYY" value={display}
                                            onChange={e => {
                                                const val = e.target.value; setDisplay(val)
                                                const parts = val.split("-")
                                                if (parts.length === 3 && parts[2]?.length === 4 && parts[0]?.length === 2 && parts[1]?.length === 2)
                                                    setInternal(`${parts[2]}-${parts[0]}-${parts[1]}`)
                                            }}
                                            className={INPUT_CLS} />
                                    </div>
                                ))}
                            </div>
                        </div>

                        <Button onClick={handleGenerate} disabled={mpIsLoading || !mpCapital}
                            className="w-full bg-emerald-600 hover:bg-emerald-700 text-white">
                            {mpIsLoading ? "Optimizing..." : "Generate Optimized Allocation"}
                        </Button>
                    </CardContent>
                </Card>
            </TabsContent>

            {/* ---- HISTORY ---- */}
            <TabsContent value="history" className="pt-8 space-y-6 outline-none">
                {!mpSimData ? (
                    <EmptyState message={mpAllocations ? "Click 'Generate Optimized Allocation' to run the backtest." : "Generate an Optimized Allocation first in the Input tab."} />
                ) : (
                    <div className="space-y-8 animate-in fade-in zoom-in-95 duration-300">
                        <div className="flex items-center justify-between px-2">
                            <h4 className="flex flex-col py-1">
                                <span className="text-sm font-medium flex items-center gap-2">
                                    Managed Portfolio: Historical Performance
                                    <Badge variant="secondary" className="text-[10px] bg-zinc-100 dark:bg-zinc-800 font-normal">Backtest</Badge>
                                </span>
                                {mpLastRunRef && (
                                    <span className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Simulation: {mpLastRunRef.start} → {mpLastRunRef.end}</span>
                                )}
                            </h4>
                        </div>

                        <div className="h-[300px] w-full bg-white dark:bg-zinc-950 border border-zinc-100 dark:border-zinc-800 rounded-xl p-4">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={mpSimData.time_series}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e4e4e7" />
                                    <XAxis dataKey="date" tickFormatter={v => new Date(v).toLocaleDateString()} minTickGap={30} fontSize={12} stroke="#a1a1aa" />
                                    <YAxis tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} fontSize={12} stroke="#a1a1aa" domain={["auto", "auto"]} />
                                    <RechartsTooltip
                                        labelFormatter={v => new Date(v).toLocaleDateString()}
                                        formatter={(value: any) => [`$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, "Portfolio Value"]}
                                    />
                                    <Line type="monotone" dataKey="value" stroke="#10b981" dot={false} strokeWidth={2} />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                            <MetricCard title="Total Return" value={`${(mpSimData.summary.total_return_pct || 0).toFixed(2)}%`} className="bg-white dark:bg-zinc-950" />
                            <MetricCard title="Annualized Return" value={`${(mpSimData.summary.annualized_return_pct || 0).toFixed(2)}%`} className="bg-white dark:bg-zinc-950" />
                            <MetricCard title="Volatility (Std Dev)" value={`${(mpSimData.summary.volatility_pct || 0).toFixed(2)}%`} className="bg-white dark:bg-zinc-950" />
                            <MetricCard title="Sharpe Ratio" value={`${(mpSimData.summary.sharpe_ratio || 0).toFixed(2)}`} trend={{ value: "4% RFR" }} className="bg-white dark:bg-zinc-950" />
                            <MetricCard title="Max Drawdown" value={`${(mpSimData.summary.max_drawdown_pct || 0).toFixed(2)}%`} className="bg-white dark:bg-zinc-950" />
                        </div>

                        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 overflow-hidden">
                            <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50">
                                <h3 className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">Monthly Rebalancing Log</h3>
                            </div>
                            <div className="max-h-[300px] overflow-auto">
                                <Table>
                                    <TableHeader className="bg-zinc-50/50 dark:bg-zinc-900/20 sticky top-0 backdrop-blur-sm z-10">
                                        <TableRow>
                                            <TableHead className="w-[100px]">Date</TableHead>
                                            <TableHead>Portfolio Value</TableHead>
                                            <TableHead>Monthly PnL</TableHead>
                                            <TableHead>Top Holding</TableHead>
                                            <TableHead>Action</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {mpSimData.audit_log?.map((log: any, i: number) => (
                                            <TableRow key={i}>
                                                <TableCell className="font-medium text-xs whitespace-nowrap">{log.date}</TableCell>
                                                <TableCell className="text-xs text-zinc-900 dark:text-zinc-100 whitespace-nowrap">${Number(log.portfolio_value).toLocaleString(undefined, { maximumFractionDigits: 0 })}</TableCell>
                                                <TableCell className={`text-xs whitespace-nowrap ${log.monthly_pnl >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-500"}`}>
                                                    {log.monthly_pnl >= 0 ? "+" : ""}${Number(log.monthly_pnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                                </TableCell>
                                                <TableCell className="text-xs text-indigo-600 dark:text-indigo-400 whitespace-nowrap">{log.top_holding}</TableCell>
                                                <TableCell className="text-xs text-zinc-500 whitespace-nowrap">{log.action}</TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        </div>
                        {mpSimData.audit_log && mpSimData.audit_log.length > 0 && mpSimData.audit_log[0].math_verified && (
                            <div className="flex justify-end pt-2 px-2">
                                <span className="text-[10px] text-zinc-500 flex items-center gap-1.5">
                                    <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                                    Reconciliation Status: Verified (Sum of Assets = Total Value)
                                </span>
                            </div>
                        )}
                    </div>
                )}
            </TabsContent>

            <TabsContent value="future" className="pt-8 outline-none"><FuturePlaceholder /></TabsContent>
        </Tabs>
    )
}

// ===========================================================================
// Income Engine Tab
// ===========================================================================
function IncomeStrategy() {
    const [anchorIncomeCapital, setAnchorIncomeCapital] = React.useState<number | "">(1000000)
    const [anchorIncomeStartDate, setAnchorIncomeStartDate] = React.useState(getTenYearsAgoStr())
    const [anchorIncomeEndDate, setAnchorIncomeEndDate] = React.useState(getTodayStr())
    const [aiStartDateDisplay, setAiStartDateDisplay] = React.useState("")
    const [aiEndDateDisplay, setAiEndDateDisplay] = React.useState("")
    const [anchorIncomeReinvestPct, setAnchorIncomeReinvestPct] = React.useState(0)

    const [incomeSimData, setIncomeSimData] = React.useState<any>(null)
    const [incomeIsSimulating, setIncomeIsSimulating] = React.useState(false)
    const [incomeLastRunRef, setIncomeLastRunRef] = React.useState<{ start: string; end: string } | null>(null)
    const [innerTab, setInnerTab] = React.useState("input")

    React.useEffect(() => {
        if (anchorIncomeStartDate.includes("-")) { const [y, m, d] = anchorIncomeStartDate.split("-"); setAiStartDateDisplay(`${m}-${d}-${y}`) }
    }, [anchorIncomeStartDate])
    React.useEffect(() => {
        if (anchorIncomeEndDate.includes("-")) { const [y, m, d] = anchorIncomeEndDate.split("-"); setAiEndDateDisplay(`${m}-${d}-${y}`) }
    }, [anchorIncomeEndDate])

    const handleRunSimulation = async () => {
        if (!anchorIncomeCapital) return
        setIncomeSimData(null)
        setIncomeIsSimulating(true)
        try {
            const res = await postAnchorIncomeSimulate({
                initial_capital: Number(anchorIncomeCapital),
                start_date: anchorIncomeStartDate,
                end_date: anchorIncomeEndDate,
                reinvest_pct: anchorIncomeReinvestPct,
            })
            setIncomeSimData(res)
            setIncomeLastRunRef({ start: anchorIncomeStartDate, end: anchorIncomeEndDate })
            setInnerTab("history")
        } catch (e) {
            console.error("Income simulation failed", e)
        } finally {
            setIncomeIsSimulating(false)
        }
    }

    return (
        <Tabs value={innerTab} onValueChange={setInnerTab} className="w-full mt-4">
            <TabsList className={INNER_TAB_LIST}>
                <TabsTrigger value="input" className={INNER_TAB_TRIGGER}>1. Input</TabsTrigger>
                <TabsTrigger value="history" className={INNER_TAB_TRIGGER}>2. History</TabsTrigger>
                <TabsTrigger value="future" className={INNER_TAB_TRIGGER}>3. Future</TabsTrigger>
            </TabsList>

            {/* ---- INPUT ---- */}
            <TabsContent value="input" className="pt-6 space-y-6 outline-none">
                <Card className="border-indigo-100 dark:border-indigo-900/30 shadow-sm">
                    <CardHeader>
                        <CardTitle className="text-base">Anchor Income Strategy</CardTitle>
                        <CardDescription>Configure parameters for the drawdown-based income strategy.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Initial Capital</label>
                            <div className="relative">
                                <div className="absolute left-3 top-2.5 text-zinc-500 text-sm pointer-events-none">$</div>
                                <input type="text" value={anchorIncomeCapital}
                                    onChange={e => { const v = e.target.value.replace(/[^0-9.]/g, ""); setAnchorIncomeCapital(v === "" ? "" : Number(v)) }}
                                    className={`${INPUT_CLS} pl-7`} />
                            </div>
                        </div>

                        <div className="flex flex-col md:flex-row gap-4">
                            {[
                                { label: "Start Date (MM-DD-YYYY)", display: aiStartDateDisplay, setDisplay: setAiStartDateDisplay, setInternal: setAnchorIncomeStartDate },
                                { label: "End Date (MM-DD-YYYY)", display: aiEndDateDisplay, setDisplay: setAiEndDateDisplay, setInternal: setAnchorIncomeEndDate },
                            ].map(({ label, display, setDisplay, setInternal }) => (
                                <div key={label} className="space-y-2 flex-1">
                                    <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{label}</label>
                                    <input type="text" placeholder="MM-DD-YYYY" value={display}
                                        onChange={e => {
                                            const val = e.target.value; setDisplay(val)
                                            const parts = val.split("-")
                                            if (parts.length === 3 && parts[2]?.length === 4 && parts[0]?.length === 2 && parts[1]?.length === 2)
                                                setInternal(`${parts[2]}-${parts[0]}-${parts[1]}`)
                                        }}
                                        className={INPUT_CLS} />
                                </div>
                            ))}
                        </div>

                        <div className="space-y-4 p-4 rounded-xl bg-indigo-50/30 dark:bg-indigo-900/10 border border-indigo-100/50 dark:border-indigo-900/30">
                            <div className="flex justify-between items-center">
                                <div>
                                    <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Income Reinvestment %</p>
                                    <p className="text-xs text-zinc-500 mt-0.5">Portion of monthly yield that compounds in cash</p>
                                </div>
                                <span className="text-lg font-bold text-indigo-600 dark:text-indigo-400">{anchorIncomeReinvestPct}%</span>
                            </div>
                            <Slider value={[anchorIncomeReinvestPct]} max={100} step={5} onValueChange={v => setAnchorIncomeReinvestPct(v[0])} className="py-2" />
                            <div className="flex justify-between text-[10px] text-zinc-400 font-medium px-1">
                                <span>0% (Withdraw All)</span><span>50%</span><span>100% (Reinvest All)</span>
                            </div>
                        </div>

                        <Button onClick={handleRunSimulation} disabled={incomeIsSimulating || !anchorIncomeCapital}
                            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white">
                            {incomeIsSimulating ? "Simulating..." : "Run Historical Simulation"}
                        </Button>
                    </CardContent>
                </Card>
            </TabsContent>

            {/* ---- HISTORY ---- */}
            <TabsContent value="history" className="pt-8 space-y-6 outline-none">
                {!incomeSimData ? (
                    <EmptyState message="Go to the Input tab to set parameters and run a simulation." />
                ) : (() => {
                    const events: any[] = incomeSimData.events || []
                    return (
                        <div className="space-y-8 animate-in fade-in zoom-in-95 duration-300">
                            <div className="flex items-center justify-between px-2">
                                <h4 className="flex flex-col py-1">
                                    <span className="text-sm font-medium flex items-center gap-2">
                                        Anchor Income Performance
                                        <Badge variant="secondary" className="text-[10px] bg-zinc-100 dark:bg-zinc-800 font-normal">Backtest</Badge>
                                    </span>
                                    {incomeLastRunRef && (
                                        <span className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Simulation: {incomeLastRunRef.start} → {incomeLastRunRef.end}</span>
                                    )}
                                </h4>
                            </div>

                            {/* Strategy Line Chart */}
                            <div className="h-[340px] w-full bg-white dark:bg-zinc-950 border border-zinc-100 dark:border-zinc-800 rounded-xl p-4">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={incomeSimData.time_series}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e4e4e7" />
                                        <XAxis dataKey="Date" tickFormatter={v => new Date(v).toLocaleDateString()} minTickGap={30} fontSize={12} stroke="#a1a1aa" />
                                        <YAxis tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} fontSize={12} stroke="#a1a1aa" domain={["auto", "auto"]} />
                                        <RechartsTooltip
                                            labelFormatter={v => new Date(v).toLocaleDateString()}
                                            formatter={(value: any, name: any) => [`$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, name.replace(/_/g, " ")]}
                                        />
                                        <Legend />
                                        <Line type="monotone" dataKey="Strategy_Value" stroke="#10b981" dot={false} strokeWidth={2} name="Strategy Value" />
                                        <Line type="monotone" dataKey="Pure_QQQ_Value" stroke="#6366f1" dot={false} strokeWidth={2} name="Pure QQQ" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>

                            {/* Income Bar Chart */}
                            <div className="h-[180px] w-full bg-white dark:bg-zinc-950 border border-zinc-100 dark:border-zinc-800 rounded-xl p-4">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={incomeSimData.time_series}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e4e4e7" />
                                        <XAxis dataKey="Date" tick={false} axisLine={false} height={10} />
                                        <YAxis tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} fontSize={12} stroke="#a1a1aa" orientation="right" />
                                        <RechartsTooltip
                                            labelFormatter={v => new Date(v).toLocaleDateString()}
                                            formatter={(value: any) => [`$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, "Cumulative Income"]}
                                        />
                                        <Bar dataKey="Cumulative_Income" fill="#f59e0b" name="Cumulative Paid to Wait" />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>

                            {/* Summary Cards — The Big Six */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-y-6 gap-x-12 bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 shadow-sm">
                                {[
                                    { label: "Final Value", value: `$${Number(incomeSimData.summary.final_strategy_value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, color: "text-emerald-600 dark:text-emerald-400" },
                                    { label: "Total Return", value: `${Number(incomeSimData.summary.total_strategy_return_pct).toFixed(1)}%`, color: "text-emerald-600 dark:text-emerald-400" },
                                    { label: "Net Wealth", value: `$${Number(incomeSimData.summary.final_strategy_value + incomeSimData.summary.total_withdrawn_income).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, color: "text-emerald-600 dark:text-emerald-400" },
                                    { label: "Total Dividends", value: `$${Number(incomeSimData.summary.final_cumulative_income).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, color: "text-emerald-600 dark:text-emerald-400" },
                                    { label: "Deepest Portfolio Drop", value: `${Number(incomeSimData.summary.portfolio_max_drawdown || 0).toFixed(1)}%`, color: "text-rose-600 dark:text-rose-400" },
                                    { label: "Deepest QQQ Drop", value: `${Number(incomeSimData.summary.qqq_max_drawdown || 0).toFixed(1)}%`, color: "text-rose-600 dark:text-rose-400" },
                                ].map(({ label, value, color }) => (
                                    <div key={label} className="flex flex-col gap-1">
                                        <span className="text-[10px] text-zinc-500 font-normal uppercase tracking-wider">{label}</span>
                                        <span className={`text-xl font-medium ${color}`}>{value}</span>
                                    </div>
                                ))}
                            </div>

                            {/* Tactical Decision Log */}
                            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 overflow-hidden">
                                <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50 flex items-center justify-between">
                                    <h3 className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">Tactical Decision Log</h3>
                                    <Badge variant="outline" className="text-xs">{events.length} events</Badge>
                                </div>
                                <div className="max-h-[400px] overflow-auto">
                                    <Table>
                                        <TableHeader className="bg-zinc-50/50 dark:bg-zinc-900/20 sticky top-0 backdrop-blur-sm z-10">
                                            <TableRow>
                                                <TableHead className="w-[90px]">Date</TableHead>
                                                <TableHead className="w-[80px]">Type</TableHead>
                                                <TableHead>Description</TableHead>
                                                <TableHead className="text-right w-[110px]">Withdrawn</TableHead>
                                                <TableHead className="text-right w-[110px]">Portfolio Value</TableHead>
                                                <TableHead className="text-right w-[100px]">Cash Balance</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {events.length === 0 ? (
                                                <TableRow>
                                                    <TableCell colSpan={6} className="text-center py-6 text-zinc-500">No tactical events recorded</TableCell>
                                                </TableRow>
                                            ) : events.map((evt: any, i: number) => (
                                                <TableRow key={i} className="hover:bg-zinc-50 dark:hover:bg-zinc-900/30">
                                                    <TableCell className="font-mono text-xs text-zinc-500 py-2 whitespace-nowrap">{evt.date}</TableCell>
                                                    <TableCell className="py-2">
                                                        <Badge className={`text-[10px] font-medium ${
                                                            evt.event_type === "Income" ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" :
                                                            evt.event_type === "Trigger" ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" :
                                                            evt.event_type === "Trade" ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400" :
                                                            evt.event_type === "Reset" ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" :
                                                            "bg-zinc-100 text-zinc-600"
                                                        }`}>{evt.event_type}</Badge>
                                                    </TableCell>
                                                    <TableCell className="text-xs text-zinc-700 dark:text-zinc-300 py-2">{evt.description}</TableCell>
                                                    <TableCell className="text-xs text-right py-2 text-rose-600 font-medium">
                                                        {evt.withdrawn ? `-$${Number(evt.withdrawn).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : "—"}
                                                    </TableCell>
                                                    <TableCell className="text-xs text-right py-2 font-medium">${Number(evt.portfolio_value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</TableCell>
                                                    <TableCell className="text-xs text-right py-2 text-emerald-600 dark:text-emerald-400">${Number(evt.cash_balance || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </div>
                            </div>
                        </div>
                    )
                })()}
            </TabsContent>

            <TabsContent value="future" className="pt-8 outline-none"><FuturePlaceholder /></TabsContent>
        </Tabs>
    )
}

// ===========================================================================
// Main page
// ===========================================================================
export function StrategiesClient() {
    const copilotActions = (
        <div className="flex gap-2 flex-wrap pt-1">
            <Badge variant="outline" className="cursor-pointer bg-white dark:bg-zinc-900 hover:bg-zinc-100 dark:hover:bg-zinc-800 font-medium text-zinc-600 dark:text-zinc-300 transition-colors">Run all strategies</Badge>
        </div>
    )

    return (
        <DashboardLayout
            copilotMessage="Run any strategy engine to see historical performance and future projections."
            copilotActions={copilotActions}
        >
            <div className="flex flex-col h-full bg-zinc-50/50 dark:bg-zinc-950/50 w-full overflow-hidden">
                <div className="flex items-center gap-3 p-4 md:p-6 border-b border-zinc-200 dark:border-zinc-800 bg-white/50 dark:bg-zinc-900/50 backdrop-blur-sm sticky top-0 z-10 flex-none">
                    <Layers className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                    <div>
                        <h2 className="font-semibold text-base md:text-lg text-zinc-900 dark:text-zinc-100 leading-tight">Strategy Lab</h2>
                        <span className="text-xs text-zinc-500">Run and compare all three strategy engines</span>
                    </div>
                </div>

                <div className="flex-1 overflow-auto p-4 md:p-6 lg:p-8">
                    <div className="mx-auto max-w-4xl">
                        <Tabs defaultValue="cp" className="w-full">
                            <TabsList className="w-full justify-start rounded-none border-b border-zinc-200 dark:border-zinc-800 bg-transparent p-0 overflow-x-auto flex-nowrap scrollbar-none">
                                <TabsTrigger value="cp" className="rounded-none border-b-2 border-transparent data-[state=active]:border-indigo-600 dark:data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none px-6 pb-3 pt-3 whitespace-nowrap font-medium">
                                    Concentrated Position
                                </TabsTrigger>
                                <TabsTrigger value="mp" className="rounded-none border-b-2 border-transparent data-[state=active]:border-indigo-600 dark:data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none px-6 pb-3 pt-3 whitespace-nowrap font-medium">
                                    Model Portfolio
                                </TabsTrigger>
                                <TabsTrigger value="income" className="rounded-none border-b-2 border-transparent data-[state=active]:border-indigo-600 dark:data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none px-6 pb-3 pt-3 whitespace-nowrap font-medium">
                                    Anchor Income
                                </TabsTrigger>
                            </TabsList>

                            <TabsContent value="cp" className="outline-none">
                                <CPStrategy />
                            </TabsContent>
                            <TabsContent value="mp" className="outline-none">
                                <MPStrategy />
                            </TabsContent>
                            <TabsContent value="income" className="outline-none">
                                <IncomeStrategy />
                            </TabsContent>
                        </Tabs>
                    </div>
                </div>
            </div>
        </DashboardLayout>
    )
}
