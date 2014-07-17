from datetime import datetime
from txeasypika import QueueConnection
from twisted.internet import reactor


def callback(channel, tag, message):
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
