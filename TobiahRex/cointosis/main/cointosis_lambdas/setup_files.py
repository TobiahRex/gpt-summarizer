import os
import shutil


lambda_services = [
    'alpaca.py',
    'broker.py',
    'indicators.py',
    'log_service.py',
    'oanda.py',
    'slack.py',
    'utils.py',
    'aws',
    'backtest_trader.py'
    'utils.py'
]

lambda_controllers = [
    'notification.py',
    'data.py',
    'calculation.py',
    'backtest_fxv2.py',
    'analysis_v2',
]

lambda_constants = [
    '__init__.py',
    'alpaca.py',
    'oanda.py',
    'backtest.py'
]

cointosis = 'fxv2.py'

def copy_files():
    for file in os.listdir(os.getcwd() + '/services'):
        if file in lambda_services:
            if os.path.isdir(f'services/{file}'):
                dest = f'lambdas/fxv2-backtest/services/{file}'
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(f'services/{file}', dest)
            else:
                shutil.copy(f'services/{file}', 'lambdas/fxv2-backtest/services')

    for file in os.listdir(os.getcwd() + '/constants'):
        shutil.copy(f'constants/{file}', 'lambdas/fxv2-backtest/constants')

    for file in os.listdir(os.getcwd() + '/controllers'):
        if file in lambda_controllers:
            if os.path.isdir(f'controllers/{file}'):
                dest = f'lambdas/fxv2-backtest/controllers/{file}'
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(f'controllers/{file}', dest)
            else:
                shutil.copy(f'controllers/{file}', 'lambdas/fxv2-backtest/controllers')

    dest = f'lambdas/fxv2-backtest/cointosis/{cointosis}'
    if os.path.exists(dest):
        os.remove(dest)
    shutil.copy(f'cointosis/{cointosis}', dest)


if __name__ == '__main__':
    copy_files()
