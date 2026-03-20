from typing import Dict, Any, List
from ai_advisory.orchestration.trace_logger import trace_log

class TLHBudgetManager:
    """
    Centralized TLH Budget Engine that enforces global tax-loss constraints
    across all strategy components. Prevents negative TLH inventory and ensures
    deterministic, auditable allocation of TLH usage.
    """
    def __init__(self, starting_inventory: float):
        self.starting_inventory = float(starting_inventory)
        self.remaining_budget = float(starting_inventory)
        self.total_used = 0.0
        self.usage_log: List[Dict[str, Any]] = []

    def request_usage(self, requested_gain: float, source: str) -> Dict[str, float]:
        """
        Approve or scale TLH usage requests.
        Returns the approved gain and the scale factor applied.
        """
        requested_gain = float(requested_gain)
        if requested_gain <= 0:
            return {
                "approved_gain": 0.0,
                "scale_factor": 1.0,
                "remaining_budget": self.remaining_budget
            }
            
        if self.remaining_budget <= 0:
            return {
                "approved_gain": 0.0,
                "scale_factor": 0.0,
                "remaining_budget": self.remaining_budget
            }
            
        if requested_gain > self.remaining_budget:
            approved_gain = self.remaining_budget
            scale_factor = approved_gain / requested_gain
        else:
            approved_gain = requested_gain
            scale_factor = 1.0
            
        return {
            "approved_gain": approved_gain,
            "scale_factor": scale_factor,
            "remaining_budget": self.remaining_budget
        }

    def consume(self, approved_gain: float, source: str) -> None:
        """
        Consumes the approved gain from the remaining budget.
        Logs the transaction.
        """
        approved_gain = float(approved_gain)
        if approved_gain <= 0:
            return
            
        if approved_gain > self.remaining_budget + 1e-9: # tiny epsilon for float math
            raise ValueError(f"Cannot consume {approved_gain} TLH; only {self.remaining_budget} remaining.")
            
        # Ensure we don't drop below 0 due to float precision
        self.remaining_budget = max(0.0, self.remaining_budget - approved_gain)
        self.total_used += approved_gain
        
        usage_record = {
            "source": source,
            "amount": approved_gain
        }
        self.usage_log.append(usage_record)
        
        trace_log(f"[TLH BUDGET]\n"
                  f"Starting: {self.remaining_budget + approved_gain:.2f}\n"
                  f"Requested: {approved_gain:.2f}\n"
                  f"Approved: {approved_gain:.2f}\n"
                  f"Remaining: {self.remaining_budget:.2f}\n"
                  f"Source: {source}")

    def add_tlh(self, amount: float, source: str) -> None:
        """
        Dynamically adds to the TLH inventory (e.g., from an option loss).
        """
        amount = float(amount)
        if amount <= 0:
            return
            
        self.remaining_budget += amount
        self.usage_log.append({
            "source": f"{source}_addition",
            "amount": -amount  # Negative amount indicates adding to inventory in this log
        })
        
        trace_log(f"[TLH BUDGET ADDITION]\n"
                  f"Amount Added: {amount:.2f}\n"
                  f"New Remaining: {self.remaining_budget:.2f}\n"
                  f"Source: {source}")

    def get_remaining(self) -> float:
        return self.remaining_budget
        
    def get_summary(self) -> Dict[str, Any]:
        breakdown = {}
        for entry in self.usage_log:
            src = entry["source"]
            amt = entry["amount"]
            breakdown[src] = breakdown.get(src, 0.0) + amt
            
        return {
            "starting_inventory": self.starting_inventory,
            "total_used": self.total_used,
            "remaining": self.remaining_budget,
            "usage_breakdown": breakdown
        }
