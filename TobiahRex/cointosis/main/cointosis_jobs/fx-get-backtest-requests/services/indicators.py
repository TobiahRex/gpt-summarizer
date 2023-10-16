import pandas_ta  # noqa: F401

from services.utilis import UtilityService
from services.broker import BrokerService
from services.log import LogService
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
            log=LogService.build('IndicatorService', should_log=True),
            s3_service=S3Service.build(env, backtest_env))

    def calc_indicators(self, context):
        symbol = context.get('symbol')
        price_data = {}
        for tf in context.get('tfs'):
            self.log.handle(0, f'{tf}: Calculating Indicators', '@calc_indicators')
            force = 0
            retries = 1
            calculating = True
            while calculating:
                price_df = []
                has_enough_data, price_df = self.__compose_backtest_indicators(symbol, tf, retries)
                if has_enough_data:
                    force = price_df.iloc[-1].force
                    price_data[tf] = price_df
                    calculating = False
                else:
                    retries += 1
                if retries >= 5:
                    break
                elif force:
                    break
        return True, price_data

    def __compose_backtest_indicators(self, symbol, tf, retries):
        root_size = 200
        next_size = root_size * retries
        price_df = self.broker_service.prices.get('get_latest_prices')(symbol, tf)
        price_df = self.broker_service.prices.get('get_prices_with_indis')(
            price_df, tf, size=next_size)
        has_enough_data = len(list(price_df.groupby(['force_polarity']).groups.keys())) >= 2
        if has_enough_data:
            return True, price_df
        else:
            self.log.handle(0, f'{tf}: Calculating more indicator values...', '@calc_indicators')
            return False, None

    def cleanup_backtest_files(self):
        self.broker_service.prices.get('cleanup_price_files')()

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
