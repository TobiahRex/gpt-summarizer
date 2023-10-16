from services.slack import SlackService


class NotificationController:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.slack_service = kwargs.get('slack_service')

    @staticmethod
    def build(env, backtest_env):
        return NotificationController(
            env=env,
            backtest_env=backtest_env,
            slack_service=SlackService.build(env, backtest_env))

    def handle_notification(self, context):
        position = context.get('position')
        if any([
            not position,
            not position.get('trades'),
            not position.get('last_order_success')
        ]):
            return context
        last_key = context.get('keys', {}).get('last_key', '')
        notification = ''
        if context.get('action') in ['open', 'increase']:
            notification = self.notify_open_order(context, last_key, context.get('action'))
        elif context.get('action') in ['close', 'decrease']:
            notification = self.notify_close_order(context, last_key, context.get('action'))
        if notification:
            context['notifications'].append(notification)
        return context

    def notify_open_order(self, context, key, action):
        if self.env.get('notifier') == 'slack':
            return self.slack_service.post_trade_opened(context, key, action, verbose=False)
        else:
            raise Exception('Need explicit notification type')

    def notify_close_order(self, context, key, action):
        if self.env.get('notifier') == 'slack':
            return self.slack_service.post_trade_closed(context, key, action)
        else:
            raise Exception('Need explicit notification type')

    def notify_backtest_results(self, symbol, results):
        return
