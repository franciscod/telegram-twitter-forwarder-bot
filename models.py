import datetime
from peewee import (Model, DateTimeField, ForeignKeyField, BigIntegerField, CharField,
                    IntegerField, TextField)


class TwitterUser(Model):
    screen_name = CharField(unique=True)
    known_at = DateTimeField(default=datetime.datetime.now)
    name = CharField()

    @property
    def full_name(self):
        return "{} ({})".format(self.name, self.screen_name)

    @property
    def last_tweet_id(self):
        if self.tweets.count() == 0:
            return 0

        return self.tweets.order_by(Tweet.tw_id.desc()).limit(1)[0].tw_id


class TelegramChat(Model):
    chat_id = IntegerField(unique=True)
    known_at = DateTimeField(default=datetime.datetime.now)
    tg_type = CharField()
    last_contact = DateTimeField(default=datetime.datetime.now)

    @property
    def is_group(self):
        return self.chat_id < 0

    def touch_contact(self):
        self.last_contact = datetime.datetime.now()
        self.save()


class Subscription(Model):
    tg_chat = ForeignKeyField(TelegramChat, related_name="subscriptions")
    tw_user = ForeignKeyField(TwitterUser, related_name="subscriptions")
    known_at = DateTimeField(default=datetime.datetime.now)
    last_tweet_id = BigIntegerField(default=0)

    @property
    def last_tweet(self):
        if self.last_tweet_id == 0:
            return None

        return Tweet.get(Tweet.tw_id == self.last_tweet_id)


class Tweet(Model):
    tw_id = BigIntegerField(unique=True)
    known_at = DateTimeField(default=datetime.datetime.now)
    text = TextField()
    created_at = DateTimeField()
    twitter_user = ForeignKeyField(TwitterUser, related_name='tweets')

    @property
    def screen_name(self):
        return self.twitter_user.screen_name

    @property
    def name(self):
        return self.twitter_user.name
