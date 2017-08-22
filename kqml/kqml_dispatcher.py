import logging
from threading import Thread
from kqml.kqml_exceptions import KQMLException

logger = logging.getLogger('KQMLDispatcher')

class KQMLDispatcher(object):
    def __init__(self, rec, inp, agent_name):
        super(KQMLDispatcher, self).__init__()
        self.receiver = rec
        self.reader = inp
        self.reply_continuations = {}
        self.counter = 0
        self.name = 'KQML-Dispatcher-%d' % self.counter
        self.agent_name = agent_name
        self.logger = logging.getLogger(agent_name)
        self.counter += 1
        self.shutdown_initiated = False
        self._handle = None
        
    def _watch(self):
        try:
            while not self.shutdown_initiated:
                msg = self.reader.read_performative()
                self.dispatch_message(msg)
        # FIXME: not handling KQMLException and
        # KQMLBadCharacterException
        except KeyboardInterrupt:
            self.receiver.receive_eof()
        except EOFError:
            self.receiver.receive_eof()
        except IOError as ex:
            if not self.shutdown_initiated:
                self.receiver.handle_exception(ex)
        except ValueError:
            pass
        return

    def start(self):
        if self._handle is None and not self.shutdown_initiated:
            self._handle = Thread(target = self._watch, name = "watcher")
            self._handle.start()
        else:
            raise KQMLException(
                "Something went wrong trying to start watcher thread."
                )
        return

    def warn(self, msg):
        logger.warning(msg)

    def shutdown(self):
        self.shutdown_initiated = True
        if self._handle.is_alive():
            self._handle.join(5)
        if self._handle.is_alive():
            raise KQMLException(
                "Something went wrong shutting down watcher."
                )
        try:
            # FIXME: print thread info instead of blank quotes
            self.logger.error('KQML dispatcher shutdown: ' + '' +
                              ': closing reader')
            self.reader.close()
            # FIXME: print thread info instead of blank quotes
            self.logger.error('KQML dispatcher shutdown: ' + '' +
                              ': done')
        except IOError:
            logger.error('KQML dispatched IOError.')
            pass

    def dispatch_message(self, msg):
        verb = msg.head()
        if verb is None:
            self.receiver.receive_message_missing_verb(msg)
            return
        reply_id_obj = msg.get('in-reply-to')
        if reply_id_obj is not None:
            reply_id = reply_id_obj.string_value().upper()
            try:
                value = self.reply_continuations[reply_id]
                value.receive(msg)
                self.reply_continuations.pop(reply_id, 0)
                return
            except KeyError:
                pass

        vl = verb.lower()
        content = msg.get('content')
        content_msg_types = ['ask-if', 'ask-all', 'ask-one', 'stream-all', 
                             'tell', 'untell', 'deny', 'insert', 'uninsert',
                             'delete-one', 'delete-all', 'undelete', 'achieve',
                             'unachieve', 'advertise', 'subscribe', 'standby', 
                             'register', 'forward', 'broadcast', 
                             'transport-address', 'broker-one', 'broker-all',
                             'recommend-one', 'recommend-all', 'recruit-one',
                             'recruit-all', 'reply', 'request']
        msg_only_types = ['eos', 'error', 'sorry', 'ready', 'next', 'next', 'rest',
                          'discard', 'unregister']
        
        method_name = 'receive_' + vl.replace('-', '_')
        if vl in content_msg_types:
            if content is None:
                self.receiver.receive_message_missing_content(msg)
                return
            
            for cmt in content_msg_types:
                if vl == cmt:
                    self.receiver.__getattribute__(method_name)(msg, content)
        elif vl in msg_only_types:
            for cmt in msg_only_types:
                self.receiver.__getattribute__(method_name)(msg)
        else:
            self.receiver.recieve_other_performative(msg)
        
        return


    def add_reply_continuation(self, reply_id, cont):
        self.reply_continuations[reply_id.upper()] = cont
