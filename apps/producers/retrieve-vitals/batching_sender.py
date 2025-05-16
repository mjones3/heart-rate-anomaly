# batching_sender.py

import threading
import json
from kafka_producer import producer

class BatchingSender:
    """
    Buffers JSON records in memory and flushes them as a single newline-delimited
    Kafka message when either size or count thresholds are met.
    """
    def __init__(self, max_batch_bytes: int = 100_000, max_batch_count: int = 200):
        self.lock = threading.Lock()
        self.buffer = []
        self.buffer_size = 0
        self.max_batch_bytes = max_batch_bytes
        self.max_batch_count = max_batch_count

    def send(self, record: dict, topic: str = 'vitals'):
        payload = json.dumps(record).encode('utf-8')
        with self.lock:
            self.buffer.append(payload)
            self.buffer_size += len(payload)
            if len(self.buffer) >= self.max_batch_count or self.buffer_size >= self.max_batch_bytes:
                self._flush(topic)

    def _flush(self, topic: str):
        if not self.buffer:
            return
        batch_payload = b'\n'.join(self.buffer)
        # produce the whole batch
        producer.produce(topic, batch_payload)
        # immediately poll to service delivery callbacks and clear queue
        producer.poll(0)
        # and block until everything's acked
        producer.flush()
        # reset
        self.buffer.clear()
        self.buffer_size = 0

    def force_flush(self, topic: str = 'vitals'):
        with self.lock:
            self._flush(topic)

# Singleton
batching_sender = BatchingSender()
