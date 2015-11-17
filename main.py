import logging
import tweepy
from envparse import Env
from bot import TwitterForwarderBot
from basebot import JobQueue

env = Env(
    TWITTER_CONSUMER_KEY=str,
    TWITTER_CONSUMER_SECRET=str,
    TWITTER_ACCESS_TOKEN=str,
    TWITTER_ACCESS_TOKEN_SECRET=str,
    TELEGRAM_BOT_TOKEN=str,
)

if __name__ == '__main__':

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.WARNING)

    logging.getLogger(TwitterForwarderBot.__name__).setLevel(logging.DEBUG)
    logging.getLogger(JobQueue.__name__).setLevel(logging.DEBUG)

    auth = tweepy.OAuthHandler(env('TWITTER_CONSUMER_KEY'), env('TWITTER_CONSUMER_SECRET'))

    try:
        auth.set_access_token(env('TWITTER_ACCESS_TOKEN'), env('TWITTER_ACCESS_TOKEN_SECRET'))
    except KeyError:
        print("Either TWITTER_ACCESS_TOKEN or TWITTER_ACCESS_TOKEN_SECRET "
              "environment variables are missing. "
              "Tweepy will be initialized in 'app-only' mode")

    twapi = tweepy.API(auth)

    bot = TwitterForwarderBot(env('TELEGRAM_BOT_TOKEN'), twapi)

    bot.kb_interruptable_loop()
