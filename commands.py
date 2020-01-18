import json
from datetime import datetime

from pytz import timezone
from pytz.exceptions import UnknownTimeZoneError
import telegram
from telegram.emoji import Emoji
import tweepy
from tweepy.auth import OAuthHandler
from tweepy.error import TweepError

from models import Subscription
from util import with_touched_chat, escape_markdown, markdown_twitter_usernames

TIMEZONE_LIST_URL = "https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"

def cmd_ping(bot, update):
    bot.reply(update, 'Pong!')


@with_touched_chat
def cmd_start(bot, update, chat=None):
    bot.reply(
        update,
        "Hello! This bot lets you subscribe to twitter accounts and receive their tweets here! "
        "Check out /help for more info.")


@with_touched_chat
def cmd_help(bot, update, chat=None):
        bot.reply(update, """
Hello! This bot forwards you updates from twitter streams!
Here's the commands:
- /sub - subscribes to updates from users
- /unsub - unsubscribes from users
- /list  - lists current subscriptions
- /export - sends you a /sub command that contains all current subscriptions
- /all - shows you the latest tweets from all subscriptions
- /wipe - remove all the data about you and your subscriptions
- /auth - start Twitter authorization process
- /verify - send Twitter verifier code to complete authorization process
- /export\_friends - generate /sub command to subscribe to all your Twitter friends (authorization required)
- /set\_timezone - set your [timezone name]({}) (for example Asia/Tokyo)
- /source - info about source code
- /help - view help text
This bot is free open source software, check /source if you want to host it!
""".format(
            TIMEZONE_LIST_URL),
                  disable_web_page_preview=True,
                  parse_mode=telegram.ParseMode.MARKDOWN)


@with_touched_chat
def cmd_sub(bot, update, args, chat=None):
    if len(args) < 1:
        bot.reply(update, "Use /sub username1 username2 username3 ...")
        return
    tw_usernames = args
    not_found = []
    already_subscribed = []
    successfully_subscribed = []

    for tw_username in tw_usernames:
        tw_user = bot.get_tw_user(tw_username)

        if tw_user is None:
            not_found.append(tw_username)
            continue

        if Subscription.select().where(
                Subscription.tw_user == tw_user,
                Subscription.tg_chat == chat).count() == 1:
            already_subscribed.append(tw_user.full_name)
            continue

        Subscription.create(tg_chat=chat, tw_user=tw_user)
        successfully_subscribed.append(tw_user.full_name)

    reply = ""

    if len(not_found) is not 0:
        reply += "Sorry, I didn't find username{} {}\n\n".format(
                     "" if len(not_found) is 1 else "s",
                     ", ".join(not_found)
                 )

    if len(already_subscribed) is not 0:
        reply += "You're already subscribed to {}\n\n".format(
                     ", ".join(already_subscribed)
                 )

    if len(successfully_subscribed) is not 0:
        reply += "I've added your subscription to {}".format(
                     ", ".join(successfully_subscribed)
                 )

    bot.reply(update, reply)


@with_touched_chat
def cmd_unsub(bot, update, args, chat=None):
    if len(args) < 1:
        bot.reply(update, "Use /unsub username1 username2 username3 ...")
        return
    tw_usernames = args
    not_found = []
    successfully_unsubscribed = []

    for tw_username in tw_usernames:
        tw_user = bot.get_tw_user(tw_username)

        if tw_user is None or Subscription.select().where(
                Subscription.tw_user == tw_user,
                Subscription.tg_chat == chat).count() == 0:
            not_found.append(tw_username)
            continue

        Subscription.delete().where(
            Subscription.tw_user == tw_user,
            Subscription.tg_chat == chat).execute()

        successfully_unsubscribed.append(tw_user.full_name)

    reply = ""

    if len(not_found) is not 0:
        reply += "I didn't find any subscription to {}\n\n".format(
                     ", ".join(not_found)
                 )

    if len(successfully_unsubscribed) is not 0:
        reply += "You are no longer subscribed to {}".format(
                     ", ".join(successfully_unsubscribed)
        )

    bot.reply(update, reply)


@with_touched_chat
def cmd_list(bot, update, chat=None):
    subscriptions = list(Subscription.select().where(
                         Subscription.tg_chat == chat))

    if len(subscriptions) == 0:
        return bot.reply(update, 'You have no subscriptions yet! Add one with /sub username')

    subs = ['']
    for sub in subscriptions:
        subs.append(sub.tw_user.full_name)

    subject = "This group is" if chat.is_group else "You are"

    bot.reply(
        update,
        subject + " subscribed to the following Twitter users:\n" +
        "\n - ".join(subs) + "\n\nYou can remove any of them using /unsub username")


@with_touched_chat
def cmd_export(bot, update, chat=None):
    subscriptions = list(Subscription.select().where(
                         Subscription.tg_chat == chat))

    if len(subscriptions) == 0:
        return bot.reply(update, 'You have no subscriptions yet! Add one with /sub username')

    subs = ['']
    for sub in subscriptions:
        subs.append(sub.tw_user.screen_name)

    subject = "Use this to subscribe to all subscribed Twitter users in another chat:\n\n"

    bot.reply(
        update,
        subject + "/sub " + " ".join(subs))


