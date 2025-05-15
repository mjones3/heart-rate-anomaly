import json
import os
import logging
from kafka import KafkaConsumer, KafkaAdminClient
from kafka.errors import KafkaError  # Corrected this import
from influxdb_client import InfluxDBClient, Point, WritePrecision
from datetime import datetime
import time

# Setup custom logger
logger = logging.getLogger("vital-timeseries-consumer")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Access environment variables
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9093")
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "vitals")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "pst")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "your-token")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "vitals")

# Initialize InfluxDB client
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN)
write_api = client.write_api()

# Function to check if Kafka brokers are available
def check_kafka_brokers():
    try:
        # Create a KafkaAdminClient to interact with Kafka brokers
        admin_client = KafkaAdminClient(bootstrap_servers=KAFKA_BROKER)
        admin_client.list_topics()  # List topics to check if brokers are available
        return True
    except KafkaError as e:  # Catch KafkaError
        logger.error(f"Error checking Kafka brokers: {e}")
        return False

# Function to check if the Kafka topic exists
def check_kafka_topic():
    try:
        # Create a KafkaAdminClient to check for the topic
        admin_client = KafkaAdminClient(bootstrap_servers=KAFKA_BROKER)
        topics = admin_client.list_topics()  # Get all available topics
        logger.info(f"Available Kafka topics: {topics}")  # Log the available topics
        if KAFKA_TOPIC in topics:
            return True
        else:
            logger.warning(f"Topic {KAFKA_TOPIC} not found, retrying...")
            return False
    except KafkaError as e:  # Catch KafkaError
        logger.error(f"Error checking Kafka topic: {e}")
        return False

# Wait until Kafka brokers are available and the topic exists
while not check_kafka_brokers() or not check_kafka_topic():
    logger.info("Waiting for Kafka brokers and topic...")
    time.sleep(5)  # Wait 5 seconds before retrying

# Initialize Kafka consumer after Kafka brokers and topic are available
logger.info(f"Consuming messages from topic {KAFKA_TOPIC}...")
consumer = KafkaConsumer(
    KAFKA_TOPIC,
    bootstrap_servers=KAFKA_BROKER,
    auto_offset_reset='earliest',  # Start consuming from the earliest message if no offset exists
    group_id=None  # Prevent offset tracking by the consumer group
)

logger.info(f"Subscribed topics: {consumer.subscription()}")  # Log the subscription details

for message in consumer:
    logger.info(f"Received message: {message.value}")  # Log received message

    try:
        # Decode the JSON message
        data = json.loads(message.value)

        # Pull out patient_id and timestamp
        patient_id    = data['patient_id']
        timestamp_str = data['time']
        timestamp     = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ")

        # Build a single point with all remaining fields
        point = (
            Point("patient_vitals")
              .tag("patient_id", patient_id)
              .time(timestamp, WritePrecision.NS)
        )

        # Dynamically add every other field in the JSON as a field on the point
        for field_name, field_value in data.items():
            if field_name in ('patient_id', 'time'):
                continue
            point = point.field(field_name, field_value)

        # Write the complete point to InfluxDB
        write_api.write(INFLUXDB_BUCKET, INFLUXDB_ORG, [point])
        logger.info(
            f"Written data for patient {patient_id} at {timestamp_str}: "
            + ", ".join(f"{k}={v!r}" for k, v in data.items() if k not in ('patient_id','time'))
        )

    except Exception as e:
        logger.error(f"Error processing message: {e}")

# Close InfluxDB client
client.close()
logger.info("InfluxDB client closed.")
