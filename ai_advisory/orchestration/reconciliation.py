import math

TOLERANCE = 1e-4

def approx_equal(val1: float, val2: float, tol: float = TOLERANCE) -> bool:
    return abs(val1 - val2) <= tol

def reconcile_step(prev_step: dict, curr_step: dict) -> dict:
    """
    Computes step-level reconciliation for the portfolio simulation.
    Ensures that values flow correctly from step to step, and that
    all sub-components sum to the expected total.
    """
    start_value = prev_step["total_portfolio_value"]
    end_value = curr_step["total_portfolio_value"]

    # Component changes
    cp_change = curr_step["concentrated_value"] - prev_step["concentrated_value"]
    income_change = curr_step["income_value"] - prev_step["income_value"]
    model_change = curr_step["model_value"] - prev_step["model_value"]
    cash_change = curr_step["cash"] - prev_step["cash"]

    # FLOW CHECK: start + deltas = end
    reconstructed_end = (
        start_value
        + cp_change
        + income_change
        + model_change
        + cash_change
    )
    flow_delta = reconstructed_end - end_value
    is_flow_valid = approx_equal(flow_delta, 0.0)

    # SUM CHECK: components = end
    concentrated_value = curr_step["concentrated_value"]
    income_value = curr_step["income_value"]
    model_value = curr_step["model_value"]
    cash = curr_step["cash"]

    component_sum = concentrated_value + income_value + model_value + cash
    sum_delta = component_sum - end_value
    is_sum_valid = approx_equal(sum_delta, 0.0)

    details = {
        "start_value": start_value,
        "end_value": end_value,
        "cp_change": cp_change,
        "income_change": income_change,
        "model_change": model_change,
        "cash_change": cash_change,
        "reconstructed_end": reconstructed_end,
        "component_sum": component_sum,
        "concentrated_value": concentrated_value,
        "income_value": income_value,
        "model_value": model_value,
        "cash": cash
    }

    return {
        "flow_delta": flow_delta,
        "sum_delta": sum_delta,
        "is_flow_valid": is_flow_valid,
        "is_sum_valid": is_sum_valid,
        "details": details
    }
