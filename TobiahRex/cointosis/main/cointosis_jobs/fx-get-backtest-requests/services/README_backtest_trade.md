## 0.backtest_trader.py

Responsible for emulating a 3rd party API service. Acts as a mock class to return similarily shaped respones as that of a Trading Service dialect.

### 1. _get_closed_trades
1. We need to define a list of closed trades. Given the size of the current order, which can be either partial size of total, or the total size, then we need to generate a list of trades that were closed. We only return trades that were closed, not trades that were reduced, but remain open. Also, the final "units" value, should be the amount the trade was reduced, therefore, the value should negative if a LONG/BUY order was placed, and should be a positive value if a SHORT/SELL order was placed.
2. Once we've reduced the `size_count` value to zero, we know we no longer need to continue modifying trades, since the decrease size has been fully distributed across the existing trades.