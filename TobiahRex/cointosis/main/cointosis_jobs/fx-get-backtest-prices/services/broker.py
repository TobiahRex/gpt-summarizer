from services.oanda import OandaService


class BrokerService:
    """Dynamic Broker Interface. The specific broker will be defined via env variable.
    """
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.prices = self._get_price_api()

    @staticmethod
    def build(env):
        return BrokerService(env=env)

    def _get_account_api(self):
        if self.env.get('broker').get('price') == 'oanda':
            return OandaService.build(self.env).get_account_api()

    def _get_price_api(self):
        if self.env.get('broker').get('price') == 'oanda':
            return OandaService.build(self.env).get_price_api()

    def _get_trader_api(self):
        if self.env.get('broker').get('trade') == 'oanda':
            return OandaService.build(self.env).get_trader_api()
