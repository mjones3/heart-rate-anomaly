from datetime import datetime, timedelta

def convert_time_from_dat(time_value, base_start_date_str="2025-05-10"):
    """
    Converts a relative time value (seconds since a base start date) into a timestamp string.

    time_value: The relative time value in seconds (as seen in the dataset).
    base_start_date_str: The base start date as a string (default is "2025-05-10").

    Returns: A formatted timestamp string in the format: "YYYY-MM-DDTHH:MM:SS.mmmZ"
    """
    base_start_date = datetime.strptime(base_start_date_str, "%Y-%m-%d")
    # Convert the time value into a timedelta
    time_delta = timedelta(seconds=time_value)  # time_value is in seconds
    adjusted_time = base_start_date + time_delta

    # Now adjusting to milliseconds
    adjusted_time_ms = adjusted_time.strftime('%Y-%m-%dT%H:%M:%S.') + f"{int((time_value % 1) * 1000):03d}Z"
    return adjusted_time_ms