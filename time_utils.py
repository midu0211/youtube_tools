# time_utils.py
import datetime
import pytz
from tkinter import messagebox
from config import VIETNAM_TZ_STR

vietnam_tz = None

def initialize_timezone(log_func=print):
    global vietnam_tz
    try:
        vietnam_tz = pytz.timezone(VIETNAM_TZ_STR)
        log_func(f"Timezone '{VIETNAM_TZ_STR}' loaded successfully.")
        return True
    except pytz.exceptions.UnknownTimeZoneError:
        log_func(f"ERROR: Timezone '{VIETNAM_TZ_STR}' not found.")
        messagebox.showerror("Timezone Error",
                             f"Could not find the timezone '{VIETNAM_TZ_STR}'.\n"
                             f"Please ensure the 'pytz' library is installed correctly (`pip install pytz`).")
        return False
    except Exception as e:
        log_func(f"ERROR initializing timezone: {e}")
        messagebox.showerror("Timezone Error", f"An unexpected error occurred initializing timezone: {e}")
        return False

def convert_utc_to_vn_str(utc_iso_string, fmt='%Y-%m-%d %H:%M:%S', log_func=print):
    if not vietnam_tz:
        initialize_timezone(log_func) # Ensure it's initialized
    if not utc_iso_string or not vietnam_tz:
        return "N/A"
    try:
        utc_dt = datetime.datetime.fromisoformat(utc_iso_string.replace('Z', '+00:00'))
        vn_dt = utc_dt.astimezone(vietnam_tz)
        return vn_dt.strftime(fmt)
    except (ValueError, TypeError) as e:
        log_func(f"Error converting UTC string '{utc_iso_string}' to VN time: {e}")
        return "Invalid Date"

def convert_vn_str_to_utc_iso(vn_time_str, fmt='%Y-%m-%d %H:%M:%S', log_func=print):
    if not vietnam_tz:
        initialize_timezone(log_func) # Ensure it's initialized
    if not vietnam_tz:
        log_func("Error: Vietnam timezone not initialized for VN to UTC conversion.")
        return None, None
    try:
        naive_dt = datetime.datetime.strptime(vn_time_str, fmt)
        vn_dt = vietnam_tz.localize(naive_dt)
        utc_dt = vn_dt.astimezone(pytz.utc)
        utc_iso_str = utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        return utc_dt, utc_iso_str
    except ValueError:
        log_func(f"Invalid VN time format: '{vn_time_str}'. Expected: '{fmt}'")
        messagebox.showerror("Invalid Time Format",
                             f"Invalid time format.\nPlease use: {fmt} (Vietnam Time).")
        return None, None
    except Exception as e:
        log_func(f"Error converting VN time string '{vn_time_str}' to UTC: {e}")
        messagebox.showerror("Time Conversion Error", f"Error converting time: {e}")
        return None, None