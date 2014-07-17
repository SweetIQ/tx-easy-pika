'''
Manage queue connections using Twisted and Pika.
'''

import pika
import json
import logging
import functools
from twisted.internet import defer, task, reactor
from pika.spec import BasicProperties

POLL_FREQ = 0.01

logger = logging.getLogger("txeasypika")


class InvalidRoutingKeyException(Exception):
    pass


class DeferToConnect():
    @classmethod
    def dispatch_queued_calls(cls, obj):
        ''' Fire off any queued-up calls we may have on this object. '''
        if not hasattr(obj, "queued_calls"):
            return

        # bind anything we have requested when we were connecting
        for method, args, kwargs in obj.queued_calls:
            method(obj, *args, **kwargs)
        obj.queued_calls = []

    def __call__(self, function):
        ''' A decorator that will queue up calls to a method and defer them to
        when we are actually connected. '''
        @functools.wraps(function)
        def _decorator(self, *args, **kwargs):
            if not self.channel:
                if not hasattr(self, "queued_calls"):
                    self.queued_calls = []

                self.queued_calls.append((function, args, kwargs))
                return

            function(*args, **kwargs)

        return _decorator


def proxy_to_channel(function):
    ''' A decorator to simply forward the call of a method to a ChannelProxy
    object. Note that the wrapped function is never called.'''
    @defer.inlineCallbacks
    def _decorator(self, *args, **kwargs):
        proxy = ChannelProxy(self.channel)
        yield getattr(proxy, function.__name__)(*args, **kwargs)

    return _decorator


def to_serializable(data):
    ''' Convert data to something that is JSON-serializable. '''
    if data is None or isinstance(data, int) or isinstance(data, float) or \
            isinstance(data, basestring):
        # some data types are converted as-is
        return data
    if isinstance(data, list):
        # Call recursively on nested structures
        return [to_serializable(d) for d in data]
    if isinstance(data, dict):
        # Call recursively on nested structures
        return {k: to_serializable(v) for k, v in data.iteritems()}

    # not in our list? just convert it to a string
    return str(data)


class ChannelProxy(object):
    ''' A little proxy to wrap around a channel object and make the interface
    a wee bit nicer. '''
    def __init__(self, channel):
        self.channel = channel

    def basic_publish(self, exchange, routing_key, message, properties=None,
                      mandatory=True, immediate=False):
        ''' Publish a message to an exchange.
        Arguments:
            - `exchange` - The exchange to publish to.
            - `routing_key` - The routing key to bind on.
            - `message` - The message to send. If this is not a string it will
                be serialized as JSON, and the properties.content_type field
                will be forced to be application/json.
            - `properties` - Dict of AMQP message properties.
            - `mandatory` - AMQP Mandatory flag.
            - `immediate` - AMQP Immediate flag.
        '''
        properties = BasicProperties(properties or {})

        if not isinstance(message, basestring):
            # Convert to JSON string if it's not a string
            message = json.dumps(to_serializable(message))
            properties.content_type = "application/json"

        if not isinstance(routing_key, basestring):
            raise InvalidRoutingKeyException("'%s' is not a valid routing key!" %
                                             routing_key)

        return self.channel.basic_publish(exchange, routing_key, message,
                                          properties=properties,
                                          mandatory=mandatory,
                                          immediate=immediate)

    def __getattr__(self, attr):
        return getattr(self.channel, attr)


