import urllib.error
import logging
import telegram
import time


try:
    from queue import Queue, PriorityQueue
except ImportError:
    from Queue import Queue, PriorityQueue


class JobQueue(object):
    def __init__(self):
        self.queue = PriorityQueue()
        self.last_enqueued = None
        self.logger = logging.getLogger(self.__class__.__name__)

    def put(self, job, next_t=0):
        self.logger.debug("Putting a {} with t={}".format(job.__class__.__name__, next_t))
        re_enqueued_last = self.last_enqueued == job
        self.queue.put((next_t, job))
        self.last_enqueued = job
        return re_enqueued_last

    def tick(self):
        now = time.time()

        self.logger.debug("Ticking jobs with t={}".format(now))
        while not self.queue.empty():
            t, j = self.queue.queue[0]
            self.logger.debug("Peeked a {} with t={}".format(j.__class__.__name__, t))

            if t < now:
                self.queue.get()
                self.logger.debug("About time! running")
                j.run()
                self.put(j, now + j.INTERVAL)
                continue

            self.logger.debug("Next task isn't due yet. Finished!")
            break


class Job(object):
    INTERVAL = 10

    def run(self):
        pass

    def __lt__(self, other):
        return False


class BaseBot(object):
    POLL_TIMEOUT = 10

    def __init__(self, token, update_offset=0):

        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Initializing")

        self.token = token
        self.tg = telegram.Bot(token=token)
        self.update_offset = update_offset
        self.update_queue = Queue()
        self.job_queue = JobQueue()

    def poll(self):
        got_something = False

        while True:
            try:
                upds = self.tg.getUpdates(offset=self.update_offset, timeout=self.POLL_TIMEOUT)
                break
            except (telegram.error.TelegramError, urllib.error.URLError):
                self.logger.debug("Network error while polling, retrying...")
                time.sleep(1)

        for u in upds:
            self.update_queue.put(u)
            got_something = True

        return got_something

    def ack(self, update):
        self.update_offset = max(self.update_offset, update.update_id + 1)

    def handle(self, upd):
        if upd.message is not None:
            self.logger.debug("Got message: " + str(upd.message))
            text = upd.message.text

            action = None

            if len(text)is not 0:
                if text[:1] == '/' and len(text) > 1:
                    command, *args = text[1:].split()
                    if '@' in command:
                        command, uname, *_ = command.lower().split('@')
                        calling_me = (uname == self.tg.username.lower())

                    if '@' not in command or calling_me:
                        action = self.handle_cmd, upd.message, command.lower(), args
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
            self.logger.debug('Command /' + cmd + ' not implemented.')
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
            self.job_queue.tick()
            self.poll()

            while not self.update_queue.empty():
                self.handle(self.update_queue.get())

    def stop(self):
        self.run = False

    def kb_interruptable_loop(self):
        try:
            self.loop()
        except KeyboardInterrupt:
            self.stop()
