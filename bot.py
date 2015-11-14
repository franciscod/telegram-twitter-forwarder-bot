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

    def send_tweet(self, msg, tweet):
        self.tg.sendMessage(
            chat_id=msg.chat_id,
            disable_web_page_preview=True,
            text="""
{text}

{name} ({screen_name}) @ {created_at}
https://twitter.com/{screen_name}/status/{id}
"""
            .format(
                text=tweet.text,
                name=tweet.user.name,
                screen_name=tweet.user.screen_name,
                created_at=tweet.created_at,
                id=tweet.id,
            ))

    def cmd_start(self, msg, args):
        self.reply(msg, "Hello! I'm a work in progress bot for now! https://github.com/franciscod/telegram-twitter-forwarder-bot")

    def handle_chat(self, msg):
        self.reply(msg, "Okay, okay! Have a tweet:")

        for tweet in self.tw.user_timeline(screen_name='twitter', count=1):
            self.send_tweet(msg, tweet)


if __name__ == '__main__':
    auth = tweepy.OAuthHandler(env('TWITTER_CONSUMER_KEY'), env('TWITTER_CONSUMER_SECRET'))

    try:
        auth.set_access_token(env('TWITTER_ACCESS_TOKEN'), env('TWITTER_ACCESS_TOKEN_SECRET'))
    except KeyError:
        print("Either TWITTER_ACCESS_TOKEN or TWITTER_ACCESS_TOKEN_SECRET environment variables are missing. " +
              "Tweepy will be initialized in 'app-only' mode")

    twapi = tweepy.API(auth)

    bot = TwitterForwarderBot(env('TELEGRAM_BOT_TOKEN'), twapi)
    bot.kb_interruptable_loop()
