from datetime import datetime, timedelta

def convert_time_from_dat(time_value, base_start_date_str="2025-05-10", prev_time=0.0):
    """
    time_value: seconds since the *previous* point (fractional).
    prev_time:  cumulative seconds so far (initially 0.0).
    """
    # 1) accumulate
    new_total = prev_time + time_value

    # 2) build a datetime from day-start + new_total seconds
    base = datetime.strptime(base_start_date_str, "%Y-%m-%d")
    dt   = base + timedelta(seconds=new_total)

    # 3) format with ms
    ts = dt.strftime('%Y-%m-%dT%H:%M:%S.') + f"{int((new_total % 1)*1000):03d}Z"
    return ts, new_total
