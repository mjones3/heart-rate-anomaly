# Heart Rate Anomaly Detection - Docker Compose Setup

## Local Setup

This project uses Docker Compose to set up and run a complete local environment for simulating heart rate anomaly detection. The services are orchestrated using Docker Compose and can be easily transitioned to cloud environments like AWS using Kubernetes later.

### **Services Overview**

- **Zookeeper**  
  - Acts as the centralized service for managing Kafka brokers.  
  - Exposes port `2181` for Kafka to connect and synchronize.

- **Kafka**  
  - A distributed messaging system used for event-driven architectures.  
  - Exposes ports `9093` (internal) and `9094` (external).  
  - Configured to not auto-create topics, which ensures that only explicitly defined topics are available.  
  - Connects to Zookeeper for cluster management and coordination.

- **Kafka Manager**  
  - A web-based UI for managing Kafka clusters.  
  - Exposes port `9000` for access.  
  - Enables the monitoring and management of Kafka topics, brokers, and more.

- **Vitals Producer**  
  - Simulates sending health data (e.g., heart rate, respiratory rate) to Kafka.  
  - Built from the `./apps/producers/retrieve-vitals` directory.  
  - Configured to push messages to the Kafka topic `vitals`.

- **Vital Timeseries Consumer**  
  - Consumes data from Kafka and writes it into InfluxDB for time-series storage and analysis.  
  - Built from the `./apps/consumers/vital-timeseries` directory.  
  - Reads Kafka data and uses InfluxDB for storing health data, including heart rate and respiratory rate.

- **InfluxDB**  
  - A time-series database used to store and analyze health-related data.  
  - Exposes port `8086` for data storage and retrieval via HTTP API.  
  - Configured to interact with Kafka and store data in a bucket named `vitals`.

## **Services Breakdown**

### **Zookeeper**
- **Purpose**: Kafka requires Zookeeper for managing brokers and maintaining the Kafka cluster.
- **Ports Exposed**: 2181 (Zookeeper client port)
- **Healthcheck**: Ensures Zookeeper is ready before Kafka attempts to connect.

### **Kafka**
- **Purpose**: The message broker in the system, used to store and transmit health data.
- **Ports Exposed**: 9093 (internal communication) and 9094 (external access).
- **Configuration**: Configured to communicate with Zookeeper and manually manage topics.

### **Kafka Manager**
- **Purpose**: A user-friendly web interface to manage Kafka clusters and topics.
- **Ports Exposed**: 9000 for accessing the Kafka Manager UI.
- **Functionality**: Used to monitor Kafka topics and manage Kafka cluster configuration.

### **Vitals Producer**
- **Purpose**: Simulates a producer of health data, pushing it to Kafka for processing.
- **Ports Exposed**: 8081 (local endpoint to interact with the producer service).
- **Environment Variables**: Configured with Kafka broker details and the `vitals` topic.
- **Functionality**: Sends simulated health data (e.g., heart rate, respiratory rate) to Kafka.

### **Vital Timeseries Consumer**
- **Purpose**: Consumes health data from Kafka and writes it into InfluxDB.
- **Ports Exposed**: N/A (does not expose ports, runs in the background).
- **Environment Variables**: Configured to connect to both Kafka and InfluxDB with the appropriate credentials and endpoints.
- **Functionality**: Consumes messages from Kafka and stores the processed health data (heart rate, respiratory rate) in InfluxDB.

### **InfluxDB**
- **Purpose**: A time-series database for storing and analyzing heart rate and other health data.
- **Ports Exposed**: 8086 for accessing the InfluxDB HTTP API.
- **Environment Variables**: Configured to store health data in a bucket named `vitals`.
- **Healthcheck**: Ensures that InfluxDB is ready to accept data before other services interact with it.

## **How It Works Locally**

1. **Zookeeper** initializes first and waits for Kafka to connect to it.
2. **Kafka** starts and waits for Zookeeper to become available, then listens for incoming messages.
3. **Kafka Manager** is accessible via `localhost:9000` for monitoring and managing Kafka.
4. **Vitals Producer** sends health data to Kafka at regular intervals.
5. **Vital Timeseries Consumer** reads health data from Kafka and writes it to InfluxDB.
6. **InfluxDB** stores the incoming health data (heart rate, respiratory rate, etc.) in the `vitals` bucket for analysis.

## **Running the Services**

To start the services locally with Docker Compose:

1. Clone the repository:
    ```bash
    git clone <repository-url>
    cd <project-directory>
    ```

2. Build and start the containers:
    ```bash
    docker-compose up --build
    ```

3. Access the services:
    - Kafka Manager: `http://localhost:9000`
    - InfluxDB: `http://localhost:8086`
    - Producer: `http://localhost:8081`
    
4. Verify that Kafka topics and data are correctly configured.

### **Future Migration to AWS (Kubernetes)**

- The services are configured to run locally using Docker Compose. When transitioning to AWS, you will need to:
  - Migrate the setup to **Kubernetes** using Kubernetes manifests or Helm charts.
  - Replace Docker Compose's `depends_on` and health checks with Kubernetes' native mechanisms (e.g., **readiness probes**).
  - Use **AWS Secrets Manager** or **Kubernetes Secrets** to securely handle tokens and other sensitive data.

---