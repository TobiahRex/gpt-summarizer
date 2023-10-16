import sys
from backtesting import Strategy, Backtest
import copy
from dateutil import parser
import json
import os

import constants
from constants.backtest import test_sqs_job
from services.aws.s3 import S3Service
from services.aws.sqs import SQSService
from services.aws.ssm import SSMService
from services.slack import SlackService
from services.log import LogService
from cointosis_fxv2 import CointosisFxv2


def backtest_factory(BacktestController, symbol, job_data, options, last_row):
    _env = BacktestController.env
    _symbol = symbol
    _option_code = job_data.get('option_code')
    _options = options
    _last_row = last_row

    def init(self):
        self.candle_count = 70
        self.env = _env
        self.htf = _options.get('htf')
        self.mtf = _options.get('mtf')
        self.ltf = _options.get('ltf')
        self.last_row = _last_row
        self.tfs = [self.htf, self.mtf, self.ltf]
        self.symbol = _symbol
        self.option_code = _option_code
        self.backtest_controller = BacktestController
        self.ema_fast = _options.get('ema_fast')
        self.ema_medium = _options.get('ema_medium')
        self.sma_slow = _options.get('sma_slow')
        self.force_htf_upgrade = _options.get('htf_upgrade')
        self.force_mtf_entry = _options.get('mtf_entry')
        self.force_ltf_exit = _options.get('ltf_exit')
        self.force_mtf_jpy_surge = _options.get('mtf_jpy_surge')
        self.force_mtf_surge = _options.get('mtf_surge')
        self.trade_max_pip_loss = _options.get('max_pip_loss')
        self.trade_max_total_trades = _options.get('max_total_trades')
        self.trade_max_symbol_trades = _options.get('max_symbol_trades')
        self.pp_pip_activation = _options.get('pip_activation')
        self.pp_decrease_percent = _options.get('decrease_percent')
        self.pp_close_percent = _options.get('close_percent')
        self.trigger_open_on_keys = _options.get('open_on_keys')
        self.trigger_open_on_force = _options.get('open_on_force')
        self.trigger_close_on_polarity_change = _options.get('close_on_polarity_change')
        self.trigger_close_on_ltf_force = _options.get('close_on_ltf_force')
        self.trigger_close_on_htf_key = _options.get('close_on_htf_key')
        self.trigger_close_on_profit_protect = _options.get('close_on_profit_protect')
        self.trigger_close_on_many_force_decrease = _options.get('close_on_many_force_decrease')
        self.trigger_decrease_on_profit_protect = _options.get('decrease_on_profit_protect')
        self.trigger_decrease_on_price_ema_crossover = _options.get('decrease_on_price_ema_crossover')
        self.trigger_decrease_on_force_decrease = _options.get('decrease_on_force_decrease')
        self.trigger_increase_on_trend_continuation = _options.get('increase_on_trend_continuation')
        self.trigger_increase_on_force_increase = _options.get('increase_on_force_increase')
        self.trigger_increase_on_force_surge = _options.get('increase_on_force_surge')
        self.context = {}
        print(f'Backtesting {self.symbol} | {self.htf}_{self.mtf}_{self.ltf}\n{json.dumps(_options, indent=4)}\n\n')

    def next(self):
        index = len(self.data.index)
        if index > self.last_row:
            return
        ltf_num = constants.tf_num_map.get(self.ltf)
        htf_num = constants.tf_num_map.get(self.htf)
        if not self.context:
            if index < 1 or index < (200 * (htf_num / ltf_num)) or not self._verify_mtf_time():
                return
        print('\ni = {i} | {s} | Time = {t} | Price = {p} | Equity: {e}'.format(
                i=index,
                s=self.symbol,
                t=self.data.Time[-1],
                p=self.data.Close[-1],
                e=round(self.position._Position__broker.equity, 2)
            ))
        if self.context.get('position', {}).get('trades'):
            self._update_trades()
        context = self.backtest_controller.run_fxv2(self)
        action = context.get('last_action')
        if not action:
            return
        if action == 'wait':
            if context.get('position').get('trades'):
                self.context = context
                self.htf = self.context.get('tfs')[0]
                self.mtf = self.context.get('tfs')[1]
                self.ltf = self.context.get('tfs')[2]
            else:
                self.context = {}
            return
        last_size = self._get_last_size(context)
        for job in context.get('jobs'):
            if job.get('action') in ['open', 'increase']:
                if last_size > 0:
                    self.buy(size=abs(last_size))
                elif last_size < 0:
                    self.sell(size=abs(last_size))
                self.context = context
            elif job.get('type') == 'position':
                if job.get('action') == 'close':
                    self.position.close()
                    self.context = {}
                    self.htf = self.tfs[0]
                    self.mtf = self.tfs[1]
                    self.ltf = self.tfs[2]
                elif job.get('action') == 'decrease':
                    dec_size = abs(abs(last_size) / self.position.size)
                    self.position.close(portion=dec_size)
                    self.context = context
            elif job.get('type') == 'trade':
                trade_id = job.get('meta', {}).get('trade_id')
                target_trade = [
                    t for t in self.position._Position__broker.trades if t.entry_bar == int(trade_id)]
                if not target_trade:
                    raise Exception(f'Missing trade to close: {trade_id}')
                else:
                    target_trade = target_trade[0]
                    if job.get('action') == 'close':
                        target_trade.close()
                    elif job.get('action') == 'decrease':
                        dec_size = abs(abs(job.get('meta').get('size')) / target_trade.size)
                        target_trade.close(portion=dec_size)
                self.context = context

    def _verify_mtf_time(self):
        curr_time = parser.parse(self.data.Time[-1])
        mtf_num = constants.tf_num_map.get(self.mtf)
        if 'day' in self.ltf and curr_time.hour == 0:
            return True
        elif '4hr' in self.ltf and curr_time.hour % 4 == 0 and curr_time.minute == 0:
            return True
        elif 'hr' in self.ltf and curr_time.minute == 0:
            return True
        elif 'min' in self.ltf and curr_time.minute % mtf_num == 0:
            return True
        return False

    def _update_trades(self):
        context_trades = self.context.get('position', {}).get('trades', {})
        if not context_trades:
            return {}
        account_balance = self.position._Position__broker.equity or 0
        self.context['position']['total_margin'] = 0
        open_trades_list = set()
        for trade in self.position._Position__broker.trades:
            trade_id = str(trade.entry_bar)
            open_trades_list.add(trade_id)
            _trade = self.context.get('position').get('trades').get(trade_id)
            margin = trade.value / 30
            next_trade = {
                **_trade,
                'size': trade.size,
                'P/L $': trade.pl,
                'P/L %': trade.pl_pct,
                'symbol': self.context.get('symbol'),
                'entry_bar': trade.entry_bar,
                'entry_price': trade.entry_price,
                'exit_price': self.data.Close[-1],
                'margin': margin,
                'state': 'OPEN' if trade.size != 0 else 'CLOSED',
                'account_balance': round(account_balance, 2)
            }
            self.context['position']['total_margin'] += margin
            context_trades[_trade.get('id')] = next_trade
        closed_trades = set()
        for trade_id, trade in context_trades.items():
            if trade_id not in open_trades_list:
                closed_trades.add(trade_id)
        if closed_trades:
            for c_trade in self.position._Position__broker.closed_trades:
                trade_id = str(c_trade.entry_bar)
                if trade_id not in closed_trades:
                    continue
                closed_trade = context_trades.get(trade_id)
                if trade_id not in open_trades_list:
                    closed_trade['state'] = 'CLOSED'
                    closed_trade['exit_bar'] = c_trade.exit_time
                    closed_trade['exit_price'] = c_trade.exit_price
                closed_trade['P/L $'] = round(c_trade.pl, 2)
                closed_trade['size'] = c_trade.size
                closed_trade['P/L %'] = round(c_trade.pl_pct * 100, 3)
        self.context['position']['exit_price'] = self.data.Close[-1]
        self.context['position']['P/L $'] = round(self.position.pl, 2)
        self.context['position']['P/L %'] = round(self.position.pl_pct, 3)
        self.context['position']['total_size'] = self.position.size
        self.context['position']['account_balance'] = round(account_balance, 2)
        average_price = (
            sum([t.get('entry_price', 0) for t in context_trades.values() if t.get('state') != 'CLOSED'])
            / len([t for t in context_trades.values() if t.get('state') == 'OPEN']))
        self.context['position']['average_price'] = round(average_price, 5)
        total_open_size = sum([t.get('size') for t in self.context.get(
            'position').get('trades').values() if t.get('state') == 'OPEN'])
        if total_open_size != self.position.size:
            raise Exception('Sizes are out of sync')
        if total_open_size > self.env.get('trading').get('size'):
            raise Exception('Size has exceeded max')

    def _get_last_size(self, context):
        last_size = 0
        for job in context.get('jobs'):
            if job.get('type') == 'position':
                if job.get('action') in ['decrease', 'increase', 'open']:
                    last_size = context.get('position').get('total_size') - self.position.size
                elif job.get('action') == 'close':
                    last_size = context.get('position').get('total_size')
            elif job.get('type') == 'trade':
                if job.get('action') in ['decrease', 'increase', 'size']:
                    last_size += job.get('meta', {}).get('size')
        return last_size

    return type('BacktestService', (Strategy,), {
        'init': init,
        'next': next,
        '_verify_mtf_time': _verify_mtf_time,
        '_update_trades': _update_trades,
        '_get_last_size': _get_last_size,
    })


