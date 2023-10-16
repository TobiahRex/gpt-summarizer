try:
    import unzip_requirements  # noqa
except ImportError:
    pass
import json

from services.aws.sqs import SQSService
from services.aws.ssm import SSMService
from services.log_service import LogService
from services.manage_backtests import ManageBacktests


def manage_backtest(event, lambda_context, debug=False):
    if not debug:
        print('Starting: ', lambda_context.function_name)
    try:
        body = event['Records'][0]['body']
        log = LogService.build(name_prefix='manage_backtest')
        if not body:
            log.handle(0, '@manage_backtest', 'No Job Data')
        context = json.loads(body)
        log.handle(0, '@manage_backtest', f'REQUEST: \n{body}')
        env = SSMService.build().get_param('/cointosis-backtest/manage_backtests')
        queued_ids = ManageBacktests.build(env).run(context)
        if queued_ids:
            log.handle(1, '@run', f'Queued IDs: \n{json.dumps(queued_ids)}')
        else:
            log.handle(0, '@run', f'Result: \n{json.dumps(queued_ids)}')
    except Exception as e:
        error_msg = str(e)
        log.handle(0, '@run', f'ERROR: {str(e)}')
        context['error'] = error_msg
        SQSService.build().send_message(env.get('sqs').get('backtest_error_q'), json.dumps(context))


if __name__ == '__main__':
    from test_events import sqs_job
    manage_backtest(sqs_job, None, debug=True)