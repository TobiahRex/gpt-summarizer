## 0.analyze_size.py

Responsible for determining the size dynamics based on the next order type; `increase`, `decrease`, `open`, `close`. If `close` next size will always be `0`. Otherwise, several conditions must be evaluated.

### 1.open
A single trade will always start out at 50% total symbol size. The assumption here is that we want to have a significant exposure to the earliest part of a trend, but not so much that we lose a large position if we're wrong.


### 2.`_analyze_decrease_size`
When a `decrease` action is initiated we first check to see if the decrease is based on `profit_protect` dynamics. If so, then we reduce the total size to 25% of the max size available.  If not, then we have 3/4, 1/2, or 1/4 total size in play; so we reduce the trade to 1/2 size if 3/4 is current, or 1/4 if 1/2 is current, or change nothing if 1/4 is current.
1. Reduce Risk exposure to 50% of max.
2. If size is already smallest size, then do nothing.
3. Decrease risk by 1 factor
4. Most dangerous condition; We should reduce the entire position size to the smallest risk exposure.
5. For a single trade, same as #2
6. For a single trade's profit protection; we should decrease the trade size to maximum smallest increment.

### 3.`_analyze_increase_size`
1. When an `increase` action is initiated we first check to see if we should allocate 100% size whenever a trade retraced but has now made a new low from it's previous low; `increase_on_trend_continuation`.
2. Otherwise, we evaluate an `increase_on_force_surge` event. This event represents the largest risk possibility; the market force has a significant spike, and we are wanting to capitalize as much as possible; however, we want to ensure we have protection activated based on our unrealized profits so we first check to see if `profit_protect_activated` is activated. If so, then we feel comfortable increasing to full-size, since we know we have profit already covering our potential future drawdown. If `profit_protect` is not active, then first ensure that the last event we responded to was not already a `force_surge` event. If so, then we do nothing. If not, then we add the smallest size to the trade.  This is simply meant to defend against consecutive `force_surge` scenarios manipulating us into a full-size position without `profit_protect_activated` being activated.
3. If the current size is already the smallest, then we simply add another small size.

## TODO
1. Build a dynamic sizing function as a function of account balance. The output will be the maximum lot size allowed, based on 1. Risk % and 2. Account Balance.
