import constants
from services.log import LogService


class AnalyzeOpen:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.log = kwargs.get('log_service')
        self.open_triggers = [t for t, active in self.env.get(
            'trading').get('triggers').get('open').items() if active]

    @staticmethod
    def build(env, backtest_env):
        return AnalyzeOpen(
            env=env,
            backtest_env=backtest_env,
            log_service=LogService.build(name_prefix='AnalyzeOpen'))

    def should_open(self, context):
        if context.get('position').get('trades'):
            return False
        curr_triggers = []
        if self._should_open_on_keys(self.open_triggers, context, self.log):
            curr_triggers.append('open_on_keys')
            context['position']['behaviors'].append('open_on_keys')
        if self._should_open_on_force(self.open_triggers, context, self.env, self.log):
            curr_triggers.append('open_on_force')
            context['position']['behaviors'].append('open_on_force')
        if not self._should_verify_open_force_and_key(curr_triggers, context):
            return False
        result = self.open_triggers == curr_triggers
        if result:
            context['jobs'].append({'type': 'position', 'action': 'open'})
            context['action'] = 'open'
        self.log.handle(0, 'TRUE' if result else 'FALSE', '@should_open')
        return result

    @staticmethod
    def _should_open_on_keys(t, context, log):
        if 'open_on_keys' not in t:
            return False
        last_key = context.get('keys').get('chained')[-1]
        [_, mtf_key, _] = last_key.split('_')
        for _, key_list in constants.mtf_trade_keys.items():
            if mtf_key in key_list:
                result = True
                break
            else:
                result = False
        log.handle(0, f'{result} | {last_key}', '@should_open_on_key')
        return result

    @staticmethod
    def _should_open_on_force(t, context, env, log):
        if 'open_on_force' not in t:
            return False
        mtf_tf = context.get('tfs')[1]
        force = context.get(
            'latest_prices').get(mtf_tf).iloc[-1].force
        if abs(force) >= env.get('indicators').get('force').get('mtf_entry', 10):
            result = True
        else:
            result = False
        log.handle(
            0, f'{"TRUE" if result else "FALSE"} | MTF Force = {force}', '@should_open_on_force')
        return result

    @staticmethod
    def _should_verify_open_force_and_key(t, context):
        if 'open_on_keys' in t and 'open_on_force' in t:
            [_, mtf_key, _] = context.get('keys').get('chained')[-1].split('_')
            last_force = context.get('latest_prices').get(
                context.get('tfs')[1]).iloc[-1].force
            if last_force > 0:
                if mtf_key in constants.mtf_trade_keys.get('BUY'):
                    return True
            if last_force < 0:
                if mtf_key in constants.mtf_trade_keys.get('SELL'):
                    return True
        return False

    @staticmethod
    def _add_behavior(context, behavior):
        behaviors = context['position']['behaviors']
        if 'open' in behavior:
            if behavior not in behaviors:
                context['position']['behaviors'].append(behavior)
            return
        context['position']['behaviors'].append(behavior)
