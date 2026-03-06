"use client"

import * as React from "react"
import { ArrowLeft, Construction } from "lucide-react"
import { useRouter } from "next/navigation"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Button } from "@/components/ui/button"

export default function IncomeStrategyPage() {
    const router = useRouter()

    return (
        <DashboardLayout
            copilotMessage="The dedicated Income Strategy module is currently under development. Proceed to the Core Portfolio or Concentrated Position workspaces for active programs."
            copilotActions={<></>}
        >
            <div className="flex flex-col h-full bg-zinc-50/50 dark:bg-zinc-950/50 w-full overflow-hidden">
                <div className="flex items-center gap-2 md:gap-4 p-4 md:p-6 border-b border-zinc-200 dark:border-zinc-800 bg-white/50 dark:bg-zinc-900/50 backdrop-blur-sm sticky top-0 z-10 transition-all flex-none">
                    <Button variant="ghost" size="sm" onClick={() => router.back()} className="gap-2 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 px-2 md:px-3">
                        <ArrowLeft className="h-4 w-4" /> <span className="hidden sm:inline">Back</span>
                    </Button>
                    <div className="h-4 w-px bg-zinc-300 dark:bg-zinc-700 mx-1 md:mx-0"></div>
                    <div className="flex flex-col ml-1 md:ml-2">
                        <h2 className="font-semibold text-base md:text-lg text-zinc-900 dark:text-zinc-100 leading-tight">Income Strategy</h2>
                        <span className="text-xs text-zinc-500">Coming Soon</span>
                    </div>
                </div>

                <div className="flex-1 overflow-auto p-4 md:p-6 lg:p-8 flex items-center justify-center">
                    <div className="flex flex-col items-center justify-center text-center max-w-sm space-y-4">
                        <div className="h-16 w-16 bg-zinc-100 dark:bg-zinc-900 rounded-full flex items-center justify-center border border-zinc-200 dark:border-zinc-800">
                            <Construction className="h-8 w-8 text-zinc-400" />
                        </div>
                        <h1 className="text-xl font-medium text-zinc-900 dark:text-zinc-100">Module Unreleased</h1>
                        <p className="text-sm text-zinc-500 dark:text-zinc-400">
                            This workspace is being connected to the execution ledger. In the meantime, you can generate income using Covered Calls on existing dense targets via the Concentrated Position module.
                        </p>
                        <Button
                            variant="default"
                            className="bg-indigo-600 hover:bg-indigo-700 text-white mt-4"
                            onClick={() => router.push('/programs/concentrated_position')}
                        >
                            Go to Concentrated Position
                        </Button>
                    </div>
                </div>
            </div>
        </DashboardLayout>
    )
}
