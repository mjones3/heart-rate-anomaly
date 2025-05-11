FROM confluentinc/cp-kafka:latest

# Copy the Kafka setup script into the container
COPY setup_kafka.sh /setup_kafka.sh

# Ensure the script is executable by using root user (run as root)
USER root

# Make the setup script executable
RUN chmod +x /setup_kafka.sh

# Set the entrypoint to the setup script
ENTRYPOINT ["/setup_kafka.sh"]
