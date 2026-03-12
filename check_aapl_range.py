import yfinance as yf
from datetime import datetime, timedelta

def get_aapl_range():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*10)
    
    ticker = "AAPL"
    # use auto_adjust=True to make sure we get a clean dataframe if possible
    data = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
    
    if not data.empty:
        # Extract the scalar values correctly
        low = float(data['Low'].min())
        high = float(data['High'].max())
        current = float(data['Close'].iloc[-1])
        print(f"AAPL Price Range (Last 10 Years):")
        print(f"Low: ${low:.2f}")
        print(f"High: ${high:.2f}")
        print(f"Current: ${current:.2f}")
    else:
        print("No data found.")

if __name__ == "__main__":
    get_aapl_range()
