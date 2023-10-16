import copy
import pandas as pd
from dateutil import parser
import json
from datetime import timedelta
import os

from services.aws.s3 import S3Service
import constants
from constants import oanda as oanda_constants
from services.log_service import LogService


class BacktestTrader:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.prices = self.get_price_api()
        self.trader = self.get_trader_api()
        self.account = self.get_account_api()
        self.s3_service = kwargs.get('s3_service')
        self.all_htf_prices_df = None
        self.all_mtf_prices_df = None
        self.all_ltf_prices_df = None
        self.last_tfs = [None, None, None]
        self.context = None
        self.price_files = []

    @staticmethod
    def build(env, backtest_env):
        return BacktestTrader(
            env=env,
            backtest_env=backtest_env,
            s3_service=S3Service.build(env, backtest_env, bucket=env.get('s3').get('bucket')),
            log_service=LogService.build(name_prefix='BacktestTrader'))

    def _get_latest_prices(self, _, tf):
        size = self.backtest_env.get('run_info').get('lookback_size')
        price_df = self._get_price_df(tf)
        latest_date = self.backtest_env.get('run_info').get('latest_date')
        end_date = latest_date
        target_data = pd.DataFrame()
        retries = 1
        while retries < 5000:
            target_data = price_df.loc[price_df.time == end_date]
            end_date = (parser.parse(latest_date) - timedelta(minutes=(retries))) \
                .strftime('%Y-%m-%dT%H:%M%:%SZ')
            retries += 1
            if not target_data.empty:
                break
        if retries >= 5000:
            raise Exception('Could not find appropriate time in price DF')
        end = target_data.row.iloc[0] + 1
        start = 0 if end < size else end - size
        price_df = price_df.iloc[start:end]
        return price_df

    def _get_price_df(self, tf):
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
                if (price_df is None) or (name != self.last_tfs[i]):
                    self.last_tfs[i] = name
                if os.path.exists(local_filename):
                    price_df = pd.read_csv(local_filename)
                elif self.s3_service.s3_file_exists(filename, backtest_bucket):
                    self.s3_service.download(filename, local_filename, backtest_bucket)
                    price_df = pd.read_csv(local_filename)
                    self.price_files.append(local_filename)
                    price_df = price_df.rename(columns={'Unnamed: 0': 'row'})
                    if i == 0: self.all_htf_prices_df = price_df
                    if i == 1: self.all_mtf_prices_df = price_df
                    if i == 2: self.all_ltf_prices_df = price_df
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

    def _get_open_positions(self, symbol):
        context = self._fetch_saved_context(symbol)
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
        context = self._fetch_saved_context(self.backtest_env.get('run_info').get('symbol'))
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

    def _fetch_saved_context(self, symbol):
        context = {}
        if self.context:
            return self.context
        job_data = self.backtest_env.get('job_data')
        _sd = parser.parse(job_data.get('start_date'))
        _ed = parser.parse(job_data.get('end_date'))
        symbol = ''.join(job_data.get('symbol').split('_'))
        filename = '{ver}/trades/{sam}/{oc}/{tw}/{sym}_{sd}-{ed}/trades_open.txt'.format(
            ver=job_data.get('version'),
            sam=job_data.get('sample'),
            oc=job_data.get('option_code'),
            tw=f'{_sd.year}-{_ed.year}',
            sym=symbol,
            sd=_sd.strftime('%Y%m%d'),
            ed=_ed.strftime('%Y%m%d'))
        bucket = self.backtest_env.get('s3').get('bucket')
        if self.s3_service.s3_file_exists(filename, bucket):
            data = self.s3_service.read_from_s3(filename, bucket)
            if data:
                context = json.loads(data)
        self.context = context
        return self.context

    def _get_open_trades(self, symbol=None):
        context = self._fetch_saved_context(self.backtest_env.get('run_info').get('symbol'))
        return context.get('position', {}).get('trades', []), None

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

    def _append_backtest_indicators(self, price_df, tf):
        indicator_version_map = {
            'forex_trader_v2': [
                'force_mas.csv', 'macd_21_55_13.csv', 'state_keys.csv', 'stoch_5_3_3.csv',
            ]
        }
        job_data =  self.backtest_env.get('job_data')
        version = job_data.get('version')
        indicator_filenames = indicator_version_map.get(version)
        if version == 'forex_trader_v2':
            for name, val in self.env.get('indicators').get('price_ma').items():
                [ma_type, _] = name.split('_')
                indicator_filenames.append(f'{ma_type}_{val}.csv')
        indi_df = pd.DataFrame()
        start_row = price_df.iloc[0].row
        end_row = price_df.iloc[-1].row
        for filename in indicator_filenames:
            s3_filename = self.s3_service.get_filename(
                'backtest-indicators', job_data, agg_name=tf, indicator_filename=filename)
            df = self.s3_service.read_df_from_s3(s3_filename, 'cointosis-backtest')
            if df.columns[0] == 'Unnamed: 0':
                df = df.rename(columns={'Unnamed: 0': 'row'})
            indi_df = indi_df.join(df[start_row:end_row], key='row')
        price_df = price_df.join(indi_df, key='row')
        return price_df

    def cleanup_price_files(self):
        self.log.handle(0, 'Removing price files', '@cleanup_price_files')
        for file in self.price_files:
            if os.path.exists(file):
                os.remove(file)
                if not os.path.exists(file):
                    self.log.handle(0, f'Removed file: {file}', '@cleanup_price_files')
                else:
                    self.log.handle(-1, f'ERROR: Could not remove file{file}', '@cleanup_price_files')


    def _refresh_on_close(self):
        self.context = None

    def _get_backtest_prices(self, *args, **kwargs):
        pass

    def get_price_api(self):
        price_api = {
            'get_prices_by_aggs': lambda _: None,
            'get_latest_prices': self._get_latest_prices,
            'get_backtest_prices': self._get_backtest_prices,
            'append_backtest_indicators': self._append_backtest_indicators,
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
