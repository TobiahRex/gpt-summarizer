import shutil
import os

files = [
    ['cointosis-sandbox/services/aws', 'cointosis-jobs/fx-get-backtest-prices/services/aws'],
    ['cointosis-sandbox/services/broker.py', 'cointosis-jobs/fx-get-backtest-prices/services/broker.py'],
    ['cointosis-sandbox/services/oanda.py', 'cointosis-jobs/fx-get-backtest-prices/services/oanda.py'],
    ['cointosis-sandbox/services/alpaca.py', 'cointosis-jobs/fx-get-backtest-prices/services/alpaca.py'],
    ['cointosis-sandbox/services/backtest_trader.py', 'cointosis-jobs/fx-get-backtest-prices/services/backtest_trader.py'],
    ['cointosis-sandbox/constants', 'cointosis-jobs/fx-get-backtest-prices/constants'],
    ['cointosis-sandbox/services/log_service.py', 'cointosis-jobs/fx-get-backtest-prices/services/log_service.py'],
]


def main():
    for [source, target] in files:
        if os.path.exists(source):
            if os.path.isdir(source):
                shutil.copytree(source, target, dirs_exist_ok=True)
            else:
                shutil.copy(source, target)


if __name__ == '__main__':
    main()
