#!/bin/bash
set -e

# Kafka and Zookeeper configurations
KAFKA_BROKER="kafka:9093"
ZOOKEEPER="zookeeper:2181"
KAFKA_CLUSTER_NAME="vitals-cluster"
KAFKA_TOPIC="vitals"

# Wait for Zookeeper to be available
echo "Waiting for Zookeeper to be ready..."
until nc -z -v -w30 $ZOOKEEPER 2181; do
  echo "Waiting for Zookeeper..."
  sleep 1
done
echo "Zookeeper is ready."

# Start Kafka in the background
echo "Starting Kafka..."
kafka-server-start /etc/kafka/server.properties &

# Wait for Kafka to be fully up and running
echo "Waiting for Kafka to be ready..."
until kafka-topics --bootstrap-server $KAFKA_BROKER --list 2>/dev/null; do
  echo "Waiting for Kafka..."
  sleep 1
done
echo "Kafka is ready."

# Create Kafka topic
echo "Creating Kafka topic '$KAFKA_TOPIC'..."
kafka-topics --bootstrap-server $KAFKA_BROKER --create --topic $KAFKA_TOPIC --partitions 1 --replication-factor 1

# List topics to confirm creation
echo "Listing Kafka topics..."
kafka-topics --bootstrap-server $KAFKA_BROKER --list

# Keep the Kafka container running (this is required for the container to stay alive)
tail -f /dev/null
