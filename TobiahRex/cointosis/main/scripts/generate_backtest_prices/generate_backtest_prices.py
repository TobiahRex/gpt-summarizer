import os
import pandas as pd
import pandas_ta
import numpy as np

from constants.oanda import aggs_map
from services.aws.s3 import S3Service
from services.broker import BrokerService
from services.indicators_service_v1 import IndicatorsService


class GenerateBacktestPrices:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.broker_service = None
        self.indicator_service = kwargs.get('indicator_service')
        self.s3_service = kwargs.get('s3_service')

    @staticmethod
    def build(env, backtest_env):
        return GenerateBacktestPrices(
            env=env,
            backtest_env=backtest_env,
            indicator_service=IndicatorsService.build(env, backtest_env),
            s3_service=S3Service.build(env, backtest_env, bucket=env.get('s3').get('bucket')))

    def run(self):
        for tf in aggs_map.keys():
            periods = self.backtest_env.get('backtest_periods')
            for p in periods:
                symbol = p.get('symbol')
                filename = 'forex_trader_v2/prices/{start}-{end}/{syear}_{eyear}_{symbol}_{tf}.csv'.format(
                    start=p.get('start').split('-')[0],
                    end=p.get('end').split('-')[0],
                    syear=''.join(p.get('start').split('-')),
                    eyear=''.join(p.get('end').split('-')),
                    symbol=''.join(symbol.split('_')),
                    tf=tf)
                price_df = None
                if self.s3_service.s3_file_exists(filename, bucket='cointosis-backtest'):
                    continue
                else:
                    self.broker_service = BrokerService.build(env, backtest_env)
                    price_df = self.broker_service.prices.get('get_backtest_prices')(
                        symbol,
                        tf=tf,
                        root_size=100,
                        retries=1,
                        backtest_data={
                            'from': p.get('start'),
                            'to': p.get('end'),
                        })
                price_df = self.indicator_service.get_backtest_indicators(symbol, price_df, tf)
                price_df = self.reformat_df(price_df)
                self.upload_results(price_df, filename)

    def upload_results(self, price_df, filename):
        local_filename = filename.split('/')[-1]
        price_df.to_csv(local_filename)
        if not self.s3_service.upload(local_filename, filename, 'cointosis-backtest'):
            raise Exception('Could not upload')
        os.remove(local_filename)

    def reformat_df(self, price_df):
        times = list(price_df.time)
        backtest_df = price_df.set_index(pd.DatetimeIndex(times))
        backtest_df = backtest_df.rename(columns={
            'time': 'Time',
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume',
        })
        row_num = [i for i in range(0, len(backtest_df))]
        backtest_df['row'] = row_num
        backtest_df = backtest_df.replace({np.nan: None})
        return backtest_df


if __name__ == '__main__':
    from services.aws.ssm import SSMService
    backtest_env = SSMService.build().get_param('/cointosis/backtest_forex_trader_v2')
    env = SSMService.build().get_param('/cointosis/forex_trader_v2')
    env['backtest_active'] = 0
    GenerateBacktestPrices.build(env, backtest_env).run()
