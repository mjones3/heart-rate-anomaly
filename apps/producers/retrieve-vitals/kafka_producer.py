# kafka_producer.py

import os
import json
from confluent_kafka import Producer

# Fetch Kafka broker and topic from environment variables
kafka_broker = os.getenv('KAFKA_BROKER', 'kafka:9093')
kafka_topic  = os.getenv('KAFKA_TOPIC',  'vitals')

# Configure the Kafka producer with compression and linger
conf = {
    'bootstrap.servers':       kafka_broker,
    'client.id':               'vitals-producer',
    'compression.codec':       'lz4',     # or 'gzip', 'snappy', 'zstd', 'none'
    'linger.ms':               100,       # wait up to 100 ms to group messages
    'batch.num.messages':      1000,      # up to 1000 msgs per batch
    # you can also tune buffer sizes:
    # 'queue.buffering.max.kbytes':  10240,   # in KB
    # 'queue.buffering.max.messages': 10000,
}

producer = Producer(conf)

def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic} [{msg.partition}] at offset {msg.offset}")

def send_json_to_kafka(json_str):
    """
    Produce a JSON message, then poll the producer once to serve delivery
    callbacks and free internal queue space.
    """
    try:
        data = json.loads(json_str)
        producer.produce(
            topic=kafka_topic,
            key=None,
            value=json.dumps(data),
            callback=delivery_report
        )
        # Immediately poll to handle delivery callbacks and clear out delivered messages
        producer.poll(0)
        print(f"Queued message to topic {kafka_topic}")
    except Exception as e:
        print(f"Error producing message: {e}")

# Optional: before your app exits, ensure all outstanding messages are sent
def shutdown_producer():
    producer.flush()
