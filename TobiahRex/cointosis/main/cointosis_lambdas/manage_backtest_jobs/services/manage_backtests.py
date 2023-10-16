import json
from dateutil.parser import parse as get_date

from services.aws.s3 import S3Service
from services.aws.sqs import SQSService
from services.log_service import LogService


class ManageBacktests:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.s3 = kwargs.get('s3_service')
        self.sqs = kwargs.get('sqs_service')
        self.version = self.env.get('version')
        self.log = LogService.build(name_prefix='ManageBacktests')

    @staticmethod
    def build(env):
        return ManageBacktests(
            env=env,
            s3_service=S3Service.build(env),
            sqs_service=SQSService.build())

    def run(self, context):
        if 'version' in context:
            self.version = context.get('version')
        price_jobs = self._find_price_files_by_option_code(context)
        if price_jobs:
            self.log.handle(0, f'PRICE Jobs: \n{json.dumps(price_jobs)}', '@run')
            return [self.sqs.send_message(
                self.env.get('sqs').get('get_prices_q'), json.dumps(j)) for j in price_jobs]
        indicator_jobs = self._find_indicator_files_by_option_code(context)
        if indicator_jobs:
            self.log.handle(0, f'INDICATOR Jobs: \n{json.dumps(indicator_jobs)}', '@run')
            return [self.sqs.send_message(
                self.env.get('sqs').get('get_indicators_q'), json.dumps(j)) for j in indicator_jobs]
        return self._queue_backtest(context)

    def _get_options_by_sub_code(self, sub_code):
        filename = f'{self.version}/option_tree/{sub_code}.txt'
        option_raw = self.s3.read_from_s3(filename, 'cointosis-backtest')
        return json.loads(option_raw)

    def _find_price_files_by_option_code(self, context):
        option_code = context.get('option_code')
        start_date = get_date(context.get('start_date'))
        end_date = get_date(context.get('end_date'))
        tfs = self._get_options_by_sub_code(option_code.split('_')[0])
        symbol = context.get('symbol')
        if len(symbol) == 7:
            symbol = ''.join(symbol.split('_'))
        jobs_to_queue = []
        for tf_name in tfs.values():
            filename = 'prices/{sy}-{ey}/{sym}_{tf}_{sd}-{ed}.csv'.format(
                v=self.version,
                sy=start_date.year,
                ey=end_date.year,
                sd=start_date.strftime('%Y%m%d'),
                ed=end_date.strftime('%Y%m%d'),
                sym=symbol,
                tf=tf_name)
            if not self.s3.s3_file_exists(filename, 'cointosis-backtest'):
                jobs_to_queue.append({
                    **context,
                    'tf': tf_name,
                })
        return jobs_to_queue

    def _find_indicator_files_by_option_code(self, context):
        option_code = context.get('option_code')
        start_date = get_date(context.get('start_date'))
        end_date = get_date(context.get('end_date'))
        tfs = self._get_options_by_sub_code(option_code.split('_')[0])
        ma_options = self._get_options_by_sub_code(option_code.split('_')[1])
        symbol = context.get('symbol')
        if len(symbol) == 7:
            symbol = ''.join(symbol.split('_'))
        jobs_to_queue = []
        for tf_name in tfs.values():
            for mk, mv in ma_options.items():
                ma_name = f'{mk.split("_")[0]}-{mv}'
                filename = 'indicators/{v}/{sy}-{ey}/{sym}_{tf}_{sd}-{ed}_{mname}.csv'.format(
                    v=self.version,
                    sy=start_date.year,
                    ey=end_date.year,
                    sd=start_date.strftime('%Y%m%d'),
                    ed=end_date.strftime('%Y%m%d'),
                    sym=symbol,
                    tf=tf_name,
                    mname=ma_name,
                    )
                if not self.s3.s3_file_exists(filename, 'cointosis-backtest'):
                    jobs_to_queue.append({
                        **context,
                        'indicator': ma_name.split('-')[0],
                        'value': mv,
                        'tf': tf_name
                    })
        return jobs_to_queue

    def _queue_backtest(self, context):
        data = json.dumps(context)
        self.log.handle(0, f'QUEUE Backtest: \n{data}', '@_queue_backtest')
        return self.sqs.send_message(self.env.get('sqs').get('backtest_req_q'), data)
