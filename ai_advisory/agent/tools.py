from datetime import datetime

def analyze_concentrated_position_tool(
    ticker: str, 
    acquisition_date: str, 
    shares: float, 
    total_risk_score: float
) -> dict:
    """
    Analyzes a user's concentrated position based on their stock, when they bought it, 
    how many shares they have, and their calculated risk score (min 0.0, max 0.501).
    
    Args:
        ticker: The stock ticker symbol (e.g., AAPL).
        acquisition_date: The date the position was acquired, formatted as YYYY-MM-DD.
        shares: The total number of shares held.
        total_risk_score: The calculated total risk score from the questionnaire.
        
    Returns:
        A dictionary containing the analysis summary and data series formatting for frontend charting.
    """
    try:
        parsed_date = datetime.strptime(acquisition_date, "%Y-%m-%d").date()
        

        # We return it as a dict so the Gemini Agent can easily consume the result
        return {"analysis": "analysis"}
        
    except Exception as e:
        return {"error": f"Failed to analyze position: {str(e)}"}

def calculate_risk_score_tool(scores: list[float]) -> dict:
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
            "raw_score_sum": raw_scores_sum,
            "component_scores": scores,
            "final_risk_score": final_score,
            "score_range": {"min": 0, "max": 100}
        }
        logging.debug(f"calculate_risk_score returning: {result}")
        return result
    except Exception as e:
        return {"error": f"Failed to calculate risk score: {str(e)}"}

# List of tools to register with the Google GenAI agent
AGENT_TOOLS = [analyze_concentrated_position_tool, calculate_risk_score_tool]