@with_touched_chat
def cmd_wipe(bot, update, chat=None):
    subscriptions = list(Subscription.select().where(
                         Subscription.tg_chat == chat))

    subs = "You had no subscriptions."
    if subscriptions:
        subs = ''.join([
            "For the record, you were subscribed to these users: ",
            ', '.join((s.tw_user.screen_name for s in subscriptions)),
            '.'])

    bot.reply(update, "Okay, I'm forgetting about this chat. " + subs +
                    " Come back to me anytime you want. Goodbye!")
    chat.delete_instance(recursive=True)


@with_touched_chat
def cmd_source(bot, update, chat=None):
    bot.reply(update, "This bot is Free Software under the LGPLv3. "
                    "You can get the code from here: "
                    "https://github.com/franciscod/telegram-twitter-forwarder-bot")


@with_touched_chat
def cmd_all(bot, update, chat=None):
    subscriptions = list(Subscription.select().where(
                         Subscription.tg_chat == chat))

    if len(subscriptions) == 0:
        return bot.reply(update, 'You have no subscriptions, so no tweets to show!')

    text = ""

    for sub in subscriptions:
        if sub.last_tweet is None:
            text += "\n{screen_name}: <no tweets yet>".format(
                screen_name=escape_markdown(sub.tw_user.screen_name),
            )
        else:
            text += ("\n{screen_name}:\n{text} "
                     "[link](https://twitter.com/{screen_name}/status/{tw_id})").format(
                text=markdown_twitter_usernames(escape_markdown(sub.last_tweet.text)),
                tw_id=sub.last_tweet.tw_id,
                screen_name=escape_markdown(sub.tw_user.screen_name),
            )

    bot.reply(update, text,
              disable_web_page_preview=True,
              parse_mode=telegram.ParseMode.MARKDOWN)


@with_touched_chat
def cmd_get_auth_url(bot, update, chat):
    auth = OAuthHandler(bot.tw.auth.consumer_key, bot.tw.auth.consumer_secret)
    auth_url = auth.get_authorization_url()
    chat.twitter_request_token = json.dumps(auth.request_token)
    chat.save()
    msg = "go to [this url]({}) and send me your verifier code using /verify code"
    bot.reply(update, msg.format(auth_url),
              parse_mode=telegram.ParseMode.MARKDOWN)


@with_touched_chat
def cmd_verify(bot, update, args, chat):
    if not chat.twitter_request_token:
        bot.reply(update, "Use /auth command first")
        return
    if len(args) < 1:
        bot.reply(update, "No verifier code specified")
        return
    verifier_code = args[0]
    auth = OAuthHandler(bot.tw.auth.consumer_key, bot.tw.auth.consumer_secret)
    auth.request_token = json.loads(chat.twitter_request_token)
    try:
        auth.get_access_token(verifier_code)
    except TweepError:
        bot.reply(update, "Invalid verifier code. Use /auth again")
        return
    chat.twitter_token = auth.access_token
    chat.twitter_secret = auth.access_token_secret
    chat.save()
    bot.reply(update, "Access token setup complete")
    api = tweepy.API(auth)
    settings = api.get_settings()
    tz_name = settings.get("time_zone", {}).get("tzinfo_name")
    cmd_set_timezone(bot, update, [tz_name])


@with_touched_chat
def cmd_export_friends(bot, update, chat):
    if not chat.is_authorized:
        if not chat.twitter_request_token:
            bot.reply(update, "You have not authorized yet. Use /auth to do it")
        else:
            bot.reply(update, "You have not verified your authorization yet. Use /verify code to do it")
        return
    bot_auth = bot.tw.auth
    api = chat.tw_api(bot_auth.consumer_key, bot_auth.consumer_secret)
    screen_names = [f.screen_name for f in tweepy.Cursor(api.friends).items()]
    bot.reply(update, "Use this to subscribe to all your Twitter friends:")
    bot.reply(update, "/sub {}".format(" ".join(screen_names)))


@with_touched_chat
def cmd_set_timezone(bot, update, args, chat):
    if len(args) < 1:
        bot.reply(update,
            "No timezone specified. Find yours [here]({})!".format(TIMEZONE_LIST_URL),
            parse_mode=telegram.ParseMode.MARKDOWN)
        return

    tz_name = args[0]

    try:
        tz = timezone(tz_name)
        chat.timezone_name = tz_name
        chat.save()
        tz_str = datetime.now(tz).strftime('%Z %z')
        bot.reply(update, "Timezone is set to {}".format(tz_str))
    except UnknownTimeZoneError:
        bot.reply(update,
            "Unknown timezone. Find yours [here]({})!".format(TIMEZONE_LIST_URL),
            parse_mode=telegram.ParseMode.MARKDOWN)


@with_touched_chat
def handle_chat(bot, update, chat=None):
    bot.reply(update, "Hey! Use commands to talk with me, please! See /help")
