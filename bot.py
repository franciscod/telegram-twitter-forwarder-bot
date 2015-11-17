from functools import wraps
import logging

import tweepy
from telegram.emoji import Emoji

from basebot import BaseBot, Job
from models import TwitterUser, Tweet, TelegramChat, Subscription


class FetchAndSendTweetsJob(Job):
    INTERVAL = 60

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(self.__class__.__name__)

    def run(self):
        self.logger.debug("Fetching tweets...")
        # fetch the tw users' tweets
        for tw_user in TwitterUser.select():
            if tw_user.subscriptions.count() == 0:
                self.logger.debug(
                    "Skipping {} because 0 subscriptions".format(tw_user.screen_name))
                continue

            try:
                if tw_user.last_tweet_id == 0:
                    # get just the latest tweet
                    self.logger.debug(
                        "Fetching the latest tweet from {}".format(tw_user.screen_name))
                    tweets = self.bot.tw.user_timeline(
                        screen_name=tw_user.screen_name,
                        count=1)
                else:
                    # get the fresh tweets
                    self.logger.debug(
                        "Fetching new tweets from {}".format(tw_user.screen_name))
                    tweets = self.bot.tw.user_timeline(
                        screen_name=tw_user.screen_name,
                        since_id=tw_user.last_tweet_id)

            except tweepy.error.TweepError:
                self.logger.debug(
                    "Whoops, I couldn't get tweets from {}!".format(tw_user.screen_name))
                continue

            for tweet in tweets:
                self.logger.debug("Got tweet: {}".format(tweet.text))
                tw, _created = Tweet.get_or_create(
                    tw_id=tweet.id,
                    text=tweet.text,
                    created_at=tweet.created_at,
                    twitter_user=tw_user,
                )

        # send the new tweets to subscribers
        for s in Subscription.select():
            # are there new tweets? send em all!
            self.logger.debug(
                "Checking subscription {} {}".format(s.tg_chat.chat_id, s.tw_user.screen_name))

            if s.last_tweet_id == 0:  # didn't receive any tweet yet
                try:
                    tw = (s.tw_user.tweets.select()
                           .order_by(Tweet.tw_id.desc())
                           .limit(1))[0]
                    self.logger.debug("Sending tweet {}".format(s.tg_chat.chat_id))
                    self.bot.send_tweet(s.tg_chat.chat_id, tw)

                    # save the latest tweet sent on this subscription
                    s.last_tweet_id = tw.tw_id
                    s.save()
                except IndexError:
                    self.logger.debug("No tweets available yet on {}".format(s.tw_user.screen_name))

                continue

            if s.tw_user.last_tweet_id > s.last_tweet_id:
                self.logger.debug("Some fresh tweets here!")
                for tw in (s.tw_user.tweets.select()
                            .where(Tweet.tw_id > s.last_tweet_id)
                            .order_by(Tweet.tw_id.desc())
                           ):
                    self.logger.debug("Sending tweet {}".format(s.tg_chat.chat_id))
                    self.bot.send_tweet(s.tg_chat.chat_id, tw)

                # save the latest tweet sent on this subscription
                s.last_tweet_id = s.tw_user.last_tweet_id
                s.save()
                continue

            self.logger.debug("No new tweets here.")


class TwitterForwarderBot(BaseBot):
    def __init__(self, token, tweepy_api_object):
        super().__init__(token)

        self.tw = tweepy_api_object
        self.job_queue.put(FetchAndSendTweetsJob(self))

        for t in (TwitterUser, TelegramChat, Tweet, Subscription):
            t.create_table(fail_silently=True)

    def send_tweet(self, chat_id, tweet):
        self.tg.sendMessage(
            chat_id=chat_id,
            disable_web_page_preview=True,
            text="""
{text}
--- {name} ({screen_name}) @ {created_at} UTC - https://twitter.com/{screen_name}/status/{tw_id}
"""
            .format(
                text=tweet.text,
                name=tweet.name,
                screen_name=tweet.screen_name,
                created_at=tweet.created_at,
                tw_id=tweet.tw_id,
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
        self.reply(
            msg,
            "Hello! This bot lets you subscribe to twitter accounts and receive their tweets here! "
            "Check out /help for more info.")

    @with_touched_chat
    def cmd_help(self, msg, args, chat=None):

        self.reply(msg, """
Hello! This bot forwards you updates from twitter streams!
Here's the commands:
- /sub - subscribes to updates from a user
- /unsub - unsubscribes to a user
- /list  - lists current subscriptions
- /all - shows you the latest tweets from all subscriptions
- /wipe - remove all the data about you and your subscriptions
- /source - info about source code
- /help - view help text
This bot is being worked on, so it may break sometimes. Contact @franciscod if you want {}
""".format(
            Emoji.SMILING_FACE_WITH_OPEN_MOUTH_AND_SMILING_EYES),
            disable_web_page_preview=True)

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

        self.reply(msg, "Okay, I'm forgetting about this chat. " + subs +
                        " Come back to me anytime you want. Goodbye!")
        chat.delete_instance(recursive=True)

    @with_touched_chat
    def cmd_source(self, msg, args, chat=None):
        self.reply(msg, "This bot is Free Software under the LGPLv3. "
                        "You can get the code from here: "
                        "https://github.com/franciscod/telegram-twitter-forwarder-bot")

    @with_touched_chat
    def cmd_all(self, msg, args, chat=None):
        subscriptions = list(Subscription.select().where(
                             Subscription.tg_chat == chat))

        if len(subscriptions) == 0:
            return self.reply(msg, 'You have no subscriptions, so no tweets to show!')

        text = ""

        for sub in subscriptions:
            tweet_text = sub.last_tweet.text if sub.last_tweet else "<no tweets yet>"
            text += "\n {}: {}".format(sub.tw_user.screen_name, tweet_text)

        self.reply(msg, text)

    @with_touched_chat
    def handle_chat(self, msg, chat=None):
        self.reply(msg, "Hey! use commands to talk with me, please!")
