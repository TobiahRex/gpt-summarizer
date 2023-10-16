class UtilityService:
    """Utility library for various repetitive function calls.
    """
    def __init__(self):
        pass

    @staticmethod
    def build():
        ds = UtilityService()
        return ds

    @staticmethod
    def divide(val1, val2, round_to=None):
        if round_to is not None:
            if val1 and val2:
                return round(val1 / val2, round_to)
            return 0
        if val1 and val2:
            return val1 / val2
        else:
            return 0


if __name__ == '__main__':
    util = UtilityService.build()
