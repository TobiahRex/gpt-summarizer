import sys
import os
import json
import io
import pandas as pd
from dateutil import parser

from services.log_service import LogService
from services.aws.s3 import S3Service
from services.aws.sqs import SQSService
from services.aws.ssm import SSMService
from services.slack import SlackService
from services.indicator_service import IndicatorsService
import constants


class GetFxIndicators:
    ERROR_MISSING_PRICE_FILE = 'Missing required price file to calculate indicators.'

    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.s3 = kwargs.get('s3_service')
        self.sqs = kwargs.get('sqs_service')
        self.log = kwargs.get('log_service')
        self.indicator_q = self.env.get('sqs').get('backtest_indicator_q')
        self.backtest_q = self.env.get('sqs').get('backtest_job_q')
        self.error_q = self.env.get('sqs').get('backtest_error_q')
        self.debug = GetFxIndicators._verify_args()
        self.indicator_service = kwargs.get('indicator_service')
        self.slack_service = kwargs.get('slack_service')

    @staticmethod
    def build():
        env = SSMService.build().get_param('/cointosis-backtest/fx-get-backtest-indicators')
        return GetFxIndicators(
            env=env,
            s3_service=S3Service.build(env),
            sqs_service=SQSService.build(),
            slack_service=SlackService.build(env),
            log_service=LogService.build(name_prefix='GetFxIndicators'),
            indicator_service=IndicatorsService.build(env),
        )

    def run(self):
        task_id = os.environ.get('TASK_ID', '<empty>')
        print('TASK_ID: ', task_id, '\nall envs:',
              json.dumps(dict(os.environ), indent=4))
        try:
            msgs = self._process_get_indicators()
            self.log.handle(1, f'FINISHED {len(msgs)} Job(s): {task_id}', '@run')
        except Exception as e:
            print(e)

    def _process_get_indicators(self):
        processed_msgs = []
        msg = self._get_sqs_msg()
        while msg:
            job_data = json.loads(msg)
            self.log.handle(0, f'Job Data: {msg}', '@_process_get_indicators')
            if not self._get_indicators(job_data):
                self.sqs.send_message(self.error_q, msg)
            elif not self.sqs.send_message(self.backtest_q, msg):
                self.log.handle(0, f'ERROR: Could not queue backtest job: \n{msg}', '@_process_get_indicators')
            else:
                self.slack_service.notify(f'Sent JOB to *Backtester*: ```{msg}```')
            processed_msgs.append(msg)
            if self.debug:
                break
            msg = self._get_sqs_msg()
        return processed_msgs

    def _get_sqs_msg(self):
        if self.debug:
            return constants.test_sqs_job.get('Messages')[0].get('Body')
        sqs_data = self.sqs.receive_messages(self.indicator_q, num_messages=1)
        msgs = sqs_data.get('Messages')
        if not msgs:
            self.log.handle(0, 'No pending messages', '@_get_sqs_msg')
            return None
        msg_body = msgs[0].get('Body', '')
        receipt_id = msgs[0].get('ReceiptHandle', '')
        self.sqs.delete_message(self.indicator_q, receipt_id)
        return msg_body

    def _get_indicators(self, job_data):
        tfs = self._get_tfs_by_option_code(job_data)
        errors = []
        for i, tf in enumerate(tfs.values()):
            price_indicator_df = self._get_backtest_indicators(job_data, tf)
            if not price_indicator_df.empty:
                err_msgs = self._upload_backtest_indicators(job_data, tf, price_indicator_df)
                if err_msgs:
                    errors.append('\n'.join(err_msgs))
                else:
                    msg = f'Finished generating {i + 1} of 3 *indicator* jobs: TF = {tf}\n```{job_data}```'
                    self.slack_service.notify(msg)
            else:
                self.log.handle(-1, f'ERROR: Could generate indicators for TF={tf}', '@_get_indicators')
        if errors:
            [self.log.handle(-1, f'ERROR: {err}', '@_get_indicators') for err in errors]
            return False
        return True

    def _get_tfs_by_option_code(self, job_data):
        tf_code = job_data.get('option_code').split('_')[0]
        filename = f'{job_data.get("version")}/option_tree/{tf_code}.txt'
        option_raw = self.s3.read_from_s3(filename, bucket=self.env.get('s3').get('bucket'))
        tfs = json.loads(option_raw)
        return tfs

    def _get_backtest_indicators(self, job_data, tf):
        price_df = self._get_backtest_price_data(job_data, tf)
        return self.indicator_service.calculate_indicators(price_df, job_data, tf)

    def _upload_backtest_indicators(self, job_data, tf, price_indicator_df):
        filename_prefix = self.s3.get_filename('backtest-indicators', job_data, agg_name=tf)
        save_data = {}
        for col in price_indicator_df.columns:
            if 'macd' in col:
                self._add_col_to_data(save_data, 'macd')
                self._save_indicator_filename(save_data, 'macd', col)
                save_data['macd']['df'][col] = price_indicator_df[col]
                save_data['macd']['df']['time'] = price_indicator_df['time']
            if 'stoch' in col:
                self._add_col_to_data(save_data, 'stoch')
                self._save_indicator_filename(save_data, 'stoch', col)
                save_data['stoch']['df'][col] = price_indicator_df[col]
                save_data['stoch']['df']['time'] = price_indicator_df['time']
            if 'force' in col:
                self._add_col_to_data(save_data, 'force')
                save_data['force']['filename'] = 'force_{}' \
                    .format(self.env.get('indicators').get('force').get('source'))
                save_data['force']['df'][col] = price_indicator_df[col]
                save_data['force']['df']['time'] = price_indicator_df['time']
            if 'state_keys' in col:
                self._add_col_to_data(save_data, 'state_keys')
                save_data['state_keys']['filename'] = 'state_keys'
                save_data['state_keys']['df'][col] = price_indicator_df[col]
                save_data['state_keys']['df']['time'] = price_indicator_df['time']
            if 'ema' in col or 'sma' in col:
                self._add_col_to_data(save_data, col)
                save_data[col]['filename'] = col
                save_data[col]['df'][col] = price_indicator_df[col]
                save_data[col]['df']['time'] = price_indicator_df['time']
        errors = []
        for indi, data in save_data.items():
            next_filename = filename_prefix + data.get('filename') + '.csv'
            buffer = io.StringIO()
            if data.get('df').columns[0] == 'Unnamed: 0':
                data['df'] = data.get('df').rename(columns={'Unnamed: 0': 'row'})
            data.get('df').to_csv(buffer)
            self.log.handle(0, f'Uploading Indicator: {indi} data to S3', '@_upload_backtest_indicators')
            success = self.s3.write_to_s3(next_filename, buffer.getvalue(), 'cointosis-backtest')
            if not success:
                errors.append(f'ERROR: Could not upload indicator file - {next_filename}')
        return errors

    def _get_backtest_price_data(self, job_data, tf):
        self.log.handle(0, 'Verifying price data exists', '@_get_backtest_price_data')
        s3_price_filename = self.s3.get_filename('backtest-prices', job_data, agg_name=tf)
        if not self.s3.s3_file_exists(s3_price_filename, 'cointosis-backtest'):
            raise Exception(self.ERROR_MISSING_PRICE_FILE)
        return self.s3.read_df_from_s3(s3_price_filename, 'cointosis-backtest')

    @staticmethod
    def _verify_args():
        debug_mode = False
        for arg in sys.argv:
            if '--debug' in arg:
                debug_mode = bool(int(sys.argv[sys.argv.index(arg) + 1]))
        return debug_mode

    @staticmethod
    def _add_col_to_data(data, col):
        if col not in data:
            data[col] = {}
            data[col]['df'] = pd.DataFrame()
        return data

    @staticmethod
    def _save_indicator_filename(data, indi_name, ref_name):
        if 'filename' not in data[indi_name]:
            data[indi_name]['filename'] = '{iname}_{iparams}'.format(
                iname=indi_name,
                iparams='_'.join(ref_name.split('_')[1:]))
        return data


if __name__ == '__main__':
    GetFxIndicators.build().run()
