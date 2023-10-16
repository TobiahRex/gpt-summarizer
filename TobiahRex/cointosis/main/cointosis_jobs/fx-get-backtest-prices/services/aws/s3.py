import boto3
import backoff
from botocore.exceptions import ClientError, ParamValidationError
from dateutil import parser

from services.log_service import LogService


class S3Service:
    default_region = 'us-west-2'

    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.resource = kwargs.get('s3_resource')
        self.client = kwargs.get('s3_client')
        self.bucket = kwargs.get('bucket') or kwargs.get('env').get('s3').get('bucket')
        self.log = kwargs.get('log_service')

    @staticmethod
    def build(env):
        return S3Service(
            env=env,
            s3_resource=boto3.resource('s3', region_name=S3Service.default_region),
            s3_client=boto3.client('s3', region_name=S3Service.default_region),
            log_service=LogService.build('S3 Service'))

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

    @backoff.on_exception(backoff.expo, exception=(ClientError, ParamValidationError), max_tries=5)
    def read_from_s3(self, key, bucket=None):
        if not bucket:
            bucket = self.bucket
        obj = self.resource.Object(bucket, key)
        body = obj.get()['Body'].read()
        return body.decode('utf-8')

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
