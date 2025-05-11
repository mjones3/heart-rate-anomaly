# Use an official Python runtime as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Set environment variables inside the Dockerfile
ENV AWS_ACCESS_KEY_ID=AKIAUJDFCKEIRC2DEVIF
ENV AWS_SECRET_ACCESS_KEY=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
ENV AWS_DEFAULT_REGION=us-east-1
ENV OUTPUT_S3_BUCKET=mjones3-patient-data
ENV OUTPUT_S3_PREFIX =processed_data/
ENV EKG_DATA_BUCKET=physionet-open
ENV EKG_DATA_PREFIX=mimic3wdb-matched/1.0
# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port that Flask will run on
EXPOSE 5000

# Run the application when the container starts
CMD ["python", "app.py"]
