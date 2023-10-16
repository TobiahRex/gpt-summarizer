from services.log import LogService
from services.utilis import UtilityService


class AnalyzeDecrease:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.log = kwargs.get('log_service')
        self.utils = kwargs.get('utils')
        self.dec_triggers = [t for t, active in self.env.get(
            'trading').get('triggers').get('decrease').items() if active]

    @staticmethod
    def build(env, backtest_env):
        return AnalyzeDecrease(
            env=env,
            backtest_env=backtest_env,
            log_service=LogService.build(name_prefix='AnalysisControllerV2'),
            utils=UtilityService.build())

    def should_position_decrease(self, context):
        behaviors, polarity, _, _, indicator_data = self.utils.setup_position_analysis(context)
        result = False
        if self._should_decrease_on_price_ema_crossover(self.dec_triggers, polarity, indicator_data):
            behaviors.append('decrease_on_price_ema_crossover')
            result = True
        elif self._should_decrease_on_force_decrease(self.dec_triggers, polarity, indicator_data, self.env):
            behaviors.append('decrease_on_force_decrease')
            result = True
        if result:
            context['jobs'].append({'type': 'position', 'action': 'decrease'})
            context['position']['behaviors'] = behaviors
        self.log.handle(0, result, '@should_decrease')
        return result

    def should_trades_decrease(self, context):
        jobs = []
        for trade_id, trade in context.get('position').get('trades').items():
            if trade.get('state') == 'CLOSED':
                continue
            behaviors = trade.get('behaviors')
            result = False
            if self._profit_protection_active(self.env, trade) and \
                    self._should_decrease_on_profit_protect(self.dec_triggers, self.env, trade, behaviors):
                result = True
            if result:
                jobs.append({'type': 'trade', 'action': 'decrease', 'meta': {'trade_id': trade_id}})
            self.log.handle(0, f'TRADE #{trade_id} | {result}', '@should_decrease')
        if jobs:
            context['jobs'] += jobs
        return bool(jobs)

    @staticmethod
    def _should_decrease_on_profit_protect(t, env, data, behaviors):
        last_decrease = [b for b in behaviors if 'decrease_on_profit_protect' in b]
        last_activation = 0
        if last_decrease:
            last_activation = int(last_decrease[-1].split('::')[1])
        pp_active = 'profit_protect_activated'
        if 'decrease_on_profit_protect' not in t:
            return False
        max_pl = data.get('max_profit')
        giveback_percent = 1 - (data.get('P/L pips') / data.get('max_profit'))
        hi_lo_tiers = sorted(
            env.get('trading').get('profit_protect').get('tiers'),
            key=lambda t: t.get('pip_activation'),
            reverse=True)
        upper_bound = float('inf')
        activated = True if pp_active in behaviors else False
        for tier in hi_lo_tiers:
            if upper_bound > max_pl and max_pl > tier.get('pip_activation'):
                upper_bound = tier.get('pip_activation')
                activated = True
                break
            upper_bound = tier.get('pip_activation')
        if activated:
            if pp_active not in behaviors:
                behaviors.append(pp_active)
            if last_activation:
                if tier.get('pip_activation') > last_activation:
                    if giveback_percent >= tier.get('downsize_percent'):
                        behaviors.append(f'decrease_on_profit_protect::{tier.get("pip_activation")}')
                        return True
                    else:
                        behaviors = behaviors[0:-1]
            elif giveback_percent >= tier.get('downsize_percent'):
                behaviors.append(f'decrease_on_profit_protect::{tier.get("pip_activation")}')
                return True
        return False

    @staticmethod
    def _should_decrease_on_price_ema_crossover(t, polarity, indicator_data):
        if 'decrease_on_price_ema_crossover' not in t:
            return False
        last_close = indicator_data.iloc[-1].close
        last_ema_med = indicator_data.iloc[-1].ema_medium
        if polarity > 0:
            if last_close < last_ema_med:
                return True
        elif polarity < 0:
            if last_close > last_ema_med:
                return True
        return False

    @staticmethod
    def _should_decrease_on_force_decrease(t, polarity, indicator_data, env):
        if 'decrease_on_force_decrease' not in t:
            return False
        latest_forces = list(indicator_data.iloc[-4:].force)
        last = float('inf') if polarity > 0 else float('-inf')
        entry_force = env.get('indicators').get(
            'force').get('mtf_entry')
        if abs(latest_forces[-1]) < entry_force:
            return True
        decrease_count = 0
        for f in latest_forces:
            if polarity > 0:
                if f <= last:
                    decrease_count += 1
                    last = f
                else:
                    decrease_count = 0
            elif polarity < 0:
                if f >= last:
                    last = f
                    decrease_count += 1
                else:
                    decrease_count = 0
        return True if decrease_count >= 3 else False

    @staticmethod
    def _profit_protection_active(env, data):
        pp = env.get('trading').get('profit_protect')
        return all([
            pp.get('active'),
            data.get('max_profit')
        ])
