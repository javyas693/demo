from ai_advisory.strategy.strategy_unwind import StrategyUnwindEngine
from datetime import datetime, timedelta

def debug_sim_data():
    ticker = "AAPL"
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=365*10)).strftime("%Y-%m-%d")
    
    print(f"Initializing engine for {ticker} from {start_date} to {end_date}")
    engine = StrategyUnwindEngine(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        initial_shares=1000
    )
    
    df = engine.price_data
    print("\nPrice Data Sample:")
    print(df.head())
    print("\nPrice Data Tail:")
    print(df.tail())
    print("\nColumns:", df.columns)
    print("Index Name:", df.index.name)
    print("Shape:", df.shape)

if __name__ == "__main__":
    debug_sim_data()
