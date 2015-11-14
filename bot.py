import logging
from functools import wraps

import tweepy
from envparse import Env
from telegram.emoji import Emoji

from basebot import BaseBot
from models import TwitterUser, Tweet, TelegramChat, Subscription


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

        for t in (TwitterUser, TelegramChat, Tweet, Subscription):
            t.create_table(fail_silently=True)

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

    def get_chat(self, tg_chat):
        db_chat, _created = TelegramChat.get_or_create(
            chat_id=tg_chat.id,
            tg_type=tg_chat.type,
        )
        return db_chat

    def get_tw_user(self, tw_username):
        try:
            tw_user = self.tw.get_user(tw_username)
        except tweepy.error.TweepError:
            return None

        db_user, _created = TwitterUser.get_or_create(
            screen_name=tw_user.screen_name,
            name=tw_user.name,
        )

        if not _created:
            if db_user.name != tw_user.name:
                db_user.name = tw_user.name
                db_user.save()

        return db_user

    def with_touched_chat(f):
        @wraps(f)
        def wrapper(self, msg=None, *args, **kwargs):
            if msg is None:
                return f(self, *args, **kwargs)

            chat = self.get_chat(msg.chat)
            chat.touch_contact()
            kwargs.update(chat=chat)

            return f(self, msg, *args, **kwargs)

        return wrapper

    @with_touched_chat
    def cmd_start(self, msg, args, chat=None):
        self.reply(msg, "Hello! I'm a work in progress bot for now! Check out /help for more info.")

    @with_touched_chat
    def cmd_help(self, msg, args, chat=None):

        self.reply(msg, """
Hello! This bot is intended to forward you updates from twitter streams!
Here's the commands that work:
- /sub username -- subscribes to updates from twitter.com/username
- /unsub username -- unsubscribes to that user
- /list  -- lists your current subscriptions
- /wipe -- I remove all the data about you and your subscriptions
- /source -- info about source code
IMPORTANT: Tweets aren't streamed back yet! Stay tuned!
This bot is being worked on, so it may not work at 100%. Contact @franciscod if you feel chatty {}
""".format(Emoji.SMILING_FACE_WITH_OPEN_MOUTH_AND_SMILING_EYES), disable_web_page_preview=True)

    @with_touched_chat
    def cmd_sub(self, msg, args, chat=None):
        if len(args) < 1:
            self.reply(msg, "Use /sub username")
            return
        tw_username = args[0]

        tw_user = self.get_tw_user(tw_username)

        if tw_user is None:
            self.reply(msg, "Sorry, I didn't found that username ({})!".format(
                tw_username
            ))
            return

        if Subscription.select().where(
                Subscription.tw_user == tw_user,
                Subscription.tg_chat == chat).count() == 1:
            self.reply(msg, "You're already subscribed to {}!".format(
                tw_username
            ))
            return

        Subscription.create(tg_chat=chat, tw_user=tw_user)

        self.reply(msg, """
OK, I've added your subscription to {}!
Remember, you can check your subscription list with /list
            """.format(tw_user.full_name))

    @with_touched_chat
    def cmd_unsub(self, msg, args, chat=None):
        if len(args) < 1:
            self.reply(msg, "Use /unsub username")
            return
        tw_username = args[0]

        tw_user = self.get_tw_user(tw_username)

        if tw_user is None or Subscription.select().where(
                Subscription.tw_user == tw_user,
                Subscription.tg_chat == chat).count() == 0:
            self.reply(msg, "I didn't found any subscription to {}!".format(tw_username))
            return

        Subscription.delete().where(
            Subscription.tw_user == tw_user,
            Subscription.tg_chat == chat).execute()

        self.reply(msg, "You are no longer subscribed to {}".format(tw_user.full_name))

    @with_touched_chat
    def cmd_list(self, msg, args, chat=None):
        subscriptions = list(Subscription.select().where(
                Subscription.tg_chat == chat))

        if len(subscriptions) == 0:
            return self.reply(msg, 'You have no subscriptions yet! Add one with /sub username')

        subs = ['']
        for sub in subscriptions:
            subs.append(sub.tw_user.full_name)

        subject = "This group is" if chat.is_group else "You are"

        self.reply(
            msg,
            subject + " subscribed to the following Twitter users:\n" +
            "\n - ".join(subs) + "\n\nYou can remove any of them using /unsub username")

    @with_touched_chat
    def cmd_wipe(self, msg, args, chat=None):
        subscriptions = list(Subscription.select().where(
                Subscription.tg_chat == chat))

        subs = "You had no subscriptions."
        if subscriptions:
            subs = ''.join([
                "For the record, you were subscribed to these users: ",
                ', '.join((s.tw_user.screen_name for s in subscriptions)),
                '.'])

        self.reply(msg, "Okay, I'm forgetting about this chat. " + subs + " Come back to me anytime you want. Goodbye!")
        chat.delete_instance(recursive=True)

    @with_touched_chat
    def cmd_source(self, msg, args, chat=None):
        self.reply(msg, """
This bot is Free Software under the LGPLv3. You can get the code from here: https://github.com/franciscod/telegram-twitter-forwarder-bot
            """)

    @with_touched_chat
    def handle_chat(self, msg, chat=None):
        self.reply(msg, "Okay, okay! Have a tweet:")

        for tweet in self.tw.user_timeline(screen_name='twitter', count=1):
            self.send_tweet(msg, tweet)


if __name__ == '__main__':

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.WARNING)

    logging.getLogger(TwitterForwarderBot.__name__).setLevel(logging.DEBUG)

    auth = tweepy.OAuthHandler(env('TWITTER_CONSUMER_KEY'), env('TWITTER_CONSUMER_SECRET'))

    try:
        auth.set_access_token(env('TWITTER_ACCESS_TOKEN'), env('TWITTER_ACCESS_TOKEN_SECRET'))
    except KeyError:
        print("Either TWITTER_ACCESS_TOKEN or TWITTER_ACCESS_TOKEN_SECRET environment variables are missing. " +
              "Tweepy will be initialized in 'app-only' mode")

    twapi = tweepy.API(auth)

    bot = TwitterForwarderBot(env('TELEGRAM_BOT_TOKEN'), twapi)

    bot.kb_interruptable_loop()
