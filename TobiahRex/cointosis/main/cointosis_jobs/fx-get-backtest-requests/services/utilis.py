import dateutil.parser
from datetime import datetime as dt


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
    def get_stats_val(list, method):
        value = 0
        if len(list) > 1:
            value = round(method(list), 4)
        elif len(list) > 0:
            value = list[0]
        else:
            value = 0
        return value

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

    @staticmethod
    def lowercase_df_cols(df):
        df.columns = [x.lower() for x in df.columns]
        return df

    @staticmethod
    def has_open_trades(context):
        open_trades = set([t.get('trade_id') for t in
                           context.get('position').get('trades').values()
                           if t.get('state', '') != 'CLOSED'])
        for job in context.get('jobs'):
            if job.get('type') == 'trade' and job.get('action') == 'close':
                trade_id = job.get('meta', {}).get('trade_id')
                if trade_id in open_trades:
                    open_trades.remove()
        return bool(open_trades)

    @staticmethod
    def _add_behavior(behavior, behaviors):
        if 'open' in behavior:
            if behavior not in behaviors:
                behaviors.append(behavior)
            return
        behaviors.append(behavior)

    @staticmethod
    def get_target_data(context):
        position = context.get('position')
        trade_id = position.get('target_trade_id')
        if trade_id:
            data = position.get('trades').get(trade_id)
            size = data.get('size')
        else:
            data = position
            size = position.get('total_size')
        return data, size

    @staticmethod
    def save_behaviors(context, position_behaviors, trade_behaviors):
        context['position']['behaviors'] = position_behaviors
        trade_id = context.get('position').get('target_trade_id')
        if trade_id:
            context['position']['trades'][trade_id]['behaviors'] = trade_behaviors

    @staticmethod
    def get_behaviors(context):
        position_behaviors = context.get('position').get('behaviors')
        trade_id = context.get('position').get('target_trade_id')
        trade_behaviors = []
        if trade_id:
            trade_behaviors = context.get('position', {}).get('trades', {}).get(trade_id).get('behaviors')
        return position_behaviors, trade_behaviors

    @staticmethod
    def setup_position_analysis(context):
        polarity = 1 if context.get('position').get('total_size') > 0 else -1
        ltf = context.get('tfs')[-1]
        mtf = context.get('tfs')[1]
        behaviors = context.get('position').get('behaviors')
        latest_force = context.get('latest_prices').get(ltf).iloc[-1].force
        keys = context.get('keys')
        indicator_data = context.get('latest_prices').get(mtf)
        return behaviors, polarity, latest_force, keys, indicator_data

    @staticmethod
    def calc_trade_time(time):
        time_stamp = dateutil.parser \
            .isoparse(time) \
            .timestamp()
        trade_time = dt.fromtimestamp(time_stamp).strftime('%Y-%m-%d %H:%M:%S')
        return trade_time


if __name__ == '__main__':
    util = UtilityService.build()
