"use client"

import * as React from "react"
import { ArrowLeft, Target, TrendingUp, Activity, Layers, AlertTriangle, ShieldCheck, Sparkles, HelpCircle } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Slider } from "@/components/ui/slider"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { MetricCard } from "@/components/ui/metric-card"
import { motion, AnimatePresence } from "motion/react"
import { simulateScenario } from "@/lib/api"

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

export function ProgramWorkspace({
    program,
    onBack,
    user,
    scenariosData
}: {
    program: string,
    onBack: () => void,
    user: any,
    scenariosData: any
}) {
    const [currentScenarioIndex, setCurrentScenarioIndex] = React.useState(2);
    const [isSimulating, setIsSimulating] = React.useState(false);
    const [hasSimulated, setHasSimulated] = React.useState<Record<number, boolean>>({});

    React.useEffect(() => {
        if (scenariosData) {
            const suggestedIndex = scenariosData.scenarios.findIndex((s: any) => s.risk === scenariosData.suggested_risk);
            setCurrentScenarioIndex(suggestedIndex >= 0 ? suggestedIndex : 2);
        }
    }, [scenariosData]);

    if (!scenariosData || !user) return null;

    const currentScenario = scenariosData.scenarios[currentScenarioIndex] || scenariosData.scenarios[0];

    const handleSliderChange = (value: number[]) => {
        const val = value[0];
        const totalBuckets = scenariosData.scenarios.length;
        let index = Math.round((val / 100) * (totalBuckets - 1));
        index = Math.max(0, Math.min(index, totalBuckets - 1));
        setCurrentScenarioIndex(index);
    };

    const sliderValue = scenariosData.scenarios.length > 1
        ? (currentScenarioIndex / (scenariosData.scenarios.length - 1)) * 100
        : 0;

    const handleRunSimulation = async () => {
        setIsSimulating(true);
        await simulateScenario();
        setIsSimulating(false);
        setHasSimulated(prev => ({ ...prev, [currentScenarioIndex]: true }));
    };

    const isCurrentScenarioSimulated = hasSimulated[currentScenarioIndex] || false;

    return (
        <div className="flex flex-col h-full bg-zinc-50/50 dark:bg-zinc-950/50">
            <div className="flex items-center gap-4 p-4 md:p-6 border-b border-zinc-200 dark:border-zinc-800 bg-white/50 dark:bg-zinc-900/50 backdrop-blur-sm sticky top-0 z-10 transition-all">
                <Button variant="ghost" size="sm" onClick={onBack} className="gap-2 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
                    <ArrowLeft className="h-4 w-4" /> Back to Main
                </Button>
                <div className="h-4 w-px bg-zinc-300 dark:bg-zinc-700"></div>
                <h2 className="font-semibold text-lg text-zinc-900 dark:text-zinc-100">{program} Workspace</h2>
            </div>

            <div className="flex-1 overflow-auto p-4 md:p-6 lg:p-8">
                <div className="mx-auto max-w-4xl space-y-8">

                    <div>
                        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50 mb-2">Current Program State Summary</h1>
                        <p className="text-zinc-500 dark:text-zinc-400">Monitoring and active adjustments for {program}.</p>
                    </div>

                    <Tabs defaultValue="overview" className="w-full">
                        <TabsList className="w-full justify-start rounded-none border-b border-zinc-200 dark:border-zinc-800 bg-transparent p-0 overflow-x-auto">
                            <TabsTrigger value="overview" className="rounded-none border-b-2 border-transparent data-[state=active]:border-indigo-600 dark:data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 pb-2 pt-2">Overview</TabsTrigger>
                            <TabsTrigger value="allocation" className="rounded-none border-b-2 border-transparent data-[state=active]:border-indigo-600 dark:data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 pb-2 pt-2">Allocation</TabsTrigger>
                            <TabsTrigger value="historical" className="rounded-none border-b-2 border-transparent data-[state=active]:border-indigo-600 dark:data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 pb-2 pt-2">Historical Impact</TabsTrigger>
                            <TabsTrigger value="future-outlook" className="rounded-none border-b-2 border-transparent data-[state=active]:border-indigo-600 dark:data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 pb-2 pt-2 whitespace-nowrap">Future Outlook</TabsTrigger>
                            <TabsTrigger value="trades" className="rounded-none border-b-2 border-transparent data-[state=active]:border-indigo-600 dark:data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 pb-2 pt-2">Trades</TabsTrigger>
                        </TabsList>

                        <TabsContent value="overview" className="pt-8 space-y-6 outline-none">

                            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                                <MetricCard title="Modeled Volatility" value={<AnimatedNumber value={`${currentScenario.vol}%`} />} trend={{ value: "Forecast", label: "based on historicals" }} className="bg-white/50 dark:bg-zinc-900/50" />
                                <MetricCard title="Modeled Income" value={<AnimatedNumber value={`${currentScenario.income}%`} />} trend={currentScenario.income > 3.9 ? { value: "Strong", positive: true } : { value: "Moderate", positive: false }} className="bg-white/50 dark:bg-zinc-900/50" />
                                <MetricCard title="Concentration" value={<AnimatedNumber value={`${currentScenario.concentration}%`} />} trend={{ value: `Max ${user.concentration_threshold}%`, label: "limit" }} className="bg-white/50 dark:bg-zinc-900/50" />
                                <MetricCard title="Diversification Score" value={<AnimatedNumber value={currentScenario.diversification} />} icon={<Layers className="h-4 w-4" />} trend={currentScenario.diversification >= 75 ? { value: "Optimal", positive: true } : { value: "Warning", positive: false }} className="bg-white/50 dark:bg-zinc-900/50" />
                            </div>

                            <Card className="border-indigo-100 dark:border-indigo-900/30 overflow-hidden relative shadow-sm">
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2 text-base">
                                        Program Modeling Simulator
                                    </CardTitle>
                                    <CardDescription>Adjust program intensity to see modeled outcomes.</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-6">
                                    {/* Slider Area */}
                                    <div className="space-y-4 pt-2">
                                        <div className="relative pt-6 pb-2">
                                            <Slider
                                                defaultValue={[sliderValue]}
                                                value={[sliderValue]}
                                                max={100}
                                                step={100 / (scenariosData.scenarios.length - 1)}
                                                onValueChange={handleSliderChange}
                                                className="z-10 relative [&_[role=slider]]:bg-white [&_[role=slider]]:border-zinc-300 [&_[role=slider]]:shadow-sm [&_[data-orientation=horizontal]>span:first-child>span]:bg-indigo-500"
                                            />
                                        </div>
                                        <div className="flex justify-between text-xs font-medium text-zinc-400 px-1">
                                            {scenariosData.scenarios.map((scenario: any, index: number) => (
                                                <span key={index} className={`cursor-pointer hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors ${currentScenarioIndex === index ? "text-indigo-600 dark:text-indigo-400 font-bold" : ""}`} onClick={() => setCurrentScenarioIndex(index)}>
                                                    Level {index + 1}
                                                </span>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Modeled Outcomes */}
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 border-t border-zinc-100 dark:border-zinc-800/50 pt-6">
                                        <div className="flex flex-col gap-1">
                                            <div className="text-zinc-500 dark:text-zinc-400 text-xs font-medium uppercase tracking-wider">Concentration Reduction</div>
                                            <div className="text-xl font-semibold flex items-center gap-3">
                                                <span className="text-zinc-400 text-base">{Math.max(...user.positions.map((p: any) => p.concentration))}%</span>
                                                <span className="text-zinc-300">&rarr;</span>
                                                <span className="text-indigo-600 dark:text-indigo-400"><AnimatedNumber value={`${currentScenario.concentration}%`} /></span>
                                            </div>
                                        </div>
                                        <div className="flex flex-col gap-1">
                                            <div className="text-zinc-500 dark:text-zinc-400 text-xs font-medium uppercase tracking-wider">Tax Impact</div>
                                            <div className="text-xl font-semibold text-emerald-600">+$12,450</div>
                                        </div>
                                        <div className="flex flex-col gap-1">
                                            <div className="text-zinc-500 dark:text-zinc-400 text-xs font-medium uppercase tracking-wider">Alignment</div>
                                            <div className="text-xl font-semibold text-zinc-900 dark:text-white">+42 pts</div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                        </TabsContent>

                        <TabsContent value="allocation" className="pt-8 text-sm text-zinc-500 dark:text-zinc-400 min-h-[300px]">
                            <p>Detailed asset allocation drift analysis compared to target weights.</p>
                        </TabsContent>

                        <TabsContent value="historical" className="pt-8 text-sm text-zinc-500 dark:text-zinc-400 min-h-[300px]">
                            <p>Historical performance backtesting based on actual asset returns.</p>
                        </TabsContent>

                        <TabsContent value="future-outlook" className="pt-8 outline-none min-h-[400px]">
                            {!isCurrentScenarioSimulated ? (
                                <div className="flex flex-col items-center justify-center py-16 px-4 text-center border border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl bg-zinc-50/50 dark:bg-zinc-900/20">
                                    <Activity className="h-8 w-8 text-zinc-300 mb-4" />
                                    <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">Projections not loaded</h3>
                                    <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-sm mb-6">
                                        Run a Monte Carlo simulation to forecast potential outcomes for the current program state.
                                    </p>
                                    <Button onClick={handleRunSimulation} disabled={isSimulating} className="bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-white dark:text-zinc-900">
                                        {isSimulating ? "Simulating..." : "Run Simulation"}
                                    </Button>
                                </div>
                            ) : (
                                <div className="space-y-4 animate-in fade-in zoom-in-95 duration-300">
                                    <div className="flex items-center justify-between px-2">
                                        <h4 className="text-sm font-medium flex items-center gap-2">
                                            10-Year Probability Distribution
                                            <Badge variant="secondary" className="text-[10px] bg-zinc-100 dark:bg-zinc-800 font-normal">10,000 Paths</Badge>
                                        </h4>
                                        <Button variant="ghost" size="sm" onClick={handleRunSimulation}>Rerun</Button>
                                    </div>
                                    <div className="h-[240px] w-full rounded-xl bg-white dark:bg-zinc-950 border border-zinc-100 dark:border-zinc-800 relative overflow-hidden flex items-end px-4 gap-1 sm:gap-2 pt-8">
                                        {[2, 5, 12, 25, 45, 75, 95, 80, 50, 20, 8, 3, 1].map((height, i) => (
                                            <div key={i} className="flex-1 bg-zinc-200 dark:bg-zinc-800 hover:bg-indigo-400 dark:hover:bg-indigo-500 transition-colors relative group rounded-t-sm" style={{ height: `${height}%` }}>
                                            </div>
                                        ))}
                                        <div className="absolute left-1/2 top-4 bottom-0 w-px border-l-2 border-dashed border-zinc-400 dark:border-zinc-500 -translate-x-1/2" />
                                    </div>
                                    <div className="flex justify-between text-xs text-zinc-500 font-medium px-2">
                                        <span>Worst Case (-2.1%)</span>
                                        <span>Median (+7.2%)</span>
                                        <span>Best Case (+11.8%)</span>
                                    </div>
                                </div>
                            )}
                        </TabsContent>

                        <TabsContent value="trades" className="pt-8 text-sm text-zinc-500 dark:text-zinc-400 min-h-[300px]">
                            <p>List of actionable trades generated to adjust allocation parameters.</p>
                            <div className="mt-6 flex gap-3">
                                <Button variant="outline">Discard Plan</Button>
                                <Button className="bg-zinc-900 text-white dark:bg-white dark:text-zinc-900">Export Trades</Button>
                            </div>
                        </TabsContent>
                    </Tabs>

                </div>
            </div>
        </div>
    )
}
