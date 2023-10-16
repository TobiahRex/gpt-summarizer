import json


class LogService:
    def __init__(self, name_prefix):
        self.name_prefix = name_prefix
        self.log = print

    @staticmethod
    def build(name_prefix):
        return LogService(name_prefix)

    def handle(self, msg_num, data='', func_name=''):
        if msg_num == 1:
            self.__success(func_name, data)
        elif msg_num == 0:
            self.__info(func_name, data)
        elif msg_num == -1:
            self.__error(func_name, data)

    def __success(self, func_name, data):
        self.log(f'\n    {func_name} | SUCCESS: {json.dumps(data)}')

    def __error(self, func_name, data):
        e = f"KNOWN_ERROR: {json.dumps(data)}"
        self.log(f'\n    {func_name} | ERROR: {e}')
        raise Exception(e)

    def __info(self, func_name, data):
        self.log(f'\n    {func_name} | INFO: {json.dumps(data)}')
