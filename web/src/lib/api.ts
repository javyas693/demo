export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

// Types
export interface SessionResponse {
    has_profile: boolean;
    is_logged_in: boolean;
    user_id?: string;
}

export interface CapitalSummary {
    portfolio_value: number;
    cash_available: number;
    largest_holding_symbol: string | null;
    largest_holding_value: number;
    concentration_pct: number;

    concentration_status: string;
    items_require_review: number;
}

export interface ProgramSignal {
    id: string;
    title: string;
    description: string;
    severity: "High" | "Medium" | "Low";
    primary_action: {
        label: string;
        route: string;
    };
}

export interface SignalsResponse {
    signals: ProgramSignal[];
}

export interface ProgramWorkspaceResponse {
    program: string;
    summary_title: string;
    summary_subtitle: string;
    status: string;
    summary_cards: {
        label: string;
        value: string;
        tag: string | null;
    }[];
    signals: ProgramSignal[];
    tabs: string[];
}

export interface TradeAction {
    type: "SELL" | "BUY" | "CASH_CREDIT" | "ALLOCATE_CASH";
    symbol?: string;
    shares?: number;
    dollars?: number;
    amount?: number;
    model_key?: string;
    notes?: string;
}

export interface TradePlan {
    plan_id: string;
    program_key: string;
    created_at: string;
    summary: string;
    why: string[];
    assumed_price_policy: string;
    cash_delta_estimate: number;
    actions: TradeAction[];
    requires_approval: boolean;
}

export interface PlanProposeResponse {
    plan: TradePlan;
}

export interface EventLog {
    date: string;
    event: string;
    reason: string;
    data: string;
    timestamp: string;
}

export interface CombinedTradePlan {
    sell_orders: TradePlan[];
    buy_orders: TradePlan[];
    total_tax_estimate: number;
    net_reinvestment_total: number;
    starting_cash: number;
    liquidity_warning: boolean;
}

export interface PlanCommitResponse {
    plan: TradePlan;
    profile: any;
    capital_summary: CapitalSummary;
    signals: SignalsResponse;
}

export interface ChatRequest {
    conversation_id?: string;
    message: string;
}

export interface ChatResponse {
    conversation_id: string;
    response_type: string;
    sequence: number;
    user_name: string | null;
    agent_message: string;
    payload: any;
}

// Helpers
async function apiGet<T>(endpoint: string): Promise<T> {
    const res = await fetch(`${API_BASE}${endpoint}`, { cache: "no-store" });
    if (!res.ok) {
        throw new Error(`API GET ${endpoint} failed with status ${res.status}`);
    }
    return res.json();
}

async function apiPost<T>(endpoint: string, data: any): Promise<T> {
    const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
        cache: "no-store"
    });
    if (!res.ok) {
        throw new Error(`API POST ${endpoint} failed with status ${res.status}`);
    }
    return res.json();
}

// Removed unused apiPatch function.

// Endpoints
export async function session(): Promise<SessionResponse> {
    return apiGet<SessionResponse>("/session");
}

export async function capitalSummary(): Promise<CapitalSummary> {
    return apiGet<CapitalSummary>("/capital/summary");
}

export async function signals(): Promise<SignalsResponse> {
    return apiGet<SignalsResponse>("/signals");
}

export async function program(programKey: string): Promise<ProgramWorkspaceResponse> {
    return apiGet<ProgramWorkspaceResponse>(`/programs/${programKey}`);
}

export async function patchProfile(data: any): Promise<any> {
    return apiPost<any>("/profile/patch", data);
}

export async function fetchProfile(): Promise<any> {
    return apiGet<any>("/profile");
}

export async function postInitializeStrategy(data: any): Promise<any> {
    return apiPost<any>("/api/v1/strategy/initialize", data);
}

export async function simulateScenario() {
    return new Promise((resolve) => {
        setTimeout(() => {
            resolve({ status: "success", simulated: true });
        }, 1500);
    });
}

export async function postPlanPropose(programKey: string, params: any): Promise<PlanProposeResponse> {
    return apiPost<PlanProposeResponse>("/plans/propose", { program_key: programKey, params });
}

export async function postPlanCommit(planId: string, mode: string = "paper"): Promise<PlanCommitResponse> {
    return apiPost<PlanCommitResponse>(`/plans/commit/${planId}?mode=${mode}`, {});
}

export async function fetchTransitionPlan(riskScore: number): Promise<CombinedTradePlan> {
    const payload = {
        model_id: "core",
        risk_score: riskScore,
        include_income: false,
        target_dte_days: 30,
        target_delta: 0.20,
        share_reduction_trigger_pct: 0.0,
        loss_handling_mode: "harvest_hold",
        max_shares_per_month: 500,
        starting_cash: 50000.0
    };
    return apiPost<CombinedTradePlan>("/api/v1/programs/transition/propose", payload);
}

export async function fetchEvents(): Promise<{ events: EventLog[] }> {
    return apiGet<{ events: EventLog[] }>("/api/v1/events");
}

export interface SimulationParams {
    symbol: string;
    initial_shares: number;
    cost_basis: number;
    starting_cash: number;
    coverage_pct: number;
    target_delta: number;
    target_dte_days: number;
    profit_capture_pct?: number;
    share_reduction_trigger_pct: number;
    start_date?: string;
    end_date?: string;
    loss_handling_mode?: string;
    max_shares_per_month?: number;
}

export interface SimulationResult {
    summary: any;
    time_series: any[];
}

export async function simulateConcentratedPosition(params: SimulationParams): Promise<SimulationResult> {
    return apiPost<SimulationResult>("/programs/concentrated_position/simulate", params);
}

export interface FrontierProposalResponse {
    as_of: string;
    model_id: string;
    frontier_version: string;
    frontier_status: string;
    risk_score: number;
    exp_return: number;
    vol: number;
    sharpe: number | null;
    target_weights: Record<string, number>;
}

export async function postFrontierPropose(riskScore: number, modelId: string = "core"): Promise<FrontierProposalResponse> {
    return apiPost<FrontierProposalResponse>("/frontier/propose", { risk_score: riskScore, model_id: modelId });
}

export interface MPSimulateParams {
    target_weights: Record<string, number>;
    initial_capital: number;
    start_date: string;
    end_date: string;
}

export async function postMPSimulate(params: MPSimulateParams): Promise<SimulationResult & { audit_log: any[] }> {
    return apiPost<SimulationResult & { audit_log: any[] }>("/programs/core_allocation/simulate", params);
}

export async function getMPHistory(): Promise<any> {
    return apiGet<any>("/programs/core_allocation/history");
}

export interface AnchorIncomeSimulateParams {
    start_date: string;
    end_date: string;
    initial_capital: number;
    reinvest_pct: number;
}

export async function postAnchorIncomeSimulate(params: AnchorIncomeSimulateParams): Promise<any> {
    return apiPost<any>("/programs/anchor_income/simulate", params);
}

export async function getAnchorIncomeHistory(): Promise<any> {
    return apiGet<any>("/programs/anchor_income/history");
}

export async function login(): Promise<any> {
    return apiPost<any>("/login", {});
}

export async function logout(): Promise<any> {
    return apiPost<any>("/logout", {});
}

export async function postChat(data: ChatRequest): Promise<ChatResponse> {
    return apiPost<ChatResponse>("/chat", data);
}
