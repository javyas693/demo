"""
Risk Score Calculator — FunctionTool

Pure computation: takes three per-question scores, produces a composite
risk score and human-readable label. No LLM reasoning needed.

"""


def calculate_risk_score(scores: list[float]) -> dict:
    """
    Calculates the final risk score from a list of user question scores.
    The formula is 100 - (100 * sum_of_scores).
    
    Args:
        scores: A list of answering scores (e.g. [0.167, 0.125, 0.083]).
        
    Returns:
       dict containing raw_score_sum, component_scores, final_risk_score, and score_range
    """
    try:
        raw_scores_sum = sum(scores)
        final_score = round(100 - (100 * raw_scores_sum), 2)

        result = {
            "status": "success",
            #"raw_score_sum": raw_scores_sum,
            #"component_scores": scores,
            "composite_score": final_score,
            #"score_range": {"min": 0, "max": 100}
        }
        #print(f"calculate_risk_score returning: {result}")
        return result
    except Exception as e:
        return {"error": f"Failed to calculate risk score: {str(e)}"}
