import json
import pandas as pd
from dateutil import parser
from datetime import timedelta

from services.log import LogService
from services.aws.s3 import S3Service


class BacktestIndicator:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.log = kwargs.get('log_service')
        self.s3_service = kwargs.get('s3_service')
        self.price_dfs = {}

    @staticmethod
    def build(env, backtest_env):
        return BacktestIndicator(
            env=env,
            backtest_env=backtest_env,
            log_service=LogService.build(name_prefix='BacktestTrader', should_log=False),
            s3_service=S3Service.build(env, backtest_env, bucket=env.get('s3').get('bucket'))
        )

    def get_prices_with_indis(self, price_df, tf, size):
        indicator_df = None
        if tf not in self.price_dfs:
            indicator_df = self.__build_indicator_df(price_df, tf)
        else:
            indicator_df = self.price_dfs.get(tf)
        price_with_indis_df = self.__get_sliced_prices_with_indis(tf, indicator_df, size)
        self.log.handle(
            0, 'Returning indicators on price_df', '@get_prices_with_indis')
        return price_with_indis_df

    def __get_sliced_prices_with_indis(self, tf, indi_df, size):
        self.log.handle(
            0, 'Slicing Indicator DF per current Time', '@__get_sliced_prices_with_indis')
        latest_date = self.backtest_env.get('run_info').get('latest_date')
        self.log.handle(0, f'Latest Date: {latest_date}', '@__get_sliced_prices_with_indis')
        search_date = latest_date
        target_data = pd.DataFrame()
        retries = 1
        while retries < 5000:
            target_data = indi_df.loc[indi_df.time == search_date]
            delta_args = self.__get_delta_args(tf, retries, latest_date)
            search_date = (parser.parse(latest_date) - timedelta(**delta_args)).strftime('%Y-%m-%dT%H:%M:%SZ')
            if not target_data.empty:
                break
            self.log.handle(0, f'Retry | {retries} | search_date = {search_date}', '@__get_sliced_prices_with_indis')
            retries += 1
            if retries >= 5000:
                raise Exception('Could not find appropriate time in price DF')
        end = int(target_data.row.iloc[-1]) + 1
        start = 0 if end < size else end - size
        indi_df = indi_df[start:end]
        self.log.handle(
            0, f'Returning Slicing Indicator DF | {len(indi_df)}', '@__get_sliced_prices_with_indis')
        return indi_df

    def __build_indicator_df(self, price_df, tf):
        self.log.handle(0, f'Building indicator DF: {tf}', '@__build_indicator_df')
        indicator_filenames = self.__get_indicator_filenames()
        self.price_dfs[tf] = None
        for filename in indicator_filenames:
            job_data = self.backtest_env.get('job_data')
            s3_filename = self.s3_service.get_filename(
                'backtest-indicators', job_data, agg_name=tf, indicator_filename=filename)
            target_indi_df = self.__download_indicator_file(s3_filename)
            target_indi_df = self.__rename_ma_columns(job_data, target_indi_df, filename)
            source_df = price_df
            if self.price_dfs.get(tf) is not None:
                source_df = self.price_dfs.get(tf)
            self.price_dfs[tf] = pd.merge(
                source_df,
                target_indi_df,
                how='left',
                left_on=['time', 'row'],
                right_on=['time', 'row'])
            if filename.split('_')[0] in ['ema', 'sma']:
                self.backtest_env.get('options').get('option_values').get('MA')
        self.log.handle(0, f'Returning indicator DF: {tf}', '@__build_indicator_df')
        return self.price_dfs.get(tf)

    def __rename_ma_columns(self, job_data, indi_df, indicator_filename):
        ma_type = indicator_filename[0:4]
        if ma_type not in ['ema_', 'sma_']:
            return indi_df
        ma_code = job_data.get('option_code')[4:7]
        ma_nums = self.backtest_env.get('options').get('option_values').get('MA').get(ma_code[-1])
        columns = list(indi_df)
        for i, num in enumerate(ma_nums):
            label = f'{ma_type}{num}'
            if label in columns:
                target_col_name = self.backtest_env.get('options').get('option_names').get('MA')[i]
                self.log.handle(0, f'Renaming MA col from {label} to {target_col_name}', '@__rename_ma_columns')
                indi_df = indi_df.rename(columns={label: target_col_name})
        return indi_df

    def __get_indicator_filenames(self):
        indicator_version_map = {
            'forex_trader_v2': [
                'force_mas.csv', 'macd_21_55_13.csv', 'state_keys.csv', 'stoch_5_3_3.csv',
            ]
        }
        job_data = self.backtest_env.get('job_data')
        version = job_data.get('version')
        indicator_filenames = indicator_version_map.get(version)
        if version == 'forex_trader_v2':
            for name, val in self.env.get('indicators').get('price_ma').items():
                [ma_type, _] = name.split('_')
                indicator_filenames.append(f'{ma_type}_{val}.csv')
        return indicator_filenames

    def __download_indicator_file(self, s3_filename):
        df = self.s3_service.read_df_from_s3(s3_filename, 'cointosis-backtest')
        if df.columns[0] == 'Unnamed: 0':
            df = df.rename(columns={'Unnamed: 0': 'row'})
        return df

    def __get_delta_args(self, tf, retries, target_date):
        target_minutes = parser.parse(target_date).minute
        delta_args = {}
        if tf in ['1day', '4hr', '1hr']:
            if target_minutes == 0:
                delta_args['hours'] = retries
            else:
                delta_args['minutes'] = retries * target_minutes
        elif 'min' in tf:
            tf_min = int(tf[0:2])
            if (target_minutes == 0) or (target_minutes % tf_min == 0):
                delta_args['minutes'] = retries * tf_min
            else:
                delta_args['minutes'] = retries
        return delta_args
