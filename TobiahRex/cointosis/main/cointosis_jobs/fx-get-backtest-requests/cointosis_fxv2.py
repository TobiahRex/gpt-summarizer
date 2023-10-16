from datetime import datetime as dt
from dateutil import parser
import copy
import json

import constants
from controllers.trade import TradeController
from controllers.notification import NotificationController
from controllers.calculation import CalculationController
from controllers.data import DataController
from services.indicators import IndicatorsService
from services.log import LogService
from services.utilis import UtilityService
from services.aws.ecs import ECSService


class CointosisFxv2:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.log = kwargs.get('log_service')
        self.trade_controller = kwargs.get('trade_controller')
        self.calculation_controller = kwargs.get('calculation_controller')
        self.notification_controller = kwargs.get('notification_controller')
        self.data_controller = kwargs.get('data_controller')
        self.indicator_service = kwargs.get('indicator_service')
        self.ecs_service = kwargs.get('ecs_service')
        self.utils = kwargs.get('utils')
        self.analysis_controller = None
        self.context = None

    @staticmethod
    def build(env, backtest_env):
        return CointosisFxv2(
            env=env,
            backtest_env=backtest_env,
            ecs_service=ECSService.build(),
            log_service=LogService.build(name_prefix='CointosisFxv2'),
            trade_controller=TradeController.build(env, backtest_env),
            calculation_controller=CalculationController.build(env, backtest_env),
            notification_controller=NotificationController.build(env, backtest_env),
            data_controller=DataController.build(env, backtest_env),
            indicator_service=IndicatorsService.build(env, backtest_env),
            utils=UtilityService.build())

    def run(self, symbol=None):
        try:
            self._setup_run(symbol)
            self._handle_run()
            self._log_results()
        except Exception as e:
            self.log.handle(-1, e, '@cointosis.run',)
            if self.env.get('ECS_TASK_ID'):
                print('Stopping ECS based on Error')
                self.ecs_service.stop_task(self.env.get('ECS_TASK_ID'))
        return self.context

    def _setup_run(self, symbol):
        if not self._setup_context(symbol, self.env.get('tfs')):
            raise Exception('Could not setup context')
        if not self._get_market_key_by_tfs(self.context):
            raise Exception('Could not calculate indicators')
        version = self.env.get('version') if not self.env.get('backtest_active') \
            else self.backtest_env.get('job_data').get('version')
        self._set_analyzer(version)

    def _handle_run(self):
        position = self.context.get('position')
        if position.get('total_size'):
            self.refresh_data()
        self.run_model()

    def refresh_data(self):
        self.context['position'] = self.trade_controller.update_position(self.context)
        self.context['action'] = 'update'
        self.context = self.calculation_controller.handle_calculations(self.context)
        self.context['action'] = ''

    def run_model(self):
        if self._verify_runtime():
            self.context = self.analysis_controller.analyze(self.context)
            self.context = self.trade_controller.handle_analysis(self.context)
            self.context = self.calculation_controller.handle_calculations(self.context)
            self.context = self.notification_controller.handle_notification(self.context)
            self.context = self.data_controller.handle_save_data(self.context)
        else:
            self.log.handle(0, 'LTF is out of bounds.', '@run_model',)

    def _log_results(self):
        if self.context.get('last_action') == 'wait':
            self.log.handle(0, 'WAIT', '@cointosis.run',)
        elif self.context.get('position').get('last_order_success'):
            self.log.handle(0, self.context.get('notifications')[-1], '@cointosis.run',)

    def _setup_context(self, symbol, tfs):
        if self.env.get('backtest_active'):
            cached_context = self.context
        else:
            cached_context = self.data_controller.get_cached_context(symbol)
        if cached_context:
            self.context = cached_context
            return True
        next_context = {
            **copy.deepcopy(constants.context_template),
            'symbol': symbol,
            'tfs': tfs,
            'keys': {**copy.deepcopy(constants.keys_template)},
            'position': {
                **copy.deepcopy(constants.position_template),
                'symbol': symbol,
            },
            'name': '{symbol}_{htf}-{mtf}-{ltf}'.format(
                symbol=symbol,
                htf=tfs[0],
                mtf=tfs[1],
                ltf=tfs[2])
        }
        self.context = next_context
        return True

    def _set_analyzer(self, analysis_type):
        self.log.handle(0, f'Setting Analyzer per Pipeline Version: "{analysis_type}"', '@_set_analyzer')
        if self.analysis_controller:
            return
        if analysis_type == 'forex_trader_v2':
            from controllers.analysis_v2.analyze import AnalysisControllerV2
            self.analysis_controller = AnalysisControllerV2.build(self.env, self.backtest_env)
            return
        raise Exception('Unable to get analyzer')

    def _verify_runtime(self):
        context = self.context
        ltf_name = context.get('tfs')[-1]
        htf_name = context.get('tfs')[0]
        time = dt.now()
        if self.env.get('backtest_active'):
            time = parser.parse(self.backtest_env.get('run_info').get('latest_date'))
        if self.env.get('test_data').get('active'):
            return True
        run_min = parser.parse(context.get('latest_prices').get(htf_name).iloc[-1].time).minute
        verified = True
        if 'min' in ltf_name:
            ltf_min = constants.tf_num_map.get(ltf_name)
            if run_min % ltf_min != 0:
                verified = False
        elif ltf_name == '1hr':
            run_min = time.minute
            if run_min != 0:
                verified = False
        elif ltf_name == '4hr':
            run_hr = time.hour
            if run_hr % 4 != 0:
                verified = False
        elif ltf_name == '1day':
            run_hr = time.hour
            run_min = time.minute
            if not (run_hr == 0 and run_min == 0):
                verified = False
        self.log.handle(0, f'Runtime Verified: {verified}', '@_verify_runtime')
        return verified

    def _get_market_key_by_tfs(self, context):
        success, latest_prices = self.indicator_service.calc_indicators(context)
        if not success:
            return False
        context['latest_prices'] = latest_prices
        context['position']['last_price'] = latest_prices.get(self.env.get('tfs')[-1]).close.iloc[-1]
        last_key = self.indicator_service.get_latest_trade_key(context.get('latest_prices'))
        if not context.get('keys').get('entry_key'):
            context['keys']['entry_key'] = last_key
        context['keys']['chained'].append(last_key)
        self.log.handle(0, f'Last Key: {last_key}', '@_get_market_key_by_tfs')
        return bool(last_key)

    def setup_backtest_env(self, _context, _env, _backtest_env):
        self.context = _context
        if _context:
            self.context['tfs'] = _env.get('tfs')
            self.context['keys'] = _context.get('keys')
            self.context['position'] = _context.get('position')
        self.env['tfs'] = _env.get('tfs')
        self.env['indicators'] = _env.get('indicators')
        self.env['trading'] = _env.get('trading')
        self.backtest_env = _backtest_env
        if not self.trade_controller.backtest_env.get('job_data'):
            self.trade_controller.backtest_env['job_data'] = _backtest_env.get('job_data')

    def cleanup_backtest_env(self):
        self.indicator_service.cleanup_backtest_files()


if __name__ == '__main__':
    from services.aws.ssm import SSMService
    from services.aws.s3 import S3Service
    env = SSMService.build().get_param('/cointosis/forex_trader_v2')
    _backtest_env = S3Service.build(env, None).read_from_s3(
        'forex_trader_v2/backtest_env_fxv2.json',
        'cointosis-backtest')
    backtest_env = json.loads(_backtest_env)
    CointosisFxv2.build(env, backtest_env).run(symbol='GBP_USD')
