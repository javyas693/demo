"use client"

import * as React from "react"
import { ArrowLeft, Target, TrendingUp, Activity, Layers, AlertTriangle, ShieldCheck, Sparkles, HelpCircle, Home } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Slider } from "@/components/ui/slider"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { MetricCard } from "@/components/ui/metric-card"
import { motion, AnimatePresence } from "motion/react"
import { simulateScenario, program as getProgram, postPlanPropose, postPlanCommit, ProgramWorkspaceResponse, TradePlan, simulateConcentratedPosition, SimulationResult, patchProfile, postFrontierPropose, FrontierProposalResponse, postMPSimulate, getMPHistory } from "@/lib/api"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { useRouter } from "next/navigation"

function AnimatedNumber({ value }: { value: number | string }) {
    return (
        <span className="flex items-baseline">
            <motion.span
                key={value}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, ease: "easeOut" }}
            >
                {value}
            </motion.span>
        </span>
    );
}

export function ProgramWorkspaceClient({ programKey }: { programKey: string }) {
    const router = useRouter();
    const [data, setData] = React.useState<ProgramWorkspaceResponse | null>(null);
    const [isLoading, setIsLoading] = React.useState(true);
    const [error, setError] = React.useState(false);

    // Simulation state
    const [isSimulating, setIsSimulating] = React.useState(false);
    const [hasSimulated, setHasSimulated] = React.useState(false);
    const [simulationData, setSimulationData] = React.useState<SimulationResult | null>(null);

    // CP Strategy Controls
    const [intensity, setIntensity] = React.useState(50); // 0 to 100 for legacy
    const [targetDelta, setTargetDelta] = React.useState(0.20);
    const [targetDteDays, setTargetDteDays] = React.useState(30);
    const [shareReductionTriggerPct, setShareReductionTriggerPct] = React.useState("5");
    const [triggerError, setTriggerError] = React.useState(false);

    const [activeTab, setActiveTab] = React.useState("current_state"); // Force dynamic tab routing

    // Plan State
    const [proposedPlan, setProposedPlan] = React.useState<TradePlan | null>(null);
    const [isGenerating, setIsGenerating] = React.useState(false);
    const [isCommitting, setIsCommitting] = React.useState(false);

    // Income Specific Simulation Params
    const [coveredPct, setCoveredPct] = React.useState(50);
    const [withdrawPct, setWithdrawPct] = React.useState(0);
    const [profitCaptureTarget, setProfitCaptureTarget] = React.useState(50);

    // CP Inputs
    const [inputSymbol, setInputSymbol] = React.useState("AAPL");
    const [inputShares, setInputShares] = React.useState<number | "">(1200);
    const [inputCostBasis, setInputCostBasis] = React.useState<number | "">(185.25);
    const [inputStartingCash, setInputStartingCash] = React.useState<number | "">(0);
    const [inputMaxSharesPerMonth, setInputMaxSharesPerMonth] = React.useState<number | "">(200);
    const [isSavingPosition, setIsSavingPosition] = React.useState(false);

    // CP Simulation Time/Mode Controls
    const getTodayStr = () => new Date().toISOString().split('T')[0];
    const getTenYearsAgoStr = () => {
        const d = new Date();
        d.setFullYear(d.getFullYear() - 10);
        return d.toISOString().split('T')[0];
    };
    const [startDate, setStartDate] = React.useState(getTenYearsAgoStr());
    const [endDate, setEndDate] = React.useState(getTodayStr());
    const [lossHandlingMode, setLossHandlingMode] = React.useState("harvest_hold");
    const [lastRunSimulationRef, setLastRunSimulationRef] = React.useState<{ start: string, end: string } | null>(null);

    // Isolated MP Card State
    const [mpCapital, setMpCapital] = React.useState<number | "">(500000);
    const [mpRiskTarget, setMpRiskTarget] = React.useState(65);
    const [mpStartDate, setMpStartDate] = React.useState(getTenYearsAgoStr());
    const [mpEndDate, setMpEndDate] = React.useState(getTodayStr());
    const [mpAllocations, setMpAllocations] = React.useState<FrontierProposalResponse | null>(null);
    const [mpIsLoading, setMpIsLoading] = React.useState(false);
    const [mpSimulationData, setMpSimulationData] = React.useState<any>(null);
    const [mpSimIsLoading, setMpSimIsLoading] = React.useState(false);
    const [mpLastRunRef, setMpLastRunRef] = React.useState<{ start: string, end: string } | null>(null);

    const handleRunMPSimulation = async () => {
        if (!mpAllocations || !mpCapital) return;
        setMpSimIsLoading(true);
        try {
            const params = {
                target_weights: mpAllocations.target_weights,
                initial_capital: Number(mpCapital),
                start_date: mpStartDate,
                end_date: mpEndDate
            };
            const res = await postMPSimulate(params);
            setMpSimulationData(res);
            setMpLastRunRef({ start: mpStartDate, end: mpEndDate });
        } catch (e) {
            console.error("Simulation failed", e);
        } finally {
            setMpSimIsLoading(false);
        }
    };

    const handleGenerateMP = async () => {
        setMpIsLoading(true);
        try {
            const res = await postFrontierPropose(mpRiskTarget);
            setMpAllocations(res);
        } catch (e) {
            console.error(e);
        } finally {
            setMpIsLoading(false);
        }
    };

    React.useEffect(() => {
        async function load() {
            try {
                const res = await getProgram(programKey);
                setData(res);
            } catch (err) {
                console.error("Failed to load program", err);
                setError(true);
            } finally {
                setIsLoading(false);
            }
        }
        load();
    }, [programKey]);

    React.useEffect(() => {
        if (programKey === 'core_allocation' && activeTab === 'historical') {
            getMPHistory().then(data => {
                if (data && data.summary) {
                    setMpSimulationData(data);
                    // Only overwrite the ref if we don't already have one from a fresh run
                    setMpLastRunRef(prev => prev || { start: "Persisted", end: "Backtest" });
                }
            }).catch(e => console.error("Failed to load mp history", e));
        }
    }, [programKey, activeTab]);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-screen text-zinc-500">
                <div className="flex flex-col items-center gap-4 animate-pulse">
                    <Sparkles className="h-8 w-8 text-zinc-300" />
                    <p>Loading Workspace...</p>
                </div>
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="flex items-center justify-center min-h-screen text-zinc-500 bg-white dark:bg-zinc-950">
                <div className="flex flex-col items-center gap-4">
                    <AlertTriangle className="h-8 w-8 text-red-400" />
                    <p className="text-zinc-600 dark:text-zinc-400 font-medium">Unable to load workspace data. Please try again.</p>
                    <Button variant="outline" onClick={() => router.push('/')}>Return Home</Button>
                </div>
            </div>
        );
    }

    const handleSliderChange = (value: number[]) => {
        setIntensity(value[0]);
    };

    const handleRunSimulation = async () => {
        if (programKey === 'concentrated_position' && shareReductionTriggerPct !== "" && Number(shareReductionTriggerPct) < 1) {
            setTriggerError(true);
            return;
        }

        setIsSimulating(true);
        try {
            if (programKey === 'concentrated_position') {
                // Automatically patch profile position first so the backend doesn't throw a 400
                await patchProfile({
                    positions: [
                        {
                            symbol: inputSymbol || "AAPL",
                            shares: Number(inputShares) || 0,
                            cost_basis: Number(inputCostBasis) || 0,
                            sleeve: "core"
                        }
                    ]
                });

                const res = await simulateConcentratedPosition({
                    coverage_pct: coveredPct,
                    target_delta: targetDelta,
                    target_dte_days: targetDteDays,
                    profit_capture_pct: profitCaptureTarget / 100.0,
                    share_reduction_trigger_pct: Number(shareReductionTriggerPct) / 100,
                    start_date: startDate,
                    end_date: endDate,
                    loss_handling_mode: lossHandlingMode,
                    starting_cash: Number(inputStartingCash) || 0,
                    max_shares_per_month: Number(inputMaxSharesPerMonth) || 200
                });
                setSimulationData(res);
                setLastRunSimulationRef({ start: startDate, end: endDate });
                setActiveTab("historical"); // Auto navigate to History on success
            } else {
                await simulateScenario();
            }
            setHasSimulated(true);
        } catch (err) {
            console.error("Simulation failed", err);
        } finally {
            setIsSimulating(false);
        }
    };

    const handleSavePosition = async () => {
        setIsSavingPosition(true);
        try {
            await patchProfile({
                positions: [
                    {
                        symbol: inputSymbol || "AAPL",
                        shares: Number(inputShares) || 0,
                        cost_basis: Number(inputCostBasis) || 0,
                        sleeve: "core"
                    }
                ]
            });
            router.refresh();
            const res = await getProgram(programKey);
            setData(res);
        } catch (err) {
            console.error("Failed to save", err);
        } finally {
            setIsSavingPosition(false);
        }
    };

    const handleGeneratePlan = async () => {
        setIsGenerating(true);
        try {
            let params = {};
            if (programKey === 'risk_reduction' || programKey === 'concentrated_position') {
                params = { intensity, reinvest_model_key: "core_v0" };
            } else if (programKey === 'income_generation' || programKey === 'income_generation_v0') {
                params = { covered_pct: coveredPct, premium_rate: 0.006, withdraw_pct: withdrawPct, reinvest_model_key: "core_v0" };
            }

            const res = await postPlanPropose(programKey, params);
            setProposedPlan(res.plan);

            // Auto switch to trades tab
            const tabsContainer = document.querySelector('[role="tablist"]');
            if (tabsContainer) {
                const tradesTab = tabsContainer.querySelector('[value="trades"]') as HTMLElement;
                if (tradesTab) tradesTab.click();
            }
        } catch (err) {
            console.error("Failed to generate plan", err);
        } finally {
            setIsGenerating(false);
        }
    };

    const handleCommitPlan = async () => {
        if (!proposedPlan) return;
        setIsCommitting(true);
        try {
            await postPlanCommit(proposedPlan.plan_id);
            // Master refresh by routing users to dashboard
            router.push('/');
            router.refresh();
        } catch (err) {
            console.error("Failed to commit plan", err);
            setIsCommitting(false);
        }
    };

    // Placeholder dynamic metrics removed since cards are now driven purely by the dynamic strings from the backend.

    const copilotActions = (
        <div className="flex gap-2 flex-wrap pt-1">
            <Badge variant="outline" className="cursor-pointer bg-white dark:bg-zinc-900 hover:bg-zinc-100 dark:hover:bg-zinc-800 font-medium text-zinc-600 dark:text-zinc-300 transition-colors">Yes, show projections</Badge>
            <Badge variant="outline" className="cursor-pointer bg-white dark:bg-zinc-900 hover:bg-zinc-100 dark:hover:bg-zinc-800 font-medium text-zinc-600 dark:text-zinc-300 transition-colors">No, thanks</Badge>
        </div>
    );

    return (
        <DashboardLayout
            copilotMessage={`Monitoring the ${data.summary_title} program. No immediate actions required at this time.`}
            copilotActions={copilotActions}
        >
            <div className="flex flex-col h-full bg-zinc-50/50 dark:bg-zinc-950/50 w-full overflow-hidden">
                <div className="flex items-center gap-2 md:gap-4 p-4 md:p-6 border-b border-zinc-200 dark:border-zinc-800 bg-white/50 dark:bg-zinc-900/50 backdrop-blur-sm sticky top-0 z-10 transition-all flex-none">
                    <Button variant="ghost" size="sm" onClick={() => router.back()} className="gap-2 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 px-2 md:px-3">
                        <ArrowLeft className="h-4 w-4" /> <span className="hidden sm:inline">Back</span>
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => router.push('/')} className="gap-2 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 px-2 md:px-3">
                        <Home className="h-4 w-4" /> <span className="hidden sm:inline">Main</span>
                    </Button>
                    <div className="h-4 w-px bg-zinc-300 dark:bg-zinc-700 mx-1 md:mx-0"></div>
                    <div className="flex flex-col ml-1 md:ml-2">
                        <h2 className="font-semibold text-base md:text-lg text-zinc-900 dark:text-zinc-100 leading-tight">{data.summary_title}</h2>
                        <span className="text-xs text-zinc-500">{data.status}</span>
                    </div>
                </div>

                <div className="flex-1 overflow-auto p-4 md:p-6 lg:p-8">
                    <div className="mx-auto max-w-4xl space-y-8">

                        <div>
                            <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50 mb-2">Current Program State</h1>
                            <p className="text-zinc-500 dark:text-zinc-400">{data.summary_subtitle}</p>
                        </div>

                        {programKey === 'concentrated_position' && (
                            <Card className="border-indigo-100 dark:border-indigo-900/30 overflow-hidden shadow-sm mt-6">
                                <CardHeader className="bg-indigo-50/50 dark:bg-indigo-900/20 pb-4">
                                    <CardTitle className="text-base text-indigo-900 dark:text-indigo-100">Portfolio Inputs</CardTitle>
                                </CardHeader>
                                <CardContent className="p-6">
                                    <div className="flex flex-col md:flex-row gap-4 items-end">
                                        <div className="space-y-2 flex-1">
                                            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Symbol</label>
                                            <input
                                                type="text"
                                                value={inputSymbol}
                                                onChange={e => setInputSymbol(e.target.value)}
                                                className="flex h-10 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 dark:border-zinc-800 dark:bg-zinc-950 dark:placeholder:text-zinc-400 dark:focus-visible:ring-indigo-400"
                                            />
                                        </div>
                                        <div className="space-y-2 flex-1">
                                            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Shares</label>
                                            <input
                                                type="number"
                                                value={inputShares}
                                                onChange={e => setInputShares(e.target.value ? Number(e.target.value) : "")}
                                                className="flex h-10 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 dark:border-zinc-800 dark:bg-zinc-950 dark:placeholder:text-zinc-400 dark:focus-visible:ring-indigo-400"
                                            />
                                        </div>
                                        <div className="space-y-2 flex-1">
                                            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Cost Basis</label>
                                            <input
                                                type="number"
                                                value={inputCostBasis}
                                                onChange={e => setInputCostBasis(e.target.value ? Number(e.target.value) : "")}
                                                className="flex h-10 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 dark:border-zinc-800 dark:bg-zinc-950 dark:placeholder:text-zinc-400 dark:focus-visible:ring-indigo-400"
                                            />
                                        </div>
                                        <div className="space-y-2 flex-1">
                                            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Starting Cash</label>
                                            <input
                                                type="number"
                                                value={inputStartingCash}
                                                onChange={e => setInputStartingCash(e.target.value ? Number(e.target.value) : "")}
                                                className="flex h-10 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 dark:border-zinc-800 dark:bg-zinc-950 dark:placeholder:text-zinc-400 dark:focus-visible:ring-indigo-400"
                                            />
                                        </div>
                                    </div>

                                    <div className="flex flex-col gap-5 mt-6 border-t border-zinc-100 dark:border-zinc-800 pt-5">
                                        <div className="flex flex-col md:flex-row gap-4">
                                            <div className="space-y-2 flex-1 relative">
                                                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Simulation Start Date</label>
                                                <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="flex h-10 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100 placeholder:text-zinc-500" />
                                            </div>
                                            <div className="space-y-2 flex-1 relative">
                                                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Simulation End Date</label>
                                                <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className={`flex h-10 w-full rounded-md border text-sm px-3 py-2 text-zinc-900 dark:text-zinc-100 bg-white dark:bg-zinc-950 focus-visible:outline-none focus-visible:ring-2 placeholder:text-zinc-500 ${startDate > endDate ? 'border-red-500 focus-visible:ring-red-500' : 'border-zinc-200 dark:border-zinc-800 focus-visible:ring-indigo-500'}`} />
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Loss Handling Mode</label>
                                            <div className="flex bg-zinc-100 dark:bg-zinc-900 p-1 rounded-lg w-full max-w-lg border border-zinc-200 dark:border-zinc-800">
                                                <button onClick={() => setLossHandlingMode("harvest_hold")} className={`flex-1 text-sm font-medium py-1.5 rounded-md transition-all ${lossHandlingMode === "harvest_hold" ? "bg-white dark:bg-zinc-800 shadow-sm text-zinc-900 dark:text-zinc-100" : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"}`}>Harvest & Hold (TLH)</button>
                                                <button onClick={() => setLossHandlingMode("tax_neutral_sell")} className={`flex-1 text-sm font-medium py-1.5 rounded-md transition-all ${lossHandlingMode === "tax_neutral_sell" ? "bg-white dark:bg-zinc-800 shadow-sm text-zinc-900 dark:text-zinc-100" : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"}`}>Tax-Neutral Sell</button>
                                            </div>
                                        </div>

                                        <div className="flex gap-2 w-full md:w-auto mt-2">
                                            <Button onClick={handleSavePosition} disabled={isSavingPosition} variant="outline" className="flex-1 md:flex-none border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 hover:bg-zinc-50 dark:hover:bg-zinc-800 text-zinc-900 dark:text-zinc-100">
                                                {isSavingPosition ? "Saving..." : "Save Position"}
                                            </Button>
                                            <Button onClick={handleRunSimulation} disabled={isSimulating || !inputShares || Number(inputShares) <= 0 || startDate > endDate} className="flex-1 md:flex-none bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-50 disabled:pointer-events-none">
                                                {isSimulating ? "Simulating..." : "Run Simulation"}
                                            </Button>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full mt-6">
                            <TabsList className="w-full justify-start rounded-none border-b border-zinc-200 dark:border-zinc-800 bg-transparent p-0 overflow-x-auto flex-nowrap scrollbar-none">
                                <TabsTrigger value="current_state" className="rounded-none border-b-2 border-transparent data-[state=active]:border-indigo-600 dark:data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 pb-2 pt-2 whitespace-nowrap">1. Current</TabsTrigger>
                                <TabsTrigger value="historical" className="rounded-none border-b-2 border-transparent data-[state=active]:border-indigo-600 dark:data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 pb-2 pt-2 whitespace-nowrap">2. History</TabsTrigger>
                                <TabsTrigger value="future_possibilities" className="rounded-none border-b-2 border-transparent data-[state=active]:border-indigo-600 dark:data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 pb-2 pt-2 whitespace-nowrap">3. Future</TabsTrigger>
                            </TabsList>

                            <TabsContent value="historical" className="pt-8 space-y-6 min-h-[300px] outline-none">
                                {!hasSimulated && programKey === 'concentrated_position' ? (
                                    <div className="flex flex-col items-center justify-center py-16 px-4 text-center border border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl bg-zinc-50/50 dark:bg-zinc-900/20">
                                        <Activity className="h-8 w-8 text-zinc-300 mb-4" />
                                        <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">No simulation results yet.</h3>
                                        <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-sm mb-6">
                                            Run a simulation to see historical performance.
                                        </p>
                                    </div>
                                ) : programKey === 'concentrated_position' && simulationData ? (
                                    <div className="space-y-8 animate-in fade-in zoom-in-95 duration-300">
                                        <div className="flex items-center justify-between px-2">
                                            <h4 className="flex flex-col py-1">
                                                <span className="text-sm font-medium flex items-center gap-2">Simulation Results <Badge variant="secondary" className="text-[10px] bg-zinc-100 dark:bg-zinc-800 font-normal">Deterministic Unwind</Badge></span>
                                                {lastRunSimulationRef && (
                                                    <span className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Simulation: {lastRunSimulationRef.start} → {lastRunSimulationRef.end}</span>
                                                )}
                                            </h4>
                                        </div>

                                        {/* Simulation Chart */}
                                        <div className="h-[300px] w-full bg-white dark:bg-zinc-950 border border-zinc-100 dark:border-zinc-800 rounded-xl p-4">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <LineChart data={simulationData.time_series}>
                                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e4e4e7" />
                                                    <XAxis dataKey="Date" tickFormatter={(val) => new Date(val).toLocaleDateString()} minTickGap={30} fontSize={12} stroke="#a1a1aa" />
                                                    <YAxis yAxisId="left" orientation="left" tickFormatter={(val) => `$${(val / 1000).toFixed(0)}k`} fontSize={12} stroke="#a1a1aa" />
                                                    <YAxis yAxisId="right" orientation="right" tickFormatter={(val) => `${val}`} fontSize={12} stroke="#a1a1aa" />
                                                    <RechartsTooltip
                                                        labelFormatter={(val) => new Date(val).toLocaleDateString()}
                                                        formatter={(value: any, name: any) => [
                                                            name === 'Shares' ? value : `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
                                                            name ? String(name).replace('_', ' ') : ''
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

                                        {/* Results grid */}
                                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                            <MetricCard title="Shares Sold" value={simulationData.summary.shares_sold || 0} className="bg-white dark:bg-zinc-950/50" />
                                            <MetricCard title="Cash" value={`$${(simulationData.summary.final_cash || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`} className="bg-white dark:bg-zinc-950 text-emerald-600 dark:text-emerald-400 font-semibold" />
                                            <MetricCard title="Option PnL" value={`$${(simulationData.summary.realized_option_pnl || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`} className="bg-white dark:bg-zinc-950 text-indigo-600 dark:text-indigo-400" />
                                            <MetricCard title="Total Return" value={`${(simulationData.summary.total_return_pct || 0).toFixed(2)}%`} className="bg-white dark:bg-zinc-950" />
                                        </div>

                                        {/* Trade Log */}
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
                                                        {simulationData.summary.audit_log?.map((log: string, i: number) => {
                                                            const parts = log.split(' | ');
                                                            return (
                                                                <TableRow key={i}>
                                                                    <TableCell className="font-medium text-xs whitespace-nowrap align-top">{parts[0]}</TableCell>
                                                                    <TableCell className="text-xs text-zinc-600 dark:text-zinc-400 whitespace-pre-wrap align-top">
                                                                        {parts.slice(1).join(' | ')}
                                                                    </TableCell>
                                                                </TableRow>
                                                            );
                                                        })}
                                                        {(!simulationData.summary.audit_log || simulationData.summary.audit_log.length === 0) && (
                                                            <TableRow>
                                                                <TableCell colSpan={2} className="text-center py-6 text-zinc-500">No events recorded during simulation</TableCell>
                                                            </TableRow>
                                                        )}
                                                    </TableBody>
                                                </Table>
                                            </div>
                                        </div>
                                    </div>
                                ) : programKey === 'core_allocation' ? (
                                    <div className="space-y-8 animate-in fade-in zoom-in-95 duration-300">
                                        <div className="flex items-center justify-between px-2">
                                            <h4 className="flex flex-col py-1">
                                                <span className="text-sm font-medium flex items-center gap-2">Managed Portfolio: Historical Performance <Badge variant="secondary" className="text-[10px] bg-zinc-100 dark:bg-zinc-800 font-normal">Backtest</Badge></span>
                                                {mpLastRunRef && (
                                                    <span className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Simulation: {mpLastRunRef.start} → {mpLastRunRef.end}</span>
                                                )}
                                            </h4>
                                            {mpAllocations && (
                                                <Button onClick={handleRunMPSimulation} disabled={mpSimIsLoading} className="bg-indigo-600 hover:bg-indigo-700 text-white">
                                                    {mpSimIsLoading ? "Simulating..." : "Run Historical Backtest"}
                                                </Button>
                                            )}
                                        </div>

                                        {!mpSimulationData ? (
                                            <div className="flex flex-col items-center justify-center py-16 px-4 text-center border border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl bg-zinc-50/50 dark:bg-zinc-900/20">
                                                <Activity className="h-8 w-8 text-zinc-300 mb-4" />
                                                <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">No MP backtest results yet.</h3>
                                                <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-sm mb-6">
                                                    {mpAllocations ? "Click 'Run Historical Backtest' to simulate your chosen allocation strategy." : "Generate an Optimized Allocation first in the Current tab."}
                                                </p>
                                            </div>
                                        ) : (
                                            <>
                                                {/* Chart */}
                                                <div className="h-[300px] w-full bg-white dark:bg-zinc-950 border border-zinc-100 dark:border-zinc-800 rounded-xl p-4">
                                                    <ResponsiveContainer width="100%" height="100%">
                                                        <LineChart data={mpSimulationData.time_series}>
                                                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e4e4e7" />
                                                            <XAxis dataKey="date" tickFormatter={(val) => new Date(val).toLocaleDateString()} minTickGap={30} fontSize={12} stroke="#a1a1aa" />
                                                            <YAxis tickFormatter={(val) => `$${(val / 1000).toFixed(0)}k`} fontSize={12} stroke="#a1a1aa" domain={['auto', 'auto']} />
                                                            <RechartsTooltip
                                                                labelFormatter={(val) => new Date(val).toLocaleDateString()}
                                                                formatter={(value: any, name: any) => [
                                                                    `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
                                                                    "Portfolio Value"
                                                                ]}
                                                            />
                                                            <Line type="monotone" dataKey="value" stroke="#10b981" dot={false} strokeWidth={2} />
                                                        </LineChart>
                                                    </ResponsiveContainer>
                                                </div>

                                                {/* Analytics Grid */}
                                                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                                                    <MetricCard title="Total Return" value={`${(mpSimulationData.summary.total_return_pct || 0).toFixed(2)}%`} className="bg-white dark:bg-zinc-950" />
                                                    <MetricCard title="Annualized Return" value={`${(mpSimulationData.summary.annualized_return_pct || 0).toFixed(2)}%`} className="bg-white dark:bg-zinc-950" />
                                                    <MetricCard title="Volatility (Std Dev)" value={`${(mpSimulationData.summary.volatility_pct || 0).toFixed(2)}%`} className="bg-white dark:bg-zinc-950" />
                                                    <MetricCard title="Sharpe Ratio" value={`${(mpSimulationData.summary.sharpe_ratio || 0).toFixed(2)}`} trend={{ value: "4% RFR" }} className="bg-white dark:bg-zinc-950" />
                                                    <MetricCard title="Max Drawdown" value={`${(mpSimulationData.summary.max_drawdown_pct || 0).toFixed(2)}%`} className="bg-white dark:bg-zinc-950" />
                                                </div>

                                                {/* Audit Log */}
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
                                                                {mpSimulationData.audit_log?.map((log: any, i: number) => (
                                                                    <TableRow key={i}>
                                                                        <TableCell className="font-medium text-xs whitespace-nowrap">{log.date}</TableCell>
                                                                        <TableCell className="text-xs text-zinc-900 dark:text-zinc-100 whitespace-nowrap">${Number(log.portfolio_value).toLocaleString(undefined, { maximumFractionDigits: 0 })}</TableCell>
                                                                        <TableCell className={`text-xs whitespace-nowrap ${log.monthly_pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500'}`}>
                                                                            {log.monthly_pnl >= 0 ? '+' : ''}${Number(log.monthly_pnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                                                        </TableCell>
                                                                        <TableCell className="text-xs text-indigo-600 dark:text-indigo-400 whitespace-nowrap">{log.top_holding}</TableCell>
                                                                        <TableCell className="text-xs text-zinc-500 whitespace-nowrap">{log.action}</TableCell>
                                                                    </TableRow>
                                                                ))}
                                                            </TableBody>
                                                        </Table>
                                                    </div>
                                                </div>
                                                {mpSimulationData.audit_log && mpSimulationData.audit_log.length > 0 && mpSimulationData.audit_log[0].math_verified && (
                                                    <div className="flex justify-end pt-2 px-2">
                                                        <span className="text-[10px] text-zinc-500 flex items-center gap-1.5"><div className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Reconciliation Status: Verified (Sum of Assets = Total Value)</span>
                                                    </div>
                                                )}
                                            </>
                                        )}
                                    </div>
                                ) : null}
                            </TabsContent>

                            <TabsContent value="current_state" className="pt-8 space-y-6 outline-none">
                                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                                    {(programKey === 'core_allocation' ? [
                                        {
                                            label: "Alignment",
                                            value: (mpAllocations && mpAllocations.risk_score === mpRiskTarget) ? "100%" : "Needs Review",
                                            tag: (mpAllocations && mpAllocations.risk_score === mpRiskTarget) ? "Aligned" : "Pending"
                                        },
                                        {
                                            label: "Rebalance",
                                            value: (mpAllocations && mpAllocations.risk_score === mpRiskTarget) ? "Optimized" : "Pending",
                                            tag: (mpAllocations && mpAllocations.risk_score === mpRiskTarget) ? undefined : "Action Needed"
                                        }
                                    ] : data.summary_cards).map((card, i) => (
                                        <MetricCard
                                            key={i}
                                            title={card.label}
                                            value={!hasSimulated && programKey === 'concentrated_position' ? "—" : <AnimatedNumber value={card.value} />}
                                            trend={!hasSimulated && programKey === 'concentrated_position' ? undefined : (card.tag ? { value: card.tag } : undefined)}
                                            className="bg-white/50 dark:bg-zinc-900/50 border-zinc-200 dark:border-zinc-800"
                                        />
                                    ))}
                                </div>

                                {/* Included Signals section inline in overview for context */}
                                {data.signals && data.signals.length > 0 && (
                                    <div className="space-y-3 mt-8">
                                        <h3 className="font-medium text-zinc-900 dark:text-zinc-100">Active Signals via Backend API</h3>
                                        {data.signals.map(signal => (
                                            <div key={signal.id} className="flex items-center justify-between p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-sm">
                                                <div className="flex items-center gap-4">
                                                    <div className={`h-2 w-2 rounded-full ${signal.severity === 'High' ? 'bg-red-500' : 'bg-orange-400'}`}></div>
                                                    <div>
                                                        <h4 className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{signal.title}</h4>
                                                        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">{signal.description}</p>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                <div className={programKey === 'concentrated_position' ? "grid grid-cols-1 lg:grid-cols-2 gap-8 mt-8" : "mt-8"}>
                                    {programKey !== 'core_allocation' && (
                                        <Card className="border-indigo-100 dark:border-indigo-900/30 overflow-hidden relative shadow-sm">
                                            <CardHeader>
                                                <CardTitle className="flex items-center gap-2 text-base">
                                                    {programKey === 'core_allocation' ? 'Cash Deployment Strategy' : 'Program Policy Builder'}
                                                </CardTitle>
                                                <CardDescription>
                                                    {programKey === 'core_allocation'
                                                        ? 'Configure parameters to deploy available cash into target portfolios.'
                                                        : 'Adjust program parameters to generate an executable strategy.'}
                                                </CardDescription>
                                            </CardHeader>
                                            <CardContent className="space-y-6">
                                                {/* Dynamic Slider Area */}
                                                {programKey === 'income_generation' || programKey === 'income_generation_v0' ? (
                                                    <div className="space-y-6 pt-2">
                                                        <div className="space-y-4">
                                                            <div className="flex justify-between items-center text-sm font-medium">
                                                                <span>Position Coverage</span>
                                                                <span>{coveredPct}%</span>
                                                            </div>
                                                            <Slider defaultValue={[50]} value={[coveredPct]} max={100} step={10} onValueChange={(v) => setCoveredPct(v[0])} />
                                                        </div>
                                                        <div className="space-y-4">
                                                            <div className="flex justify-between items-center text-sm font-medium">
                                                                <span>Premium Withdrawal</span>
                                                                <span>{withdrawPct}%</span>
                                                            </div>
                                                            <Slider defaultValue={[0]} value={[withdrawPct]} max={100} step={10} onValueChange={(v) => setWithdrawPct(v[0])} />
                                                        </div>
                                                    </div>
                                                ) : programKey === 'concentrated_position' ? (
                                                    <div className="space-y-6 pt-2">
                                                        <div className="space-y-4">
                                                            <div className="flex justify-between items-center text-sm font-medium">
                                                                <span>Coverage %</span>
                                                                <span>{coveredPct}%</span>
                                                            </div>
                                                            <Slider defaultValue={[50]} value={[coveredPct]} max={100} step={10} onValueChange={(v) => setCoveredPct(v[0])} />
                                                        </div>
                                                        <div className="space-y-4">
                                                            <div className="flex justify-between items-center text-sm font-medium">
                                                                <span>Target Delta</span>
                                                                <span>{targetDelta.toFixed(2)}</span>
                                                            </div>
                                                            <Slider defaultValue={[0.20]} value={[targetDelta]} min={0.05} max={0.50} step={0.05} onValueChange={(v) => setTargetDelta(v[0])} />
                                                        </div>
                                                        <div className="space-y-4">
                                                            <div className="flex justify-between items-center text-sm font-medium">
                                                                <span>Option Duration (Days)</span>
                                                                <span>{targetDteDays}</span>
                                                            </div>
                                                            <Slider defaultValue={[30]} value={[targetDteDays]} min={7} max={90} step={1} onValueChange={(v) => setTargetDteDays(v[0])} />
                                                        </div>
                                                        <div className="space-y-4">
                                                            <div className="flex justify-between items-start text-sm font-medium">
                                                                <div className="flex flex-col">
                                                                    <span>Profit Capture Target (%)</span>
                                                                    <span className="text-xs text-zinc-500 font-normal mt-1">0% captures profit immediately; 100% holds until expiration.</span>
                                                                </div>
                                                                <span>{profitCaptureTarget}%</span>
                                                            </div>
                                                            <Slider defaultValue={[50]} value={[profitCaptureTarget]} min={0} max={100} step={5} onValueChange={(v) => setProfitCaptureTarget(v[0])} />
                                                        </div>
                                                        <div className="space-y-2">
                                                            <div className="flex justify-between items-center text-sm font-medium">
                                                                <div className="flex flex-col">
                                                                    <span>Share Reduction Trigger</span>
                                                                    {triggerError && (
                                                                        <span className="text-xs text-red-500 font-normal mt-1">Must be &ge; 1% (or blank)</span>
                                                                    )}
                                                                </div>
                                                            </div>
                                                            <div className="relative w-full sm:w-1/4">
                                                                <input
                                                                    type="text"
                                                                    value={shareReductionTriggerPct}
                                                                    onChange={(e) => {
                                                                        const val = e.target.value;
                                                                        if (val === "" || /^\d*\.?\d*$/.test(val)) {
                                                                            setShareReductionTriggerPct(val);
                                                                            if (triggerError) setTriggerError(false);
                                                                        }
                                                                    }}
                                                                    onBlur={(e) => {
                                                                        const val = e.target.value;
                                                                        if (val !== "" && Number(val) < 1) {
                                                                            setTriggerError(true);
                                                                        }
                                                                    }}
                                                                    disabled={lossHandlingMode === 'harvest_hold'}
                                                                    placeholder="0"
                                                                    className={`flex h-10 w-full rounded-md border text-sm px-3 py-2 pr-8 text-zinc-900 dark:text-zinc-100 bg-white dark:bg-zinc-950 focus-visible:outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-50 ${triggerError ? 'border-red-500 focus-visible:ring-red-500' : 'border-zinc-200 dark:border-zinc-800 focus-visible:ring-indigo-500'}`}
                                                                />
                                                                <div className="absolute right-3 top-2.5 text-zinc-500 text-sm pointer-events-none">%</div>
                                                            </div>
                                                        </div>
                                                        <div className="space-y-2">
                                                            <div className="flex justify-between items-center text-sm font-medium">
                                                                <span>Max Shares / Month</span>
                                                            </div>
                                                            <div className="relative w-full sm:w-1/4">
                                                                <input
                                                                    type="number"
                                                                    value={inputMaxSharesPerMonth}
                                                                    onChange={(e) => setInputMaxSharesPerMonth(e.target.value === "" ? "" : Number(e.target.value))}
                                                                    placeholder="200"
                                                                    disabled={lossHandlingMode === 'harvest_hold'}
                                                                    className="flex h-10 w-full rounded-md border text-sm px-3 py-2 text-zinc-900 dark:text-zinc-100 bg-white dark:bg-zinc-950 focus-visible:outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-50 border-zinc-200 dark:border-zinc-800 focus-visible:ring-indigo-500"
                                                                />
                                                            </div>
                                                        </div>
                                                    </div>
                                                ) : programKey === 'core_allocation' ? (
                                                    <div className="space-y-4 pt-2">
                                                        <div className="bg-zinc-50 dark:bg-zinc-900 rounded-lg p-4 border border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
                                                            <div>
                                                                <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">Target Model</p>
                                                                <p className="text-xs text-zinc-500">Core Market Beta (60% VTI, 30% VXUS, 10% BND)</p>
                                                            </div>
                                                            <Badge className="bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400">Target Core_V0</Badge>
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <div className="space-y-4 pt-2">
                                                        <div className="relative pt-6 pb-2">
                                                            <Slider
                                                                defaultValue={[50]}
                                                                value={[intensity]}
                                                                max={100}
                                                                step={25}
                                                                onValueChange={handleSliderChange}
                                                                className="z-10 relative [&_[role=slider]]:bg-white [&_[role=slider]]:border-zinc-300 [&_[role=slider]]:shadow-sm [&_[data-orientation=horizontal]>span:first-child>span]:bg-indigo-500"
                                                            />
                                                        </div>
                                                        <div className="flex justify-between text-xs font-medium text-zinc-400 px-1">
                                                            {[1, 2, 3, 4, 5].map((level, i) => (
                                                                <span key={i} className={`cursor-pointer hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors ${intensity === i * 25 ? "text-indigo-600 dark:text-indigo-400 font-bold" : ""}`} onClick={() => setIntensity(i * 25)}>
                                                                    Level {level}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}

                                                <div className="pt-4 border-t border-zinc-100 dark:border-zinc-800">
                                                    <Button onClick={handleGeneratePlan} disabled={isGenerating} size="lg" className="w-full bg-indigo-600 hover:bg-indigo-700 text-white">
                                                        {isGenerating ? "Generating Plan..." : programKey === 'core_allocation' ? "Deploy Available Cash" : "Generate Action Plan"}
                                                    </Button>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    )}

                                    {/* Isolated MP Strategy Card */}
                                    {programKey === 'core_allocation' && (
                                        <Card className="border-indigo-100 dark:border-indigo-900/30 overflow-hidden relative shadow-sm">
                                            <CardHeader>
                                                <CardTitle className="flex items-center gap-2 text-base">
                                                    Managed Portfolio (MP) Strategy
                                                </CardTitle>
                                                <CardDescription>
                                                    Configure target risk for your managed portfolio separately from your concentrated position.
                                                </CardDescription>
                                            </CardHeader>
                                            <CardContent className="space-y-6">
                                                <div className={`grid ${mpAllocations ? 'grid-cols-1 lg:grid-cols-2 gap-8' : 'grid-cols-1'}`}>
                                                    <div className="space-y-6">
                                                        <div className="space-y-6 pt-2">
                                                            <div className="space-y-2">
                                                                <div className="flex justify-between items-center text-sm font-medium">
                                                                    <span>Initial Capital</span>
                                                                </div>
                                                                <div className="relative">
                                                                    <div className="absolute left-3 top-2.5 text-zinc-500 text-sm pointer-events-none">$</div>
                                                                    <input
                                                                        type="text"
                                                                        value={mpCapital}
                                                                        onChange={(e) => {
                                                                            const val = e.target.value.replace(/[^0-9.]/g, '');
                                                                            setMpCapital(val === "" ? "" : Number(val));
                                                                        }}
                                                                        className="flex h-10 w-full rounded-md border text-sm px-3 py-2 pl-7 text-zinc-900 dark:text-zinc-100 bg-white dark:bg-zinc-950 focus-visible:outline-none focus-visible:ring-2 border-zinc-200 dark:border-zinc-800 focus-visible:ring-indigo-500"
                                                                    />
                                                                </div>
                                                            </div>

                                                            <div className="space-y-4">
                                                                <div className="flex justify-between items-center text-sm font-medium">
                                                                    <span>MP Risk Target (1-100)</span>
                                                                    <span>{mpRiskTarget}</span>
                                                                </div>
                                                                <Slider defaultValue={[65]} value={[mpRiskTarget]} min={1} max={100} step={1} onValueChange={(v) => setMpRiskTarget(v[0])} />
                                                            </div>

                                                            <div className="space-y-4">
                                                                <div className="flex justify-between items-center text-sm font-medium">
                                                                    <span>Simulation Period</span>
                                                                </div>
                                                                <div className="flex gap-4">
                                                                    <div className="space-y-1.5 flex-1">
                                                                        <span className="text-xs text-zinc-500 font-medium">Start</span>
                                                                        <input
                                                                            type="date"
                                                                            value={mpStartDate}
                                                                            onChange={(e) => setMpStartDate(e.target.value)}
                                                                            className="flex h-9 w-full rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-500 text-zinc-900 dark:text-zinc-100"
                                                                        />
                                                                    </div>
                                                                    <div className="space-y-1.5 flex-1">
                                                                        <span className="text-xs text-zinc-500 font-medium">End</span>
                                                                        <input
                                                                            type="date"
                                                                            value={mpEndDate}
                                                                            onChange={(e) => setMpEndDate(e.target.value)}
                                                                            className="flex h-9 w-full rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-500 text-zinc-900 dark:text-zinc-100"
                                                                        />
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </div>

                                                        <div className="pt-4 border-t border-zinc-100 dark:border-zinc-800">
                                                            <Button onClick={handleGenerateMP} disabled={mpIsLoading} size="lg" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white">
                                                                {mpIsLoading ? "Optimizing..." : "Generate Optimized Allocation"}
                                                            </Button>
                                                        </div>


                                                    </div>

                                                    {/* Right Column Donut */}
                                                    {(() => {
                                                        if (!mpAllocations) return null;

                                                        // Aggregate weights by asset class
                                                        let equityWeight = 0;
                                                        let fixedIncomeWeight = 0;
                                                        Object.entries(mpAllocations.target_weights).forEach(([ticker, weight]) => {
                                                            if (ticker === 'BND' || ticker === 'TLT' || ticker === 'IEF') {
                                                                fixedIncomeWeight += weight;
                                                            } else {
                                                                equityWeight += weight;
                                                            }
                                                        });

                                                        const assetClassData = [];
                                                        if (equityWeight > 0) assetClassData.push({ name: 'Equity', value: equityWeight * 100 });
                                                        if (fixedIncomeWeight > 0) assetClassData.push({ name: 'Fixed Income', value: fixedIncomeWeight * 100 });

                                                        return (
                                                            <div className="flex flex-col items-center justify-center p-6 bg-zinc-50 dark:bg-zinc-900/30 rounded-xl border border-zinc-200 dark:border-zinc-800 h-full">
                                                                <div className="relative w-[80%] h-[200px] sm:w-[200px]">
                                                                    {/* Centered Total Value */}
                                                                    <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-10">
                                                                        <span className="text-xs text-zinc-500 font-medium tracking-wide">TOTAL CAPITAL</span>
                                                                        <span className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mt-1">
                                                                            ${Number(mpCapital).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                                                        </span>
                                                                    </div>
                                                                    <ResponsiveContainer width="100%" height="100%">
                                                                        <PieChart>
                                                                            <Pie
                                                                                data={assetClassData}
                                                                                cx="50%"
                                                                                cy="50%"
                                                                                innerRadius="65%"
                                                                                outerRadius="85%"
                                                                                paddingAngle={2}
                                                                                dataKey="value"
                                                                                stroke="none"
                                                                            >
                                                                                {assetClassData.map((entry, index) => {
                                                                                    const colors = ['#6366f1', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6'];
                                                                                    return <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />;
                                                                                })}
                                                                            </Pie>
                                                                            <RechartsTooltip
                                                                                formatter={(value: any) => [`${Number(value).toFixed(1)}%`, 'Target Weight']}
                                                                                contentStyle={{ borderRadius: '8px', border: '1px solid #e4e4e7', fontSize: '12px' }}
                                                                            />
                                                                        </PieChart>
                                                                    </ResponsiveContainer>
                                                                </div>
                                                                {/* Custom Legend */}
                                                                <div className="flex flex-wrap justify-center gap-4 mt-8">
                                                                    {assetClassData.map((entry, i) => {
                                                                        const colors = ['#6366f1', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6'];
                                                                        return (
                                                                            <div key={entry.name} className="flex items-center gap-1.5">
                                                                                <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: colors[i % colors.length] }} />
                                                                                <span className="text-sm font-medium">{entry.name}</span>
                                                                                <span className="text-sm text-zinc-500">{entry.value.toFixed(1)}%</span>
                                                                            </div>
                                                                        );
                                                                    })}
                                                                </div>
                                                            </div>
                                                        );
                                                    })()}
                                                </div>

                                                {/* Full Width MP Results Table Bottom */}
                                                {mpAllocations && (
                                                    <div className="pt-6 border-t border-zinc-100 dark:border-zinc-800">
                                                        <h4 className="font-semibold text-sm mb-3">Target Allocation Matrix</h4>
                                                        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 overflow-hidden">
                                                            <Table>
                                                                <TableHeader className="bg-zinc-50/50 dark:bg-zinc-900/20">
                                                                    <TableRow>
                                                                        <TableHead>Ticker</TableHead>
                                                                        <TableHead>Asset Class</TableHead>
                                                                        <TableHead className="text-right">Weight %</TableHead>
                                                                        <TableHead className="text-right">Value ($)</TableHead>
                                                                    </TableRow>
                                                                </TableHeader>
                                                                <TableBody>
                                                                    {Object.entries(mpAllocations.target_weights).map(([ticker, weight]) => (
                                                                        <TableRow key={ticker}>
                                                                            <TableCell className="font-medium text-xs py-2">{ticker}</TableCell>
                                                                            <TableCell className="text-xs text-zinc-500 py-2">
                                                                                {ticker === 'BND' || ticker === 'TLT' || ticker === 'IEF' ? 'Fixed Income' : 'Equity'}
                                                                            </TableCell>
                                                                            <TableCell className="text-xs text-right py-2">{(weight * 100).toFixed(1)}%</TableCell>
                                                                            <TableCell className="text-xs text-right py-2">${(weight * Number(mpCapital)).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</TableCell>
                                                                        </TableRow>
                                                                    ))}
                                                                </TableBody>
                                                            </Table>
                                                        </div>
                                                    </div>
                                                )}
                                            </CardContent>
                                        </Card>
                                    )}
                                </div>
                            </TabsContent>

                            <TabsContent value="future_possibilities" className="pt-8 space-y-6 outline-none min-h-[400px]">
                                <div className="flex flex-col items-center justify-center py-16 px-4 text-center border border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl bg-zinc-50/50 dark:bg-zinc-900/20">
                                    <h3 className="text-xl font-medium text-zinc-900 dark:text-zinc-100 mb-2">Future Scenario Modeling</h3>
                                    <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-sm mb-6">
                                        Monte Carlo projections will appear here.
                                    </p>
                                </div>
                            </TabsContent>

                            <TabsContent value="trades" className="pt-8 text-sm text-zinc-500 dark:text-zinc-400 min-h-[300px] outline-none">
                                {proposedPlan ? (
                                    <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2">
                                        <div className="p-6 rounded-xl border border-indigo-100 bg-white dark:border-indigo-900/40 dark:bg-zinc-950 shadow-sm">
                                            <div className="flex items-center justify-between mb-4">
                                                <h3 className="font-semibold text-lg text-zinc-900 dark:text-white">Proposed Execution Ledger</h3>
                                                <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400">Ready</Badge>
                                            </div>

                                            <div className="bg-zinc-50 dark:bg-zinc-900 p-4 rounded-lg mb-6 border border-zinc-100 dark:border-zinc-800">
                                                <h4 className="font-medium text-base text-zinc-900 dark:text-zinc-100 mb-1">{proposedPlan.summary}</h4>
                                                <ul className="list-disc pl-5 mt-2 space-y-1">
                                                    {proposedPlan.why.map((reason, i) => (
                                                        <li key={i} className="text-zinc-600 dark:text-zinc-400">{reason}</li>
                                                    ))}
                                                </ul>
                                            </div>

                                            <h4 className="font-medium mb-3 text-zinc-900 dark:text-zinc-100">Trade Actions</h4>
                                            <div className="space-y-3 mb-8">
                                                {proposedPlan.actions.map((act, i) => (
                                                    <div key={i} className="flex items-center justify-between p-3 bg-white dark:bg-zinc-950 rounded-lg border border-zinc-200 dark:border-zinc-800 shadow-sm">
                                                        <div className="flex items-center gap-3">
                                                            <Badge variant="outline" className={`
                                                                ${act.type === 'SELL' ? 'text-rose-600 border-rose-200 bg-rose-50 dark:bg-rose-950/30 dark:border-rose-900/50 dark:text-rose-400' : ''}
                                                                ${act.type === 'BUY' ? 'text-emerald-600 border-emerald-200 bg-emerald-50 dark:bg-emerald-950/30 dark:border-emerald-900/50 dark:text-emerald-400' : ''}
                                                                ${act.type === 'ALLOCATE_CASH' ? 'text-indigo-600 border-indigo-200 bg-indigo-50 dark:bg-indigo-950/30 dark:border-indigo-900/50 dark:text-indigo-400' : ''}
                                                                ${act.type === 'CASH_CREDIT' ? 'text-amber-600 border-amber-200 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-900/50 dark:text-amber-400' : ''}
                                                            `}>
                                                                {act.type}
                                                            </Badge>
                                                            <span className="font-medium text-zinc-900 dark:text-zinc-100">{act.symbol || act.model_key || "Cash Account"}</span>
                                                        </div>
                                                        <span className="text-zinc-500">{act.notes}</span>
                                                    </div>
                                                ))}
                                            </div>

                                            <div className="flex gap-3 justify-end pt-4 border-t border-zinc-100 dark:border-zinc-800">
                                                <Button variant="outline" onClick={() => setProposedPlan(null)}>Discard Plan</Button>
                                                <Button onClick={handleCommitPlan} disabled={isCommitting} className="bg-emerald-600 hover:bg-emerald-700 text-white min-w-[200px]">
                                                    {isCommitting ? "Committing..." : "Apply to Paper Portfolio"}
                                                </Button>
                                            </div>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="flex flex-col items-center justify-center py-16 px-4 text-center border border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl bg-zinc-50/50 dark:bg-zinc-900/20">
                                        <AlertTriangle className="h-8 w-8 text-amber-400 mb-4" />
                                        <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">No active trade plan</h3>
                                        <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-sm mb-6">
                                            Return to the Overview tab and generate an Action Plan to see the projected trade impact here.
                                        </p>
                                        <Button variant="outline" onClick={() => {
                                            const tabsContainer = document.querySelector('[role="tablist"]');
                                            if (tabsContainer) {
                                                const overviewTab = tabsContainer.querySelector('[value="current_state"]') as HTMLElement;
                                                if (overviewTab) overviewTab.click();
                                            }
                                        }}>
                                            Go to Current State
                                        </Button>
                                    </div>
                                )}
                            </TabsContent>

                        </Tabs >

                    </div >
                </div >
            </div >
        </DashboardLayout >
    )
}
