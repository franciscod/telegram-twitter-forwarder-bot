import logging
from os import environ

import tweepy
from telegram.ext import CommandHandler
from telegram.ext import Updater
from telegram.ext.messagehandler import MessageHandler, Filters

from bot import TwitterForwarderBot
from commands import *
from job import FetchAndSendTweetsJob

if "TELEGRAM_BOT_TOKEN" in environ:
    # The project is using environment vars, so load from those
    if "TWITTER_ACCESS_TOKEN" in environ:
        # The project explicitly has twitter access token, so use that in the dict
        env = dict(
            TELEGRAM_BOT_TOKEN=environ.get("TELEGRAM_BOT_TOKEN"),
            TWITTER_CONSUMER_KEY=environ.get("TWITTER_CONSUMER_KEY"),
            TWITTER_CONSUMER_SECRET=environ.get("TWITTER_CONSUMER_SECRET"),

            # Optionals
            TWITTER_ACCESS_TOKEN=environ.get("TWITTER_ACCESS_TOKEN"),
            TWITTER_ACCESS_TOKEN_SECRET=environ.get("TWITTER_ACCESS_TOKEN_SECRET"),
        )
    else:
        # The project doesn't have an access token, so don't add the keys so the checks below pass
        env = dict(
            TELEGRAM_BOT_TOKEN=environ.get("TELEGRAM_BOT_TOKEN"),
            TWITTER_CONSUMER_KEY=environ.get("TWITTER_CONSUMER_KEY"),
            TWITTER_CONSUMER_SECRET=environ.get("TWITTER_CONSUMER_SECRET"),
        )
else:
    # The project isn't using environment vars, so we should use the secrets file instead
    try:
        from secrets import env
    except ImportError:

        print("""
        CONFIGURATION ERROR: missing secrets.py!
    
        Make sure you have copied secrets.example.py into secrets.py and completed it!
        See README.md for extra info.
    """)
        exit(42)

if __name__ == '__main__':

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.WARNING)

    logging.getLogger(TwitterForwarderBot.__name__).setLevel(logging.DEBUG)
    logging.getLogger(FetchAndSendTweetsJob.__name__).setLevel(logging.DEBUG)

    # initialize Twitter API
    try:
        auth = tweepy.OAuthHandler(env['TWITTER_CONSUMER_KEY'], env['TWITTER_CONSUMER_SECRET'])
    except KeyError as exc:
        var = exc.args[0]
        print(("The required configuration variable {} is missing. "
               "Please review secrets.py.").format(var))
        exit(123)

    try:
        auth.set_access_token(env['TWITTER_ACCESS_TOKEN'], env['TWITTER_ACCESS_TOKEN_SECRET'])
    except KeyError as exc:
        var = exc.args[0]
        print(("The optional configuration variable {} is missing. "
               "Tweepy will be initialized in 'app-only' mode.").format(var))

    twapi = tweepy.API(auth)

    # initialize telegram API
    token = env['TELEGRAM_BOT_TOKEN']
    updater = Updater(bot=TwitterForwarderBot(token, twapi))
    dispatcher = updater.dispatcher

    # set commands
    dispatcher.add_handler(CommandHandler('start', cmd_start))
    dispatcher.add_handler(CommandHandler('help', cmd_help))
    dispatcher.add_handler(CommandHandler('ping', cmd_ping))
    dispatcher.add_handler(CommandHandler('sub', cmd_sub, pass_args=True))
    dispatcher.add_handler(CommandHandler('unsub', cmd_unsub, pass_args=True))
    dispatcher.add_handler(CommandHandler('list', cmd_list))
    dispatcher.add_handler(CommandHandler('export', cmd_export))
    dispatcher.add_handler(CommandHandler('all', cmd_all))
    dispatcher.add_handler(CommandHandler('wipe', cmd_wipe))
    dispatcher.add_handler(CommandHandler('source', cmd_source))
    dispatcher.add_handler(CommandHandler('auth', cmd_get_auth_url))
    dispatcher.add_handler(CommandHandler('verify', cmd_verify, pass_args=True))
    dispatcher.add_handler(CommandHandler('export_friends', cmd_export_friends))
    dispatcher.add_handler(CommandHandler('set_timezone', cmd_set_timezone, pass_args=True))
    dispatcher.add_handler(MessageHandler([Filters.text], handle_chat))

    # put job
    queue = updater.job_queue
    queue.put(FetchAndSendTweetsJob(), next_t=0)

    # poll
    updater.start_polling()
