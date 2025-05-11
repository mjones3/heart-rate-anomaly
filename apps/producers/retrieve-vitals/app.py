from flask import Flask, jsonify, request
import os
import math
import json
import logging
import numpy as np
import wfdb  # Ensure wfdb is correctly imported
from time_utils import convert_time_from_dat  # Assuming this is defined in your time_utils.py
from s3_utils import download_patient_data, upload_json_to_s3, OUTPUT_S3_BUCKET, OUTPUT_S3_PREFIX  # Assuming your S3 utils are properly defined
from kafka_producer import send_json_to_kafka
from botocore.exceptions import NoCredentialsError, ClientError
from datetime import datetime, timedelta

DOWNLOAD_DIRECTORY = "/tmp/patientdata"
app = Flask(__name__)

# Set up logging configuration explicitly
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app.logger.setLevel(logging.INFO)
logger = logging.getLogger(__name__)

def is_valid_patient_id(patient_id):
    #logger.info(f"Validating patient ID: {patient_id}")
    return patient_id.startswith("p") and len(patient_id) == 7


def handle_nan_values(signal):
    """Handles NaN values and returns None for NaN items in the signal."""
    #logger.info(f"Handling NaN values for signal: {signal}")

    # Replace NaN values with None (which will be null in JSON)
    if isinstance(signal, list):
        signal = [None if isinstance(x, float) and math.isnan(x) else x for x in signal]
    elif isinstance(signal, np.ndarray):
        signal = np.where(np.isnan(signal), None, signal)  # Replaces NaNs with None in numpy arrays

    #logger.info(f"After handling NaN values: {signal}")
    return signal


def convert_to_list(signal):
    """Converts a signal to a list if it's a numpy array."""
    #logger.info(f"Converting signal to list if numpy array: {signal}")
    if isinstance(signal, np.ndarray):
        signal = signal.tolist()
    #logger.info(f"After converting to list: {signal}")
    return signal

def safe_write_data(value):
    """Safely write data by checking for NaN and replacing with None"""
    #logger.info(f"Checking if value is NaN or None: {value}")
    if value is None:
        #logger.info(f"Value is None, replacing with None")
        return None
    if isinstance(value, float) and math.isnan(value):
        #logger.info(f"Value is NaN, replacing with None")
        return None
    if isinstance(value, int) and math.isnan(value):
        #logger.info(f"Value is NaN in an integer context, replacing with None")
        return None
    #logger.info(f"Value is valid: {value}")
    return value


def safe_write_data(value):
    """Safely write data by checking for NaN and replacing with None"""
    #logger.info(f"Checking if value is NaN or None: {value}")
    if value is None:
        #logger.info(f"Value is None, replacing with None")
        return None
    if isinstance(value, float) and math.isnan(value):
        #logger.info(f"Value is NaN, replacing with None")
        return None
    if isinstance(value, int) and math.isnan(value):
        #logger.info(f"Value is NaN in an integer context, replacing with None")
        return None
    #logger.info(f"Value is valid: {value}")
    return value

def log_signal_values(signal, signal_name):
    """Log each value of the signal with its index for debugging"""
    if signal is None:
        #logger.info(f"{signal_name} is None.")
        return

    #logger.info(f"{signal_name} signal values (first 50 samples):")
    #for idx, value in enumerate(signal[:50]):  # Log first 50 values for debugging
        #logger.info(f"Index {idx}: {value}")

    #logger.info(f"{signal_name} signal values (total {len(signal)} samples):")
    #for idx, value in enumerate(signal):  # Log all values in the signal
        #logger.info(f"Index {idx}: {value}")

    #logger.info(f"End of {signal_name} signal")

def safe_write_data(value):
    """Safely write data by checking for NaN and replacing with None"""
    # logger.info(f"Checking if value is NaN or None: {value}")
    if value is None:
        logger.info(f"Value is None, replacing with None")
        return None
    if isinstance(value, float) and math.isnan(value):
        logger.info(f"Value is NaN, replacing with None")
        return None
    if isinstance(value, int) and math.isnan(value):
        logger.info(f"Value is NaN in an integer context, replacing with None")
        return None
    # logger.info(f"Value is valid: {value}")
    return value

def handle_invalid_signal(signal, signal_name):
    """Handles invalid signals by checking for None, empty, or NaN values"""
    # logger.info(f"Processing signal: {signal_name}")
    # logger.info(f"Before processing {signal_name}: {signal}")

    if signal is None:
        logger.error(f"{signal_name} signal is None. Populating with null.")
        return None
    if isinstance(signal, np.ndarray):
        if np.any(np.isnan(signal)):  # Check for NaN values in numpy arrays
            logger.debug(f"{signal_name} contains NaN values before processing.")
            logger.debug(f"NaN indices: {np.where(np.isnan(signal))}")  # Log the indices of NaN values
            logger.error(f"{signal_name} signal contains NaN values. Populating with null.")
            return None
    elif isinstance(signal, list):
        if any(math.isnan(x) for x in signal):  # Check for NaN in lists
            logger.debug(f"{signal_name} contains NaN values before processing.")
            logger.debug(f"NaN indices: {[i for i, x in enumerate(signal) if math.isnan(x)]}")  # Log the indices of NaN values
            logger.error(f"{signal_name} signal contains NaN values. Populating with null.")
            return None

    # logger.info(f"After processing {signal_name}: {signal}")
    return signal