class QueueConnection(object):

    def __init__(self, host="localhost", port=5672, username="guest",
                 password="guest", heartbeat=600, prefetch_count=1,
                 log_level=logging.WARNING):
        ''' Connect to the queues.
        Arguments:
            - `host` - The server that RabbitMQ is on.
            - `port` - The port that RabbitMQ is listening on.
            - `username` - Username for RabbitMQ.
            - `password` - Password for RabbitMQ.
            - `heartbeat` - Heartbeat frequency in seconds for RabbitMQ.
            - `prefetch_count` - How many messages to prefetch for this connection.
            - `log_level` - Logging level for Pika
        '''

        # Pika logs like crazy, let's disable it
        logging.getLogger("pika").setLevel(log_level)
        logging.getLogger("pika.frame").setLevel(log_level)
        logging.getLogger("pika.callback").setLevel(log_level)
        logging.getLogger("pika.channel").setLevel(log_level)
        logging.getLogger("pika.connection").setLevel(log_level)

        self.prefetch_count = prefetch_count

        self.channel = None
        self.connection = None

        # connect
        connection_params = pika.ConnectionParameters(
            host=host,
            port=port,
            credentials=pika.PlainCredentials(username, password),
            heartbeat_interval=heartbeat
        )
        pika.adapters.twisted_connection.TwistedConnection(
            connection_params,
            self._on_connect
        )

    def _on_close(self, *args, **kwargs):
        ''' Called when the Rabbit connection closes. '''
        # Default behaviour is to just quit
        logger.warning("Connection to Rabbit failed, going down.")
        reactor.stop()

    @defer.inlineCallbacks
    def _on_connect(self, connection):
        ''' Called when we have successfully connected. '''
        logger.debug("Connected to queues.")

        self.connection = connection

        connection.add_on_close_callback(self._on_close)

        self.channel = yield connection.channel()
        yield self.channel.basic_qos(prefetch_count=self.prefetch_count)

        DeferToConnect.dispatch_queued_calls(self)

        self.channel.confirm_delivery(self._on_confirm_delivery)

    def _on_confirm_delivery(self, method_frame):
        ''' Called when a delivery has been confirmed. '''
        if method_frame.method.NAME == "Basic.Nack":
            logger.error("Rabbit delivery tag %s failed" %
                         method_frame.method.delivery_tag)

    @DeferToConnect()
    @proxy_to_channel
    def basic_publish(self, *args, **kwargs):
        ''' Publish a message to the queues. '''
        pass

    @DeferToConnect()
    @proxy_to_channel
    def exchange_declare(self, *args, **kwargs):
        ''' Declare an exchange. '''
        pass

    @DeferToConnect()
    @defer.inlineCallbacks
    def bind(self, queue_name, exchange, routing_key, callback=None,
             arguments=None, no_ack=False):
        ''' Declare and bind a queue.
        Arguments:
            `queue_name` - The name of the queue we want to declare.
            `exchange` - The exchange of the initial binding on the new queue.
            `routing_key` - The routing key of the initial binding on the new
                queue.
            `callback` - A function to call when a message is received on this
                queue.  Arguments are (channel object, delivery tag,
                JSON-parsed message).
            `arguments` - AMQP Arguments for declaring the queue.
            `no_ack` - Whether this consumer will ack or not. Ignored if
                `callback` is None.

        Note that this will throw an exception if the exchange has not been
        declared. You can declare an exchange with exchange_declare().
        '''

        if arguments is None:
            arguments = {
                "x-ha-policy": "all"
            }

        @defer.inlineCallbacks
        def handle_message(queue_object):
            channel, method, header, message = yield queue_object.get()

            try:
                message = json.loads(message)
            except ValueError:
                # If the JSON can't be parsed, this message is broke - ack it
                # so that it doesn't hang out in the queue and break other
                # consumers
                logger.error("Error parsing JSON: %s" % message)
                channel.basic_ack(method.delivery_tag)
                return

            callback(ChannelProxy(channel), method.delivery_tag, message)

        logger.debug("Binding %s to %s/%s" % (queue_name, exchange, routing_key))

        yield self.channel.queue_declare(queue=queue_name,
                                         auto_delete=False,
                                         exclusive=False,
                                         durable=True,
                                         arguments=arguments)
        yield self.channel.queue_bind(queue=queue_name,
                                      exchange=exchange,
                                      routing_key=routing_key)

        if callback:
            # If they've passed in a callback, start up a looping call to
            # periodically check for messages on that queue.
            message_queue, ctag = yield self.channel.basic_consume(queue=queue_name,
                                                                   no_ack=no_ack)

            loop = task.LoopingCall(handle_message, message_queue)
            loop.start(POLL_FREQ)

    def close(self):
        ''' Close the connection to the queues. '''
        if self.channel:
            self.channel.close()

        if self.connection:
            self.connection.close()
