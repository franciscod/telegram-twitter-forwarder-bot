# telegram-twitter-forwarder-bot

You'll need a telegram bot token, you can get it via BotFather [more info here](https://core.telegram.org/bots).

Also, setting this up will need an Application-only authentication token from Twitter [more info here](https://dev.twitter.com/oauth/application-only). Optionally, you can provide a user access token and secret.

You can get this by creating a Twitter App [here](https://apps.twitter.com/).

Bear in mind that if you don't have added a mobile phone to your Twitter account you'll get this:

>You must add your mobile phone to your Twitter profile before creating an application. Please read https://support.twitter.com/articles/110250-adding-your-mobile-number-to-your-account-via-web for more information.

Get a consumer key, consumer secret, access token and access token secret (the latter two are optional), fill in your `secrets.env` and then run the bot!

```
$ source secrets.env
$ python bot.py
```
