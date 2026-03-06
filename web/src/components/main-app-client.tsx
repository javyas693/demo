"use client"

import * as React from "react"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { CapitalSummary } from "@/components/views/capital-summary"
import { useRouter } from "next/navigation"
import { Badge } from "@/components/ui/badge"

export function MainAppClient() {
    const router = useRouter();

    const handleSelectProgram = (programKey: string) => {
        // We receive the programKey from the UI, e.g. "risk_reduction"
        // And we need to route to the actual page /programs/risk_reduction
        if (programKey.startsWith("/")) {
            router.push(programKey);
        } else {
            router.push(`/programs/${programKey}`);
        }
    };

    const copilotActions = (
        <div className="flex gap-2 flex-wrap pt-1">
            <Badge variant="outline" className="cursor-pointer bg-white dark:bg-zinc-900 hover:bg-zinc-100 dark:hover:bg-zinc-800 font-medium text-zinc-600 dark:text-zinc-300 transition-colors">Show summary</Badge>
            <Badge variant="outline" className="cursor-pointer bg-white dark:bg-zinc-900 hover:bg-zinc-100 dark:hover:bg-zinc-800 font-medium text-zinc-600 dark:text-zinc-300 transition-colors">Auto-resolve</Badge>
        </div>
    );

    return (
        <DashboardLayout
            copilotMessage="Your capital is aligned. 2 items require attention."
            copilotActions={copilotActions}
        >
            <div className="flex-1 overflow-auto bg-white dark:bg-zinc-950 w-full h-full relative">
                <CapitalSummary onSelectProgram={handleSelectProgram} />
            </div>
        </DashboardLayout>
    );
}
