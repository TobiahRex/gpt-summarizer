import os
from io import StringIO
import boto3
import backoff
from botocore.exceptions import ClientError, ParamValidationError
import json
import uuid
import copy
import pandas as pd

from services.log_service import LogService


class S3Service:
    default_region = 'us-west-2'

    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.resource = kwargs.get('s3_resource')
        self.client = kwargs.get('s3_client')
        self.bucket = kwargs.get('bucket') or kwargs.get('env').get('s3').get('bucket')
        self.log = kwargs.get('log_service')

    @staticmethod
    def build(env, backtest_env=None, bucket=''):
        return S3Service(
            env=env,
            backtest_env=backtest_env,
            s3_resource=boto3.resource('s3', region_name=S3Service.default_region),
            s3_client=boto3.client('s3', region_name=S3Service.default_region),
            bucket=bucket,
            log_service=LogService.build('S3 Service'))

    @backoff.on_exception(backoff.expo, exception=(ClientError, ParamValidationError), max_tries=5)
    def read_from_s3(self, key, bucket=None):
        if not bucket:
            bucket = self.bucket
        obj = self.resource.Object(bucket, key)
        body = obj.get()['Body'].read()
        return body.decode('utf-8')

    @backoff.on_exception(backoff.expo, exception=(ClientError, ParamValidationError), max_tries=5)
    def read_df_from_s3(self, key, bucket=None):
        if not bucket:
            bucket = self.bucket
        obj = self.client.get_object(Bucket=bucket, Key=key)
        data_frame = pd.read_csv(obj['Body'])
        return data_frame

    @backoff.on_exception(backoff.expo, exception=(ClientError, ParamValidationError), max_tries=5)
    def write_to_s3(self, key, body, bucket=None):
        if not bucket:
            bucket = self.bucket
        obj = self.resource.Object(bucket, key)
        res = obj.put(Body=body)
        success = res.get('ResponseMetadata', {}).get('HTTPStatusCode', 0) == 200
        return success

    def s3_file_exists(self, key, bucket=None):
        try:
            if not bucket:
                bucket = self.bucket
            if self.client.head_object(Bucket=bucket, Key=key):
                return True
            return False
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') in ['NoSuchBucket', '404']:
                return False

    def download(self, key, download_loci, bucket=None):
        try:
            if not bucket:
                bucket = self.bucket
            self.client.download_file(bucket, key, download_loci)
        except ClientError as ce:
            if ce.response['Error']['Code'] == '404':
                self.log.handle(-1, ce, '@download')
            return False
        except Exception as err:
            self.log.handle(-1, err, '@download')
            return False
        return True

    def upload(self, filename, upload_loci, bucket=None):
        try:
            if not bucket:
                bucket = self.bucket
            self.client.upload_file(Filename=filename, Bucket=bucket, Key=upload_loci)
        except ClientError as e:
            if e.response['Error']['Code'] == "404":
                self.log.handle(-1, "The object does not exist.", '@upload')
            return False
        except Exception as err:
            self.log.handle(-1, f's3 - Failed download of file: {err}', '@upload')
            return False
        return True

    def list_objects_v2(self, prefix, bucket=None):
        if not bucket:
            bucket = self.bucket
        list_args = {'Bucket': bucket, 'Prefix': prefix}
        continuation_token = True
        while continuation_token:
            response = self.client.list_objects_v2(**list_args)
            for item in response.get('Contents', []):
                yield item
            continuation_token = response.get('NextContinuationToken')
            list_args['ContinuationToken'] = continuation_token

    def delete_objects(self, keys, quiet=True, bucket=None):
        try:
            if not bucket:
                bucket = self.bucket
            response = self.client.delete_objects(
                Bucket=bucket,
                Delete={'Objects': [{'Key': k} for k in keys], 'Quiet': quiet},
            )
            return [e for e in response.get('Errors', [])]
        except Exception as e:
            self.log.error(-1, '@delete_objects', f'Bulk deleting objects failed. Error {e}')
            raise e

    def post_trade_opened(self, context):
        symbol = context.get('symbol')
        filename = ''
        bucket = ''
        if self.env.get('backtest_active'):
            period = self.backtest_env.get('active_period')  # TODO: change this to use "backtest_env.job_data"
            filename = '{v}/trades/{s}/{t}/{sd}/{sy}/{code}/trades_open.txt'.format(
                v=self.env.get('version'),
                s=period.get('sample'),
                t=period.get('trend'),
                sd=period.get('start_date'),
                sy=symbol,
                code=self.backtest_env.get('options').get('active_code'))
            bucket = 'cointosis-backtest'
        else:
            filename = f'{self.env.get("version")}/{symbol}/trades_open.txt'
            bucket = 'cointosis'
        tfs = context.get('tfs')
        upgrade_tfs = context.get('position').get('upgrade_tfs')
        context['name'] = f'{symbol}_{"_".join(upgrade_tfs if upgrade_tfs else tfs)}'
        del context['latest_prices']
        return self.write_to_s3(filename, json.dumps(context, indent=4), bucket)

    def post_trade_closed(self, context):
        symbol = context.get('symbol')
        close_filename = ''
        bucket = ''
        if self.env.get('backtest_active'):
            period = self.backtest_env.get('active_period')  # TODO: change this to use "backtest_env.job_data"
            close_filename = '{v}/trades/{s}/{t}/{sd}/{sy}/{code}/trades_closed.txt'.format(
                v=self.env.get('version'),
                s=period.get('sample'),
                t=period.get('trend'),
                sd=period.get('start_date'),
                sy=symbol,
                code=self.backtest_env.get('options').get('active_code'))
            bucket = 'cointosis-backtest'
        else:
            close_filename = '{v}/{s}/trades_closed.txt'
            bucket = 'cointosis'
        closed_trades = []
        if self.s3_file_exists(close_filename, bucket):
            data = self.read_from_s3(close_filename, bucket)
            if data:
                closed_trades = json.loads(data)
        del context['latest_prices']
        context['name'] = f'{symbol}_{"_".join(context.get("tfs"))}'
        closed_trades.append(context)
        self.write_to_s3(close_filename, json.dumps(closed_trades, indent=4), bucket)
        open_filename = '/'.join(close_filename.split('/')[0:-1]) + '/trades_open.txt'
        self.write_to_s3(open_filename, '', bucket)

    def post_trade_upgraded(self, context):
        self.post_trade_opened(context)

    def post_backtest_trade(self, context):
        symbol = context.get('symbol')
        backtest_env = self.env.get('backtest')
        save_data = backtest_env.get('save_data')
        version = self.env.get('version')
        filename = 'cointosis-backtest/{version}/trades/{sample}/{trend}/{start_date}/1y_{symbol}_{code}.{file_type}'.format(
            version=version,
            sample=save_data.get('sample_type'),
            trend=save_data.get('trend_type'),
            start_date=save_data.get('start_date'),
            symbol=symbol,
            code=save_data.get('scene_code'),
            file_type='txt'
        )
        bucket = self.env.get('backtest').get('s3').get('bucket')
        trades = {}
        if self.s3_file_exists(filename, bucket=bucket):
            saved_trades = self.read_from_s3(filename)
            if saved_trades:
                trades = json.loads(saved_trades)
        trades[str(uuid.uuid1)] = {**copy.deepcopy(context)}
        self.write_to_s3(filename, json.dumps(trades, indent=4), bucket)

    def save_backtest_results(self, env, period, option_code, options, results, test):
        version = env.get('version')
        symbol = period.get('symbol')
        base_filename = '{v}/results/{s}/{t}/{d}/{sy}/{c}'.format(
            v=version,
            sy=symbol,
            s=period.get('sample'),
            t=period.get('trend'),
            d=period.get('start_date'),
            c=option_code)
        trades_filename = self._save_backtest_trades(base_filename, results)
        plot_filename = self._save_backtest_plot(base_filename, test)
        report_filename, report = self._save_backtest_report(base_filename, results, options, version, symbol)
        result = {
            'plot_file': f'https://cointosis-backtest.s3.us-west-2.amazonaws.com/{plot_filename}',
            'trades_file': f'https://cointosis-backtest.s3.us-west-2.amazonaws.com/{trades_filename}',
            'report_file': f'https://cointosis-backtest.s3.us-west-2.amazonaws.com/{report_filename}',
            'report': f"```{json.dumps(report, indent=4, separators=('', ': '))}```",
        }
        return result

    def _save_backtest_trades(self, base_filename, results):
        trades_filename = base_filename + '/backtest_trades.csv'
        trades_buffer = StringIO()
        results._trades.to_csv(trades_buffer)
        self.write_to_s3(trades_filename, trades_buffer.getvalue(), 'cointosis-backtest')
        return trades_filename

    def _save_backtest_plot(self, base_filename, plotter):
        plot_filename = base_filename + '/backtest_plot.html'
        plotter.plot(filename='./backtest_plot.html')
        self.upload('./backtest_plot.html',plot_filename, 'cointosis-backtest')
        os.remove('./backtest_plot.html')
        return plot_filename

    def _save_backtest_report(self, base_filename, raw_report, options, version, symbol):
        report_filename = base_filename + '/backtest_report.txt'
        report = dict(raw_report)
        for k in ['_trades', '_equity_curve', '_strategy']:
            if k in report:
                del report[k]
        report['Calmar Ratio'] = report.get('Return [%]') / abs(report.get('Max. Drawdown [%]'))
        for k, v in report.items():
            if v:
                report[k] = round(v, 4)
            else:
                report[k] = 0
        tfs = str('-'.join([options.get('htf'), options.get('mtf'), options.get('ltf')]))
        report['Name'] = f'{version}_{symbol}_{tfs}'
        self.write_to_s3(report_filename, json.dumps(report, indent=4), 'cointosis-backtest')
        return report_filename, report

    def reset_backtest_files(self, env, period, option_code):
        base = '{v}/trades/{s}/{t}/{d}/{sy}/{c}/'.format(
            v=env.get('version'),
            sy=period.get('symbol'),
            s=period.get('sample'),
            t=period.get('trend'),
            d=period.get('start_date'),
            c=option_code)
        self.upload('./trades_open.txt', base + 'trades_open.txt', 'cointosis-backtest')
        self.upload('./trades_closed.txt', base + 'trades_closed.txt', 'cointosis-backtest')

