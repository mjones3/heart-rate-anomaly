FROM influxdb:2.6

# Copy the setup script into the container
COPY setup_influx.sh /setup_influx.sh

# Make the script executable
RUN chmod +x /setup_influx.sh

# Set the entrypoint to the setup script
ENTRYPOINT ["/setup_influx.sh"]
