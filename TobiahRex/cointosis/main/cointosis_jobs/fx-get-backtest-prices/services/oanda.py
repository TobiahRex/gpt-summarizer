from datetime import timedelta
import pytz
from dateutil import parser
import oandapyV20 as oanda
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

    def _get_backtest_prices(self, symbol, tf, root_size, retries, backtest_data):
        # NOTE: Calls Oanda Price API to retrive prices for backtesting.
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
            if not self.__keep_candle(candle, seed_date):
                continue
            candle['time'] = self.__clean_time(candle.get('time'))
            candles.append(self.__parse_candle(candle))
        prices_df = pd.DataFrame.from_records(candles)
        return prices_df

    def get_price_api(self):
        price_api = {
            'get_backtest_prices': self._get_backtest_prices,
        }
        return price_api

    @staticmethod
    def __parse_candle(candle):
        return {
            'time': candle.get('time'),
            'open': float(candle.get('mid').get('o')),
            'high': float(candle.get('mid').get('h')),
            'low': float(candle.get('mid').get('l')),
            'close': float(candle.get('mid').get('c')),
            'volume': float(candle.get('volume'))
        }

    @staticmethod
    def __clean_time(utc_time):
        pst_time = parser \
            .parse(utc_time) \
            .strftime('%Y-%m-%dT%H:%M:%SZ')
        return pst_time

    @staticmethod
    def __keep_candle(candle, seed_date):
        candle_date = parser.parse(candle.get('time'))
        if candle_date > seed_date:
            return False
        return True

if __name__ == '__main__':
    from services.aws.ssm import SSMService
    oanda = OandaService.build(SSMService.build().get_param('/cointosis/forex_trader_v2'))
    result = oanda.get_trader_api().get('close_position')('EUR_JPY', 20000)
    print(result)
