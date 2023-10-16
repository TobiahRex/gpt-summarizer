import shutil
import os

files = [
    ['cointosis-sandbox/services/aws', 'cointosis-lambdas/manage-backtest-jobs/services/aws'],
    ['cointosis-sandbox/services/log_service.py', 'cointosis-lambdas/manage-backtest-jobs/services/log_service.py'],
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