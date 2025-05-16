# app.py
from flask import Flask, jsonify, request
import os
import math
import json
import logging
import numpy as np
import wfdb
import wfdb.processing as wp
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient
from s3_utils import download_patient_data
import scipy.signal as sps
from kafka_producer import send_json_to_kafka

# -----------------------------------------------------------------------------
# Config & Initialization
# -----------------------------------------------------------------------------
DOWNLOAD_DIRECTORY = "/tmp/patientdata"

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

INFLUX_URL    = os.getenv("INFLUXDB_URL",    "http://localhost:8086")
INFLUX_TOKEN  = os.getenv("INFLUXDB_TOKEN",  "")
INFLUX_ORG    = os.getenv("INFLUXDB_ORG",    "")
INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET", "vitals")

influx_client = InfluxDBClient(
    url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG
)
write_api = influx_client.write_api()

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------
def is_valid_patient_id(patient_id: str) -> bool:
    return patient_id.startswith("p") and len(patient_id) == 7

def safe_write_data(value):
    if value is None: return None
    if isinstance(value, float) and math.isnan(value): return None
    return value

def handle_nan_values(signal):
    if signal is None:
        return None
    if isinstance(signal, list):
        return [None if isinstance(x, float) and math.isnan(x) else x for x in signal]
    if isinstance(signal, np.ndarray):
        return np.where(np.isnan(signal), None, signal)
    return signal

def handle_invalid_signal(signal, name):
    if signal is None:
        logger.error(f"{name} signal is None. Populating with null.")
        return None
    if isinstance(signal, np.ndarray) and np.any(np.isnan(signal)):
        logger.error(f"{name} contains NaN. Populating with null.")
        return None
    if isinstance(signal, list) and any(isinstance(x, float) and math.isnan(x) for x in signal):
        logger.error(f"{name} contains NaN. Populating with null.")
        return None
    return signal

def compute_heart_rate(ecg, fs):
    if ecg is None or len(ecg) < fs:
        logger.warning("ECG too short")
        return None
    nyq = 0.5 * fs
    b, a = sps.butter(2, [5/nyq, 15/nyq], btype='band')
    ecg_filt = sps.filtfilt(b, a, ecg)
    try:
        qrs = wp.xqrs_detect(sig=ecg_filt, fs=fs)
    except Exception as e:
        logger.warning(f"QRS detect failed: {e}")
        return None
    if len(qrs) < 2:
        logger.warning("Too few QRS for HR")
        return None
    rr = np.diff(qrs) / fs
    rr = rr[rr > 0]
    if len(rr) == 0:
        logger.warning("No positive RR intervals")
        return None
    hr = 60.0 / rr
    times = qrs[1:][rr>0]
    idxs = np.arange(len(ecg))
    try:
        return np.interp(idxs, times, hr, left=hr[0], right=hr[-1])
    except Exception as e:
        logger.warning(f"HR interp failed: {e}")
        return None

def convert_time_from_dat(time_value, base_start_date_str="2025-05-10", prev_time=0.0):
    new_total = prev_time + time_value
    base = datetime.strptime(base_start_date_str, "%Y-%m-%d")
    dt   = base + timedelta(seconds=new_total)
    ts   = dt.strftime('%Y-%m-%dT%H:%M:%S.') + f"{int((new_total % 1)*1000):03d}Z"
    return ts, new_total

def generate_file_name(patient_id, timestamp, idx):
    ts_clean = str(timestamp).replace(":", "-").replace(".", "_")
    return f"{patient_id}_{ts_clean}_{idx}"

