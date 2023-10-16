import os
import boto3
import logging

boto3.set_stream_logger('botocore.credentails', logging.CRITICAL)


class ECSService:
    _default_region = os.environ.get('AWS_REGION', 'us-west-2')

    def __init__(self, *args, **kwargs):
        self.ecs = kwargs.get('ecs_client')

    @staticmethod
    def build(region=None):
        return ECSService(
            ecs_client=boto3.client('ecs', region_name=ECSService._default_region))

    def stop_task(self, task_id, reason='Manual Stop'):
        if not task_id:
            print('Could not stop unidentified task')
            return
        result = self.ecs.stop_task(
            cluster='cointosis',
            task=task_id,
            reason=reason)
        if result.get('ResponseMetaData', {}).get('HTTPStatusCode', 0) != 200:
            return result
        return None


if __name__ == '__main__':
    ECSService.build().stop_task('11811ebb6a0944319b546a18be0ff2c4')
