"use client"

import * as React from "react"
import { Target, TrendingUp, Activity, Layers, AlertTriangle, ShieldCheck, Sparkles } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

import { capitalSummary, signals, CapitalSummary as CapitalSummaryType, ProgramSignal } from "@/lib/api"

export function CapitalSummary({ onSelectProgram }: { onSelectProgram: (p: string) => void }) {
    const [summary, setSummary] = React.useState<CapitalSummaryType | null>(null);
    const [allSignals, setAllSignals] = React.useState<ProgramSignal[]>([]);
    const [isLoading, setIsLoading] = React.useState(true);
    const [error, setError] = React.useState(false);

    React.useEffect(() => {
        async function loadData() {
            try {
                const [summaryData, signalsData] = await Promise.all([
                    capitalSummary(),
                    signals()
                ]);
                setSummary(summaryData);

                // Sort signals: High -> Medium -> Low
                const severityRank = { "High": 3, "Medium": 2, "Low": 1 };
                const sorted = (signalsData.signals || []).sort((a, b) => severityRank[b.severity] - severityRank[a.severity]);
                setAllSignals(sorted);
            } catch (err) {
                console.error("Failed to load capital summary", err);
                setError(true);
            } finally {
                setIsLoading(false);
            }
        }
        loadData();
    }, []);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-full text-zinc-500 min-h-[400px]">
                <div className="flex flex-col items-center gap-4 animate-pulse">
                    <Sparkles className="h-8 w-8 text-zinc-300" />
                    <p>Loading Capital Summary...</p>
                </div>
            </div>
        );
    }

    if (error || !summary) {
        return (
            <div className="flex items-center justify-center h-full text-zinc-500 min-h-[400px]">
                <div className="flex flex-col items-center gap-4">
                    <AlertTriangle className="h-8 w-8 text-red-400" />
                    <p className="text-zinc-600 dark:text-zinc-400">Unable to load your capital summary. Please try again.</p>
                </div>
            </div>
        );
    }

    // Only show Medium + High in Action Center
    const actionCenterSignals = allSignals.filter(s => s.severity === "High" || s.severity === "Medium");

    const handleFormatCurrency = (val: number) => {
        const sign = val >= 0 ? "+" : "-";
        return `${sign}$${Math.abs(val).toLocaleString()}`;
    };

    return (
        <div className="mx-auto max-w-4xl space-y-12 py-8 px-4 sm:px-8">
            {/* Executive Summary */}
            <div>
                <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50 mb-6">Your Capital Today</h1>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    <Card className="bg-white dark:bg-zinc-900 shadow-sm border-zinc-200 dark:border-zinc-800">
                        <CardContent className="p-5 flex flex-col justify-between h-full space-y-3">
                            <div className="text-zinc-500 dark:text-zinc-400 font-medium text-xs uppercase tracking-wider">Portfolio Value</div>
                            <div className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                                ${summary.portfolio_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="bg-white dark:bg-zinc-900 shadow-sm border-zinc-200 dark:border-zinc-800">
                        <CardContent className="p-5 flex flex-col justify-between h-full space-y-3">
                            <div className="text-zinc-500 dark:text-zinc-400 font-medium text-xs uppercase tracking-wider">Cash Available</div>
                            <div className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 text-emerald-600 dark:text-emerald-500">
                                ${summary.cash_available.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="bg-white dark:bg-zinc-900 shadow-sm border-zinc-200 dark:border-zinc-800">
                        <CardContent className="p-5 flex flex-col justify-between h-full space-y-3">
                            <div className="text-zinc-500 dark:text-zinc-400 font-medium text-xs uppercase tracking-wider">Largest Holding</div>
                            <div className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 flex flex-col">
                                <span>{summary.largest_holding_symbol || "None"}</span>
                                <span className="text-sm font-normal text-zinc-500">${summary.largest_holding_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="bg-white dark:bg-zinc-900 shadow-sm border-zinc-200 dark:border-zinc-800">
                        <CardContent className="p-5 flex flex-col justify-between h-full space-y-3">
                            <div className="text-zinc-500 dark:text-zinc-400 font-medium text-xs uppercase tracking-wider">Concentration</div>
                            <div className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                                {(summary.concentration_pct * 100).toFixed(1)}%
                            </div>
                        </CardContent>
                    </Card>
                </div>

                <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-zinc-50 dark:bg-zinc-900/40 p-5 rounded-xl border border-zinc-100 dark:border-zinc-800/60">
                    <p className="text-sm text-zinc-600 dark:text-zinc-300">
                        <span className="text-zinc-900 dark:text-white font-medium block sm:inline">Your capital is aligned with your goals.</span> {summary.items_require_review} items require review.
                    </p>
                    {actionCenterSignals.length > 0 && (
                        <Button onClick={() => onSelectProgram(actionCenterSignals[0].primary_action.route)} className="w-full sm:w-auto bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-200">
                            Review Actions
                        </Button>
                    )}
                </div>
            </div>

            {/* Action Center Section */}
            {actionCenterSignals.length > 0 && (
                <div>
                    <h2 className="text-xl font-medium text-zinc-900 dark:text-zinc-100 mb-5">Action Center</h2>
                    <div className="space-y-3">
                        {actionCenterSignals.map(signal => (
                            <div key={signal.id} className="flex items-center justify-between p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-sm group hover:border-zinc-300 dark:hover:border-zinc-700 transition-colors">
                                <div className="flex items-center gap-4">
                                    <div className={`h-2 w-2 rounded-full ${signal.severity === 'High' ? 'bg-red-500' : 'bg-orange-400'}`}></div>
                                    <div>
                                        <h4 className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{signal.title}</h4>
                                        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">{signal.description}</p>
                                    </div>
                                </div>
                                <Button variant="outline" size="sm" onClick={() => onSelectProgram(signal.primary_action.route)}>
                                    {signal.primary_action.label}
                                </Button>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Active Capital Programs Section */}
            <div>
                <h2 className="text-xl font-medium text-zinc-900 dark:text-zinc-100 mb-5">Active Capital Programs</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

                    <Card className="cursor-pointer hover:shadow-md transition-shadow border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950" onClick={() => onSelectProgram('concentrated_position')}>
                        <CardContent className="p-6 flex flex-col justify-between h-full space-y-4">
                            <div className="flex items-center justify-between">
                                <h3 className="font-medium text-zinc-900 dark:text-zinc-100">Concentrated Position</h3>
                                {summary.concentration_status !== 'ok' ? (
                                    <span className="text-xs text-rose-500 font-medium">Action Req</span>
                                ) : (
                                    <span className="text-xs text-zinc-500">Active</span>
                                )}
                            </div>
                            <p className="text-sm text-zinc-500 dark:text-zinc-400">Manage large single-stock exposures, risk reduction, and covered calls.</p>
                        </CardContent>
                    </Card>

                    <Card className="cursor-pointer hover:shadow-md transition-shadow border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950" onClick={() => onSelectProgram('core_allocation')}>
                        <CardContent className="p-6 flex flex-col justify-between h-full space-y-4">
                            <div className="flex items-center justify-between">
                                <h3 className="font-medium text-zinc-900 dark:text-zinc-100">Core Portfolio</h3>
                                <span className="text-xs text-zinc-500">Active</span>
                            </div>
                            <p className="text-sm text-zinc-500 dark:text-zinc-400">Long-term diversified beta matching your risk profile. Deploy cash here.</p>
                        </CardContent>
                    </Card>

                    <Card className="cursor-pointer hover:shadow-md transition-shadow border-dashed border-zinc-300 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-950" onClick={() => onSelectProgram('income_strategy')}>
                        <CardContent className="p-6 flex flex-col justify-between h-full space-y-4 opacity-70">
                            <div className="flex items-center justify-between">
                                <h3 className="font-medium text-zinc-900 dark:text-zinc-100">Income Strategy</h3>
                                <span className="text-xs text-zinc-400 bg-zinc-200 dark:bg-zinc-800 px-2 py-0.5 rounded-full">Coming Soon</span>
                            </div>
                            <p className="text-sm text-zinc-500 dark:text-zinc-400">Yield-focused diversified portfolio construction.</p>
                        </CardContent>
                    </Card>

                </div>
            </div>
        </div>
    )
}

