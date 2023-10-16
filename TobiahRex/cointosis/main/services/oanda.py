import json
from datetime import datetime as dt, timedelta
import pytz
from dateutil import parser
import oandapyV20 as oanda
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.positions as positions
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.forexlabs as labs
from oandapyV20.definitions.instruments import CandlestickGranularity
from oandapyV20.contrib.factories import InstrumentsCandlesFactory
import pandas as pd

import constants
import constants.oanda as oanda_constants
from services.log_service import LogService


pacific_tz = pytz.timezone('US/Pacific')


class OandaService:
    NON_FLOAT_KEYS = ['id', 'userID', 'batchID', 'requestID', 'time', 'type', 'instrument', 'reason', 'tradesClosed',
                      'tradeReduced', 'fullPrice', 'homeConversionFactors', 'accountID', 'timestamp']

    def __init__(self, oanda_client, log_service, account_id):
        self.oanda = oanda_client
        self.log = log_service
        self.account_id = account_id

    @staticmethod
    def build(env):
        oanda_env = env.get('oanda')
        env_type = 'practice' if 'paper' in env.get('run_type') else 'live'
        env_account_id = oanda_env.get('paper_account_id' if 'paper' in env_type else 'live_account_id')
        token = oanda_env.get('paper_token' if 'paper' in env.get('run_type') else 'live_token')
        log_service = LogService.build(name_prefix='OandaService')
        oanda_client = None
        if env.get('lambda_env') in ['DEV', 'TEST'] or env_type == 'practice':
            oanda_client = oanda.API(access_token=token, environment=env_type)
        else:
            oanda_client = oanda.API(access_token=token, environment=env_type)
        return OandaService(oanda_client, log_service, env_account_id)

    def _get_instruments(self):
        if not self.account_id:
            return Exception('Account Id not found.')
        req = accounts.AccountInstruments(accountID=self.account_id)
        res = self.oanda.request(req)
        pairs = [p.get('name') for p in res.get('instruments', [])]
        f = open('oanda-pairs.json', 'w')
        f.write(json.dumps(pairs, indent=4))
        f.close()

    def _get_spread(self, symbol, lookback=50):
        req_params = {
            'instrument': symbol,
            'period': lookback
        }
        req = labs.Spreads(params=req_params)
        res = self.oanda.request(req)
        return res

    def _get_latest_prices(self, symbol, aggregation, size=200):
        timeframe = oanda_constants.aggs_map.get(aggregation)
        req_params = {
            'granularity': timeframe,
            'count': size,
        }
        if timeframe not in CandlestickGranularity().definitions:
            raise Exception('Aggregation is not in whitelist')
        req = instruments.InstrumentsCandles(
            instrument=symbol, params=req_params)
        res = None
        try:
            res = self.oanda.request(req)
        except oanda.V20Error as e:
            self.log.handle(1, str(e), '@oanda._get_latest_prices')
        candles = []
        for candle in res.get('candles', []):
            candles.append(self._parse_candle(candle))
        candles_df = pd.DataFrame.from_records(candles)
        return candles_df

    def _get_account_info(self, value=None):
        req = accounts.AccountSummary(self.account_id)
        res = self.oanda.request(req)
        if value is None:
            return res.get('account')
        return res.get('account', {}).get(value)

    def _get_open_positions(self, symbol=None):
        """Summary of all open trades given a specific instrument symbol, or all symbols if None is given.
        Positions simply shows all the open trades (by id), whether the symbol has long or shorts
        attached to them, and the overall P/L, Unrealized P/L, and total size open.

        Args:
            symbol ([str], optional): Instrument symbol to filter positions results by.

        Returns:
            (tuple): Open positions, and the latest Transaction Id.
        """
        req = positions.OpenPositions(self.account_id)
        res = self.oanda.request(req)
        open_positions = res.get('positions', [])
        last_tx_id = res.get('lastTransactionID', None)
        if symbol is not None:
            open_positions = [
                p for p in open_positions if p.get('instrument') == symbol]
            if open_positions:
                return open_positions[0], last_tx_id
        return open_positions, last_tx_id

    def _get_open_trades(self, symbol=None):
        req = trades.OpenTrades(self.account_id)
        res = self.oanda.request(req)
        open_trades = res.get('trades', [])
        last_tx_id = res.get('lastTransactionID', None)
        if symbol is not None:
            open_trades = [t for t in open_trades if t.get('instrument') == symbol]
        return open_trades, last_tx_id

    def _get_closed_trades(self, symbol=None):
        if not symbol or symbol not in oanda_constants.pairs:
            raise Exception('Symbol not in available symbol list')
        req_params = {'instrument': symbol}
        req = trades.TradesList(self.account_id, params=req_params)
        res = self.oanda.request(req)
        symbol_trades = res.get('trades', [])
        last_tx_id = res.get('lastTransactionID', None)
        closed_trades = [
            t for t in symbol_trades if t.get('state') == 'CLOSED']
        return closed_trades, last_tx_id

    def _get_trade_by_id(self, trade_id):
        if not trade_id:
            raise Exception('Trade ID required')
        req = trades.TradeDetails(self.account_id, tradeID=trade_id)
        res = self.oanda.request(req)
        trade = res.get('trade')
        for k, v in trade.items():
            if k not in ['instrument', 'openTime', 'state', 'id']:
                trade[k] = float(v)
        return trade

    def _close_trade(self, context, size):
        symbol = context.get('symbol')
        trade_id = context.get('position').get('target_trade_id')
        if not trade_id:
            self.log.handle(-1, 'Missing required "trade_id".', '@close_trade')
        req_params = {'units': size}
        try:
            req = trades.TradeClose(self.account_id, trade_id, data=req_params)
            res = self.oanda.request(req)
        except oanda.V20Error as e:
            e_msg = json.loads(e.msg).get('errorMessage')
            self.log.handle(-1, f'Failed to Close Trade: {e_msg}', '@close_trade')
            return False, json.loads(e.msg), None
        order_filled = res.get('orderFillTransaction', {})
        self.log.handle(0, f'Symbol: {symbol} | Closed Trade: {order_filled.get("id")} | Size: {size}', '@close_trade')
        return True, order_filled, res

    def _close_position(self, context, size):
        symbol = context.get('symbol')
        req_params = {
            'longUnits': 'NONE',
            'shortUnits': 'NONE'
        }
        order_type = 'long' if size > 0 else 'short'
        if order_type == 'long':
            req_params['longUnits'] = str(size)
        elif order_type == 'short':
            req_params['shortUnits'] = str(size)
        try:
            req = positions.PositionClose(self.account_id, instrument=symbol, data=req_params)
            res = self.oanda.request(req)
        except oanda.V20Error as e:
            e_msg = json.loads(e.msg).get('errorMessage')
            self.log.handle(-1, f'Failed to Close Position: {e_msg}', '@_close_position')
            return False, json.loads(e.msg), None
        orders_filled = res.get(f'{order_type}OrderFillTransaction', {})
        for k, v in orders_filled.items():
            if k not in self.NON_FLOAT_KEYS:
                orders_filled[k] = float(v)
        self.log.handle(
            0, f'Symbol: {symbol} | Closed Trade: {orders_filled.get("id")} | Size: {size}', '@close_trade')
        return True, orders_filled, res

    def _open_trade(self, symbol, size, trade_type, order_type='MARKET'):
        """Opens a trade using Oanda's order API.

        Args:
            symbol (str): The instrument to trade.
            size (int): # of Lots to trade
            trade_type (str): 'BUY' or 'SELL'
            order_type (str, optional): Type of order. Either 'MARKET' or 'LIMIT'. Defaults to 'MARKET'.

        Raises:
            Exception: If the given symbol is not in the Oanda universe.
            Exception: If the trade_type is not specified.

        Returns:
            tuple:
                - bool: If the open trade order was successful
                - dict: The order details.
                - str: The last transaction id. Can be used to close an order.
        """
        if symbol not in oanda_constants.pairs:
            raise Exception('Symbol not in available symbol list')
        if not trade_type:
            raise Exception(
                'Cannot open a trade without specified trade type "BUY" or "SELL", etc...')
        req_params = {
            'order': {
                'type': 'MARKET',
                'instrument': symbol,
                'units': size,
                'timeInForce': 'FOK' if order_type == 'MARKET' else 'GTC',
                'positionFill': 'DEFAULT',
            }
        }
        req = orders.OrderCreate(self.account_id, data=req_params)
        res = self.oanda.request(req)
        order_canceled = res.get('orderCancelTransaction', {})
        last_tx_id = res.get('lastTransactionID', '')
        if order_canceled.get('type', '') == 'ORDER_CANCEL':
            return False, order_canceled, last_tx_id
        order_filled = res.get('orderFillTransaction')
        for k, v in order_filled.items():
            if k not in self.NON_FLOAT_KEYS and (type(v) is not dict):
                order_filled[k] = float(v)
        for k, v in order_filled.get('tradeOpened').items():
            if k not in self.NON_FLOAT_KEYS:
                order_filled['tradeOpened'][k] = float(v)
        for k, v in order_filled.get('fullPrice').items():
            if k not in self.NON_FLOAT_KEYS and (type(v) is not list):
                order_filled['fullPrice'][k] = float(v)
        return True, order_filled, last_tx_id

    def _get_prices_by_aggs(self, symbol, aggs):
        latest_prices = {}
        for agg in aggs:
            if symbol not in oanda_constants.pairs:
                raise Exception(f'Symbol: {symbol} not recognized')
            oanda_agg = oanda_constants.aggs_map.get(agg)
            price_df = self._get_latest_prices(symbol, oanda_agg)
            latest_prices[agg] = price_df
        return latest_prices

    def _get_backtest_prices(self, symbol, tf, root_size, retries, backtest_data):
        if all([
            'from' in backtest_data,
            'to' in backtest_data
        ]):
            seed_date = pytz.utc.localize(
                parser.parse(backtest_data.get('to')))
            req_params = {
                'granularity': oanda_constants.aggs_map.get(tf),
                'from': parser.parse(backtest_data.get('from')).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'to': parser.parse(backtest_data.get('to')).strftime('%Y-%m-%dT%H:%M:%SZ'),
            }
        else:
            seed_date = parser.parse(backtest_data.get('last_date'))
            tf_mins = constants.tf_num_map.get(tf)
            weekend_mins = (2 * 24 * 60)  # days * hrs * mins
            lookback_mins = tf_mins * root_size * retries
            if all([
                retries > 1,
                seed_date.weekday() in [0, 1],
                tf_mins < 240
            ]):
                lookback_mins += weekend_mins
            start_date = seed_date - timedelta(minutes=lookback_mins)
            end_date = seed_date + timedelta(minutes=tf_mins)
            req_params = {
                'granularity': oanda_constants.aggs_map.get(tf),
                'from': start_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'to': end_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
            }
        if req_params.get('granularity') not in CandlestickGranularity().definitions:
            raise Exception('Aggregation is not in whitelist')
        prices_df = self._get_candles_by_factory(symbol, req_params, seed_date)
        if 'volume' in prices_df:
            prices_df['volume'] = [v * 100000 for v in list(prices_df.volume)]
        return prices_df

    def _get_candles_by_factory(self, symbol, params, seed_date):
        candles_raw = []
        try:
            if len(symbol) == 6:
                symbol = f'{symbol[0:3]}_{symbol[3:]}'
            for req in InstrumentsCandlesFactory(instrument=symbol, params=params):
                data = self.oanda.request(req)
                candles_raw += data.get('candles')
                if len(candles_raw) % 10 == 0:
                    self.log.handle(0, f'Candles #: {len(candles_raw)}', '@get_candles_by_factory')
                if params.get('count') and len(candles_raw) >= params.get('count'):
                    break
        except oanda.V20Error as e:
            self.log.handle(1, str(e), '@_get_backtest_prices')
        candles = []
        self.log.handle(0, f'Cleaning Candles #: {len(candles_raw)}', '@get_candles_by_factory')
        last_p = 0
        for i, candle in enumerate(candles_raw):
            completion_percent = round(((i + 1) / len(candles_raw)) * 100, 1)
            if completion_percent % 1 in [0, 0.0] and completion_percent != last_p:
                last_p = completion_percent
                print('Cleaning Percent: ', completion_percent)
            if not self.keep_candle(candle, seed_date):
                continue
            candle['time'] = self.clean_time(candle.get('time'))
            candles.append(self._parse_candle(candle))
        prices_df = pd.DataFrame.from_records(candles)
        return prices_df

    def get_price_api(self):
        price_api = {
            'get_prices_by_aggs': self._get_prices_by_aggs,
            'get_latest_prices': self._get_latest_prices,
            'get_backtest_prices': self._get_backtest_prices,
        }
        return price_api

    def get_trader_api(self):
        trader_api = {
            'close_trade': self._close_trade,
            'close_position': self._close_position,
            'open_trade': self._open_trade,
            'get_open_positions': self._get_open_positions,
            'get_open_trades': self._get_open_trades,
            'get_closed_trades': self._get_closed_trades,
            'get_trade_by_id': self._get_trade_by_id,
            'get_spread': self._get_spread,
        }
        return trader_api

    def get_account_api(self):
        account_api = {
            'get_account_info': self._get_account_info,
            'get_instruments': self._get_instruments,
            'get_account_id': lambda _: None,
        }
        return account_api

    @staticmethod
    def _parse_candle(candle):
        return {
            'time': candle.get('time'),
            'open': float(candle.get('mid').get('o')),
            'high': float(candle.get('mid').get('h')),
            'low': float(candle.get('mid').get('l')),
            'close': float(candle.get('mid').get('c')),
            'volume': float(candle.get('volume'))
        }

    @staticmethod
    def clean_time(utc_time):
        pst_time = parser \
            .parse(utc_time) \
            .strftime('%Y-%m-%dT%H:%M:%SZ')
            # .replace(tzinfo=timezone.utc) \
            # .astimezone(tz=pytz.timezone('US/Pacific')) \
        return pst_time

    @staticmethod
    def keep_candle(candle, seed_date):
        candle_date = parser.parse(candle.get('time'))
        if candle_date > seed_date:
            return False
        return True

if __name__ == '__main__':
    from services.aws.ssm import SSMService
    oanda = OandaService.build(SSMService.build().get_param('/cointosis/forex_trader_v2'))
    result = oanda.get_trader_api().get('close_position')('EUR_JPY', 20000)
    print(result)
