import copy
import pandas as pd
from dateutil import parser
import json
import os

from services.aws.s3 import S3Service
from services.log import LogService
from services.backtest_indicator import BacktestIndicator
import constants


class BacktestTrader:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.log = kwargs.get('log_service')
        self.prices = self.get_price_api()
        self.trader = self.get_trader_api()
        self.account = self.get_account_api()
        self.s3_service = kwargs.get('s3_service')
        self.backtest_indicators = kwargs.get('backtest_indicator_service')
        self.all_htf_prices_df = None
        self.all_mtf_prices_df = None
        self.all_ltf_prices_df = None
        self.last_tfs = [None, None, None]
        self.context = None
        self.price_filenames = []

    @staticmethod
    def build(env, backtest_env):
        return BacktestTrader(
            env=env,
            backtest_env=backtest_env,
            log_service=LogService.build(name_prefix='BacktestTrader', should_log=False),
            backtest_indicator_service=BacktestIndicator.build(env, backtest_env),
            s3_service=S3Service.build(env, backtest_env, bucket=env.get('s3').get('bucket')))

    def _get_latest_prices(self, _, tf):
        price_df = self._get_price_df(tf)
        return price_df

    def _get_prices_with_indis(self, price_df, tf, size):
        return self.backtest_indicators.get_prices_with_indis(price_df, tf, size)

    def _get_price_df(self, tf):
        self.log.handle(0, f'Getting price_df for TF = {tf}', '@_get_price_df')
        backtest_bucket = 'cointosis-backtest'
        _tfs = self.env.get('tfs')
        job_data = self.backtest_env.get('job_data')
        filename = self.s3_service.get_filename('backtest-prices', job_data, agg_name=tf)
        local_filename = filename.split('/')[-1]
        for i, [price_df, name] in enumerate([
            [self.all_htf_prices_df, _tfs[0]],
            [self.all_mtf_prices_df, _tfs[1]],
            [self.all_ltf_prices_df, _tfs[2]],
        ]):
            if name == tf:
                if price_df is None or name != self.last_tfs[i]:
                    self.last_tfs[i] = name
                    if os.path.exists(local_filename):
                        price_df = pd.read_csv(local_filename)
                        if not self.price_filenames:
                            self.price_filenames.append(local_filename)
                    elif self.s3_service.s3_file_exists(filename, backtest_bucket):
                        price_df = self.s3_service.read_df_from_s3(filename, backtest_bucket)
                        price_df = price_df.rename(columns={'Unnamed: 0': 'row'})
                    if i == 0: self.all_htf_prices_df = price_df
                    if i == 1: self.all_mtf_prices_df = price_df
                    if i == 2: self.all_ltf_prices_df = price_df
                self.log.handle(
                    0, f'Returning price_df for TF = {tf} | length = {len(price_df)}', '@_get_price_df')
                return price_df

    def _close_trade(self, context, size):
        symbol = context.get('symbol')
        trade_id = context.get('position').get('target_trade_id')
        target_trade = context.get('position').get('trades').get(trade_id)
        trade = {
            'instrument': symbol,
            **copy.deepcopy(constants.backtest_close_trade_template),
            'units': size,
            'accountBalance': target_trade.get('account_balance', 0),
            'tradesClosed': [{
                'id': trade_id,
                'units': target_trade.get('size'),
                'realizedPL': target_trade.get('P/L $')
            }]
        }
        return True, trade, None

    def _close_position(self, context, size):
        closed_position = {
            'id': self.backtest_env.get('run_info').get('entry_bar'),
            'price': str(self.backtest_env.get('run_info').get('latest_price')),
            'batchID': '',
            'accountBalance': '',
            'reason': 'MARKET_ORDER_POSITION_CLOSEOUT',
            'tradesClosed': self._get_closed_trades(context, size),
            'instrument': context.get('symbol'),
            'time': self.backtest_env.get('run_info').get('latest_date'),
            'units': str(size),
            'type': 'ORDER_FILL',
            'pl': str(context.get('position').get('P/L $')),
        }
        return True, closed_position, None

    def _open_trade(self, symbol, size, *args, **kwargs):
        trade = {
            'id': self.backtest_env.get('run_info').get('entry_bar'),
            'time': parser \
                .parse(self.backtest_env.get('run_info').get('latest_date')) \
                .strftime('%Y-%m-%dT%H:%M:%SZ'),
            'units': size,
            'price': self.backtest_env.get('run_info').get('latest_price'),
            'accountBalance': self.backtest_env.get('run_info').get('account_balance'),
            'instrument': symbol,
            'reason': 'MARKET_OPEN',
            'pl': 0.00,
            'tradeOpened': {
                'units': size,
                'halfSpreadCost': 0,
                'initialMarginRequired': 0,
            },
            'fullPrice': {
                'closeoutAsk': 0,
                'closeoutBid': 0,
                'bids': [{'liquidity': 10000000}]
            }
        }
        return True, trade, None

    def _get_open_positions(self):
        context = self._fetch_saved_context()
        type = 'long' if context.get('position').get('total_size') > 0 else 'short'
        position = {
            type: {
                'tradeIDs': context.get('position').get('trade_ids'),
                'units': context.get('position').get('total_size'),
                'unrealizedPL': context.get('position').get('P/L $'),
                'marginUsed': context.get('position').get('total_margin')
            }
        }
        return position, None

    def _get_trade_by_id(self, id):
        context = self._fetch_saved_context()
        trade = context.get('position').get('trades').get(id)
        api_trade = {
            'id': trade.get('id'),
            'currentUnits': trade.get('size'),
            'unrealizedPL': trade.get('P/L $'),
            'instrument': trade.get('symbol'),
            'price': trade.get('entry_price'),
            'marginUsed': trade.get('margin'),
            'state': 'OPEN' if not trade.get('exit_time') else 'CLOSE'
        }
        return api_trade

    def _fetch_saved_context(self):
        context = {}
        if self.context:
            return self.context
        job_data = self.backtest_env.get('job_data')
        s3_filename = self.s3_service.get_filename('backtest-trades-open', job_data)
        bucket = self.backtest_env.get('s3').get('bucket')
        if self.s3_service.s3_file_exists(s3_filename, bucket):
            data = self.s3_service.read_from_s3(s3_filename, bucket)
            if data:
                context = json.loads(data)
        self.context = context
        return self.context

    def _get_open_trades(self, symbol=None):
        context = self._fetch_saved_context()
        trades = list(context.get('position', {}).get('trades', {}).values())
        trades = [t for t in trades if t.get('state') == 'OPEN']
        return trades, None

    def _get_open_position(self, symbol=None):
        context = self._fetch_saved_context()
        return context.get('position', {})

    def _get_closed_trades(self, context, size):
        close_all = True if abs(size) == abs(
            context.get('position').get('total_size')) else False
        result = []
        size_count = abs(size)
        for trade_id, trade in context.get('position').get('trades').items():
            if not size_count:
                break  # See README 1.2
            polarity = 1 if trade.get('size') > 0 else -1
            trade_size = abs(trade.get('size'))
            next_trade = {
                'tradeID': trade_id,
                'realizedPL': str(trade.get('P/L $')),
                'units': 0
            }
            # See README 1.1
            if close_all:
                next_trade['units'] = trade_size * polarity * -1,
            elif size_count:
                if trade_size <= size_count:
                    size_count -= trade_size
                    next_trade['units'] = trade_size * polarity * -1
                elif trade_size > size_count:
                    next_trade['units'] = size_count * polarity * -1
                    size_count = 0
            result.append(next_trade)
        return result

    def _refresh_on_close(self):
        self.context = None

    def _get_backtest_prices(self, *args, **kwargs):
        pass

    def get_price_api(self):
        price_api = {
            'get_prices_by_aggs': lambda _: None,
            'get_latest_prices': self._get_latest_prices,
            'get_backtest_prices': self._get_backtest_prices,
            'get_prices_with_indis': self._get_prices_with_indis,
            'cleanup_price_files': self._cleanup_price_files,
        }
        return price_api

    def get_trader_api(self):
        trader_api = {
            'close_trade': self._close_trade,
            'close_position': self._close_position,
            'open_trade': self._open_trade,
            'get_open_positions': self._get_open_positions,
            'get_open_trades': self._get_open_trades,
            'get_closed_trades': lambda _: None,
            'get_trade_by_id': self._get_trade_by_id,
            'refresh_on_close': self._refresh_on_close,
            'get_open_position': self._get_open_position,
            'get_spread': lambda _: None,
        }
        return trader_api

    def get_account_api(self):
        account_api = {
            'get_account_info': lambda _: None,
            'get_instruments': lambda _: None,
            'get_account_id': lambda _: None,
        }
        return account_api

    def _cleanup_price_files(self):
        self.log.handle(0, 'Removing indicator files', '@cleanup_price_files')
        for file in self.price_filenames:
            if os.path.exists(file):
                os.remove(file)
                if not os.path.exists(file):
                    self.log.handle(1, f'Removed file: {file}', '@cleanup_price_files')
                else:
                    self.log.handle(-1, f'ERROR: Could not remove file{file}', '@cleanup_price_files')
