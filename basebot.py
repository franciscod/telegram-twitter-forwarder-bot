import logging
import telegram

try:
    from queue import Queue
except ImportError:
    from Queue import Queue


class BaseBot(object):
    POLL_TIMEOUT = 1

    def __init__(self, token, update_offset=0):

        logging.getLogger("telegram.bot").setLevel(logging.WARNING)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.logger.info("Initializing")

        self.token = token
        self.tg = telegram.Bot(token=token)
        self.update_offset = update_offset
        self.queue = Queue()

    def poll(self):
        got_something = False

        for u in self.tg.getUpdates(offset=self.update_offset, timeout=self.POLL_TIMEOUT):
            self.queue.put(u)
            got_something = True

        return got_something

    def ack(self, update):
        self.update_offset = max(self.update_offset, update.update_id + 1)

    def handle(self, upd):
        if upd.message is not None:
            self.logger.debug("Got message: " + str(upd.message))
            text = upd.message.text

            action = None

            if text is not None:
                if text[:1] == '/' and len(text) > 1:
                    command, *args = text[1:].split()
                    if '@' in command:
                        command, uname = command.lower().split('@')
                        calling_me = (uname == self.tg.username.lower())

                    if '@' not in command or calling_me:
                        action = self.handle_cmd, upd.message, command, args
                else:
                    action = self.handle_chat, upd.message
            else:
                action = self.handle_other, upd.message

            if action is not None:

                fn, *args = action

                try:
                    fn(*args)

                except telegram.TelegramError as e:

                    self.logger.warning(
                        "TelegramError while handling message: " + str(e))

            self.ack(upd)

    def handle_cmd(self, msg, cmd, args):

        try:
            handler = getattr(self, 'cmd_' + cmd)
        except AttributeError:
            self.logger.warning('Command /' + cmd + ' not implemented.')
            return

        handler(msg, args)

    def cmd_ping(self, msg, args):
        self.reply(msg, 'Pong!')

    def handle_chat(self, msg):
        pass

    def handle_other(self, msg):
        pass

    def reply(self, msg, text, *args, **kwargs):
        self.tg.sendMessage(chat_id=msg.chat_id, text=text, *args, **kwargs)

    def loop(self):
        self.run = True

        while self.run:
            self.poll()

            while not self.queue.empty():
                self.handle(self.queue.get())

    def stop(self):
        self.run = False

    def kb_interruptable_loop(self):
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.DEBUG)

        try:
            self.loop()
        except KeyboardInterrupt:
            self.stop()
