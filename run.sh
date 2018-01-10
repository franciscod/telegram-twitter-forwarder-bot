#!/bin/sh
if [ `pgrep -f telegram-twitter-forwarder-bot.py` ];
then
    echo "Already running"
    exit 1
else
    . venv/bin/activate
    . ./secrets.env
    python telegram-twitter-forwarder-bot.py
    exit 0
fi
