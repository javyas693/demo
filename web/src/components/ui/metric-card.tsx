import * as React from "react"
import { motion, AnimatePresence } from "motion/react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

export interface MetricCardProps extends React.HTMLAttributes<HTMLDivElement> {
    title: string
    value: string | React.ReactNode
    trend?: {
        value: string
        positive?: boolean
        label?: string
    }
    icon?: React.ReactNode
}

export function MetricCard({
    title,
    value,
    trend,
    icon,
    className,
    ...props
}: MetricCardProps) {
    // Try to extract only the numeric part for the animation key if it's a string
    const animationKey = typeof value === 'string' ? value : "complex-value";

    return (
        <Card className={cn("overflow-hidden", className)} {...props}>
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
                    {title}
                </CardTitle>
                {icon && <div className="text-zinc-400 dark:text-zinc-500">{icon}</div>}
            </CardHeader>
            <CardContent>
                <div className="relative h-8 w-full overflow-hidden">
                    <AnimatePresence mode="popLayout" initial={false}>
                        <motion.div
                            key={animationKey}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20, position: "absolute" }}
                            transition={{ duration: 0.3, type: "spring", bounce: 0.4 }}
                            className="text-2xl font-bold text-zinc-900 dark:text-zinc-50 whitespace-nowrap"
                        >
                            {value}
                        </motion.div>
                    </AnimatePresence>
                </div>

                {trend && (
                    <div className="mt-1 flex items-center text-xs space-x-2">
                        <AnimatePresence mode="wait">
                            <motion.div
                                key={trend.value}
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                transition={{ duration: 0.2 }}
                            >
                                <Badge
                                    variant={trend.positive ? "success" : "destructive"}
                                    className="px-1.5 py-0 rounded-sm"
                                >
                                    {trend.positive ? "+" : "-"}
                                    {trend.value}
                                </Badge>
                            </motion.div>
                        </AnimatePresence>
                        {trend.label && (
                            <span className="text-zinc-500 dark:text-zinc-400 truncate">
                                {trend.label}
                            </span>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
