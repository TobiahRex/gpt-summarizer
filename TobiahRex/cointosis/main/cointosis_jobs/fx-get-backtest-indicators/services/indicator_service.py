from fileinput import filename
import math
import pandas_ta
from services.aws.s3 import S3Service  # noqa: F401
from services.utilis import UtilityService
from services.log_service import LogService
import constants

class IndicatorsService:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.utility_service = kwargs.get('utils')
        self.broker_service = kwargs.get('broker_service')
        self.s3 = kwargs.get('s3_service')
        self.log = kwargs.get('log')

    @staticmethod
    def build(env):
        return IndicatorsService(
            env=env,
            s3_service=S3Service.build(env),
            utils=UtilityService.build(),
            log=LogService.build('IndicatorService'))

    def calculate_indicators(self, price_df, job_data, tf):
        filename_prefix = self.s3.get_filename('backtest-indicators', job_data, agg_name=tf)
        indicator_value_map = constants.version_indicator_map.get(job_data.get('version'))
        for name, params in indicator_value_map.items():
            if name == 'macd':
                indi_filename = filename_prefix + f'macd_{params[0]}_{params[1]}_{params[2]}.csv'
                if not self.s3.s3_file_exists(indi_filename):
                    price_df = self._calc_macd(price_df, fast=params[0], slow=params[1], signal=params[2])
            if name == 'stochastics':
                indi_filename = filename_prefix + f'stoch_{params[0]}_{params[1]}_3.csv'
                if not self.s3.s3_file_exists(indi_filename):
                    price_df = self._calc_stochastics(price_df, k=params[0], d=params[1])
            if name == 'mas':
                for param in params:
                    indi_filename = filename_prefix + f'{param[0]}_{param[1]}.csv'
                    if not self.s3.s3_file_exists(indi_filename):
                        price_df = self._calc_emas(price_df, param)
            if name == 'states':
                indi_filename = filename_prefix + 'state_keys.csv'
                if not self.s3.s3_file_exists(indi_filename):
                    price_df = self._calc_states(price_df, job_data.get('tf'))
            if name == 'force':
                indi_filename = filename_prefix + 'force_mas.csv'
                if not self.s3.s3_file_exists(indi_filename):
                    price_df = self._calc_force(price_df, job_data.get('symbol'))
        return price_df

    @staticmethod
    def _calc_macd(price_df, close='close', fast=21, slow=55, signal=13, append=True):
        price_df.ta.macd(close=close, fast=fast, slow=slow, signal=signal, append=append)
        price_df.columns = [x.lower() for x in price_df.columns]
        return price_df

    @staticmethod
    def _calc_stochastics(price_df, high='high', low='low', k=5, d=3, append=True):
        price_df.ta.stoch(high=high, low=low, k=k, d=d, append=append)
        price_df.columns = [x.lower() for x in price_df.columns]
        return price_df

    @staticmethod
    def _calc_emas(price_df, param, append=True):
        [_type, length] = param
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

    def _calc_states(self, price_df, agg):
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
                raise Exception(f'No state keys given for {agg} price data')
        price_df['state_keys'] = states
        return price_df

    def _calc_force(self, price_df, symbol):
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
            macd_vals = [c for c in price_df.columns if 'macd' in c]
            price_df['force_fast'] = price_df[macd_vals[0]].fillna(0)
            price_df['force_slow'] = price_df[macd_vals[1]].fillna(0)
            m = 100 if 'JPY' in symbol else 1000
        elif self.env.get('indicators').get('force').get('source') == 'mas':
            ema_vals = [c for c in price_df.columns if 'ema' in c]
            price_df['force_fast'] = price_df[ema_vals[0]].fillna(0)
            price_df['force_slow'] = price_df[ema_vals[1]].fillna(0)
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
            run = self._get_force_window_size(
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
                rise = self._get_force_rise(price_df, start_i, i, m)
                accel = self._get_force_acceleration(
                    price_df, polarity, run, start_i, i, m)
                slope = (rise / run) * polarity if rise and run else 0
                mass_i = self._get_force_mass(
                    price_df, polarity, run, mass_i, slope, start_i, i, m)
                raw_force = round(mass_i * accel, 4)
                force = raw_force * polarity if raw_force else 0
                if abs(force) > 10:
                    force
                p = round((i / len(price_df))*100, 2)
                # print(f'{i} | {row.close} | {row.matrix_state} | {round(mass_i, 1)} | {round(accel, 1)} | {force}')
                if p % 1 == 0 and p != last_p:
                    print(f'* Force * | {row.time} | {p} % | i = {i}')
                    last_p = p
            price_df.loc[i, 'force'] = force
            price_df.loc[i, 'force_acceleration'] = accel
            price_df.loc[i, 'force_mass'] = mass_i
            price_df.loc[i, 'force_polarity'] = polarity
        return price_df

    @staticmethod
    def _get_force_window_size(df, p, run, start_i, end_i):
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
    def _get_force_rise(df, start_i, end_i, m):
        if end_i >= df.iloc[-1].name:
            end_i = df.iloc[-1].name
        if start_i >= df.iloc[-1].name:
            start_i = df.iloc[-1].name
        start_data = df.loc[start_i]
        end_data = df.loc[end_i]
        rise = abs((start_data.force_slow * m) - (end_data.force_slow * m))
        return rise

    @staticmethod
    def _get_force_acceleration(df, polarity, run, start_i, end_i, m):
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
    def _get_force_mass(df, p, run, mass_i, slope, start_i, end_i, m):
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
