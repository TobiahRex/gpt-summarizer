import os
import sys
import io
import json
from dateutil import parser
import pandas as pd

from services.aws.sqs import SQSService
from services.aws.s3 import S3Service
from services.aws.ssm import SSMService
from services.slack import SlackService
from services.broker import BrokerService
from services.log_service import LogService
from constants.tests import test_sqs_job

class GetFxPrices:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.sqs = kwargs.get('sqs_service')
        self.s3 = kwargs.get('s3_service')
        self.broker_service = kwargs.get('broker_service')
        self.slack_service = kwargs.get('slack_service')
        self.debug = GetFxPrices._verify_args()
        self.error_q = self.env.get('sqs').get('backtest_error_q')
        self.price_q = self.env.get('sqs').get('backtest_price_q')
        self.indicator_q = self.env.get('sqs').get('backtest_indicator_q')
        self.log = kwargs.get('log_service')

    @staticmethod
    def build():
        env = SSMService.build().get_param('/cointosis-backtest/fx-get-backtest-prices')
        return GetFxPrices(
            env=env,
            sqs_service=SQSService.build(),
            s3_service=S3Service.build(env),
            slack_service=SlackService.build(env),
            log_service=LogService.build(name_prefix='GetFxPrices'),
            broker_service=BrokerService.build({
                **env,
                'backtest_active': 0, 'run_type': 'paper'
            }))

    def run(self):
        task_id = os.environ.get('TASK_ID', '<empty>')
        print('TASK_ID: ', task_id, '\nall envs:',
              json.dumps(dict(os.environ), indent=4))
        try:
            msgs = self._process_get_backtest_prices()
            self.log.handle(1, f'FINISHED {len(msgs)} Jobs: {task_id}', '@run')
        except Exception as e:
            print(e)

    def _process_get_backtest_prices(self):
        processed_msgs = []
        msg = self._get_sqs_msg()
        while msg:
            self.broker_service = BrokerService.build({
                **self.env,
                'backtest_active': 0, 'run_type': 'paper'
            })
            job_data = json.loads(msg)
            self.log.handle(0, f'Job Data: {json.dumps(job_data)}', '@_process_get_backtest_prices')
            if not self._get_prices(job_data):
                self.sqs.send_message(self.error_q, msg)
            elif not self.sqs.send_message(self.indicator_q, msg):
                self.log.handle(
                    -1, f'ERROR: Could not queue indicator job: \n{msg}', '@_process_get_backtest_prices')
            else:
                self.slack_service.notify(f'Sent JOB to *Indicator* Gen.: ```{msg}```')
            processed_msgs.append(msg)
            if self.debug:
                break
            msg = self._get_sqs_msg()
        return processed_msgs

    def _get_sqs_msg(self):
        if self.debug:
            return test_sqs_job.get('Messages')[0].get('Body')
        sqs_data = self.sqs.receive_messages(self.price_q, num_messages=1)
        msgs = sqs_data.get('Messages')
        if not msgs:
            self.log.handle(0, 'No pending messages', '@_get_sqs_msg')
            return None
        msg_body = msgs[0].get('Body', '')
        receipt_id = msgs[0].get('ReceiptHandle', '')
        self.sqs.delete_message(self.price_q, receipt_id)
        return msg_body

    def _get_prices(self, job_data):
        tfs = self._get_tfs_by_option_code(job_data)
        for i, tf in enumerate(tfs.values()):
            price_df = self._get_backtest_price_data(job_data, tf)
            if not price_df.empty:
                self._upload_backtest_prices(job_data, tf, price_df)
                msg = f'Finished generating {i + 1} of 3 *price* jobs: TF = {tf}\n ```{job_data}```'
                self.slack_service.notify(msg)
            elif price_df is None:
                self.log.handle(-1, f'ERROR: Could not generate prices for TF = {tf}', '@_get_prices')
        return True

    def _get_backtest_price_data(self, job_data, tf):
        self.log.handle(0, f'Fetching price data', '@_get_backtest_price_data')
        price_df = pd.DataFrame()
        s3_filename = self.s3.get_filename('backtest-prices', job_data, agg_name=tf)
        if self.s3.s3_file_exists(s3_filename):
            self.log.handle(0, 'Prices already exist; skipping', '@_get_backtest_prices')
            return price_df
        price_df = self.broker_service.prices.get('get_backtest_prices')(
            symbol=job_data.get('symbol'),
            tf=tf,
            root_size=100,
            retries=1,
            backtest_data={
                'from': job_data.get('start_date'),
                'to': job_data.get('end_date')
                })
        self.log.handle(1, f'Successfully fetched price data.', '@_get_backtest_price_data')
        return price_df

    def _prices_exist(self, start_date, end_date, symbol, tf):
        filename = f'prices/{start_date}-{end_date}/{symbol}_{tf}.csv'
        return self.s3.s3_file_exists(filename)

    def _upload_backtest_prices(self, job_data, tf, price_df):
        self.log.handle(0, f'Uploading price data', '@_upload_backtest_prices')
        start = parser.parse(job_data.get('start_date'))
        end = parser.parse(job_data.get('end_date'))
        symbol = job_data.get('symbol')
        if len(symbol) == 7:
            symbol = ''.join(symbol.split('_'))
        filename = 'prices/{sy}-{ey}/{sym}_{tf}_{sd}-{ed}.csv'.format(
            sy=start.year,
            ey=end.year,
            sym=symbol,
            tf=tf,
            sd=start.strftime('%Y%m%d'),
            ed=end.strftime('%Y%m%d'))
        buffer = io.StringIO()
        price_df.reset_index(inplace=True)
        price_df = price_df.rename(columns={'index': 'row'})
        price_df.to_csv(buffer, index=False)
        success = self.s3.write_to_s3(filename, buffer.getvalue())
        if not success:
            self.log.handle(-1, f'ERROR | Could not upload price data to {filename}', '@_upload_backtest_prices')
        else:
            self.log.handle(1, f'SUCCESS | Uploaded price data to {filename}', '@_upload_backtest_prices')

    def _get_tfs_by_option_code(self, job_data):
        self.log.handle(0, f'Getting TFs by option_code', '@_get_tfs_by_option_code')
        tf_code = job_data.get('option_code').split('_')[0]
        filename = f'{job_data.get("version")}/option_tree/{tf_code}.txt'
        option_raw = self.s3.read_from_s3(filename)
        tfs = json.loads(option_raw)
        payload = [-1, 'Could not get TFs by option_code'] if not tfs else [
            1, 'Fetched TFs by option_code']
        return tfs

    @staticmethod
    def _verify_args():
        debug_mode = False
        for arg in sys.argv:
            if '--debug' in arg:
                debug_mode = bool(int(sys.argv[sys.argv.index(arg) + 1]))
        print(f'DEBUG_MODE={debug_mode}', '@_verify_args')
        return debug_mode


if __name__ == '__main__':
    GetFxPrices.build().run()
