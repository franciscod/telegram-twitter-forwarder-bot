import tweepy
from envparse import Env

from basebot import BaseBot

env = Env(
    TWITTER_CONSUMER_KEY=str,
    TWITTER_CONSUMER_SECRET=str,
    TWITTER_ACCESS_TOKEN=str,
    TWITTER_ACCESS_TOKEN_SECRET=str,
    TELEGRAM_BOT_TOKEN=str,
)


class TwitterForwarderBot(BaseBot):
    def __init__(self, token, tweepy_api_object):
        super().__init__(token)

        self.tw = tweepy_api_object

    def cmd_start(self, msg, args):
        self.reply(msg, "Hello! I'm a work in progress bot for now! https://github.com/franciscod/telegram-twitter-forwarder-bot")

    def handle_chat(self, msg):
        self.reply(msg, "Still a work in progress, I don't do much!")


if __name__ == '__main__':
    auth = tweepy.OAuthHandler(env('TWITTER_CONSUMER_KEY'), env('TWITTER_CONSUMER_SECRET'))
    auth.set_access_token(env('TWITTER_ACCESS_TOKEN'), env('TWITTER_ACCESS_TOKEN_SECRET'))
    twapi = tweepy.API(auth)

    bot = TwitterForwarderBot(env('TELEGRAM_BOT_TOKEN'), twapi)
    bot.kb_interruptable_loop()
