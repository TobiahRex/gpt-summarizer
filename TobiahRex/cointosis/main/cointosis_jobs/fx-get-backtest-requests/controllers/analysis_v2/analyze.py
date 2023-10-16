import constants
from services.log import LogService
from services.broker import BrokerService
from services.utilis import UtilityService
from controllers.data import DataController
from controllers.analysis_v2.analyze_close import AnalyzeClose
from controllers.analysis_v2.analyze_open import AnalyzeOpen
from controllers.analysis_v2.analyze_increase import AnalyzeIncrease
from controllers.analysis_v2.analyze_decrease import AnalyzeDecrease
from controllers.analysis_v2.analyze_size import AnalyzeSize
from controllers.analysis_v2.analyze_upgrade import AnalyzeUpgrade


class AnalysisControllerV2:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.log = kwargs.get('log_service')
        self.broker_service = kwargs.get('broker_service')
        self.utility_service = kwargs.get('utility_service')
        self.data_controller = kwargs.get('data_controller')
        self.open = kwargs.get('analyze_open')
        self.close = kwargs.get('analyze_close')
        self.increase = kwargs.get('analyze_increase')
        self.decrease = kwargs.get('analyze_decrease')
        self.size = kwargs.get('analyze_size')
        self.upgrade = kwargs.get('analyze_upgrade')

    @staticmethod
    def build(env, backtest_env):
        return AnalysisControllerV2(
            env=env,
            backtest_env=backtest_env,
            log_service=LogService.build(name_prefix='AnalysisControllerV2'),
            broker_service=BrokerService.build(env, backtest_env),
            utility_service=UtilityService.build(),
            data_controller=DataController.build(env, backtest_env),
            analyze_open=AnalyzeOpen.build(env, backtest_env),
            analyze_close=AnalyzeClose.build(env, backtest_env),
            analyze_increase=AnalyzeIncrease.build(env, backtest_env),
            analyze_decrease=AnalyzeDecrease.build(env, backtest_env),
            analyze_size=AnalyzeSize.build(env, backtest_env),
            analyze_upgrade=AnalyzeUpgrade.build(env, backtest_env))

    def analyze(self, context):
        context['jobs'] = []
        should_open = self.open.should_open(context)
        has_position = self._symbol_has_position(context)
        if should_open and not has_position:
            context['action'] = 'open'
        else:
            if has_position:
                if self.close.should_position_close(context):
                    context['action'] = 'close'
                elif self.close.should_trades_close(context):
                    context['action'] = 'close'
                elif self.decrease.should_position_decrease(context):
                    context['action'] = 'decrease'
                elif self.decrease.should_trades_decrease(context):
                    context['action'] = 'decrease'
                elif self.increase.should_position_increase(context):
                    context['action'] = 'increase'
                elif self.increase.should_trade_increase(context):
                    context['action'] = 'increase'
                else:
                    context['action'] = 'wait'
        self._analyze_trade_type(context)
        self.size.analyze_size(context)
        self.upgrade.analyze_tf_upgrade(context)
        self._update_keys(context)
        self._cleanup_analysis(context)
        return context

    def _cleanup_analysis(self, context, error_msg=None):
        if error_msg:
            self.log.handle(-1, error_msg, '@get_analysis')
        else:
            if context.get('jobs'):
                for job in context.get('jobs'):
                    if job.get('type') == 'position':
                        action = job.get('action')
                        behavior = context.get('position').get('behaviors')[-1]
                    elif job.get('type') == 'trade':
                        trade_id = job.get('meta', {}).get('trade_id', '')
                        behavior = context.get('position').get('trades').get(trade_id).get('behaviors')[-1]
                        action = job.get('action')
                    self.log.handle(
                        0, f'ACTION = {action} | {behavior}', '@analyze_ltf_action')
            else:
                self.log.handle(0, 'ACTION = wait', '@analyze_ltf_action')
        if self.env.get('backtest_active') and context.get('jobs'):
            last_job = context.get('jobs')[-1]
            if last_job.get('type') == 'position' and last_job.get('action') == 'close':
                self.broker_service.trader.get('refresh_on_close')()

    def _analyze_trade_type(self, context):
        curr_key = context.get('keys').get('chained')[-1]
        seed_direction = self._get_trade_direction(curr_key)
        direction = self._check_for_overwrites(self.env, context, seed_direction)
        self._set_direction(context, direction)

    @staticmethod
    def _check_for_overwrites(env, context, direction):
        t_data = env.get('test_data')
        if t_data.get('active'):
            ta = t_data.get('test_action')
            td = t_data.get('test_direction')
            tb = t_data.get('test_behaviors')
            direction = td if td else direction
            if ta:
                context['action'] = ta
            if tb:
                context['position']['behaviors'] += tb
        return direction

    def _symbol_has_trades(self, context):
        trades, _ = self.broker_service.trader.get('get_open_trades')(context.get('symbol'))
        return bool(trades)

    def _symbol_has_position(self, context):
        position = self.broker_service.trader.get('get_open_position')(context.get('symbol'))
        return bool(len(position.get('trades', {}).keys()))

    @staticmethod
    def _get_trade_direction(key):
        [_, mtf_key, _] = key.split('_')
        direction = ''
        for key_direction, key_list in constants.mtf_trade_keys.items():
            if mtf_key in key_list:
                direction = key_direction
                break
        return direction

    @staticmethod
    def _set_direction(context, trade_direction):
        if context.get('action') in ['close', 'decrease']:
            polarity = 1 if context.get(
                'position').get('total_size') > 0 else -1
            context['position']['trade_type'] = 'SELL' if polarity > 0 else 'BUY'
            return
        if context.get('action') == 'open':
            if not trade_direction:
                context['action'] = 'wait'
                return
            else:
                context['position']['trade_type'] = trade_direction
        if context.get('action') == 'increase':
            polarity = 1 if context.get(
                'position').get('total_size') > 0 else -1
            context['position']['trade_type'] = 'BUY' if polarity > 0 else 'SELL'

    @staticmethod
    def _update_keys(context):
        if context.get('action') == 'close':
            context['keys']['exit_key'] = context.get('keys').get('last_key')
        else:
            curr_key = context.get('keys').get('chained')[-1]
            context['keys']['last_key'] = curr_key
