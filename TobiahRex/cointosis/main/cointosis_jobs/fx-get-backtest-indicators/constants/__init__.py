test_sqs_job = {
    'Messages': [
        {
            "Body": '{"start_date": "2005-01-01", "end_date": "2014-12-31", "version": "forex_trader_v2", "option_code": "TF5_MA1_FR1_TM1_PP10_TG1", "symbol": "EUR_JPY", "sample": "in_sample"}'
        }
    ]
}

version_indicator_map = {
    'forex_trader_v2': {
        'macd': [21, 55, 13],
        'stochastics': [5, 3],
        'mas': [
            ('ema', 8),
            ('ema', 13),
            ('ema', 21),
            ('ema', 34),
            ('sma', 55)
        ],
        'force': None,
        'states': None
    }
}
