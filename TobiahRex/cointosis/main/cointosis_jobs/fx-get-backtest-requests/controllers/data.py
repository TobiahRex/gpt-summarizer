import json

from services.aws.s3 import S3Service
from services.log import LogService
from services.utilis import UtilityService


class DataController:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.s3_service = kwargs.get('s3_service')
        self.log_service = kwargs.get('log_service')
        self.utils = kwargs.get('utils')

    @staticmethod
    def build(env, backtest_env):
        return DataController(
            env=env,
            backtest_env=backtest_env,
            s3_service=S3Service.build(env, backtest_env),
            log_service=LogService.build('DataController'),
            utils=UtilityService.build())

    def handle_save_data(self, context):
        position = context.get('position')
        action = context.get('action')
        context['last_action'] = action
        context['action'] = ''
        if not position or not position.get('trades'):
            return context
        if position.get('upgrade_tfs') and context.get('tfs')[0] != '4hr':
            context['tfs'] = position.get('upgrade_tfs')
            context['position']['upgrade_tfs'] = []
        should_close = False
        jobs = context.get('jobs', [])
        if jobs and jobs[0].get('type') == 'position' and jobs[0].get('action') == 'close':
            should_close = True
        elif not self.utils.has_open_trades(context):
            should_close = True
        if action == 'close' and should_close:
            self.s3_service.post_trade_closed({**context})
        elif action == 'open':
            self.s3_service.post_trade_opened({**context})
        elif action == 'wait' and self.env.get('backtest_active'):
            self.s3_service.update_backtest_context({**context}, self.backtest_env.get('job_data'))
        return context

    def get_cached_context(self, symbol):
        """Reads the opened trades file (aka "position") and returns position information to caller.
        Returns:
            dict: position data.
        """
        version = self.env.get('version')
        context = {}
        if not self.env.get('backtest_active'):
            filename = f'{version}/{symbol}/trades_open.txt'
            if self.s3_service.s3_file_exists(filename):
                data = self.s3_service.read_from_s3(filename)
                if data:
                    context = json.loads(data)
            return context
        job_data = self.backtest_env.get('job_data')
        s3_filename = self.s3_service.get_filename('backtest-trades-open', job_data)
        if self.s3_service.s3_file_exists(s3_filename, 'cointosis-backtest'):
            data = self.s3_service.read_from_s3(s3_filename, 'cointosis-backtest')
            if data:
                context = json.loads(data)
            return context
