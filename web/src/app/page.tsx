"use client"

import * as React from "react"
import { motion, AnimatePresence } from "motion/react"
import { Sparkles, AlertTriangle } from "lucide-react"

import { session, patchProfile } from "@/lib/api"
import { WelcomeLanding, ChatSummaryPayload } from "@/components/welcome-landing"
import { MainAppClient } from "@/components/main-app-client"

export default function Home() {
  const [isLoggedIn, setIsLoggedIn] = React.useState<boolean>(false);
  const [showBanner, setShowBanner] = React.useState(false);
  const [isLoading, setIsLoading] = React.useState(true);
  const [apiError, setApiError] = React.useState(false);

  React.useEffect(() => {
    async function checkSession() {
      try {
        const res = await session();
        setIsLoggedIn(res.is_logged_in);
      } catch (error) {
        console.error("Failed to load session:", error);
        setApiError(true);
      } finally {
        setIsLoading(false);
      }
    }
    checkSession();
  }, []);

  const handleLogin = async () => {
    try {
      await import("@/lib/api").then(api => api.login());
      setIsLoggedIn(true);
    } catch (error) {
      console.error("Login failed:", error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen text-zinc-500 bg-white dark:bg-zinc-950">
        <div className="flex flex-col items-center gap-4 animate-pulse">
          <Sparkles className="h-8 w-8 text-zinc-300" />
          <p>Loading Platform...</p>
        </div>
      </div>
    );
  }

  if (apiError) {
    return (
      <div className="flex items-center justify-center min-h-screen text-zinc-500 bg-white dark:bg-zinc-950">
        <div className="flex flex-col items-center gap-4">
          <AlertTriangle className="h-8 w-8 text-red-400" />
          <p className="text-zinc-600 dark:text-zinc-400 font-medium">Unable to connect to advisory services. Please try again later.</p>
        </div>
      </div>
    );
  }

  if (!isLoggedIn) {
    return <WelcomeLanding 
      onLogin={handleLogin}
      onGetStarted={async (payload: ChatSummaryPayload) => {
        try {
          await patchProfile({
            risk_score: Math.round(payload.risk_score_final),
            cash_to_invest: payload.starting_cash,
            positions: payload.position_lots.map(lot => ({
              symbol: lot.ticker,
              shares: lot.shares,
              cost_basis: lot.cost_basis,
            })),
          });
          await handleLogin();
        } catch (e) {
          console.error("Failed to persist initial profile", e);
        }
        setShowBanner(true);
      }} 
    />;
  }

  return (
    <>
      {/* Banner */}
      <AnimatePresence>
        {showBanner && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="bg-zinc-900 border-b border-zinc-800 text-white flex items-center justify-center text-sm font-medium relative py-2 z-[60]"
          >
            <Sparkles className="w-4 h-4 mr-2 text-zinc-400" /> Capital Plan Active
            <button onClick={() => setShowBanner(false)} className="absolute right-4 opacity-70 hover:opacity-100">×</button>
          </motion.div>
        )}
      </AnimatePresence>

      <MainAppClient />
    </>
  );
}