class BacktestController:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.cointosis_fxv2 = kwargs.get('cointosis_fxv2')
        self.s3_service = kwargs.get('s3_service')
        self.slack_service = kwargs.get('slack_service')
        self.sqs = kwargs.get('sqs_service')
        self.job_q = self.env.get('sqs').get('backtest_job_q')
        self.error_q = self.env.get('sqs').get('backtest_error_q')
        self.debug = BacktestController._verify_args()
        self.log = kwargs.get('log_service')

    @staticmethod
    def build():
        env = SSMService.build().get_param('/cointosis-backtest/fx-get-backtest-requests')
        _backtest_env = S3Service.build(env, None).read_from_s3(
            'forex_trader_v2/backtest_env_fxv2.json',
            'cointosis-backtest')

        backtest_env = json.loads(_backtest_env)
        return BacktestController(
            env=env,
            backtest_env=backtest_env,
            cointosis_fxv2=CointosisFxv2.build(env, backtest_env),
            s3_service=S3Service.build(env, backtest_env),
            slack_service=SlackService.build(env, backtest_env),
            sqs_service=SQSService.build(),
            log_service=LogService.build(name_prefix='BacktestController'))

    def run(self):
        try:
            task_id = os.environ.get('TASK_ID', '')
            print('TASK_ID: ', task_id, '\nall envs:', json.dumps(dict(os.environ), indent=4))
            msgs = self._process_get_backtest_jobs()
            self.log.handle(1, f'FINISHED {len(msgs)} Job(s): {task_id}', '@run')
        except Exception as e:
            print(e)

    def _process_get_backtest_jobs(self):
        processed_msgs = []
        msg = self._get_sqs_msg()
        while msg:
            job_data = json.loads(msg)
            self.log.handle(0, f'Job Data: {json.dumps(job_data)}', '@_process_backtest_jobs')
            if not self._get_backtest(job_data):
                self.sqs.send_message(self.error_q, msg)
            else:
                self.log.handle(f'Finished Backtest Job: {msg}')
            self._reset_backtester()
            processed_msgs.append(msg)
            if self.debug:
                break
            msg = self._get_sqs_msg()
        return processed_msgs

    def _get_sqs_msg(self):
        if self.debug:
            return test_sqs_job.get('Messages')[0].get('Body')
        sqs_data = self.sqs.receive_messages(self.job_q, num_messages=1)
        msgs = sqs_data.get('Messages')
        if not msgs:
            self.log.handle(0, 'No pending messages', '@_get_sqs_msg')
            return None
        msg_body = msgs[0].get('Body', '')
        receipt_id = msgs[0].get('ReceiptHandle', '')
        self.sqs.delete_message(self.job_q, receipt_id)
        return msg_body

    def _get_backtest(self, job_data):
        self.backtest_env['job_data'] = job_data
        option_code = job_data.get('option_code')
        symbol = job_data.get('symbol')
        options = self._get_options_by_code(job_data)
        if option_code:
            ltf_price_df = self._get_backtest_ltf_prices(job_data, options.get('ltf'))
            last_row = ltf_price_df.iloc[-2].row
            self.s3_service.reset_backtest_trade_files(job_data)
            self._send_pretest_msg(job_data, options)
            BacktestService = backtest_factory(self, symbol, job_data, options, last_row)
            tester = Backtest(
                data=ltf_price_df,
                strategy=BacktestService,
                commission=0,
                margin=1/30,
                cash=100000)
            results = tester.run()
            if self.backtest_env.get('notify').get('active'):
                backtest_report = self.s3_service.save_backtest_results(
                    job_data, options, results, tester)
                self.slack_service.post_backtest_report(backtest_report)
            if self.backtest_env.get('options').get('optimize_active'):
                options = self.backtest_env.get('options').get('option')
                stats, heatmap = tester.optimize(**options)
                self.s3_service.save_backtest_optimize_stats(symbol, stats)
                self.s3_service.save_backtest_heatmap(symbol, heatmap)
        return True

    def run_fxv2(self, Backtester):
        _env = self.overwrite_env_with_backtester(Backtester)
        _env['ECS_TASK_ID'] = os.environ.get('TASK_ID', '')
        if self.debug:
            self.backtest_env['run_info']['verify_runtime'] = False
        self.backtest_env['run_info']['last_bar'] = len(Backtester.data.index) == Backtester.last_row
        self.backtest_env['run_info']['symbol'] = Backtester.symbol
        self.backtest_env['run_info']['entry_bar'] = f'{len(Backtester.data.index)}'
        self.backtest_env['run_info']['latest_date'] = Backtester.data.Time[-1]
        self.backtest_env['run_info']['latest_price'] = Backtester.data.Close[-1]
        self.backtest_env['run_info']['account_balance'] = Backtester.position._Position__broker.equity
        self.backtest_env['options']['active_code'] = Backtester.option_code
        self.cointosis_fxv2.setup_backtest_env(
            Backtester.context, _env, self.backtest_env)
        return self.cointosis_fxv2.run(Backtester.symbol)

    def _get_backtest_ltf_prices(self, job_data, ltf_name):
        s3_filename = self.s3_service.get_filename('backtest-prices', job_data, agg_name=ltf_name)
        bucket = self.env.get('s3').get('bucket')
        price_df = None
        if self.s3_service.s3_file_exists(s3_filename, bucket):
            price_df = self.s3_service.read_df_from_s3(s3_filename, bucket)
        if price_df.empty:
            raise Exception('Could not get initial backtest prices')
        price_df = price_df.rename(columns={
            'Unnamed: 0': 'row',
            'time': 'Time',
            'close': 'Close',
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'volume': 'Volume',
        })
        return price_df

    def _get_option_keys(self):
        filename = './option_keys.txt'
        if os.path.exists('./option_keys.txt'):
            f = open(filename)
            data = f.read().split('\n')
            return data
        bucket = self.env.get('s3').get('bucket')
        filename = f'{self.env.get("version")}/option_tree/option_keys.txt'
        s3_data = self.s3_service.read_from_s3(filename, bucket)
        self.s3_service.download(filename, './option_keys.txt', bucket)
        data = [r for r in s3_data.split('\n')]
        return data

    def _get_options_by_code(self, job_data):
        all_options = {}
        for code in job_data.get('option_code').split('_'):
            filename = f'{job_data.get("version")}/option_tree/{code}.txt'
            option_raw = self.s3_service.read_from_s3(filename, bucket=self.env.get('s3').get('bucket'))
            options = json.loads(option_raw)
            all_options = {
                **all_options,
                **options
            }
        return all_options

    def _reset_backtester(self):
        env = SSMService.build().get_param('/cointosis-backtest/fx-get-backtest-requests')
        _backtest_env = S3Service.build(env, None).read_from_s3(
            'forex_trader_v2/backtest_env_fxv2.json',
            'cointosis-backtest')
        backtest_env = json.loads(_backtest_env)
        self.env = env
        self.backtest_env = backtest_env
        self.cointosis_fxv2.cleanup_backtest_env()
        self.cointosis_fxv2.build(env, backtest_env)

    def _send_pretest_msg(self, job_data, options):
        msg_options = {**options}
        trading_env = self.env.get('trading')
        msg_options['option code'] = job_data.get('option_code')
        msg_options['version'] = job_data.get('version')
        msg_options['max pip loss'] = trading_env.get('max_pip_loss')
        msg_options['max trades per symbol'] = trading_env.get('max_symbol_trades')
        msg_options['max size'] = trading_env.get('size')
        option_msg = ''
        for k in sorted(msg_options.keys()):
            v = msg_options[k]
            option_msg += ' '.join([wrd.capitalize() for wrd in k.split('_')]) \
                .replace('Htf', 'HTF') \
                .replace('Ltf', 'LTF') \
                .replace('Mtf', 'MTF')
            option_msg += f': {"True" if v == 1 else "False" if v == 0 else v}\n'
        self.slack_service.notify(
            '*Backtesting* | `{sym}` | `{oc}` | `{htf}_{mtf}_{ltf}`\n```{opxns}```\n\n'.format(
                sym=job_data.get('symbol'),
                oc=job_data.get('option_code'),
                htf=msg_options.get('htf'),
                mtf=msg_options.get('mtf'),
                ltf=msg_options.get('ltf'),
                opxns=option_msg))

    @staticmethod
    def overwrite_env_with_backtester(Backtester):
        env = {**copy.deepcopy(Backtester.env)}
        env['tfs'] = [Backtester.htf, Backtester.mtf, Backtester.ltf]
        env['indicators']['price_ma']['ema_fast'] = Backtester.ema_fast
        env['indicators']['price_ma']['ema_medium'] = Backtester.ema_medium
        env['indicators']['price_ma']['sma_slow'] = Backtester.sma_slow
        env['indicators']['force']['htf_upgrade'] = Backtester.force_htf_upgrade
        env['indicators']['force']['mtf_entry'] = Backtester.force_mtf_entry
        env['indicators']['force']['ltf_exit'] = Backtester.force_ltf_exit
        env['indicators']['force']['mtf_jpy_surge'] = Backtester.force_mtf_jpy_surge
        env['indicators']['force']['mtf_surge'] = Backtester.force_mtf_surge
        env['trading']['max_pip_loss'] = Backtester.trade_max_pip_loss
        env['trading']['max_total_trades'] = Backtester.trade_max_total_trades
        env['trading']['max_symbol_trades'] = Backtester.trade_max_symbol_trades
        env['trading']['profit_protect']['pip_activation'] = Backtester.pp_pip_activation
        env['trading']['profit_protect']['downsize_percent'] = Backtester.pp_decrease_percent
        env['trading']['profit_protect']['close_percent'] = Backtester.pp_close_percent
        env['trading']['triggers']['open']['open_on_keys'] = Backtester.trigger_open_on_keys
        env['trading']['triggers']['close']['open_on_force'] = Backtester.trigger_open_on_force
        env['trading']['triggers']['close']['close_on_polarity_change'] = Backtester.trigger_close_on_polarity_change
        env['trading']['triggers']['close']['close_on_ltf_force'] = Backtester.trigger_close_on_ltf_force
        env['trading']['triggers']['close']['close_on_htf_key'] = Backtester.trigger_close_on_htf_key
        env['trading']['triggers']['close']['close_on_profit_protect'] = Backtester.trigger_close_on_profit_protect
        env['trading']['triggers']['close']['close_on_many_force_decrease'] = Backtester.trigger_close_on_many_force_decrease  # noqa: E501
        env['trading']['triggers']['decrease']['decrease_on_profit_protect'] = Backtester.trigger_decrease_on_profit_protect  # noqa: E501
        env['trading']['triggers']['decrease']['decrease_on_price_ema_crossover'] = Backtester.trigger_decrease_on_price_ema_crossover  # noqa: E501
        env['trading']['triggers']['decrease']['decrease_on_force_decrease'] = Backtester.trigger_decrease_on_force_decrease  # noqa: E501
        env['trading']['triggers']['increase']['increase_on_trend_continuation'] = Backtester.trigger_increase_on_trend_continuation  # noqa: E501
        env['trading']['triggers']['increase']['increase_on_force_increase'] = Backtester.trigger_increase_on_force_increase  # noqa: E501
        env['trading']['triggers']['increase']['increase_on_force_surge'] = Backtester.trigger_increase_on_force_surge  # noqa: E501
        return env

    @staticmethod
    def _verify_args():
        debug_mode = False
        for arg in sys.argv:
            if '--debug' in arg:
                debug_mode = bool(int(sys.argv[sys.argv.index(arg) + 1]))
        return debug_mode


if __name__ == '__main__':
    BacktestController.build().run()