# -----------------------------------------------------------------------------
# Core Processing
# -----------------------------------------------------------------------------
def process_and_upload_to_kafka(patient_data_dir, patient_id):
    dat_files = [f for f in os.listdir(patient_data_dir) if f.endswith('.dat')]
    prev_time = 0.0

    for dat_file in dat_files[:10]:
        base, _ = dat_file.split('.')
        hea = base + '.hea'
        hea_path = os.path.join(patient_data_dir, hea)
        if not os.path.exists(hea_path):
            logger.warning(f"Missing header for {dat_file}, skipping.")
            continue

        try:
            record = wfdb.rdrecord(os.path.join(patient_data_dir, base))
        except Exception as e:
            logger.error(f"Error reading {dat_file}: {e}")
            continue

        # 1) choose analog or digital
        if record.p_signal is not None:
            signals = record.p_signal
            names   = record.sig_name
        else:
            signals = record.d_signal
            names   = record.channel_names
            # apply gain/baseline scaling if available
            gains = getattr(record, 'adc_gain', None)
            basec = getattr(record, 'baseline', None)
            if gains is not None and basec is not None:
                signals = (signals - basec) * gains

        # 2) find channel indices
        def idx_of(label, default):
            return names.index(label) if label in names else default
        time_idx = idx_of('Time', 0)
        ecg_idx  = idx_of('ECG_II', 1)
        abp_idx  = idx_of('ABP',      2)
        resp_idx = idx_of('RESP',     3)

        time_vals = signals[:, time_idx]
        ecg       = signals[:, ecg_idx]  if signals.shape[1] > ecg_idx  else None
        abp       = signals[:, abp_idx]  if signals.shape[1] > abp_idx  else None
        resp      = signals[:, resp_idx] if signals.shape[1] > resp_idx else None

        # sanitize
        ecg  = handle_invalid_signal(ecg,  'ECG_II')
        abp  = handle_invalid_signal(abp,  'ABP')
        resp = handle_invalid_signal(resp, 'RESP')
        ecg  = handle_nan_values(ecg) if ecg is not None else None
        abp  = handle_nan_values(abp) if abp is not None else None
        resp = handle_nan_values(resp) if resp is not None else None

        hr_series = compute_heart_rate(ecg, record.fs)

        # iterate through samples
        for idx, t_val in enumerate(time_vals):
            timestamp_str, prev_time = convert_time_from_dat(t_val, prev_time=prev_time)
            scaled_abp  = abp[idx]*100 if abp  is not None else None
            scaled_resp = resp[idx]*20  if resp is not None else None
            scaled_map  = abp[idx]*100  if abp  is not None else None
            actual_hr   = None
            if hr_series is not None:
                try:
                    actual_hr = float(hr_series[idx])
                except Exception:
                    logger.warning(f"HR index error at {idx}")

            data = {
                "time":                   safe_write_data(timestamp_str),
                "patient_id":             patient_id,
                "ECG_II":                 safe_write_data(ecg[idx]) if ecg  is not None else None,
                "ABP":                    safe_write_data(scaled_abp),
                "RESP":                   safe_write_data(scaled_resp),
                "heart_rate":             safe_write_data(actual_hr),
                "systolic_bp":            safe_write_data(scaled_abp),
                "diastolic_bp":           safe_write_data(scaled_abp),
                "respiratory_rate":       safe_write_data(scaled_resp),
                "mean_arterial_pressure": safe_write_data(scaled_map)
            }

            # 3) produce to Kafka
            send_json_to_kafka(json.dumps(data))

            # 4) (optional) upload JSON to S3 if you re-enable it
            # fn = generate_file_name(patient_id, timestamp_str, idx)
            # key = f"{OUTPUT_S3_PREFIX.rstrip('/')}/{patient_id}/{fn}.json"
            # upload_json_to_s3(json.dumps(data), patient_id, fn)

    # done

# -----------------------------------------------------------------------------
# Flask Routes
# -----------------------------------------------------------------------------
@app.route("/fetchPatientData", methods=["POST"])
def fetch_patient_data():
    try:
        payload = request.get_json()
        if "fetchPatientId" not in payload:
            return jsonify({"error": "Missing 'fetchPatientId'"}), 400

        pid = payload["fetchPatientId"]
        if not is_valid_patient_id(pid):
            return jsonify({"error": "Invalid patient ID format"}), 400

        # Download from S3
        data_dir = download_patient_data(pid)
        if not data_dir:
            return jsonify({"error": f"No data for {pid}"}), 404

        process_and_upload_to_kafka(data_dir, pid)
        return jsonify({"message": f"Processed data for {pid}"}), 200

    except Exception as exc:
        logger.error(f"Route error: {exc}")
        return jsonify({"error": str(exc)}), 500

# -----------------------------------------------------------------------------
# Main Entry
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    os.makedirs(DOWNLOAD_DIRECTORY, exist_ok=True)
    app.debug = True
    app.run(host="0.0.0.0", port=8080, use_reloader=True)
