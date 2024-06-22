from datetime import datetime, timedelta
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # For sentiment analysis
from lumibot.backtesting import YahooDataBacktesting
from lumibot.brokers import Alpaca
from lumibot.traders import Trader
from alpaca_trade_api import REST 
from lumibot.strategies.strategy import Strategy
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL

ALPACA_CREDS = {
    "API_KEY": ALPACA_API_KEY, 
    "API_SECRET": ALPACA_SECRET_KEY, 
    "PAPER": True
}

class NewsBasedTrading(Strategy):
    def initialize(self, symbol: str = "SPY", cash_at_risk: float = 0.5):
        self.symbol = symbol
        self.sleeptime = "24H"
        self.last_trade = None
        self.cash_at_risk = cash_at_risk
        self.api = REST(base_url=ALPACA_BASE_URL, key_id=ALPACA_API_KEY, secret_key=ALPACA_SECRET_KEY)
        self.analyzer = SentimentIntensityAnalyzer()
    
    def position_sizing(self):
        cash = self.get_cash()
        last_price = self.get_last_price(self.symbol)
        quantity = round(cash * self.cash_at_risk / last_price, 0)
        return cash, last_price, quantity

    def fetch_news(self):
        end_date = self.get_datetime()
        start_date = (end_date - timedelta(days=2)).strftime('%Y-%m-%d')
        end_date = end_date.strftime('%Y-%m-%d')
        news = self.api.get_news(symbol=self.symbol, 
                                 start=start_date, 
                                 end=end_date)
        news = [ev.__dict__["_raw"]["headline"] for ev in news]
        return news

    def analyze_sentiment(self, articles):
        sentiments = []
        for article in articles:
            analysis = self.analyzer.polarity_scores(article)
            sentiments.append(analysis['compound'])
        return sum(sentiments) / len(sentiments) if sentiments else 0

    def on_trading_iteration(self):
        articles = self.fetch_news()
        sentiment_score = self.analyze_sentiment(articles)
        
        cash, last_price, quantity = self.position_sizing()
        
        if sentiment_score > 0.2 and cash > last_price:
            if self.last_trade != "buy":
                if self.last_trade == "sell":
                    self.sell_all()
                order = self.create_order(
                    self.symbol, quantity, "buy", type="bracket", 
                    take_profit_price=last_price * 1.20, stop_loss_price=last_price * 0.95
                )
                self.submit_order(order)
                self.last_trade = "buy"
        elif sentiment_score < -0.2:
            if self.last_trade == "buy":
                self.sell_all()
            if quantity > 0:
                order = self.create_order(self.symbol, quantity, "sell")
                self.submit_order(order)
                self.last_trade = "sell"

# Change dates based on own preferences
start_date = datetime(2024, 6, 1)
end_date = datetime(2024, 6, 20)
broker = Alpaca(ALPACA_CREDS)
strategy = NewsBasedTrading(name='mlstrat', broker=broker, parameters={"symbol": "SPY", "cash_at_risk": 0.5})

# Backtest
strategy.backtest(
    YahooDataBacktesting,
    start_date,
    end_date,
    parameters={"symbol": "SPY", "cash_at_risk": 0.5}
)

# Real-time
# trader = Trader()
# trader.add_strategy(strategy)
# trader.run_all()
