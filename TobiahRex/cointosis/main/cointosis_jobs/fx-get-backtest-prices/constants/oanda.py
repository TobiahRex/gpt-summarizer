order_template = {
    'type': 'MARKET',
    'time': '',
    'instrument': '',
    'commission': '',
    'halfSpreadCost': '',
    'pl': 0,
    'units': 0,
    'fullPrice': 0,
    'timeInForce': 'FOK',
    'positionFill': 'DEFAULT',
    'reason': '',
}

aggs_map = {
    "5sec": "S5",  # 5 second candlesticks, minute alignment
    "10sec": "S10",  # 10 second candlesticks, minute alignment
    "15sec": "S15",  # 15 second candlesticks, minute alignment
    "30sec": "S30",  # 30 second candlesticks, minute alignment
    "1min": "M1",  # 1 minute candlesticks, minute alignment
    "2min": "M2",  # 2 minute candlesticks, hour alignment
    "4min": "M4",  # 4 minute candlesticks, hour alignment
    "5min": "M5",  # 5 minute candlesticks, hour alignment
    "10min": "M10",  # 10 minute candlesticks, hour alignment
    "15min": "M15",  # 15 minute candlesticks, hour alignment
    "30min": "M30",  # 30 minute candlesticks, hour alignment
    "1hr": "H1",  # 1 hour candlesticks, hour alignment
    "2hr": "H2",  # 2 hour candlesticks, day alignment
    "3hr": "H3",  # 3 hour candlesticks, day alignment
    "4hr": "H4",  # 4 hour candlesticks, day alignment
    "6hr": "H6",  # 6 hour candlesticks, day alignment
    "8hr": "H8",  # 8 hour candlesticks, day alignment
    "12hr": "H12",  # 12 hour candlesticks, day alignment
    "1day": "D",  # 1 day candlesticks, day alignment
    "1wk": "W",  # 1 week candlesticks, aligned to start of week
    "1mon": "M",  # 1 month candlesticks, aligned to first day of the month
}

pairs = set([
    "EUR_HUF",
    "EUR_DKK",
    "USD_MXN",
    "GBP_USD",
    "CAD_CHF",
    "EUR_GBP",
    "GBP_CHF",
    "USD_THB",
    "USD_ZAR",
    "EUR_NOK",
    "CAD_JPY",
    "EUR_HKD",
    "AUD_HKD",
    "USD_SEK",
    "GBP_SGD",
    "GBP_HKD",
    "EUR_NZD",
    "SGD_CHF",
    "AUD_SGD",
    "EUR_JPY",
    "USD_CHF",
    "USD_TRY",
    "GBP_JPY",
    "EUR_CZK",
    "CHF_ZAR",
    "EUR_TRY",
    "USD_JPY",
    "GBP_ZAR",
    "SGD_JPY",
    "USD_CZK",
    "USD_NOK",
    "ZAR_JPY",
    "TRY_JPY",
    "USD_DKK",
    "EUR_PLN",
    "AUD_CAD",
    "USD_HKD",
    "CAD_SGD",
    "GBP_NZD",
    "NZD_USD",
    "AUD_NZD",
    "CHF_HKD",
    "NZD_HKD",
    "USD_CNH",
    "NZD_SGD",
    "USD_SGD",
    "EUR_SEK",
    "NZD_CHF",
    "HKD_JPY",
    "AUD_CHF",
    "CHF_JPY",
    "AUD_JPY",
    "EUR_ZAR",
    "EUR_AUD",
    "NZD_JPY",
    "USD_CAD",
    "EUR_CHF",
    "EUR_CAD",
    "USD_HUF",
    "NZD_CAD",
    "EUR_SGD",
    "AUD_USD",
    "EUR_USD",
    "GBP_AUD",
    "USD_PLN",
    "CAD_HKD",
    "GBP_CAD",
    "GBP_PLN"
])
