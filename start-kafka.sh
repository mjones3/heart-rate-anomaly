#!/bin/bash

# Start the Docker Compose services (Zookeeper and Kafka)
docker-compose up -d

# Wait for Kafka to be ready (this assumes Kafka listens on port 9093)
echo "Waiting for Kafka to start..."
while ! nc -z localhost 9093; do
  sleep 1
done
echo "Kafka is up and running!"

# Create the Kafka topic 'vitals'
echo "Creating Kafka topic 'vitals'..."
docker exec -it $(docker ps -q -f "name=kafka") kafka-topics.sh --create --topic vitals --partitions 1 --replication-factor 1 --bootstrap-server localhost:9093

# Verify the topic was created
echo "Verifying the topic 'vitals'..."
docker exec -it $(docker ps -q -f "name=kafka") kafka-topics.sh --list --bootstrap-server localhost:9093

echo "Kafka topic 'vitals' created successfully!"
