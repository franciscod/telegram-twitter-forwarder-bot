import datetime
from peewee import Model, DateTimeField, ForeignKeyField, BigIntegerField, CharField, IntegerField, TextField
from playhouse.fields import ManyToManyField


class TwitterUser(Model):
    screen_name = CharField(unique=True)
    known_at = DateTimeField(default=datetime.datetime.now)
    name = CharField()

    @property
    def full_name(self):
        return "{} ({})".format(self.name, self.screen_name)


class TelegramChat(Model):
    chat_id = IntegerField(unique=True)
    known_at = DateTimeField(default=datetime.datetime.now)
    tg_type = CharField()
    last_contact = DateTimeField(default=datetime.datetime.now)
    subscriptions = ManyToManyField(TwitterUser, related_name="subscriptions")

    @property
    def is_group(self):
        return self.chat_id < 0

    def touch_contact(self):
        self.last_contact = datetime.datetime.now()
        self.save()


class Tweet(Model):
    tw_id = BigIntegerField(unique=True)
    known_at = DateTimeField(default=datetime.datetime.now)
    text = TextField()
    created_at = DateTimeField()
    twitter_user = ForeignKeyField(TwitterUser, related_name='tweets')
