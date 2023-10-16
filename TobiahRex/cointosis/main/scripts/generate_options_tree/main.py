import numpy as np
import json

from services.aws.ssm import SSMService
from services.aws.s3 import S3Service


class GenerateOptions:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.s3_service = kwargs.get('s3_service')

    @staticmethod
    def build(env, backtest_env):
        return GenerateOptions(
            env=env,
            backtest_env=backtest_env,
            s3_service=S3Service.build(env, backtest_env, bucket='cointosis-backtest'))

    def run(self):
        filename = f'{self.env.get("version")}/option_tree/options.json'
        if self.s3_service.s3_file_exists(filename):
            option_tree = self.s3_service.read_from_s3(filename)
            return option_tree
        options = self.backtest_env.get('options')
        option_names = options.get('option_names')
        option_values = options.get('option_values')
        option_map = {}
        option_codes = {}
        for name, values in option_values.items():
            option_codes[name] = set()
            for n, v in values.items():
                option_code = f'{name}{n}'
                option_codes[name].add(option_code)
                option_map[option_code] = v
        for name, values in option_map.items():
            n_code = name[0:2]
            opt_names = option_names.get(n_code)
            result = {}
            for i in range(0, len(opt_names)):
                result[opt_names[i]] = values[i]
            option_map[name] = result
        option_combos = [
            list(l) for l in np.array(
                np.meshgrid(*[list(v) for v in option_codes.values()]))
            .T.reshape(-1, 6)
        ]
        for key, option in option_map.items():
            filename = f'{self.env.get("version")}/option_tree/{key}.txt'
            if not self.s3_service.write_to_s3(filename, json.dumps(option)):
                raise Exception('Could not write option tree to S3')
        # option_tree = {}
        # for options in option_combos:
        #     option_name = '_'.join(options)
        #     option_tree[option_name] = {}
        #     for o in options:
        #         option_tree[option_name] = {
        #             **option_tree.get(option_name),
        #             **option_map.get(o),
        #         }
        # if not self.s3_service.write_to_s3(filename, json.dumps(option_tree)):
        #     raise Exception('Could not write option tree to S3')
        return option_tree


    def upload_tree(self):
        f = open('options.txt', 'r')
        raw_data = f.read()
        data = json.loads(raw_data)
        for option_code, option_value in data.items():
            filename = '{v}/{o}/{oc}.txt'.format(
                v=self.env.get('version'),
                o='option_tree',
                oc=option_code)
            self.s3_service.write_to_s3(filename, json.dumps(option_value, indent=4))


if __name__ == '__main__':
    env = SSMService.build().get_param('/cointosis/forex_trader_v2')
    _backtest_env = S3Service.build(env, None).read_from_s3(
        'forex_trader_v2/backtest_forex_trader_v2.json',
        'cointosis-backtest')
    backtest_env = json.loads(_backtest_env)
    gen = GenerateOptions.build(env, backtest_env).run()
