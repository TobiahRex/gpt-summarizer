from pandas.core.frame import DataFrame
import pandas_ta  # noqa: E501
import math

from services.utilis import UtilityService
from services.broker import BrokerService
from services.log_service import LogService
from services.aws.s3 import S3Service


class IndicatorsService:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.utility_service = kwargs.get('utils')
        self.broker_service = kwargs.get('broker_service')
        self.log = kwargs.get('log')

    @staticmethod
    def build(env, backtest_env):
        return IndicatorsService(
            env=env,
            backtest_env=backtest_env,
            utils=UtilityService.build(),
            broker_service=BrokerService.build(env, backtest_env),
            log=LogService.build('IndicatorService'),
            s3_service=S3Service.build(env, backtest_env))

    def calc_indicators(self, context):
        symbol = context.get('symbol')
        latest_prices = {}
        for tf in context.get('tfs'):
            self.log.handle(0, f'{tf}: Calculating Indicators', '@calc_indicators')
            force = 0
            retries = 1
            calculating = True
            while calculating:
                price_df = []
                if self.env.get('backtest_active'):
                    price_df = self.broker_service.prices.get('get_latest_prices')(symbol, tf)
                    price_df = self.broker_service.prices.get('append_backtest_indicators')(price_df, tf)
                    latest_prices[tf] = price_df
                    calculating = False
                    break
                else:
                    root_size = 70
                    next_size = retries * root_size
                    price_df = self.broker_service.prices.get('get_latest_prices')(symbol, tf, size=next_size)
                    try:
                        price_df = self.calc_macd(price_df)
                        price_df = self.calc_stochastics(price_df)
                        price_df = self.calc_emas(price_df, self.env.get('indicators').get('price_ma'))
                        price_df = self.calc_force(price_df, symbol)
                        has_enough_data = len(list(price_df.groupby(['force_polarity']).groups.keys())) == 3
                    except Exception as e:
                        has_enough_data = False
                    if has_enough_data:
                        force = price_df.iloc[-1].force
                        latest_prices[tf] = price_df
                        calculating = False
                    else:
                        self.log.handle(0, f'{tf}: Calculating more indicator values...', '@calc_indicators')
                        retries += 1
                    if retries >= 5:
                        break
                    elif force:
                        break
        return True, latest_prices

    def get_backtest_indicators(self, symbol, price_df, mtf_agg=None):
        if mtf_agg is None:
            mtf_agg = self.env.get('tfs')[1]
        self.log.handle(0, 'Calculating Backtest Indicators...', '@get_backtest_indicators')
        price_df = self.calc_macd(price_df)
        price_df = self.calc_stochastics(price_df)
        price_df = self.calc_emas(price_df, self.env.get('indicators').get('price_ma'))
        price_df = self.calc_states(price_df, mtf_agg)
        price_df = self.calc_force(price_df, symbol)
        price_df = self.clean_nas(df=price_df,
            names=[
                'macd_21_55_13',
                'macds_21_55_13',
                'macdh_21_55_13',
                'stochk_5_3_3',
                'stochd_5_3_3',
                'force',
                'force_fast',
                'force_slow',
                'force_polarity',
                'force_acceleration',
                'force_mass'],
            fill_value=0)
        price_df['state_keys'] = price_df['state_keys'].fillna('')
        return price_df

    @staticmethod
    def calc_macd(price_df:DataFrame, close='close', fast=21, slow=55, signal=13, append=True):
        price_df.ta.macd(close='close', fast=fast, slow=slow, signal=signal, append=append)
        price_df.columns = [x.lower() for x in price_df.columns]
        return price_df

    @staticmethod
    def calc_stochastics(price_df:DataFrame, high='high', low='low', k=5, d=3, append=True):
        price_df.ta.stoch(high=high, low=low, k=k, d=d, append=append)
        price_df.columns = [x.lower() for x in price_df.columns]
        return price_df

    @staticmethod
    def calc_emas(price_df, ma_values, append=True):
        ma_values = [
            {'ema': 8},
            {'ema': 13},
            {'ema': 21},
            {'ema': 34},
            {'sma': 55},
        ]
        for data in ma_values:
            [_type, length] = list(*data.items())
            if 'ema' in _type:
                price_df.ta.ema(close='close', length=length, append=append)
                name = f'EMA_{length}'
                price_df[name] = price_df[name].fillna(0)
            if 'sma' in _type:
                price_df.ta.sma(close='close', length=length, append=append)
                name = f'SMA_{length}'
                price_df[name] = price_df[name].fillna(0)
        price_df.columns = [x.lower() for x in price_df.columns]
        return price_df

    def calc_states(self, price_df:DataFrame, agg: str) -> list:
        """
            Calculates a state set where each price point is mapped to an
            alpha-numeric system (B1-B8 & S1-S8)
            where each state denotes a particular pattern of price momentum.
            e.g.
                B1 = Momo + and Increasing
                B2 = Momo + and Stationary
                B5 = Momo + and Decreasing
                B7 = Momo + and Decreasing
                etc...
            :param price_data: current dictionary of price information for
                all aggs
            :param agg: string denoting the aggregation period to
                calculate states values for.
            :return matrix_vals: List of matrix values. Index denotes
                the row the state maps to.
            """
        states = [''] * 66
        prev_row = None
        last_percent = 0
        for i, row in price_df[66:].iterrows():
            matrix_val = ''
            if i == 66:
                prev_row = row
            macd_avg = row.get('macds_21_55_13')
            macd_val = row.get('macd_21_55_13')
            stoch_d = row.get('stochd_5_3_3')
            prev_stoch_d = prev_row.get('stochd_5_3_3')
            if macd_avg >= 0:
                if macd_val >= macd_avg:
                    if stoch_d >= prev_stoch_d:
                        if stoch_d >= 50:
                            matrix_val = 'B1'
                        else:
                            matrix_val = 'B4'
                    else:
                        if stoch_d >= 50:
                            matrix_val = 'B2'
                        else:
                            matrix_val = 'B3'
                else:
                    if stoch_d >= prev_stoch_d:
                        if stoch_d >= 50:
                            matrix_val = 'B5'
                        else:
                            matrix_val = 'B8'
                    else:
                        if stoch_d >= 50:
                            matrix_val = 'B6'
                        else:
                            matrix_val = 'B7'
            else:
                if macd_val < macd_avg:
                    if stoch_d >= prev_stoch_d:
                        if stoch_d >= 50:
                            matrix_val = 'S3'
                        else:
                            matrix_val = 'S2'
                    else:
                        if stoch_d >= 50:
                            matrix_val = 'S4'
                        else:
                            matrix_val = 'S1'
                else:
                    if stoch_d >= prev_stoch_d:
                        if stoch_d >= 50:
                            matrix_val = 'S7'
                        else:
                            matrix_val = 'S6'
                    else:
                        if stoch_d >= 50:
                            matrix_val = 'S8'
                        else:
                            matrix_val = 'S5'
            states.append(matrix_val)
            prev_row = row
            percent = self.utility_service.divide(i, len(price_df), 4) * 100
            if percent - last_percent >= 10:
                last_percent = percent
            if not states:
                raise Exception(f'No state keys given {agg} price data')
        price_df['state_keys'] = states
        return price_df

    def get_latest_trade_key(self, prices:dict):
        """Scans through a list of price dataframes and calculates the momentum indicator values,
        attaches those values to the underlying dataframe, then calculates the underlying
        state key values from that data, then parses together a 3-state key and returns to caller.

        Args:
            latest_prices (dict): A collection of 3 aggregations' name and price data.

        Raises:
            Exception: If there's not at least 33 data points to calculate momoentum indicator values from.
            Exception: If state key generation failed or was fruitless.

        Returns:
            str: A single state key that maps all three aggregations to a particular state given latest prices
            for those three aggregations.
        """
        latest_trade_key = ''
        for agg, price_df in prices.items():
            if not len(price_df) >= 33:
                raise Exception(
                    'Not enough raw price data to calculate momentum indicators')
            if price_df.empty:
                self.log.handle(0, 'Could not calculate latest trade key. DataFrame is empty', '@get_latest_trade_key')
                return latest_trade_key
            if not self.env.get('backtest_active'):
                price_df = self.calc_states(price_df, agg)
            latest_trade_key += f'_{price_df.iloc[-1].state_keys}' if latest_trade_key else price_df.iloc[-1].state_keys
            prices[agg] = price_df
        return latest_trade_key

    def calc_force(self, price_df, symbol):
        slope = 0
        rise = 0
        run = 0
        accel = 0
        mass_i = 0
        force = 0
        polarity = 0
        start_i = 0
        last_p = 0
        price_df['force'] = [0] * len(price_df)
        price_df['force_polarity'] = [0] * len(price_df)
        m = 1
        if self.env.get('indicators').get('force').get('source') == 'macd':
            price_df['force_fast'] = price_df['macd_21_55_13'].fillna(0)
            price_df['force_slow'] = price_df['macds_21_55_13'].fillna(0)
            m = 100 if 'JPY' in symbol else 1000
        elif self.env.get('indicators').get('force').get('source') == 'mas':
            price_df['force_fast'] = price_df['ema_13'].fillna(0)
            price_df['force_slow'] = price_df['ema_21'].fillna(0)
            m = 10 if 'JPY' in symbol else 1000
        last_p = 0
        for i, row in price_df.iterrows():
            price_df.loc[i, 'force'] = 0
            price_df.loc[i, 'force_polarity'] = 0
            if not start_i:
                start_i = i
            if start_i >= price_df.iloc[-1].name:
                break
            next_polarity = 0
            if row.force_fast and row.force_slow:
                if row.force_fast > row.force_slow:
                    next_polarity = 1
                else:
                    next_polarity = -1
            run = self.get_force_window_size(
                price_df, polarity, run, start_i, i)
            if next_polarity != polarity:
                # No change in run means the sequence is finished
                start_i = i
                mass_i = 0
                force = 0
                accel = 0
                slope = 0
                rise = 0
                polarity = next_polarity
            else:
                polarity = next_polarity
                rise = self.get_force_rise(price_df, start_i, i, m)
                accel = self.get_force_acceleration(price_df, polarity, run, start_i, i, m)
                slope = (rise / run) * polarity if rise and run else 0
                mass_i = self.get_force_mass(price_df, polarity, run, mass_i, slope, start_i, i, m)
                raw_force = round(mass_i * accel, 4)
                force = raw_force * polarity if raw_force else 0
                if abs(force) > 10:
                    force
                p = round((i / len(price_df))*100, 2)
                # print(f'{i} | {row.close} | {row.matrix_state} | {round(mass_i, 1)} | {round(accel, 1)} | {force}')
                if p % 1 == 0 and p != last_p:
                    # print(f'** PROGRESS ** | {row.time} | {p} % | i = {i}')
                    last_p = p
            price_df.loc[i, 'force'] = force
            price_df.loc[i, 'acceleration'] = accel
            price_df.loc[i, 'mass'] = mass_i
            price_df.loc[i, 'force_polarity'] = polarity
        return price_df

    @staticmethod
    def get_force_window_size(df, p, run, start_i, end_i):
        if end_i >= df.iloc[-1].name:
            end_i = df.iloc[-1].name
        if start_i >= df.iloc[-1].name:
            start_i = df.iloc[-1].name
        if start_i == end_i:
            return run + 1
        s_force_slow = df.loc[start_i].force_slow
        e_force_slow = df.loc[end_i].force_slow
        if p == 1:
            if e_force_slow >= s_force_slow:
                run += 1
            else:
                run = 1
        if p == -1:
            if e_force_slow <= s_force_slow:
                run += 1
            else:
                run = 1
        return run

    @staticmethod
    def get_force_rise(df, start_i, end_i, m):
        if end_i >= df.iloc[-1].name:
            end_i = df.iloc[-1].name
        if start_i >= df.iloc[-1].name:
            start_i = df.iloc[-1].name
        start_data = df.loc[start_i]
        end_data = df.loc[end_i]
        rise = abs((start_data.force_slow * m) - (end_data.force_slow * m))
        return rise

    @staticmethod
    def get_force_acceleration(df, polarity, run, start_i, end_i, m):
        if end_i >= df.iloc[-1].name:
            end_i = df.iloc[-1].name
        if start_i >= df.iloc[-1].name:
            start_i = df.iloc[-1].name
        start_data = df.loc[start_i]
        end_data = df.loc[end_i]
        start_force_fast = start_data.force_fast * m
        start_force_slow = start_data.force_slow * m
        end_force_fast = end_data.force_fast * m
        rise = abs(start_force_fast - end_force_fast)
        numerator = abs(start_force_slow - end_force_fast)**2 - \
            abs(start_force_fast - start_force_slow)**2
        denominator = 2 * math.sqrt(run**2 + rise**2)
        acceleration = (numerator / denominator) * \
            polarity if numerator and denominator else 0
        return acceleration

    @staticmethod
    def get_force_mass(df, p, run, mass_i, slope, start_i, end_i, m):
        if end_i >= df.iloc[-1].name:
            end_i = df.iloc[-1].name
        if start_i >= df.iloc[-1].name:
            start_i = df.iloc[-1].name
        start_data = df.loc[start_i]
        end_data = df.loc[end_i]
        start_force_fast = start_data.force_fast * m
        end_force_fast = end_data.force_fast * m
        diff = abs(abs(slope * run) - abs(start_force_fast - end_force_fast))
        mass = (abs(mass_i) + diff) * p
        return mass

    @staticmethod
    def clean_nas(df, names, fill_value):
        for n in names:
            df[n] = df[n].fillna(fill_value)
        return df