# Generate unique file name
def generate_file_name(patient_id, timestamp, index):
    """Generates a unique filename for the JSON file using patient_id, timestamp, and index."""
    # Ensure the timestamp is a string that can be used safely in filenames
    timestamp_str = str(timestamp)
    # We will remove any non-alphanumeric characters and ensure a clean name
    clean_timestamp = timestamp_str.replace(".", "_")
    return f"{patient_id}_{clean_timestamp}_{index}"

# Function to accumulate time and convert it to a timestamp
def convert_time_from_dat(time_value, base_start_date_str="2025-05-10", prev_time=0):
    """
    Converts a relative time value (seconds since a base start date) into a timestamp string.
    Accumulates time for each sample if time_value is fractional.

    time_value: The relative time value in seconds (as seen in the dataset).
    base_start_date_str: The base start date as a string (default is "2025-05-10").
    prev_time: The previous time value (for time accumulation).

    Returns: A formatted timestamp string in the format: "YYYY-MM-DDTHH:MM:SS.mmmZ"
    """
    # Accumulate the time from previous values
    accumulated_time = prev_time + time_value

    # Calculate the adjusted time
    base_start_date = datetime.strptime(base_start_date_str, "%Y-%m-%d")
    time_delta = timedelta(seconds=accumulated_time)
    adjusted_time = base_start_date + time_delta

    # Format the time string with milliseconds
    adjusted_time_ms = adjusted_time.strftime('%Y-%m-%dT%H:%M:%S.') + f"{int((accumulated_time % 1) * 1000):03d}Z"

    return adjusted_time_ms, accumulated_time  # Return both the formatted time and the accumulated time

def scale_abp_signal(abp_signal):
    """Scale the ABP (Arterial Blood Pressure) values to mmHg (Multiply by 100)."""
    if abp_signal is None:
        return None
    return abp_signal * 100

def scale_resp_signal(resp_signal):
    """Scale the Respiration Rate (Multiply by a factor to normalize)."""
    if resp_signal is None:
        return None
    return resp_signal * 20  # Assuming resp_rate is scaled to 0-1, scaling to 12-20 bpm

def scale_map_signal(map_signal):
    """Scale the mean arterial pressure (MAP) to a realistic range of 70-100 mmHg."""
    if map_signal is None:
        return None
    return map_signal * 100  # Assuming MAP needs to be scaled

def scale_ecg_signal(ecg_signal):
    """
    Scales the raw ECG signal from volts to millivolts (mV).
    Assumes the ECG signal is in volts, and scales it to mV by multiplying by 1000.

    Args:
    - ecg_signal (float or list or np.ndarray): The raw ECG signal value(s) in volts.

    Returns:
    - Scaled ECG signal(s) in millivolts (mV).
    """
    if isinstance(ecg_signal, (list, np.ndarray)):
        # For lists or arrays, scale each element
        return [x * 1000 if isinstance(x, (int, float)) else None for x in ecg_signal]
    elif isinstance(ecg_signal, (int, float)):
        # For single float or integer values, just scale them
        return ecg_signal * 1000 if isinstance(ecg_signal, (int, float)) else None
    else:
        # If the signal type is unexpected, return None
        return None

