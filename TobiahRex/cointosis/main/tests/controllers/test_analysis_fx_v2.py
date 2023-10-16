from multiprocessing import log_to_stderr
import unittest
from unittest.mock import MagicMock
import copy
import constants

from services.aws.ssm import SSMService
from services.indicators_service_v1 import IndicatorsService
from services.indicators_service_v1 import BrokerService
from services.utilis import UtilityService
from controllers.analysis_fx_v2 import AnalysisController


class TestAnalysisV2(unittest.TestCase):
    def setUp(self):
        self.env = SSMService.build().get_param('/cointosis/forex_trader_v2')

    unittest.skip('')
    def test_should_close_on_htf_key(self):
        context = copy.deepcopy(constants.context_template)
        context['keys']['chained'] = ['S5_B1_B1']
        context['keys']['entry_key'] = 'S5_B1_B1'
        context['keys']['last_key'] = 'S5_B1_B1'
        analysis = AnalysisController(env=self.env,
                                      log_service=MagicMock(),
                                      IndicatorsService=MagicMock(),
                                      broker_service=MagicMock(),
                                      utility_service=MagicMock())
        trade_type = 'BUY'
        close_triggers = analysis._get_triggers(self.env.get('trading').get('triggers'), 'close')
        result = analysis._should_close_on_htf_key(close_triggers, context.get('keys'), trade_type)
        self.assertTrue(result)
        close_triggers = []
        result = analysis._should_close_on_htf_key(close_triggers, context.get('keys'), trade_type)
        self.assertFalse(result)
        close_triggers = ['close_on_something']
        result = analysis._should_close_on_htf_key(close_triggers, context.get('keys'), trade_type)
        self.assertFalse(result)
        close_triggers = ['close_on_htf_key']
        context['keys']['chained'] = ['S5_B1_B4']
        result = analysis._should_close_on_htf_key(close_triggers, context.get('keys'), trade_type)
        self.assertTrue(result)

    def test_should_close_on_ltf_force(self):
        broker_service = BrokerService.build(env=self.env)
        analysis = AnalysisController(env=self.env,
                                      log_service=MagicMock(),
                                      indicator_service=IndicatorsService(
                                          env=self.env,
                                          log=MagicMock(),
                                          broker_service=broker_service,
                                          utils=UtilityService.build()),
                                      broker_service=broker_service,
                                      utility_service=MagicMock())
        tfs = ['30min', '15min', '5min']
        analysis.analyze_mkt_key('GBP_USD', tfs)
        context = {**copy.deepcopy(analysis.context)}
        context['position']['trade_type'] = 'BUY'
        context['tfs'] = tfs
        df = context['latest_prices'][tfs[-1]]
        threshold_val = self.env.get('indicators').get('force').get('ltf_exit')
        df.iat[99, df.columns.get_loc('force')] = threshold_val * 1.5 * -1
        context['latest_prices'][tfs[-1]] = df
        close_triggers = analysis._get_triggers(self.env.get('trading').get('triggers'), 'close')
        result = analysis._should_close_on_ltf_force(close_triggers, context, self.env)
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
