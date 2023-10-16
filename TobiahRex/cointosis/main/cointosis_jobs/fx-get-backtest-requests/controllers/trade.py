from datetime import datetime as dt
from dateutil import parser
import pytz
import copy

import constants
from controllers.data import DataController
from services.broker import BrokerService
from services.log import LogService
from services.utilis import UtilityService


class TradeController:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.log = kwargs.get('log_service')
        self.broker_service = kwargs.get('broker_service')
        self.data_controller = kwargs.get('data_controller')
        self.utils = kwargs.get('utils')

    @staticmethod
    def build(env, backtest_env):
        return TradeController(
            env=env,
            backtest_env=backtest_env,
            log_service=LogService.build(name_prefix='TradeController'),
            data_controller=DataController.build(env, backtest_env),
            broker_service=BrokerService.build(env, backtest_env),
            utils=UtilityService.build())

    def handle_analysis(self, context):
        for job in context.get('jobs'):
            if job.get('action') in ['open', 'increase']:
                context = self._handle_open_trade(context)
            elif job.get('action') in ['close', 'decrease']:
                if job.get('type') == 'position':
                    size = (
                        context.get('position', {}).get('total_size', 0)
                        if job.get('action') == 'close'
                        else context.get('position', {}).get('next_order_size', 0))
                    context = self._handle_close_position(context, size)
                elif job.get('type') == 'trade':
                    context = self._handle_close_trade(context, job)
        return context

    def _handle_close_position(self, context, size):
        did_close, res, _ = self.broker_service.trader.get('close_position')(context, size)
        if did_close:
            close_price = float(res.get('price'))
            close_time = res.get('time')
            for closed_trade in res.get('tradesClosed'):
                trade_id = closed_trade.get('tradeID')
                trade = context.get('position').get('trades').get(trade_id)
                trade['P/L $'] = float(closed_trade.get('realizedPL'))
                trade['exit_price'] = close_price
                trade['exit_time'] = close_time
                if not self.env.get('backtest_active'):
                    trade['size'] += float(closed_trade.get('units'))
                    if trade.get('size') == 0:
                        trade['state'] = 'CLOSED'
            context['position']['exit_price'] = close_price
            context['position']['exit_time'] = close_time
            context['position']['P/L $'] = float(res.get('pl'))
            context['position']['last_order_success'] = True
            context['position']['total_size'] += float(res.get('units'))
        return context

    def _handle_close_trade(self, context, job):
        trade_id = job.get('meta', {}).get('trade_id', '')
        if not trade_id:
            self.log.handle(-1, 'No required trade_id to close trade', '@_handle_close_trade')
            return context
        context['position']['target_trade_id'] = trade_id
        size = job.get('meta', {}).get('size')
        did_close, res, _ = self.broker_service.trader.get('close_trade')(context, size)
        if did_close:
            context['position']['trades'][trade_id]['exit_price'] = float(
                res.get('tradesClosed', [])[0].get('realizedPL', 0))
            context['position']['trades'][trade_id]['account_balance'] = float(
                res.get('accountBalance', 0))
            context['position']['last_order_success'] = did_close
        return context

    def _handle_open_trade(self, context):
        position = context.get('position')
        if not position.get('next_order_size'):
            return context
        if context.get('action') in ['open', 'increase']:
            verified, reason = self.verify_trading_allowed(position.get('symbol'))
            if not verified:
                self.log.handle(0, reason, '@open_trade')
                context['action'] = 'wait'
                last_behavior = position['behaviors'].pop()
                last_behavior += f'-{reason}'
                position['behaviors'].append(f'::{last_behavior}')
                position['next_order_size'] = 0
                return context
        did_open, res, _ = self.broker_service.trader.get('open_trade')(
            symbol=position.get('symbol'),
            size=position.get('next_order_size'),
            trade_type=position.get('trade_type'))
        if did_open:
            trade = {
                **copy.deepcopy(constants.metric_template),
                'id': res.get('id'),
                'size': res.get('units'),
                'entry_time': self.utils.calc_trade_time(res.get('time')),
                'entry_price': res.get('price'),
                'account_balance': res.get('accountBalance', 0),
                'symbol': res.get('instrument'),
                'reason': res.get('reason'),
                'margin': res.get('tradeOpened').get('initialMarginRequired'),
                'spread': res.get('fullPrice').get('closeoutAsk') - res.get('fullPrice').get('closeoutBid'),
                'volume': float(res.get('fullPrice').get('bids')[0].get('liquidity')),
                'behaviors': [],
            }
            position['total_size'] += position.get('next_order_size')
            position['next_order_size'] = 0
            position['total_margin'] += trade.get('margin')
            position['trades'][trade.get('id')] = trade
            position['trade_ids'].append(trade.get('id'))
            if context.get('action') == 'open':
                position = {
                    **copy.deepcopy(position),
                    'entry_price': res.get('price'),
                    'entry_time': self.utils.calc_trade_time(res.get('time')),
                    'exit_price': res.get('price'),
                    'total_size': res.get('units'),
                    'margin': res.get('tradeOpened').get('initialMarginRequired'),
                    'account_balance': res.get('accountBalance', 0),
                }
        else:
            position['next_order_size'] = 0
        position['last_order_success'] = did_open
        context['position'] = position
        return context

    def verify_trading_allowed(self, symbol):
        if not self.verify_all_orders(symbol):
            return False, 'max_orders_all'
        if not self.verify_symbol_orders(symbol):
            return False, 'symbol_max_orders'
        if not self.verify_time_of_day(symbol):
            return False, 'time_of_day'
        return True, ''

    def verify_all_orders(self, symbol):
        all_open_orders, _ = self.broker_service.trader.get('get_open_trades')()
        max_trades = int(self.env.get('trading').get('max_total_trades'))
        if len(all_open_orders) == max_trades:
            self.log.handle(
                0, f'Max trades for {symbol} = {max_trades}. No trading allowed.', '@verify_all_orders',)
            return False
        elif len(all_open_orders) > max_trades:
            self.KILL_TRADING(symbol)
            return False
        return True

    def verify_symbol_orders(self, symbol):
        symbol_open_orders, _ = self.broker_service.trader.get('get_open_trades')(symbol)
        max_symbol_trades = self.env.get('trading').get('max_symbol_trades')
        if len(symbol_open_orders) >= max_symbol_trades:
            self.log.handle(
                0, f'Max trades for {symbol} = {max_symbol_trades}. No trading allowed', '@verify_symbol_orders')
            return False
        elif len(symbol_open_orders) > max_symbol_trades:
            self.KILL_TRADING(symbol)
        return True

    def verify_time_of_day(self, symbol):
        time = dt.utcnow()
        if self.env.get('backtest_active'):
            time = parser.parse(self.backtest_env.get('run_info').get('latest_date'))
        pst_time = time\
            .replace(tzinfo=pytz.utc)\
            .astimezone(pytz.timezone('US/Pacific'))
        if not self.backtest_env.get('run_info', {}).get('verify_runtime', True):
            self.log.handle(0, 'Backtest Active: Overwriting manual Time Verification - Allowing Trade', '@verify_time_of_day')
            return True
        if self.env.get('test_data').get('active'):
            return True
        if 'JPY' in symbol:
            if 17 <= pst_time.hour or pst_time.hour <= 8:
                return True
            return False
        else:
            if 23 <= pst_time.hour or pst_time.hour < 10:
                return True
            return False

    def get_position_by_symbol(self, context):
        position, _ = self.broker_service.trader.get('get_open_positions')()
        if not position:
            return {}
        trade_type = 'long' if context.get('position').get('total_size') > 0 else 'short'
        info = position.get(trade_type)
        context['position']['average_price'] = float(info.get('averagePrice'))
        context['position']['trade_ids'] = info.get('tradeIDs')
        context['position']['total_size'] = float(info.get('units'))
        context['position']['P/L $'] = float(info.get('unrealizedPL'))
        context['position']['total_margin'] = float(info.get('marginUsed'))
        return context.get('position')

    def update_position(self, context):
        if self.env.get('backtest_active'):
            return context.get('position')
        context['position'] = self.get_position_by_symbol(context)
        for trade_id in context.get('position').get('trade_ids'):
            api_trade = self.broker_service.trader.get('get_trade_by_id')(trade_id)
            if api_trade.get('state') != 'OPEN':
                continue
            trade = context.get('position').get('trades').get(trade_id)
            updated_trade = self._update_trade(trade, api_trade)
            context['position']['trades'][trade_id] = updated_trade
        context['position']['trade_ids'] = list(context.get('position').get('trades').keys())
        return context.get('position')

    @staticmethod
    def _update_trade(trade, api_trade):
        updated_trade = {
            **trade,
            'id': api_trade.get('id'),
            'size': api_trade.get('currentUnits'),
            'P/L $': api_trade.get('unrealizedPL'),
            'symbol': api_trade.get('instrument'),
            'entry_price': api_trade.get('price'),
            'margin': api_trade.get('marginUsed'),
            'state': api_trade.get('state')
        }
        return updated_trade


if __name__ == '__main__':
    from services.aws.ssm import SSMService
    env = SSMService.build().get_param('/cointosis/forex_trader_v2')
    from constants.tests import test_context
    trader = TradeController.build(env).update_trades(test_context)