# In the process_and_upload_to_s3 method, update how you handle these signals
def process_and_upload_to_s3(patient_data_dir, patient_id):
    # List all .dat files in the patient folder
    dat_files = [f for f in os.listdir(patient_data_dir) if f.endswith('.dat')]

    prev_time = 0  # Initialize the accumulated time to 0 for each file

    for dat_file in dat_files[:10]:  # Process only the first 10 files
        base, extension = dat_file.split('.')
        hea_file = base + '.hea'
        logger.info(f"Attempting to read .hea file: {os.path.join(patient_data_dir, hea_file)}")

        # Full path for the .dat and .hea files
        dat_file_path = os.path.join(patient_data_dir, dat_file)
        hea_file_path = os.path.join(patient_data_dir, hea_file)

        # Check if the corresponding .hea file exists
        if not os.path.exists(hea_file_path):
            logger.warning(f"Missing header file for {dat_file} ({hea_file}), skipping.")
            continue  # Skip if .hea file doesn't exist

        # Read the .dat and .hea file using WFDB library
        try:
            record = wfdb.rdrecord(os.path.join(patient_data_dir, base))
            logger.info(f"Successfully read {dat_file} and {hea_file}")
        except Exception as e:
            logger.error(f"Error reading file {dat_file}: {e}")
            continue  # Skip file if there's an error reading

        # Get the shape of the data to check the number of signals
        num_signals = record.p_signal.shape[1]
        logger.info(f"Number of signals: {num_signals}")

        # Extract the time and other signals, only if they exist
        time = record.p_signal[:, 0] if num_signals > 0 else None
        logger.info(f"time: {time}")

        ecg_ii = record.p_signal[:, 1] if num_signals > 1 else None
        abp_signal = record.p_signal[:, 2] if num_signals > 2 else None
        resp_signal = record.p_signal[:, 3] if num_signals > 3 else None

        # Handle missing or invalid signals
        ecg_ii = handle_invalid_signal(ecg_ii, "ECG_II")
        abp_signal = handle_invalid_signal(abp_signal, "ABP")
        resp_signal = handle_invalid_signal(resp_signal, "RESP")

        # Skip if all signals are invalid
        if ecg_ii is None and abp_signal is None and resp_signal is None:
            logger.error(f"Skipping processing due to missing or invalid signals for {dat_file}.")
            continue  # Skip if all signals are missing or invalid

        # Handle NaN values in ECG, ABP, and RESP signals
        ecg_ii = handle_nan_values(ecg_ii) if ecg_ii is not None else None
        abp_signal = handle_nan_values(abp_signal) if abp_signal is not None else None
        resp_signal = handle_nan_values(resp_signal) if resp_signal is not None else None

        # Iterate over each sample point in time
        for idx in range(len(time)):  # Iterate over the time points (samples)
            # Accumulate time and convert to formatted timestamp
            timestamp_str, prev_time = convert_time_from_dat(time[idx], "2025-05-10", prev_time)

            # Scale the signals
            scaled_abp = scale_abp_signal(abp_signal[idx]) if abp_signal is not None else None
            scaled_resp = scale_resp_signal(resp_signal[idx]) if resp_signal is not None else None
            scaled_map = scale_map_signal(abp_signal[idx]) if abp_signal is not None else None

            # Handle NaN values and replace them with None (which will be represented as null in JSON)
            data = {
                'time': safe_write_data(timestamp_str),
                'patient_id': patient_id,
                'ECG_I': safe_write_data(ecg_ii[0]) if ecg_ii is not None and len(ecg_ii) > 0 else None,
                'ECG_II': safe_write_data(ecg_ii[1]) if ecg_ii is not None and len(ecg_ii) > 1 else None,
                'ECG_III': safe_write_data(ecg_ii[2]) if ecg_ii is not None and len(ecg_ii) > 2 else None,
                'ABP': safe_write_data(scaled_abp),
                'RESP': safe_write_data(scaled_resp),
                'SpO2': None,  # Removed hardcoded value of SpO2
                'heart_rate': safe_write_data(75),  # Static heart rate if not available
                'systolic_bp': safe_write_data(scaled_abp) if scaled_abp is not None else None,
                'diastolic_bp': safe_write_data(scaled_abp) if scaled_abp is not None else None,
                'respiratory_rate': safe_write_data(16),  # Static value for respiratory rate
                'mean_arterial_pressure': safe_write_data(scaled_map),
            }

            # Generate the unique filename using patient_id and the timestamp (or time)
            file_name = generate_file_name(patient_id, time[idx], idx)

            # Convert the data to JSON
            json_buffer = json.dumps(data)

            # logger.info(f"ecg i {ecg_ii[0]}")
            # logger.info(f"ecg ii {ecg_ii[1]}")
            # logger.info(f"ecg iii {ecg_ii[2]}")
            # logger.info(f"abp {abp_signal[idx]}")
            # logger.info(f"RESP {resp_signal[idx]}")
            # logger.info(f"systolic_bp {abp_signal[idx]}")
            # logger.info(f"diastolic_bp {abp_signal[idx]}")

            logger.info(json_buffer)
            send_json_to_kafka(json_buffer)

            # Upload the JSON file to S3
            output_s3_key = f"{OUTPUT_S3_PREFIX}{patient_id}/{file_name}"
            try:
                upload_json_to_s3(json_buffer, patient_id, file_name)
            except (NoCredentialsError, ClientError) as e:
                logger.error(f"Error uploading to S3: {e}")


@app.route('/fetchPatientData', methods=['POST'])
def fetch_patient_data():
    try:
        # Parse the incoming JSON data
        data = request.get_json()

        if 'fetchPatientId' not in data:
            return jsonify({"error": "Missing 'fetchPatientId'"}), 400

        patient_id = data['fetchPatientId']

        # Validate the patient ID format
        if not is_valid_patient_id(patient_id):
            return jsonify({"error": "Invalid patient ID format"}), 400

        # Try downloading the patient data from S3
        patient_data_dir = download_patient_data(patient_id=patient_id)

        if patient_data_dir:
            # Process the data and upload the JSON files to S3
            process_and_upload_to_s3(patient_data_dir, patient_id)
            return jsonify({"message": f"Patient data for {patient_id} successfully processed and uploaded."}), 200
        else:
            return jsonify({"error": f"Patient data for {patient_id} not found."}), 404

    except Exception as e:
        logger.error(f"Error processing patient data: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Make sure the download directory exists
    try:
        os.makedirs(DOWNLOAD_DIRECTORY, exist_ok=True)
    except Exception as e:
        logger.error(f"Error creating download directory: {e}")

    # Run the Flask app
    app.run(host='0.0.0.0', port=8080)  # Run Flask server on 8080 port