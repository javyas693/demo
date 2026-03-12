"use client"

import * as React from "react"
import { motion, AnimatePresence } from "motion/react"
import { Sparkles, ArrowRight, UserCircle, Send, Target, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { postChat, ChatResponse } from "@/lib/api"

export function WelcomeLanding({ onGetStarted, onLogin }: { onGetStarted: () => void, onLogin: () => void }) {
    const [step, setStep] = React.useState<'hero' | 'chat'>('hero')

    const [messages, setMessages] = React.useState<{ role: 'assistant' | 'user', content: string }[]>([])
    const [inputValue, setInputValue] = React.useState("")
    const [conversationId, setConversationId] = React.useState<string | undefined>(undefined)
    const [isTyping, setIsTyping] = React.useState(false)
    const [isComplete, setIsComplete] = React.useState(false)

    // Meter states
    const [meterScore, setMeterScore] = React.useState(50) // 0-100

    const getMeterLabel = (score: number) => {
        if (score < 40) return "Conservative"
        if (score < 70) return "Balanced"
        return "Growth"
    }

    // Auto-scroll chat to bottom
    const chatEndRef = React.useRef<HTMLDivElement>(null)
    React.useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [messages, isTyping])

    const handleSendMessage = async (e?: React.FormEvent, manualText?: string, silent: boolean = false) => {
        e?.preventDefault()
        const textToSend = manualText || inputValue.trim()
        if (!textToSend || isTyping || isComplete) return

        if (!silent) {
            setInputValue("")
            setMessages(prev => [...prev, { role: 'user', content: textToSend }])
        }
        setIsTyping(true)

        try {
            const response = await postChat({
                message: textToSend,
                conversation_id: conversationId
            })

            setConversationId(response.conversation_id)
            setMessages(prev => [...prev, { role: 'assistant', content: response.agent_message }])

            // Update meter if risk score is in payload
            if (response.response_type === 'risk_score_complete' && response.payload?.risk_score_result?.final_risk_score) {
                setMeterScore(response.payload.risk_score_result.final_risk_score)
            }

            // If analysis is complete or flow ends
            if (response.response_type === 'analysis_result') {
                setIsComplete(true)
                setTimeout(() => {
                    onGetStarted()
                }, 3000)
            }
        } catch (error) {
            console.error("Chat error:", error)
            setMessages(prev => [...prev, { role: 'assistant', content: "I'm sorry, I'm having trouble connecting right now. Please try again." }])
        } finally {
            setIsTyping(false)
        }
    }

    // Auto-initialize chatbot on first open
    React.useEffect(() => {
        if (step === 'chat' && messages.length === 0 && !isTyping) {
            handleSendMessage(undefined, "hi", true)
        }
    }, [step])

    const handleQuickReply = (text: string) => {
        handleSendMessage(undefined, text)
    }

    return (
        <div className="min-h-screen bg-zinc-950 text-zinc-50 flex flex-col items-center justify-center p-6 relative overflow-hidden selection:bg-indigo-500/30 font-sans">

            {/* Top Right Login */}
            <div className="absolute top-6 right-8">
                <button 
                  onClick={onLogin}
                  className="text-sm font-medium text-zinc-400 hover:text-white transition-colors"
                >
                  Log In
                </button>
            </div>

            {/* Decorative dark theme background glow */}
            <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-indigo-900/20 blur-[120px] rounded-[100%] pointer-events-none" />

            <main className="w-full max-w-4xl mx-auto relative z-10 flex flex-col items-center justify-center min-h-[80vh]">

                {/* Generous Whitespace & Centered Content */}
                <AnimatePresence mode="wait">
                    {step === 'hero' && (
                        <motion.div
                            key="hero-text"
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20, filter: "blur(4px)" }}
                            transition={{ duration: 0.5, ease: "easeOut" }}
                            className="text-center mb-12"
                        >
                            <h1 className="text-[32px] font-medium tracking-tight text-white mb-10 leading-[1.15] max-w-3xl mx-auto">
                                You worked hard to build your wealth.<br />
                                <span className="text-zinc-400">Now manage it with clarity and confidence.</span>
                            </h1>
                            <p className="text-lg md:text-[20px] text-white/90 font-normal max-w-2xl mx-auto leading-relaxed">
                                Reduce concentration risk, optimize tax efficiency, and generate income.<br />
                                Aligned to your goals.
                            </p>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Centered Assistant Card */}
                <motion.div
                    layout
                    initial={{ opacity: 0, scale: 0.95, y: 30 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    transition={{ duration: 0.6, type: "spring", bounce: 0.2 }}
                    className={`w-full bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col transition-all duration-500 ease-in-out ${step === 'hero' ? 'max-w-[600px] min-h-[220px]' : 'max-w-[700px] h-[600px]'
                        }`}
                >
                    {/* Card Header */}
                    <div className="flex-none p-5 border-b border-zinc-800/50 bg-zinc-900/80 backdrop-blur-md flex items-center justify-between z-10 relative">
                        <div className="flex items-center gap-3">
                            <div className="h-8 w-8 rounded-full bg-indigo-500/20 flex items-center justify-center">
                                <Sparkles className="h-4 w-4 text-indigo-400" />
                            </div>
                            <div>
                                <h2 className="text-base font-semibold text-white leading-tight">Capital Assistant</h2>
                                {step === 'chat' && (
                                    <p className="text-xs text-zinc-400 flex items-center gap-1">
                                        <span className="relative flex h-2 w-2">
                                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                                        </span>
                                        AI Online
                                    </p>
                                )}
                            </div>
                        </div>

                        {/* Capital Alignment Meter (Only visible in chat) */}
                        <AnimatePresence>
                            {step === 'chat' && (
                                <motion.div
                                    initial={{ opacity: 0, x: 20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.3 }}
                                    className="flex items-center gap-4 bg-zinc-950/50 px-4 py-2 rounded-xl border border-zinc-800/80"
                                >
                                    <div className="flex flex-col items-end mr-2">
                                        <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium leading-tight">Alignment</span>
                                        <span className="text-sm font-bold text-white leading-tight">{getMeterLabel(meterScore)}</span>
                                    </div>

                                    <div className="flex items-center gap-3">
                                        <div className="w-32 h-2.5 rounded-full bg-zinc-800 relative overflow-hidden flex">
                                            <div className="absolute inset-0 w-full h-full opacity-30 bg-gradient-to-r from-emerald-500 via-yellow-500 to-red-500 flex" />

                                            {/* Animated Indicator */}
                                            <motion.div
                                                className="absolute h-full w-1 shadow-[0_0_8px_2px_rgba(255,255,255,0.8)] bg-white rounded-full top-0 bottom-0 z-10"
                                                animate={{ left: `calc(${meterScore}% - 2px)` }}
                                                transition={{ type: "spring", bounce: 0.1, duration: 1.2 }}
                                            />

                                            {/* Filled Track up to indicator */}
                                            <motion.div
                                                className="h-full bg-gradient-to-r from-emerald-500 via-amber-400 to-red-500 z-0"
                                                animate={{ width: `${meterScore}%` }}
                                                transition={{ type: "spring", bounce: 0.1, duration: 1.2 }}
                                            />
                                        </div>
                                        <motion.div
                                            key={meterScore}
                                            initial={{ opacity: 0, scale: 0.5 }}
                                            animate={{ opacity: 1, scale: 1 }}
                                            className="font-mono text-xs font-bold w-6 text-right text-indigo-300"
                                        >
                                            {meterScore}
                                        </motion.div>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>

                    {/* Dynamic Content Body */}
                    <div className="flex-1 overflow-hidden relative flex flex-col bg-zinc-950/30">
                        <AnimatePresence mode="wait">
                            {step === 'hero' ? (
                                // Hero State Content
                                <motion.div
                                    key="hero-content"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    className="flex-1 flex flex-col items-center justify-center p-8 text-center"
                                >
                                    <p className="text-xl text-zinc-300 mb-8 max-w-md font-medium">
                                        "Let’s design how your wealth should work for you."
                                    </p>
                                    <Button
                                        size="lg"
                                        className="h-12 px-8 rounded-full bg-white text-black hover:bg-zinc-200 hover:scale-105 transition-all text-base font-semibold"
                                        onClick={() => setStep('chat')}
                                    >
                                        Begin <ArrowRight className="ml-2 h-4 w-4" />
                                    </Button>
                                </motion.div>
                            ) : (
                                // Chat State Content
                                <motion.div
                                    key="chat-content"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    transition={{ delay: 0.2 }}
                                    className="flex-1 flex flex-col h-full absolute inset-0"
                                >
                                    {/* Message List */}
                                    <div className="flex-1 overflow-y-auto p-6 space-y-6">
                                        {messages.map((msg, idx) => (
                                            <motion.div
                                                key={idx}
                                                initial={{ opacity: 0, y: 10, scale: 0.98 }}
                                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                                className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                                            >
                                                <div className={`mt-0.5 h-8 w-8 shrink-0 rounded-full flex items-center justify-center ${msg.role === 'user' ? 'bg-zinc-800' : 'bg-indigo-500/20'
                                                    }`}>
                                                    {msg.role === 'user' ? (
                                                        <UserCircle className="h-5 w-5 text-zinc-400" />
                                                    ) : (
                                                        <Sparkles className="h-4 w-4 text-indigo-400" />
                                                    )}
                                                </div>
                                                <div className={`px-4 py-3 text-sm rounded-2xl max-w-[85%] leading-relaxed ${msg.role === 'user'
                                                    ? 'bg-indigo-600 text-white rounded-tr-sm'
                                                    : 'bg-zinc-800/80 text-zinc-200 rounded-tl-sm border border-zinc-700/50'
                                                    }`}>
                                                    {msg.content}
                                                </div>
                                            </motion.div>
                                        ))}

                                        {isTyping && (
                                            <motion.div
                                                initial={{ opacity: 0 }}
                                                animate={{ opacity: 1 }}
                                                className="flex gap-3"
                                            >
                                                <div className="mt-0.5 h-8 w-8 shrink-0 rounded-full bg-indigo-500/20 flex items-center justify-center">
                                                    <Sparkles className="h-4 w-4 text-indigo-400" />
                                                </div>
                                                <div className="px-4 py-4 rounded-2xl rounded-tl-none bg-zinc-800/50 border border-zinc-700/50 flex items-center gap-1.5">
                                                    <div className="h-1.5 w-1.5 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                                                    <div className="h-1.5 w-1.5 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                                                    <div className="h-1.5 w-1.5 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                                                </div>
                                            </motion.div>
                                        )}
                                        <div ref={chatEndRef} />
                                    </div>

                                    {/* Quick Replies - Show based on messages instead of chatStage */}
                                    {!isTyping && messages.length === 1 && (
                                        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="px-6 pb-2 flex flex-wrap gap-2">
                                            <Badge variant="outline" className="cursor-pointer bg-zinc-900 border-zinc-700 hover:bg-zinc-800 py-1.5" onClick={() => handleQuickReply("Long-term Growth")}>Long-term Growth</Badge>
                                            <Badge variant="outline" className="cursor-pointer bg-zinc-900 border-zinc-700 hover:bg-zinc-800 py-1.5" onClick={() => handleQuickReply("Steady Income")}>Steady Income</Badge>
                                            <Badge variant="outline" className="cursor-pointer bg-zinc-900 border-zinc-700 hover:bg-zinc-800 py-1.5" onClick={() => handleQuickReply("Capital Preservation")}>Capital Preservation</Badge>
                                        </motion.div>
                                    )}

                                    {/* Input Area */}
                                    <div className="p-4 border-t border-zinc-800/80 bg-zinc-900/50 backdrop-blur-md pb-6">
                                        <form onSubmit={handleSendMessage} className="relative flex items-center max-w-3xl mx-auto">
                                            <input
                                                type="text"
                                                value={inputValue}
                                                onChange={(e) => setInputValue(e.target.value)}
                                                placeholder="Type a message..."
                                                disabled={isTyping || isComplete}
                                                className="w-full h-12 rounded-full border border-zinc-700 bg-zinc-950/50 pl-5 pr-12 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50 placeholder:text-zinc-500 transition-all disabled:opacity-50"
                                            />
                                            <Button
                                                type="submit"
                                                size="icon"
                                                disabled={!inputValue.trim() || isTyping || isComplete}
                                                className="absolute right-1.5 h-9 w-9 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white disabled:bg-zinc-800 disabled:text-zinc-600 disabled:opacity-100"
                                            >
                                                <Send className="h-4 w-4 ml-0.5" />
                                            </Button>
                                        </form>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                </motion.div>
            </main>
        </div>
    )
}
