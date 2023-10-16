import json
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dateutil import parser
import pytz


pacific_tz = pytz.timezone('US/Pacific')


class SlackService:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.client = kwargs.get('client')
        self.channel = kwargs.get('channel')
        self.channel_id = None

    @staticmethod
    def build(env, backtest_env):
        if env.get('backtest_active'):
            token = backtest_env.get('notify').get('slack_token')
            channel = backtest_env.get('notify').get('channel_name')
        else:
            token = env.get('slack').get('token')
            channel = env.get('slack').get('channel_name')
        return SlackService(
            env=env,
            backtest_env=backtest_env,
            client=WebClient(token=token),
            channel=channel)

    def get_channel_id(self):
        if self.channel_id is None:
            if all([
                self.env.get('backtest_active'),
                self.backtest_env.get('notify').get('active')
            ]):
                self.channel = self.backtest_env.get('notify').get('channel_name')
            for res in self.client.conversations_list():
                for channel in res.data.get('channels'):
                    if channel.get('name') == self.channel:
                        self.channel_id = channel.get('id')
                        break
                break
        return None

    def notify(self, msg):
        if self.channel_id is None:
            self.get_channel_id()
        try:
            self.client.chat_postMessage(channel=self.channel_id, text=msg)
        except SlackApiError as e:
            print('Slack Error: ', e)

    def post_trade_progress(self, open_trades):
        if self.channel_id is None:
            self.get_channel_id()
        try:
            self.client.chat_postMessage(
                channel=self.channel_id, text=json.dumps('Trade Progress', indent=4))
        except SlackApiError as e:
            print('Slack Error: ', e)

    def post_trade_opened(self, context, key, action, verbose=True):
        position = context.get('position')
        if self.channel_id is None or self.env.get('backtest_active'):
            self.get_channel_id()
        behaviors = position.get('behaviors')
        trade = position.get('trades').get(position.get('target_trade_id'))
        msg = {
            'Symbol': trade.get('symbol'),
            'Time': trade.get('entry_time'),
            'Size': trade.get('size'),
            'Trade ID': trade.get('id'),
            'Opening Key': key,
            'Margin Req $': trade.get('margin'),
            'Price': trade.get('entry_price'),
            'Account Balance': trade.get('account_balance'),
            'Spread (pips)': trade.get('spread') * (100 if 'JPY' in trade.get('symbol') else 10000),
            'Jobs': ', '.join([f'{j.get("type").upper()}-{j.get("action")}' for j in context.get('jobs')])
        }
        header = action.upper()
        slack_msg = ''
        if verbose:
            slack_msg = f'----- {header} ----\n'
            slack_msg += '\n'.join([f'*{k}*:  `{v}`' for k, v in msg.items()])
        else:
            slack_msg = '`{h} | {s} | {k} | p:{p} | sz:{z} | {t} | {b} | id:{id} | {j}`'.format(
                h=header,
                s=msg.get('Symbol'),
                k=msg.get('Opening Key'),
                p=msg.get('Price'),
                z=msg.get('Size'),
                t=msg.get('Time'),
                b=behaviors[-1],
                id=msg.get('Trade ID'),
                j=msg.get('Jobs'))
        if not all([
            self.env.get('backtest_active'),
            self.backtest_env.get('notify').get('active'),
        ]):
            return slack_msg
        try:
            if not os.environ.get('TASK_ID', ''):
                # App is running inside ECS task
                self.client.chat_postMessage(channel=self.channel_id, text=slack_msg)
            return slack_msg
        except SlackApiError as e:
            print('Slack Error: ', e)

    def post_trade_closed(self, context, key, action):
        position = context.get('position')
        if self.channel_id is None or self.env.get('backtest_active'):
            self.get_channel_id()
        info = {
            'Symbol': context.get('symbol'),
            'Behavior': '',
            'Jobs': ' | '.join([f'{j.get("type").upper()}-{j.get("action")}' for j in context.get('jobs')]),
            'P/L pips': 0,
            'P/L %': 0,
            'P/L $': 0,
            'Size': 0,
            'Closing Key': key,
            'Time': '',
            'Account Balance $': position.get('account_balance'),
        }
        for job in context.get('jobs'):
            if job.get('type') == 'position':
                info['Behavior'] = position.get('behaviors')[-1]
                info['Size'] = position.get('next_order_size')
                info['Time'] = position.get('exit_time')
                info['P/L pips'] = position.get('P/L pips')
                info['P/L %'] = position.get('P/L %')
                info['P/L $'] = position.get('P/L $')
                info['Exit Price'] = position.get('exit_price')
            elif job.get('type') == 'trade':
                trade_id = job.get('meta', {}).get('trade_id')
                trade = position.get('trades').get(trade_id)
                info['Size'] += job.get('meta').get('size')
                if job.get('action') in ['close', 'decrease']:
                    info['Behavior'] += f' {trade.get("behaviors")[-1]}'
                    info['Time'] = trade.get('exit_time')
                    info['P/L pips'] += trade.get('P/L pips')
                    info['P/L %'] += trade.get('P/L %')
                    info['P/L $'] += trade.get('P/L $')
                    info['Exit Price'] = trade.get('exit_price')
                    info['Trade ID'] = trade_id
        try:
            header = action.upper()
            slack_msg = f'----- {header} ----\n'
            slack_msg += '\n'.join([f'*{k}*:  `{v}`' for k, v in info.items()])
            if self.env.get('backtest_active') and not self.backtest_env.get('notify').get('active'):
                return slack_msg
            if not os.environ.get('TASK_ID', ''):
                # App is running inside ECS task
                self.client.chat_postMessage(channel=self.channel_id, text=slack_msg)
            return slack_msg
        except SlackApiError as e:
            print('Slack Error: ', e)

    def post_trade_canceled(self, order_details, key, symbol):
        if self.channel_id is None:
            self.get_channel_id()
        txn = order_details.get('orderRejectTransaction')
        msg = {
            'Instrument': symbol,
            'Reason': order_details.get('errorMessage'),
            'Canceled Key': key,
            'Time': parser.parse(txn.get('time')).astimezone(pacific_tz).strftime('%Y-%m-%d %H:%M:%S') + ' PST',
            'Trade ID': txn.get('id'),
        }
        try:
            slack_msg = '\n\n----- CANCELLED ----\n'
            slack_msg += '\n'.join([f'*{k}*:  `{v}`' for k, v in msg.items()])
            if not os.environ.get('TASK_ID', ''):
                # App is running inside ECS task
                self.client.chat_postMessage(
                    channel=self.channel_id, text=slack_msg)
        except SlackApiError as e:
            print('Slack Error: ', e)

    def post_backtest_report(self, data):
        self.get_channel_id()
        header = 'BACKTEST RESULTS'
        slack_msg = f'----- {header} ----\n'
        report = data.get('report')
        del data['report']
        slack_msg += '\n'.join([f'*{k}*:  `{v}`' for k, v in data.items()])
        slack_msg += f'\n*report*\n{report}'
        self.client.chat_postMessage(channel=self.channel_id, text=slack_msg)


if __name__ == '__main__':
    from aws.ssm import SSMService
    env = SSMService.build().get_param('/cointosis/forex_trader_v2')
    slack = SlackService.build(env).notify('Test message')
