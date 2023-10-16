import os
from io import StringIO
from tracemalloc import start
import boto3
import backoff
from botocore.exceptions import ClientError, ParamValidationError
import json
import uuid
import copy
import pandas as pd
from dateutil import parser


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
            filename = self.get_filename('backtest-trades-open', self.backtest_env.get('job_data'))
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
        filename = ''
        bucket = ''
        job_data = self.backtest_env.get('job_data')
        if self.env.get('backtest_active'):
            filename = self.get_filename('backtest-trades-closed', job_data)
            bucket = 'cointosis-backtest'
        else:
            filename = '{v}/{s}/trades_closed.txt'
            bucket = 'cointosis'
        closed_trades = []
        if self.s3_file_exists(filename, bucket):
            data = self.read_from_s3(filename, bucket)
            if data:
                closed_trades = json.loads(data)
        del context['latest_prices']
        context['name'] = f'{symbol}_{"_".join(context.get("tfs"))}'
        closed_trades.append(context)
        self.write_to_s3(filename, json.dumps(closed_trades, indent=4), bucket)
        open_filename = self.get_filename('backtest-trades-open', job_data)
        self.write_to_s3(open_filename, '', bucket)

    def post_trade_upgraded(self, context):
        self.post_trade_opened(context)

    # def post_backtest_trade(self, context):
    #     symbol = context.get('symbol')
    #     backtest_env = self.env.get('backtest')
    #     save_data = backtest_env.get('save_data')
    #     version = self.env.get('version')
    #     filename = 'cointosis-backtest/{version}/trades/{sample}/{trend}/{start_date}/1y_{symbol}_{code}.{file_type}'.format(
    #         version=version,
    #         sample=save_data.get('sample_type'),
    #         trend=save_data.get('trend_type'),
    #         start_date=save_data.get('start_date'),
    #         symbol=symbol,
    #         code=save_data.get('scene_code'),
    #         file_type='txt'
    #     )
    #     bucket = self.env.get('backtest').get('s3').get('bucket')
    #     trades = {}
    #     if self.s3_file_exists(filename, bucket=bucket):
    #         saved_trades = self.read_from_s3(filename)
    #         if saved_trades:
    #             trades = json.loads(saved_trades)
    #     trades[str(uuid.uuid1)] = {**copy.deepcopy(context)}
    #     self.write_to_s3(filename, json.dumps(trades, indent=4), bucket)

    def save_backtest_results(self, job_data, options, results, tester):
        trades_filename = self._save_backtest_trades(results)
        plot_filename = self._save_backtest_plot(tester)
        report_filename, report = self._save_backtest_report(results, options)
        result = {
            'plot_file': f'https://cointosis-backtest.s3.us-west-2.amazonaws.com/{plot_filename}',
            'trades_file': f'https://cointosis-backtest.s3.us-west-2.amazonaws.com/{trades_filename}',
            'report_file': f'https://cointosis-backtest.s3.us-west-2.amazonaws.com/{report_filename}',
            'report': f"```{json.dumps(report, indent=4, separators=('', ': '))}```",
        }
        return result

    def reset_backtest_trade_files(self, job_data):
        open_trades_file = self.get_filename('backtest-trades-open', job_data)
        closed_trades_file = self.get_filename('backtest-trades-closed', job_data)
        bucket = self.env.get('s3').get('bucket')
        self.upload('./trades_open.txt', open_trades_file, bucket)
        self.upload('./trades_closed.txt', closed_trades_file, bucket)

    def _save_backtest_trades(self, results):
        bucket = 'cointosis-backtest'
        filename = self.get_filename(
            'backtest-results', self.backtest_env.get('job_data'), result_filename='backtest_trades.csv')
        trades_buffer = StringIO()
        results._trades.to_csv(trades_buffer)
        self.write_to_s3(filename, trades_buffer.getvalue(), bucket)
        return bucket + filename

    def _save_backtest_plot(self, plotter):
        bucket = 'cointosis-backtest'
        filename = self.get_filename(
            'backtest-results', self.backtest_env.get('job_data'), result_filename='backtest_plot.html')
        plotter.plot(filename='./backtest_plot.html')
        self.upload('./backtest_plot.html', filename, bucket)
        os.remove('./backtest_plot.html')
        return bucket + filename

    def _save_backtest_report(self, raw_report, options):
        job_data = self.backtest_env.get('job_data')
        bucket = 'cointosis-backtest'
        filename = self.get_filename('backtest-results', job_data, result_filename='backtest_report.txt')
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
        report['Name'] = f'{job_data.get("version")}_{job_data.get("symbol")}_{tfs}'
        self.write_to_s3(filename, json.dumps(report, indent=4), bucket)
        return bucket + filename, report

    def get_filename(self, label, job_data, result_filename='', agg_name='', indicator_filename=''):
        start_date = parser.parse(job_data.get('start_date'))
        end_date = parser.parse(job_data.get('end_date'))
        s_year = start_date.year
        e_year = end_date.year
        sd = start_date.strftime('%Y%m%d')
        ed = end_date.strftime('%Y%m%d')
        symbol = ''.join(job_data.get('symbol').split('_'))
        version = job_data.get('version')
        sample_type = job_data.get('sample')
        option_code = job_data.get('option_code')
        label_map = {
            'backtest-results': '{vxn}/results/{sam}/{oc}/{sym}_{tw}/{rfl}'.format(
                vxn=version,
                sam=sample_type,
                oc=option_code,
                sym=symbol,
                tw=f'{sd}-{ed}',
                rfl=result_filename),
            'backtest-trades-open': '{vxn}/trades/{sam}/{oc}/{sym}_{tw}/trades_open.txt'.format(
                vxn=version,
                sam=sample_type,
                oc=option_code,
                sym=symbol,
                tw=f'{sd}-{ed}'),
            'backtest-trades-closed': '{vxn}/trades/{sam}/{oc}/{sym}_{tw}/trades_closed.txt'.format(
                vxn=version,
                sam=sample_type,
                oc=option_code,
                sym=symbol,
                tw=f'{sd}-{ed}'),
            'backtest-prices': 'prices/{yrs}/{sym}_{agg}_{tw}.csv'.format(
                yrs=f'{s_year}-{e_year}',
                sym=symbol,
                agg=agg_name,
                tw=f'{sd}-{ed}'),
            'backtest-indicators': 'indicators/{yrs}/{sym}_{agg}_{tw}/{ifl}'.format(
                yrs=f'{s_year}-{e_year}',
                sym=symbol,
                agg=agg_name,
                tw=f'{sd}-{ed}',
                ifl=indicator_filename),
        }
        return label_map.get(label)
