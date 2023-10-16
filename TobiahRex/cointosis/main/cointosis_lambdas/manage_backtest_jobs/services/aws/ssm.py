import boto3
import json
import backoff
from botocore.exceptions import ClientError


class SSMService:
    default_region = 'us-west-2'

    def __init__(self, client):
        self.client = client

    @staticmethod
    def build():
        client = boto3.client('ssm', region_name=SSMService.default_region)
        return SSMService(client)

    def run(self):
        print(self.client)

    @backoff.on_exception(backoff.expo, exception=(ClientError), max_tries=5)
    def get_param(self, param_name):
        try:
            param = self.client.get_parameter(Name=param_name, WithDecryption=True)
            if param.get('ResponseMetadata', {}).get('HTTPStatusCode') != 200:
                raise Exception('Non 200 status from get_param')
            else:
                return json.loads(param.get('Parameter', {}).get('Value', {}))
        except Exception as e:
            print(f'---- ERROR \nduring get_param: \n{e}')
            raise e


if __name__ == '__main__':
    env = SSMService.build().get_param('/cointosis/forex_trader_v1')
    print('SSM params: ', env)
