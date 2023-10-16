import json
import sys
from services.aws.sqs import SQSService


class QueueJobs:
    def __init__(self, *args, **kwargs):
        self.sqs_service = kwargs.get('sqs_service')
        self.is_preview = QueueJobs._verify_cli_args()

    @staticmethod
    def build():
        return QueueJobs(
            sqs_service=SQSService.build(),
        )

    def run(self):
        print('\nPreview: ', self.is_preview)
        start_date = '2005-01-01'
        end_date = '2014-12-31'
        pairs = {
            'AUD_NZD': 0,
            'CAD_CHF': 0,
            'EUR_JPY': 1,
            'EUR_USD': 0,
            'GBP_USD': 1,
            'GBP_JPY': 0,
            'GBP_NZD': 0,
            'USD_JPY': 0,
        }
        pipeline = {
            'prices': 0,
            'indicators': 0,
            'jobs': 1
        }
        options = {
            'TF': 5,
            'MA': 1,
            'FR': 1,
            'TM': 1,
            'PP': 10,
            'TG': 1,
        }
        for symbol, symbol_active in pairs.items():
            if not symbol_active:
                continue
            print(f'\n\nQueue: {symbol}')
            for step, step_active in pipeline.items():
                if not step_active:
                    continue
                print(f' - Pipeline Starts @: "{step}"')
                job_details = {
                    'start_date': start_date,
                    'end_date': end_date,
                    'symbol': symbol,
                    'version': 'forex_trader_v2',
                    'sample': 'in_sample',
                    'option_code': [],
                }
                for code, code_num in options.items():
                    if not code_num:
                        continue
                    job_details['option_code'].append(f'{code}{code_num}')
                job_details['option_code'] = '_'.join(job_details.get('option_code'))
                print(' - Options Code: ', job_details.get('option_code'))
                if step == 'prices':
                    if not self.is_preview:
                        self.sqs_service.send_message('fx-get-backtest-prices', json.dumps(job_details))
                    print(' - Job Q: PRICE')
                elif step == 'indicators':
                    if not self.is_preview:
                        self.sqs_service.send_message('fx-get-backtest-indicators', json.dumps(job_details))
                    print(' - Job Q: INDICATOR')
                elif step == 'jobs':
                    if not self.is_preview:
                        self.sqs_service.send_message('fx-backtest-requests', json.dumps(job_details))
                    print(' - Job Q: BACKTEST')

    @staticmethod
    def _verify_cli_args():
        is_preview = False
        for i, arg in enumerate(sys.argv):
            if arg == '-p':
                is_preview = bool(int(sys.argv[i + 1]))
        return is_preview


if __name__ == '__main__':
    QueueJobs.build().run()
