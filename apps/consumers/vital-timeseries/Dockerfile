# Use an official Python runtime as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Set environment variables inside the Dockerfile
ENV AWS_DEFAULT_REGION=us-east-1
# ENV API-KEY=

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8082

# Run the application when the container starts
CMD ["python", "app.py"]
