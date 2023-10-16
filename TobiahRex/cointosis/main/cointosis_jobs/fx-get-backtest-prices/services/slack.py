from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import pytz

pacific_tz = pytz.timezone('US/Pacific')


class SlackService:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.client = kwargs.get('client')
        self.channel = kwargs.get('channel')
        self.channel_id = None

    @staticmethod
    def build(env):
        token = env.get('slack').get('token')
        channel = env.get('slack').get('channel_name')
        return SlackService(
            env=env,
            client=WebClient(token=token),
            channel=channel)

    def get_channel_id(self):
        if self.channel_id is None:
            self.channel = self.env.get('slack').get('channel_name')
            for res in self.client.conversations_list():
                for channel in res.data.get('channels'):
                    if channel.get('name') == self.channel:
                        self.channel_id = channel.get('id')
                        break
                break
        return None

    def notify(self, msg):
        if self.channel_id is None:
            self.get_channel_id()
        try:
            self.client.chat_postMessage(channel=self.channel_id, text=msg)
        except SlackApiError as e:
            print('Slack Error: ', e)


if __name__ == '__main__':
    from aws.ssm import SSMService
    env = SSMService.build().get_param('/cointosis/forex_trader_v2')
    slack = SlackService.build(env).notify('Test message')
