context_template = {
    'name': '',
    'symbol': '',
    'tfs': [],
    'action': '',
    'last_action': '',
    'htf_action': '',
    'latest_prices': None,
    'keys': None,
    'position': None,
    'notifications': [],
    'backtest': None,
    'jobs': [],
}

keys_template = {
    'entry_key': '',
    'last_key': '',
    'exit_key': '',
    'chained': [],
}
position_template = {
    'symbol': '',
    'total_size': 0,
    'next_order_size': 0,
    'upgrade_tfs': [],
    'behaviors': [],
    'target_trade_id': '',
    'last_order_success': None,
    'average_price': 0,
    'last_price': 0,
    'total_margin': 0,
    'P/L $': 0,
    'P/L %': 0,
    'P/L pips': 0,
    'trade_ids': [],
    'trades': {},
    'account_balance': 0,
}
metric_template = {
    'symbol': '',
    'size': 0,
    'entry_time': '',
    'exit_time': '',
    'entry_price': 0,
    'exit_price': 0,
    'trade_low': float('inf'),
    'trade_high': float('-inf'),
    'max_profit': float('-inf'),
    'max_drawdown': float('inf'),
    'margin': 0,
    'P/L $': 0,
    'P/L pips': 0,
    'P/L %': 0,
    'account_balance': 0,
}
trade_template = {
    'id': '4576',
    'instrument': '',
    'price': 0,
    'openTime': '',
    'initialUnits': 0,
    'initialMarginRequired': 0,
    'state': '',
    'currentUnits': 0,
    'realizedPL': 0,
    'financing': 0,
    'dividendAdjustment': 0,
    'unrealizedPL': 0,
    'marginUsed': 0
}
tfs_3_map = {
    # Backtesting shows this combo is by far better than the rest.
    '1d-4hr-1hr': ['1day', '4hr', '1hr'],
    '4hr-1hr-30min': ['4hr', '1hr', '30min'],
    '1hr-30min-15min': ['1hr', '30min', '15min'],
    '30min-15min-5min': ['30min', '15min', '5min'],
    '15min-5min-1min': ['15min', '5min', '1min'],
}
open_trade_keys = {
    'BUY': [
        'B1_B1_B1',
        'B1_B1_B2',
        'B1_B1_B4',
        'B1_B2_B1',
        'B1_B2_B2',
        'B1_B2_B4',
        'B1_B4_B1',
        'B1_B4_B2',
        'B1_B4_B4',
        'S7_B1_B1',
        'S7_B1_B2',
        'S7_B1_B4',
        'S7_B2_B1',
        'S7_B2_B2',
        'S7_B2_B4',
        'S7_B4_B1',
        'S7_B4_B2',
        'S7_B4_B4',
        'S6_B1_B1',
        'S6_B1_B2',
        'S6_B2_B1',
        'S6_B2_B2',
    ],
    'SELL': [
        'S1_S1_S1',
        'S1_S1_S2',
        'S1_S1_S4',
        'S1_S2_S1',
        'S1_S2_S2',
        'S1_S2_S4',
        'S1_S4_S1',
        'S1_S4_S2',
        'S1_S4_S4',
        'B7_S1_S1',
        'B7_S1_S2',
        'B7_S1_S4',
        'B7_S2_S1',
        'B7_S2_S2',
        'B7_S2_S4',
        'B7_S4_S1',
        'B7_S4_S2',
        'B7_S4_S4',
        'B6_S1_S1',
        'B6_S1_S2',
        'B6_S2_S1',
        'B6_S2_S2',
    ]
}

mtf_trade_keys = {
    'BUY': [
        'B1',
        'B4',
        'S6',
        'S7'],
    'SELL': [
        'S1',
        'S4',
        'B6',
        'B7']
}
htf_close_keys = {
    'BUY': [
        'S5',
        # 'S1',
        # 'S4',
        # 'S8'
        ],
    'SELL': [
        'B5',
        # 'B1',
        # 'B4',
        # 'B8'
    ]
}

tf_num_map = {
    '1min': 1,
    '5min': 5,
    '15min': 15,
    '30min': 30,
    '1hr': 60,
    '4hr': 240,
    '1day': 1440,
}

backtest_open_trade_template = {
    "type": "MARKET",
    "time": '',
    "instrument": '',
    "commission": 0,
    "halfSpreadCost": 0,
    "pl": 0,
    "units": 0,
    "timeInForce": None,
    "positionFill": "DEFAULT",
    "reason": "",
    "accountBalance": 0,
    "tradeOpened": {
        "price": 0,
        "units": 0,
    }
}

backtest_close_trade_template = {
    "id": 0,
    "accountID": '',
    "userID": 21607112,
    "batchID": 0,
    "requestID": 0,
    "time": '',
    "type": "ORDER_FILL",
    "orderID": 0,
    "instrument": '',
    "units": 0,
    "requestedUnits": 0,
    "price": 0,
    "pl": 0,
    "quotePL": 0,
    "financing": 0,
    "reason": "MARKET_ORDER_TRADE_CLOSE",
    "tradesClosed": [
        {
            "tradeID": '',
            "units": 0,
            "realizedPL": 0,
            "financing": 0,
            "baseFinancing": 0,
            "price": 0,
            "guaranteedExecutionFee": 0,
            "quoteGuaranteedExecutionFee": 0,
            "halfSpreadCost": 0
        }
    ],
}