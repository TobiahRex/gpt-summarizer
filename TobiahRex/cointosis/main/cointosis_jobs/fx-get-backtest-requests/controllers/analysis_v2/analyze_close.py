import constants
from services.log import LogService
from services.utilis import UtilityService


class AnalyzeClose:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.log = kwargs.get('log_service')
        self.utils = kwargs.get('utils')
        self.close_triggers = [t for t, active in self.env.get(
            'trading').get('triggers').get('close').items() if active]

    @staticmethod
    def build(env, backtest_env):
        return AnalyzeClose(
            env=env,
            backtest_env=backtest_env,
            log_service=LogService.build(name_prefix='AnalyzeClose'),
            utils=UtilityService.build())

    def should_position_close(self, context):
        behaviors, polarity, latest_force, keys, _ = self.utils.setup_position_analysis(context)
        result = False
        if self.backtest_env.get('run_info').get('last_bar'):
            behaviors.append('close_on_end_of_backtest')
            result = True
        elif self._should_close_on_polarity_change(self.close_triggers, keys):
            behaviors.append('close_on_polarity_change')
            result = True
        elif self._should_close_on_ltf_force(self.close_triggers, polarity, latest_force, self.env):
            behaviors.append('close_on_ltf_force')
            result = True
        elif self._should_close_on_htf_key(self.close_triggers, polarity, keys, behaviors):
            behaviors.append('close_on_htf_key')
            result = True
        elif self._should_close_on_many_force_decrease(self.close_triggers, behaviors):
            behaviors.append('close_on_many_force_decrease')
            result = True
        elif self._should_close_on_pip_loss(self.close_triggers, context.get('position'), self.env):
            behaviors.append('close_on_pip_loss')
            result = True
        if result:
            context['jobs'].append({'type': 'position', 'action': 'close'})
            context['position']['behaviors'] = behaviors
        self.log.handle(0, result, '@should_close')
        return result

    def should_trades_close(self, context):
        jobs = context.get('jobs')
        for trade_id, trade in context.get('position', {}).get('trades', {}).items():
            behaviors = trade.get('behaviors')
            result = False
            if trade.get('state') == 'CLOSED':
                continue
            if self._profit_protection_active(self.env, trade) and \
                    self._should_close_on_profit_protect(self.close_triggers, trade, self.env, behaviors):
                behaviors.append('close_on_profit_protect')
                result = True
            elif self._should_close_on_pip_loss(self.close_triggers, trade, self.env):
                behaviors.append('close_on_pip_loss')
                result = True
            if result:
                jobs.append({'type': 'trade', 'action': 'close', 'meta': {'trade_id': trade_id}})
            self.log.handle(0, f'TRADE #{trade_id} | {result}', '@should_close')
        if jobs:
            jobs = self._check_for_position_close(context, jobs)
            context['jobs'] = jobs
        return bool(jobs)

    @staticmethod
    def _should_close_on_polarity_change(t, keys):
        if 'close_on_polarity_change' not in t:
            return False
        curr_key = keys.get('chained')[-1]
        last_key = keys.get('last_key')
        [_, l_mtf_key, _] = last_key.split('_')
        [_, mtf_key, _] = curr_key.split('_')
        if l_mtf_key and mtf_key:
            if l_mtf_key[0] != mtf_key[0]:
                return True
        return False

    @staticmethod
    def _should_close_on_ltf_force(t, size, ltf_force, env):
        if 'close_on_ltf_force' not in t:
            return False
        polarity = 1 if size > 0 else -1
        ltf_exit_force = env.get('indicators').get(
            'force').get('ltf_exit')
        if any([
            polarity > 0 and ltf_force < (ltf_exit_force * -1),
            polarity < 0 and ltf_force > ltf_exit_force,
        ]):
            return True
        return False

    @staticmethod
    def _should_close_on_htf_key(t, size, keys, behaviors):
        if 'close_on_htf_key' not in t:
            return False
        if 'profit_protect_activated' in behaviors:
            return False
        curr_key = keys.get('chained')[-1]
        htf_key = curr_key.split('_')[0]
        trade_type = 'BUY' if size > 0 else 'SELL'
        for key_direction, key_list in constants.htf_close_keys.items():
            if key_direction == trade_type:
                if htf_key in key_list:
                    return True
        return False

    @staticmethod
    def _should_close_on_profit_protect(t, data, env, behaviors):
        if 'close_on_profit_protect' not in t:
            return False
        if 'decrease_on_profit_protect' not in behaviors:
            return False
        max_pl = data.get('max_profit')
        giveback_percent = (1 - data.get('P/L pips') /
                            data.get('max_profit'))
        hi_lo_tiers = sorted(
            env.get('trading').get('profit_protect').get('tiers'),
            key=lambda t: t.get('pip_activation'),
            reverse=True)
        upper_bound = float('inf')
        for tier in hi_lo_tiers:
            if upper_bound > max_pl and max_pl > tier.get('pip_activation'):
                upper_bound = tier.get('pip_action')
                break
            upper_bound = tier.get('pip_activation')
        if giveback_percent >= tier.get('close_percent'):
            return True
        return False

    @staticmethod
    def _should_close_on_pip_loss(t, data, env):
        if 'close_on_pip_loss' not in t:
            return False
        if all([
            data.get('P/L pips'),
            data.get('P/L pips') < (env.get('trading').get('max_pip_loss') * -1)
        ]):
            return True
        return False

    @staticmethod
    def _should_close_on_many_force_decrease(t, behaviors):
        if 'close_on_many_force_decrease' not in t:
            return False
        last_4_behaviors = behaviors[-4:]
        for b in last_4_behaviors:
            if b != 'decrease_on_force_decrease':
                return False
        return True

    @staticmethod
    def _profit_protection_active(env, data):
        pp = env.get('trading').get('profit_protect')
        return all([
            pp.get('active'),
            data.get('max_profit')
        ])

    @staticmethod
    def _check_for_position_close(context, jobs):
        trades = context.get('position').get('trades')
        open_trades = set([id for id, t in trades.items() if t.get('state', '') != 'CLOSED'])
        has_position_close = False
        last_trade_behavior = ''
        for job in jobs:
            if has_position_close:
                return [job]
            if job.get('type') == 'position' and job.get('action') == 'close':
                has_position_close = True
            elif job.get('type') == 'trade' and job.get('action') == 'close':
                trade_id = job.get('meta', {}).get('trade_id')
                last_trade_behavior = trades.get(trade_id).get('behaviors')[-1]
                open_trades.remove(trade_id)
                context['position']['trades'][trade_id]['state'] = 'CLOSED'
        if not open_trades:
            context['position']['behaviors'].append(last_trade_behavior)
            return [{'type': 'position', 'action': 'close'}]
        return jobs
