import math
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def calculate_heart_rate(ecg_signal):
    if not isinstance(ecg_signal, list):
        logger.error(f"Invalid ECG signal: {type(ecg_signal)}")
        return []
    return [75] * len(ecg_signal)

def calculate_respiratory_rate(resp_signal):
    if not isinstance(resp_signal, list):
        logger.error(f"Invalid Resp signal: {type(resp_signal)}")
        return []
    return [16] * len(resp_signal)

def handle_nan_values(signal):
    if isinstance(signal, list):
        return [None if math.isnan(x) else x for x in signal]
    logger.error(f"Expected a list for signal, but got {type(signal)}")
    return []

def handle_invalid_signal(signal, signal_name):
    if signal is None or (isinstance(signal, list) and not signal):
        logger.error(f"Invalid {signal_name} signal: {signal}")
        return None
    return signal

# Scale ECG signals
def scale_ecg_signals(ecg_signal):
    if ecg_signal is None:  # If signal is None, skip scaling
        logger.debug(f"ECG signal is None, skipping scaling.")
        return None
    if not isinstance(ecg_signal, list):
        logger.error(f"Invalid ECG signal: {ecg_signal}")
        return None
    scaled = [x * 1000 if isinstance(x, (int, float)) else None for x in ecg_signal]
    logger.debug(f"Scaled ECG signals: {scaled[:5]}")
    return scaled

# Scale ABP signal
def scale_abp_signal(abp_signal):
    if abp_signal is None:  # If signal is None, skip scaling
        logger.debug(f"ABP signal is None, skipping scaling.")
        return None
    if not isinstance(abp_signal, (int, float)):
        logger.error(f"Invalid ABP signal: {abp_signal}")
        return None
    scaled = abp_signal * 100
    logger.debug(f"Scaled ABP signal: {scaled}")
    return scaled

# Scale BP values (systolic, diastolic, MAP)
def scale_bp_values(bp_value):
    if bp_value is None:  # If signal is None, skip scaling
        logger.debug(f"BP signal is None, skipping scaling.")
        return None
    if not isinstance(bp_value, (int, float)):
        logger.error(f"Invalid BP value: {bp_value}")
        return None
    scaled = bp_value * 100
    logger.debug(f"Scaled BP value: {scaled}")
    return scaled

# Scale respiration signal
def scale_resp_signal(resp_signal):
    if resp_signal is None:  # If signal is None, skip scaling
        logger.debug(f"Respiration signal is None, skipping scaling.")
        return None
    if not isinstance(resp_signal, (int, float)):
        logger.error(f"Invalid Respiration signal: {resp_signal}")
        return None
    scaled = resp_signal * (20 - 12) + 12
    logger.debug(f"Scaled Respiration signal: {scaled}")
    return scaled

def generate_json_data(time, patient_id, ecg_ii, abp_signal, resp_signal, heart_rate, systolic_bp, diastolic_bp, oxygen_saturation, respiratory_rate, map_bp):
    # Validate types before scaling
    if not isinstance(ecg_ii, list):
        logger.error(f"Invalid type for ECG signal: {type(ecg_ii)}")
    if not isinstance(abp_signal, (list, float, int)):
        logger.error(f"Invalid type for ABP signal: {type(abp_signal)}")
    if not isinstance(resp_signal, (list, float, int)):
        logger.error(f"Invalid type for Resp signal: {type(resp_signal)}")

    # Apply scaling for valid signals
    ecg_ii = scale_ecg_signals(ecg_ii)
    abp_signal = scale_abp_signal(abp_signal)
    systolic_bp = scale_bp_values(systolic_bp)
    diastolic_bp = scale_bp_values(diastolic_bp)
    map_bp = scale_bp_values(map_bp)
    resp_signal = scale_resp_signal(resp_signal)

    # Handling None before returning data
    return {
        'time': time,
        'patient_id': patient_id,
        'ECG_I': handle_nan_values([ecg_ii[0]])[0] if ecg_ii else None,
        'ECG_II': handle_nan_values([ecg_ii[1]])[0] if ecg_ii else None,
        'ECG_III': handle_nan_values([ecg_ii[2]])[0] if ecg_ii else None,
        'ABP': abp_signal,  # Directly return abp_signal if None
        'RESP': resp_signal,  # Directly return resp_signal if None
        'SpO2': oxygen_saturation,
        'heart_rate': handle_nan_values([heart_rate])[0] if heart_rate is not None else None,
        'systolic_bp': systolic_bp,
        'diastolic_bp': diastolic_bp,
        'respiratory_rate': respiratory_rate,
        'mean_arterial_pressure': map_bp
    }