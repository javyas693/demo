import * as React from "react"
import { Sparkles, MessageSquare, Send, HelpCircle } from "lucide-react"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Badge } from "@/components/ui/badge"

export function DashboardLayout({ children, copilotMessage, copilotActions }: { children: React.ReactNode, copilotMessage: string, copilotActions: React.ReactNode }) {
    return (
        <TooltipProvider delayDuration={300}>
            <div className="flex h-screen w-full flex-col bg-zinc-50 dark:bg-zinc-950 font-sans">
                {/* Global Header */}
                <header className="flex h-14 items-center justify-between border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 px-4 xl:px-8 z-50 transition-colors">
                    <div className="flex items-center gap-2 font-semibold text-lg text-zinc-900 dark:text-zinc-50 tracking-tight">
                        <Sparkles className="h-5 w-5 text-zinc-900 dark:text-zinc-100 shadow-sm" />
                        <span>AI Advisory</span>
                    </div>
                    <div className="flex items-center gap-4">
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button variant="ghost" size="icon" className="hidden sm:flex text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
                                    <HelpCircle className="h-5 w-5" />
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent><p>Get help</p></TooltipContent>
                        </Tooltip>
                        <ThemeToggle />
                    </div>
                </header>

                {/* Main 2-Column Layout */}
                <main className="flex flex-1 overflow-hidden relative">

                    {/* Left Panel (75%) */}
                    <section className="flex flex-1 flex-col bg-white dark:bg-zinc-950 transition-colors relative z-0">
                        {children}
                    </section>

                    {/* Right Panel: Copilot (25% - Persistent) */}
                    <aside className="w-[320px] lg:w-[380px] flex-col border-l border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/30 hidden md:flex transition-colors z-20">
                        <div className="p-5 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-900/50 flex-none flex items-center justify-between sticky top-0 backdrop-blur-md z-10">
                            <h2 className="flex items-center gap-2 font-medium text-zinc-900 dark:text-zinc-100">
                                <MessageSquare className="h-4 w-4 text-zinc-500 dark:text-zinc-400" />
                                Copilot
                            </h2>
                        </div>

                        <div className="flex-1 overflow-auto p-5 space-y-6">
                            {/* Context-Aware Initial Message */}
                            <div className="flex gap-3">
                                <div className="mt-0.5 h-8 w-8 shrink-0 rounded-lg bg-zinc-200 dark:bg-zinc-800 flex items-center justify-center border border-zinc-300 dark:border-zinc-700 shadow-sm">
                                    <Sparkles className="h-4 w-4 text-zinc-700 dark:text-zinc-300" />
                                </div>
                                <div className="space-y-2">
                                    <div className="rounded-2xl rounded-tl-sm bg-white dark:bg-zinc-800 border border-zinc-200/50 dark:border-zinc-700/50 px-4 py-3 text-[14px] text-zinc-900 dark:text-zinc-100 shadow-sm leading-relaxed">
                                        {copilotMessage}
                                    </div>
                                    {copilotActions}
                                </div>
                            </div>
                        </div>

                        <div className="p-5 border-t border-zinc-200 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-900/50 pt-4 flex-none">
                            <div className="relative flex items-center shadow-sm rounded-full bg-white dark:bg-zinc-950">
                                <input
                                    type="text"
                                    placeholder="Ask Copilot..."
                                    className="w-full h-11 rounded-full border border-zinc-300 dark:border-zinc-700 bg-transparent pl-4 pr-12 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600 placeholder:text-zinc-400 dark:placeholder:text-zinc-500 transition-all font-medium"
                                />
                                <Button size="icon" className="absolute right-1 h-9 w-9 rounded-full bg-zinc-900 dark:bg-zinc-700 hover:bg-zinc-800 dark:hover:bg-zinc-600 text-white shadow-sm">
                                    <Send className="h-4 w-4" />
                                </Button>
                            </div>
                        </div>
                    </aside>

                </main>
            </div>
        </TooltipProvider>
    )
}
