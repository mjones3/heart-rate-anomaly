#!/usr/bin/env python3
import os
import json
import time
import logging

from kafka import KafkaConsumer, KafkaAdminClient
from kafka.errors import NoBrokersAvailable
from pymongo import MongoClient, errors as mongo_errors

# ─── Configuration via ENV ──────────────────────────────────────────────────────

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9093").split(",")
KAFKA_TOPIC            = os.getenv("KAFKA_TOPIC", "vitals-json")
CONSUMER_GROUP         = os.getenv("CONSUMER_GROUP", "vitals-fhir-consumers")

MONGO_URI              = os.getenv("MONGO_URI", "mongodb://admin:s3cr3tPassw0rd@mongo:27017/admin")
MONGO_DB               = os.getenv("MONGO_DB", "ehr")
MONGO_COLLECTION       = os.getenv("MONGO_COLLECTION", "observations")

# ─── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── Wait for topic to appear ───────────────────────────────────────────────────

def wait_for_topic(admin, topic, interval=5):
    while True:
        try:
            topics = admin.list_topics()
            logger.info(f"Looking for topic '{topic}', broker has: {', '.join(sorted(topics))}")
            if topic in topics:
                logger.info(f"Found topic '{topic}', proceeding to consume.")
                return
        except Exception as e:
            logger.warning(f"Failed to list topics ({e}), retrying in {interval}s…")
        time.sleep(interval)

# connect Kafka admin client
admin = None
while not admin:
    try:
        admin = KafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    except NoBrokersAvailable:
        logger.warning(f"No Kafka brokers at {KAFKA_BOOTSTRAP_SERVERS}, retrying…")
        time.sleep(5)

wait_for_topic(admin, KAFKA_TOPIC)

# ─── Initialize Kafka consumer ──────────────────────────────────────────────────

consumer = KafkaConsumer(
    KAFKA_TOPIC,
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    group_id=CONSUMER_GROUP,
    auto_offset_reset="earliest",
    enable_auto_commit=True,
    # Let kafka-python handle decompression; get raw bytes
    value_deserializer=lambda v: v,
    consumer_timeout_ms=10000,
)

# ─── Initialize Mongo client ────────────────────────────────────────────────────

try:
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    mongo_client.admin.command("ping")
    mongo_col = mongo_client[MONGO_DB][MONGO_COLLECTION]
    logger.info("Connected to MongoDB")
except mongo_errors.PyMongoError as e:
    logger.error(f"Cannot connect to MongoDB: {e}")
    raise SystemExit(1)

# ─── Build a FHIR Observation dict ──────────────────────────────────────────────

def build_observation(vitals: dict) -> dict:
    if not all(k in vitals for k in ("time", "patient_id")):
        raise ValueError("Missing 'time' or 'patient_id' in vitals payload")

    obs = {
        "resourceType": "Observation",
        "status": "final",
        "category": [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "vital-signs"
            }]
        }],
        "subject": {"reference": f"Patient/{vitals['patient_id']}"},
        "effectiveDateTime": vitals["time"],
        "component": []
    }

    mapping = {
        "ECG_I":    ("ECG Lead I",    "mmV",         "http://loinc.org", "ECG Lead I LOINC"),
        "ECG_II":   ("ECG Lead II",   "mmV",         "http://loinc.org", "ECG Lead II LOINC"),
        "ABP":      ("Arterial BP",   "mmHg",        "http://loinc.org", "Arterial BP LOINC"),
        "RESP":     ("Resp Rate",     "breaths/min", "http://loinc.org", "Resp Rate LOINC"),
        "SpO2":     ("O₂ Saturation", "%",           "http://loinc.org", "SpO₂ LOINC"),
        "heart_rate":("Heart rate",   "beats/min",   "http://loinc.org", "Heart Rate LOINC"),
        "systolic_bp":("Systolic BP", "mmHg",        "http://loinc.org", "Systolic BP LOINC"),
        "diastolic_bp":("Diastolic BP","mmHg",        "http://loinc.org", "Diastolic BP LOINC"),
        "mean_arterial_pressure":("MAP","mmHg",       "http://loinc.org", "MAP LOINC")
    }

    for key, (display, unit, system, code) in mapping.items():
        val = vitals.get(key)
        if val is None:
            continue
        try:
            obs["component"].append({
                "code": {
                    "coding": [{
                        "system": system,
                        "code": code,
                        "display": display
                    }],
                    "text": display
                },
                "valueQuantity": {
                    "value": float(val),
                    "unit": unit,
                    "system": "http://unitsofmeasure.org",
                    "code": unit
                }
            })
        except Exception as ex:
            logger.warning(f"Skipping '{key}' with bad value={val}: {ex}")

    return obs

# ─── Main Loop ─────────────────────────────────────────────────────────────────

logger.info("Starting Kafka → FHIR → Mongo consumer…")
while True:
    try:
        for msg in consumer:
            # decode bytes → str
            try:
                payload = msg.value.decode("utf-8")
            except Exception as e:
                logger.error(f"Failed to decode bytes: {e}")
                continue

            # parse JSON
            try:
                vitals = json.loads(payload)
            except json.JSONDecodeError as je:
                logger.error(f"Invalid JSON payload: {je}")
                continue

            # map to FHIR
            try:
                obsd = build_observation(vitals)
            except Exception as ve:
                logger.error(f"Mapping error: {ve}")
                continue

            # insert into Mongo
            try:
                r = mongo_col.insert_one(obsd)
                logger.info(f"Inserted Observation _id={r.inserted_id}")
            except mongo_errors.PyMongoError as me:
                logger.error(f"MongoDB insert failed: {me}")

    except Exception as fatal:
        logger.exception(f"Unexpected consumer error: {fatal}")
        time.sleep(5)
