from cgitb import small
from services.log import LogService
from services.utilis import UtilityService


class AnalyzeSize:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.log = kwargs.get('log_service')
        self.utils = kwargs.get('utils')

    @staticmethod
    def build(env, backtest_env):
        return AnalyzeSize(
            env=env,
            backtest_env=backtest_env,
            log_service=LogService.build(name_prefix='AnalyzeSize'),
            utils=UtilityService.build())

    def analyze_size(self, context):
        context['position']['next_order_size'] = 0
        if any([
            not context.get('jobs'),
            context.get('action') == 'wait',
        ]):
            return True
        trade_type = context.get('position').get('trade_type')
        polarity = 1 if trade_type == 'BUY' else -1 if trade_type == 'SELL' else 0
        if not polarity:
            return False
        max_size = self.env.get('trading').get('size')
        if 'JPY' in context.get('symbol'):
            max_size = max_size / 100
        max_trades = self.env.get('trading').get('max_symbol_trades')
        smallest_size = max_size / max_trades
        total_size = abs(context.get('position').get('total_size'))
        if context.get('action') == 'open':
            context['position']['next_order_size'] = (smallest_size * 2) * polarity
            return True
        if context.get('action') == 'close':
            self._analyze_close_size(context)
        if context['action'] == 'increase':
            updated_jobs = self._analyze_increase_size(context, max_size, total_size, smallest_size, polarity)
            if not updated_jobs:
                self._pop_last_behavior(context)
            context['jobs'] = updated_jobs
        elif context['action'] == 'decrease':
            updated_jobs = self._analyze_decrease_size(context, max_size, total_size, smallest_size, polarity)
            if not updated_jobs:
                self._pop_last_behavior(context)
            context['jobs'] = updated_jobs
        return True

    def _analyze_close_size(self, context):
        for job in context.get('jobs'):
            if job.get('type') == 'trade' and job.get('action') == 'close':
                trade_id = job.get('meta', {}).get('trade_id', '')
                trade = context.get('position').get('trades').get(trade_id)
                job['meta']['size'] = trade.get('size')

    def _analyze_increase_size(self, context, max_size, curr_size, smallest_size, polarity):
        if curr_size == max_size:
            return []
        jobs_update = []
        for job in context.get('jobs'):
            if job.get('type') == 'position' and job.get('action') == 'increase':
                behaviors = context.get('position').get('behaviors')
                lb = behaviors[-1]
                free_size = max_size - curr_size
                last_2 = ''.join(behaviors[-2:]).replace('::time_of_day', '')
                if last_2 == (lb + lb):
                    continue
                elif free_size <= smallest_size:
                    next_size = free_size
                elif lb == 'increase_on_trend_continuation':
                    next_size = max_size - curr_size
                elif lb == 'increase_on_force_surge':
                    next_size = smallest_size * 2 if free_size > (max_size / 2) else smallest_size
                else:
                    next_size = smallest_size
                jobs_update.append(job)
                context['position']['next_order_size'] = next_size * polarity
            else:
                continue
        return jobs_update

    @staticmethod
    def _analyze_decrease_size(context, max_size, curr_size, smallest_size, polarity):
        jobs_update = []
        for job in context.get('jobs'):
            if job.get('type') == 'position' and job.get('action') == 'decrease':
                posxn_behaviors = context.get('position').get('behaviors')
                lpb = posxn_behaviors[-1]
                if lpb == 'decrease_on_force_decrease':
                    if curr_size == max_size:
                        jobs_update.append(job)
                        context['position']['next_order_size'] = (curr_size / 2) * polarity  # See README 2.1
                    elif curr_size <= smallest_size:  # See README 2.2
                        context['position']['next_order_size'] = 0
                        return jobs_update
                    else:
                        jobs_update.append(job)
                        context['position']['next_order_size'] = smallest_size * polarity  # See README 2.3
                elif lpb == 'decrease_on_price_ema_crossover':
                    if curr_size <= smallest_size:
                        context['position']['next_order_size'] = 0
                        return jobs_update
                    context['position']['next_order_size'] = (curr_size - smallest_size) * polarity  # See README 2.4
                    jobs_update.append(job)
                    return jobs_update
            elif job.get('type') == 'trade' and job.get('action') == 'decrease':
                trade_id = job.get('meta').get('trade_id')
                trade_data = context.get('position').get('trades').get(trade_id)
                trade_behaviors = trade_data.get('behaviors')
                ltb = trade_behaviors[-1]
                trade_size = abs(trade_data.get('size'))
                if trade_size <= smallest_size:
                    if 'decrease_on_profit_protect' in ltb and ((smallest_size / 2) != trade_size):
                        job['meta']['size'] = (trade_size / 2) * polarity
                        jobs_update.append(job)
                    else:
                        continue  # See README 2.5
                else:  # decrease on profit protection
                    dec_size = (trade_size - smallest_size) * polarity  # See README 2.6
                    job['meta']['size'] = dec_size
                    jobs_update.append(job)
        return jobs_update

    @staticmethod
    def _pop_last_behavior(context):
        for job in context['jobs']:
            if job.get('type') == 'position':
                context['position']['behaviors'].pop(-1)
            else:
                trade_id = job.get('meta').get('trade_id')
                context['position']['trades'][trade_id]['behaviors'].pop(-1)
        context['jobs'] = []
        context['action'] = 'wait'
