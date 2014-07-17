# Description

A wrapper around pika's Twisted connection to make it simpler to use.

Main assumptions:

* All messages are JSON. Non-JSON messages log an error and are acked immediately. You can publish non-JSON messages, any non-strings that are published are converted to JSON strings.
* All you really want to do is consume and publish.

# Installation

Use pip:

    pip install tx-easy-pika

# Usage

## Example

```python
from datetime import datetime
from txeasypika import QueueConnection
from twisted.internet import reactor


def callback(channel, tag, message):
    ''' This function will be called whenever the server sends us a message. '''
    print "Received a message:"
    print message
    channel.basic_ack(tag)

queues = QueueConnection()

# Create an exchange
queues.exchange_declare(exchange="test-exchange")

# Set up a listener on a queue
queues.bind("my-queue", "test-exchange", "test-routing-key", callback)

# Now publish some messages to that queue
# Note that this message will not be published until we have started the
# Twisted reactor and we have successfully connected to Rabbit.
for i in range(5):
    queues.basic_publish("test-exchange", "test-routing-key", {
        "value": i,
        "message_data": "This is a message",
        "nested_field": {
            "an_array": ["this has an array"],
            "a_date": datetime.now()
        }
    })

# Start up the reactor
reactor.run()
```

## QueueConnection

Class to represent a connection to the queues.

### __init__()

Construct a new connection to the queues. Note that this is based on Twisted,
so no connection is actually made until the reactor is running.

Arguments:
- `host` (str) - The server that RabbitMQ is on.
- `port` (str) - The port that RabbitMQ is listening on.
- `username` (str) - Username for RabbitMQ.
- `password` (str) - Password for RabbitMQ.
- `heartbeat` (int) - Heartbeat frequency in seconds for RabbitMQ.
- `prefetch_count` (int) - How many messages to prefetch for this connection.
- `log_level` (logging log level) - Logging level for Pika

### basic_publish()

Publish a message to the queues. This is a deferred method, the actual call
will be made when the system has successfully connected to the AMQP server.

Arguments:
- `exchange` (str or unicode sequence of these characters: letters, digits, hyphen, underscore, period, or colon.) - The exchange to publish to.
- `routing_key` (str) - The routing key to bind on.
- `message` (anything) - The message to send. If this is not a string it will be serialized as JSON, and the properties.content_type field will be forced to be application/json.
- `properties` (dict) - Dict of AMQP message properties.
- `mandatory` (bool) - AMQP Mandatory flag.
- `immediate` (bool) - AMQP Immediate flag.

### exchange_declare()

Declare an exchange. This is a deferred method, the actual call will be made
when the system has successfully connected to the AMQP server.

If `passive` set, the server will reply with Declare-Ok if the exchange already
exists with the same name, and raise an error if not and if the exchange does
not already exist, the server MUST raise a channel exception with reply code
404 (not found).

Parameters:	

- `callback` (method) – Call this method on Exchange.DeclareOk
- `exchange` (str or unicode sequence of these characters: letters, digits, hyphen, underscore, period, or colon.) – The exchange name consists of a non-empty
- `exchange_type` (str) – The exchange type to use
- `passive` (bool) – Perform a declare or just check to see if it exists
- `durable` (bool) – Survive a reboot of RabbitMQ
- `auto_delete` (bool) – Remove when no more queues are bound to it
- `internal` (bool) – Can only be published to by other exchanges
- `nowait` (bool) – Do not expect an Exchange.DeclareOk response
- `arguments` (dict) – Custom key/value pair arguments for the exchange

### bind()

Declare a queue, create a binding on it. Optionally attach a function to call.
Note that the function will be called once for each call to `bind()`

- `queue_name` (str) - The name of the queue we want to declare.
- `exchange` (str) - The exchange of the initial binding on the new queue.
- `routing_key` (str) - The routing key of the initial binding on the new queue.
- `callback` (function) - A function to call when a message is received on this queue.  Arguments are (channel object, delivery tag, JSON-parsed message).
- `arguments` (dict) - AMQP Arguments for declaring the queue.
- `no_ack` (bool) - Whether this consumer will ack or not. Ignored if `callback` is None.

### close()

Close the connection to the AMQP server.
