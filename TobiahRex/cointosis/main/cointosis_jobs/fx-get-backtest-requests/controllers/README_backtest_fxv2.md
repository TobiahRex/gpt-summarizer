# Backtest Pipeline


## What & Why
Backtesting is conducted by using a 3rd party library to conduct tests to abstract away from the local development pipeline, managing trade dynamics such as walk-forward testing, equity managements, etc.

The Backtest Pipeline is designed to integrate with the Paper & Live trading pipelines seamlessly.  The only footprint within the live trading code is miscellaneous enviroment checks to detect if backtesting is activated or not. The point is, the backtesting control flow should operate as closely to live trading control flows as possible to get the most assurance that backtesting results should reflect future results.

## How
There's 2 main parts.

1. *Backtest Data Generation*
2. *Backtest Execution*

### Backtest Data Generation

The `generate_backtest_prices` script is used to generate various in-sample & out-sample data sets to be used for backtesting. Qualitative Backtesting is dependent upon separating data into sample groups such that a model is fitted to an in-sample group, and tested on a larger out of sample group to preserve non-bias results.  The backtesting data is thus organized to accomodate this paradigm.  The script will read from an environmentally defined (SSM param store) list of trend types. These trend types are classified beforehand as one of; *uptrend*, *downtrend* or *ranging*.
```json
"uptrends": [
        {
            "symbol": "GBP_USD",
            "start_date": "2013-07-04",
            "end_date": "2014-07-04",
            "sample": "in_sample"
        }
    ],
    "downtrends": [
        {
            "symbol": "GBP_USD",
            "start_date": "2015-11-01",
            "end_date": "2016-11-01",
            "sample": "out_sample"
        }
    ],
```
The script will iterate across all defined periods within each trend type and conduct a data gathering operation using a specified broker (default; Oanda FX Api).  The data will be OHLCV data that will then be used to generate indicator values across the entire year.
```python
    price_df = self.broker_service.prices.get('get_backtest_prices')(
                        symbol,
                        tf=tf,
                        root_size=70,
                        retries=1,
                        backtest_data={
                            'from': t_data.get('start_date'),
                            'to': t_data.get('end_date'),
                        })

    price_df = self.indicator_service.get_backtest_indicators(symbol, price_df, tf)
```
The data will be OHLCV data that will then be used to generate indicator values across the entire year. The nature of the trading model is such that indicator generation can be timely and expensive, thus pre-calculated indicators are vital to expediant backtest runtime.  We do not need to require the backtest control flow to generate live-like data, when all the data is available before a backtest is ran.

However, given that we want the backtest control flow to operate as closely as possible to live trading conditions the question naturally arises; how do we use pre-calculated data and run a live-like backtest?  The answer is we use a special class to emulate the Data Fetching operations of a live/paper situation; `BacktestTrader`. This class contains all the various methods assumed to exist on a Live/Paper trader with stubs filled in where needed. For the methods actually required to return valid price data, we simply read from the pre-calculated data files and return a slice of that data to the caller to emulate a live fetch. The slice's time window is determined by the input time given to `BacktestTrader` from the live model control flow via environment variable, passed in by the `Backtest.next` method running the test.