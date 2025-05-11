#!/bin/bash
set -e

# InfluxDB URL and organization details
INFLUX_URL="http://localhost:8086"
ORG_NAME="pst"
BUCKET_NAME="vitals"
USER_NAME="service"
USER_PASSWORD="password"

# Wait for InfluxDB to be ready
echo "Waiting for InfluxDB to be ready..."
until influx ping -t "" --host "$INFLUX_URL" &>/dev/null; do
  sleep 1
done
echo "InfluxDB is ready."

# Create user
echo "Creating user '$USER_NAME'..."
USER_ID=$(influx user create --name "$USER_NAME" --password "$USER_PASSWORD" --org "$ORG_NAME" --host "$INFLUX_URL" -t "" | grep -oP '(?<=ID: ).*')

# Generate token for the user
echo "Generating token for user '$USER_NAME'..."
TOKEN=$(influx auth create -u "$USER_NAME" -o "$ORG_NAME" --read-buckets --write-buckets --host "$INFLUX_URL" -t "" | grep -oP '(?<=Token: ).*')

# Create bucket
echo "Creating bucket '$BUCKET_NAME'..."
influx bucket create --name "$BUCKET_NAME" --org "$ORG_NAME" --retention 0 --host "$INFLUX_URL" -t "$TOKEN"

# Output the generated token
echo "Setup complete. The generated token for user '$USER_NAME' is:"
echo "$TOKEN"
