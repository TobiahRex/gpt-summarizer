from services.oanda import OandaService
from services.alpaca import AlpacaService
from services.backtest_trader import BacktestTrader


class BrokerService:
    """Dynamic Broker Interface. The specific broker will be defined via env variable.
    """
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.prices = self._get_price_api()
        self.trader = self._get_trader_api()
        self.account = self._get_account_api()

    @staticmethod
    def build(env, backtest_env):
        return BrokerService(
            env=env,
            backtest_env=backtest_env)

    def _get_account_api(self):
        if self.env.get('backtest_active'):
            return BacktestTrader.build(self.env, self.backtest_env).get_account_api()
        elif self.env.get('broker').get('price') == 'oanda':
            return OandaService.build(self.env).get_account_api()
        elif self.env.get('broker').get('price') == 'alpaca':
            return AlpacaService.build(self.env).get_account_api()

    def _get_price_api(self):
        if self.env.get('backtest_active'):
            return BacktestTrader.build(self.env, self.backtest_env).get_price_api()
        elif self.env.get('broker').get('price') == 'oanda':
            return OandaService.build(self.env).get_price_api()
        elif self.env.get('broker').get('price') == 'alpaca':
            return AlpacaService.build(self.env).get_price_api()

    def _get_trader_api(self):
        if self.env.get('backtest_active'):
            return BacktestTrader.build(self.env, self.backtest_env).get_trader_api()
        elif self.env.get('broker').get('trade') == 'oanda':
            return OandaService.build(self.env).get_trader_api()
        elif self.env.get('broker').get('trade') == 'alpaca':
            return AlpacaService.build(self.env).get_trader_api()
