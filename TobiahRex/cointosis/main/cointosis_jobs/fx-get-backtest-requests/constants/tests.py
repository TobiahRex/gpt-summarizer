test_context = {
    "name": "EUR_JPY_1day_4hr_1hr",
    "symbol": "EUR_JPY",
    "tfs": [
            "1day",
            "4hr",
            "1hr"
    ],
    "action": "",
    "htf_action": "",
    "keys": {
        "entry_key": "B2_B1_B5",
        "last_key": "B1_B1_B2",
        "exit_key": "",
        "chained": [
            "B2_B1_B5",
            "B2_B1_B5",
            "B2_B1_B6",
            "B1_B2_B1",
            "B1_B2_B2",
            "B1_B1_B2",
            "B1_B1_B1",
            "B1_B1_B2",
            "B1_B1_B2",
            "B1_B1_B1",
            "B1_B1_B2",
            "B1_B1_B2",
            "B1_B1_B2"
        ]
    },
    "position": {
        "total_size": 100000.0,
        "next_size": 0,
        "trade_type": "",
        "upgrade_tfs": [
            "1day",
            "4hr",
            "1hr"
        ],
        "entry_time": "2022-04-19 00:51:23",
        "exit_time": "2022-04-19 01:00:00",
        "entry_price": 138.261,
        "exit_price": 138.64,
        "trade_low": 138.261,
        "trade_high": 138.767,
        "max_profit": 50.6,
        "max_drawdown": 0.0,
        "behaviors": [
            "open_on_keys",
            "open_on_force",
            "increase_on_force_surge",
            "upgrade_on_htf_force",
            "upgrade_on_htf_force",
            "upgrade_on_htf_force"
        ],
        "trades": [
            {
                "id": "4578",
                "instrument": "EUR_JPY",
                "price": "139.171",
                "openTime": "2022-04-20T06:16:59.756426665Z",
                "initialUnits": "75000",
                "initialMarginRequired": "2700.8464",
                "state": "OPEN",
                "currentUnits": "75000",
                "realizedPL": "0.0000",
                "financing": "0.0000",
                "dividendAdjustment": "0.0000",
                "unrealizedPL": "-9.3715",
                "marginUsed": "2700.8464"
            },
            {
                "id": "4576",
                "instrument": "EUR_JPY",
                "price": "139.168",
                "openTime": "2022-04-20T06:16:51.760440072Z",
                "initialUnits": "50000",
                "initialMarginRequired": "1800.5643",
                "state": "OPEN",
                "currentUnits": "50000",
                "realizedPL": "0.0000",
                "financing": "0.0000",
                "dividendAdjustment": "0.0000",
                "unrealizedPL": "-5.0762",
                "marginUsed": "1800.5643"
            }
        ],
        "P/L $": 0.0,
        "P/L pips": 37.9,
        "P/L %": 0.27,
        "last_order_success": True
    },
    "notifications": [
        "`OPEN | EUR_JPY | key = B2_B1_B5 | units = 25000.0 | 2022-04-19 00:51:23 PST | open_on_force`",
        "`INCREASE | EUR_JPY | key = B2_B1_B5 | units = 75000.0 | 2022-04-19 00:56:25 PST | increase_on_force_surge`"
    ],
    "backtest": None
}
