import os
import json
from confluent_kafka import Producer

# Fetch Kafka broker and topic from environment variables
kafka_broker = os.getenv('KAFKA_BROKER', 'kafka:9093')  # Default to 'kafka:9093' if not set
kafka_topic = os.getenv('KAFKA_TOPIC', 'vitals')  # Default to 'vitals' if not set

# Configure the Kafka producer
conf = {
    'bootstrap.servers': kafka_broker,  # Use the Kafka broker from the environment variable
    'client.id': 'vitals-producer'
}

# Create the Kafka producer
producer = Producer(conf)

# Callback to handle delivery reports
def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic} [{msg.partition}] at offset {msg.offset}")

# Function to send JSON string to Kafka
def send_json_to_kafka(json_str):
    try:
        # Parse the JSON string to a dictionary (if needed)
        data = json.loads(json_str)

        # Produce a message to the Kafka topic
        producer.produce(kafka_topic, json.dumps(data), callback=delivery_report)  # Use topic from environment
        producer.flush()  # Ensure message is sent before closing
        print(f"Message sent to topic {kafka_topic}")
    except Exception as e:
        print(f"Error producing message: {e}")