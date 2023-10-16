from services.log import LogService
from services.utilis import UtilityService


class AnalyzeIncrease:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.log = kwargs.get('log_service')
        self.utils = kwargs.get('utils')
        self.inc_triggers = [t for t, active in self.env.get(
            'trading').get('triggers').get('increase').items() if active]

    @staticmethod
    def build(env, backtest_env):
        return AnalyzeIncrease(
            env=env,
            backtest_env=backtest_env,
            log_service=LogService.build(name_prefix='AnalysisControllerV2'),
            utils=UtilityService.build())

    def should_position_increase(self, context):
        position = context.get('position')
        behaviors, polarity, _, _, indicator_data = self.utils.setup_position_analysis(context)
        result = False
        max_size = self.env.get('trading').get('size')
        if position.get('total_size') == max_size:
            self.log.handle(0, f'Position @ MAX SIZE: {max_size}', '@should_position_increase')
            result = False
        elif self._should_increase_on_trend_continuation(self.inc_triggers, position, polarity,
                                                         indicator_data, behaviors):
            behaviors.append('increase_on_trend_continuation')
            result = True
        elif self._should_increase_on_force_increase(self.inc_triggers, polarity, indicator_data,
                                                     self.env, behaviors):
            behaviors.append('increase_on_force_increase')
            result = True
        elif self._should_increase_on_force_surge(self.inc_triggers, context.get('symbol'),
                                                  indicator_data, self.env, behaviors):
            behaviors.append('increase_on_force_surge')
            result = True
        if result:
            context['jobs'].append({'type': 'position', 'action': 'increase'})
            context['position']['behaviors'] = behaviors
        self.log.handle(0, f'POSITION | {result}', '@should_position_increase')
        return result

    def should_trade_increase(self, context):
        return False

    @staticmethod
    def _should_increase_on_trend_continuation(t, data, polarity, indicator_data, behaviors):
        """Checks if force value is approaching Zero.
        """
        if 'increase_on_trend_continuation' not in t:
            return False
        trend_was_weak = 'decrease_on_price_ema_crossover' in behaviors
        if not trend_was_weak:
            return False
        last_close = indicator_data.iloc[-1].close
        if polarity > 0:
            if last_close > data.get('trade_high'):
                return True
        elif polarity < 0:
            if last_close < data.get('trade_low'):
                return True
        return False

    @staticmethod
    def _should_increase_on_force_increase(t, polarity, indicator_data, env, behaviors):
        """Checks if force value is moving away from Zero.
        """
        if 'increase_on_force_increase' not in t:
            return False
        force_was_weak = 'decrease_on_force_decrease' == behaviors[-1]
        if not force_was_weak:
            return False
        latest_forces = list(indicator_data.iloc[-2:].force)
        last = float('-inf') if polarity > 0 else float('inf')
        increase_count = 0
        entry_force = env.get('indicators').get(
            'force').get('mtf_entry')
        if abs(latest_forces[-1]) > entry_force:
            return True
        for f in latest_forces:
            if polarity > 0:
                if f >= last:
                    last = f
                    increase_count += 1
                else:
                    increase_count = 0
            elif polarity < 0:
                if f <= last:
                    last = f
                    increase_count += 1
                else:
                    increase_count = 0
        return True if increase_count >= 2 else False

    @staticmethod
    def _should_increase_on_force_surge(t, symbol, indicator_data, env, behaviors):
        if 'increase_on_force_surge' not in t:
            return False
        if 'increase_on_force_surge' == behaviors[-1]:
            return False
        latest_force = abs(indicator_data.iloc[-1].force)
        jpy_surge_threshold = env.get('indicators').get(
            'force').get('mtf_jpy_surge')
        non_jpy_surge_threshold = env.get('indicators').get(
            'force').get('mtf_surge')
        if 'JPY' in symbol and latest_force > jpy_surge_threshold:
            return True
        elif latest_force > non_jpy_surge_threshold:
            return True
        return False
