import copy

import constants
from services.log import LogService
from services.utilis import UtilityService


class CalculationController:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.log_service = kwargs.get('log_service')
        self.utils = kwargs.get('utils')

    @staticmethod
    def build(env, backtest_env):
        return CalculationController(
            env=env,
            backtest_env=backtest_env,
            log_service=LogService.build(name_prefix='CalculationController'),
            utils=UtilityService.build())

    def handle_calculations(self, context):
        psxn = context.get('position')
        trades = psxn.get('trades')
        if not trades:
            return context
        for trade_id, trade in trades.items():
            context['position']['target_trade_id'] = trade_id
            polarity = 1 if trade.get('size') > 0 else -1
            trade = self._setup_calculation(context, trade)
            updated_trade = self._calculate_metrics(context, trade, trade.get('exit_price'), polarity)
            context['position']['trades'][trade_id] = updated_trade
        polarity = 1 if psxn.get('total_size') > 0 else -1 if psxn.get('total_size') else 0
        context['position'] = self._setup_calculation(context, psxn)
        new_position = self._calculate_metrics(
            context,
            psxn,
            psxn.get('exit_price'),
            polarity)
        context['position'] = new_position
        return context

    def _setup_calculation(self, context, data):
        self._apply_time_price_to_trade(
            context.get('action'),
            data,
            *self._calc_time_price(
                *self._get_time_price(context, data)))
        return data

    def _apply_time_price_to_trade(self, action, data, time, price):
        if action in ['open']:
            data['entry_time'] = time
            data['entry_price'] = price
            data['exit_price'] = price
        elif action in ['decrease', 'close', 'wait', 'update', 'increase']:
            data['exit_time'] = time
            data['exit_price'] = price

    def _get_time_price(self, context, data):
        if self.env.get('backtest_active'):
            _time = self.backtest_env.get('run_info').get('latest_date')
            _price = self.backtest_env.get('run_info').get('latest_price')
        elif context.get('action') in ['increase', 'decrease', 'wait', 'update']:
            _time = context.get('latest_prices').get(
                context.get('tfs')[-1]).time.iloc[-1]
            _price = context.get('latest_prices').get(
                context.get('tfs')[-1]).close.iloc[-1]
        elif context.get('action') in ['open', 'close']:
            _time = data.get('time') or data.get('entry_time')
            _price = data.get('entry_price')
        return _time, _price

    def _calc_time_price(self, time, price):
        time = self.utils.calc_trade_time(time)
        price = float(price)
        return time, price

    def _calculate_metrics(self, context, data, price, polarity):
        new_data = {
            **copy.deepcopy(constants.metric_template),
            **data,
        }
        new_data = self._calc_upper_lower_bounds(new_data, price, polarity)
        new_data = self._calc_trade_pl(new_data, polarity)
        new_data = self._clean_values(new_data, context.get('symbol'))
        return new_data

    def _calc_upper_lower_bounds(self, data, price, polarity):
        data['trade_high'] = self._calc_trade_high(data, price)
        data['trade_low'] = self._calc_trade_low(data, price)
        if 'trades' in data and data.get('average_price'):
            price = data.get('average_price')
        if polarity > 0:
            data['max_drawdown'] = (data.get('entry_price') - data.get('trade_low')) * -1
            data['max_profit'] = data.get('trade_high') - data.get('entry_price')
        elif polarity < 0:
            data['max_drawdown'] = (data.get('trade_high') - data.get('entry_price')) * -1
            data['max_profit'] = data.get('entry_price') - data.get('trade_low')
        return data

    def _calc_trade_pl(self, data, polarity):
        if not data.get('entry_price'):
            self.log_service.handle(-1, '@_calc_trade_pl', 'Do not have required price data to calculate "P/L" metrics')
        data['P/L pips'] = self._calc_pl_pips(data, polarity)
        data['P/L %'] = self._calc_pl_percent(data)
        return data

    @staticmethod
    def _clean_values(data, symbol):
        for k, v in data.items():
            if k in ['P/L $']:
                data[k] = round(v, 4)
            if k in ['max_drawdown', 'max_profit', 'P/L pips', 'spread']:
                if symbol.split('_')[-1] == 'JPY':
                    data[k] = round(v * 100, 4)
                else:
                    data[k] = round(v * 10000, 4)
        if 'trades' in data:
            del data['size']
            del data['margin']
        if 'time' in data:
            del data['time']
        return data

    @staticmethod
    def _calc_trade_high(data, price):
        return max(data.get('trade_high'), price)

    @staticmethod
    def _calc_trade_low(data, price):
        return min(data.get('trade_low'), price)

    @staticmethod
    def _calc_pl_pips(data, polarity):
        is_position = all(['trades' in data, data.get('average_price')])
        if polarity > 0:
            price = data.get('average_price') if is_position else data.get('entry_price')
            return round(data.get('exit_price') - price, 6)
        elif polarity < 0:
            price = data.get('average_price') if is_position else data.get('entry_price')
            return round(price - data.get('exit_price'), 6)

    @staticmethod
    def _calc_pl_percent(data):
        if not all([
            data.get('P/L $'),
            data.get('account_balance')
        ]):
            return 0
        return round((data.get('P/L $', 0) / data.get('account_balance', 0)) * 100, 2)
