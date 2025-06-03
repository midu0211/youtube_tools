# auth.py
import os
import pickle
import threading
from tkinter import messagebox

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import CLIENT_SECRETS_FILE, ALL_APP_SCOPES, TOKEN_PICKLE_FILE

current_credentials = None
auth_lock = threading.Lock()

def _save_credentials(creds):
    try:
        with open(TOKEN_PICKLE_FILE, 'wb') as token:
            pickle.dump(creds, token)
    except Exception as e:
        print(f"Error saving credentials: {e}")

def _load_credentials():
    if os.path.exists(TOKEN_PICKLE_FILE):
        try:
            with open(TOKEN_PICKLE_FILE, 'rb') as token:
                return pickle.load(token)
        except Exception as e:
            print(f"Error loading credentials: {e}")
            try:
                os.remove(TOKEN_PICKLE_FILE)
                print(f"Removed corrupt token file: {TOKEN_PICKLE_FILE}")
            except OSError:
                pass
    return None

def get_authenticated_service(api_name, api_version, log_func=print):
    global current_credentials
    with auth_lock:
        if current_credentials and current_credentials.valid:
            if not all(s in current_credentials.scopes for s in ALL_APP_SCOPES):
                log_func("Current credentials do not cover all required scopes. Re-authenticating.")
                current_credentials = None
            if current_credentials and current_credentials.expired and current_credentials.refresh_token:
                try:
                    log_func("Refreshing expired credentials...")
                    current_credentials.refresh(Request())
                    _save_credentials(current_credentials)
                    log_func("Credentials refreshed successfully.")
                except Exception as e:
                    log_func(f"Failed to refresh credentials: {e}. Re-authentication needed.")
                    current_credentials = None

        if not current_credentials or not current_credentials.valid:
            log_func("No valid current credentials. Attempting to load or re-authenticate.")
            loaded_creds = _load_credentials()
            if loaded_creds:
                if all(s in loaded_creds.scopes for s in ALL_APP_SCOPES):
                    current_credentials = loaded_creds
                    log_func("Credentials loaded from file.")
                    if current_credentials.expired and current_credentials.refresh_token:
                        try:
                            log_func("Refreshing expired loaded credentials...")
                            current_credentials.refresh(Request())
                            _save_credentials(current_credentials)
                            log_func("Loaded credentials refreshed successfully.")
                        except Exception as e:
                            log_func(f"Failed to refresh loaded credentials: {e}. Re-authentication needed.")
                            current_credentials = None
                    elif not current_credentials.valid:
                        log_func("Loaded credentials are not valid and cannot be refreshed. Re-authentication needed.")
                        current_credentials = None
                else:
                    log_func("Loaded credentials do not cover all required application scopes. Re-authentication needed.")
                    current_credentials = None

            if not current_credentials or not current_credentials.valid:
                if not os.path.exists(CLIENT_SECRETS_FILE):
                    log_func(f"ERROR: Client secrets file not found: {CLIENT_SECRETS_FILE}")
                    if threading.current_thread() is threading.main_thread():
                        messagebox.showerror("Authentication Error", f"Client secrets file '{CLIENT_SECRETS_FILE}' not found.")
                    else:
                        print(f"CRITICAL ERROR (non-UI thread): Client secrets file '{CLIENT_SECRETS_FILE}' not found.")
                    return None
                try:
                    log_func("Initiating new OAuth flow...")
                    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, ALL_APP_SCOPES)
                    current_credentials = flow.run_local_server(port=0)
                    _save_credentials(current_credentials)
                    log_func("New authentication successful. Credentials saved.")
                except Exception as e:
                    log_func(f"Authentication Error during OAuth flow: {e}")
                    if threading.current_thread() is threading.main_thread():
                        messagebox.showerror("Authentication Error", f"Could not authenticate: {e}")
                    else:
                        print(f"CRITICAL ERROR (non-UI thread): Authentication failed: {e}")
                    return None

        if current_credentials and current_credentials.valid:
            try:
                service = build(api_name, api_version, credentials=current_credentials)
                log_func(f"Service '{api_name} v{api_version}' built successfully with current credentials.")
                return service
            except Exception as e:
                log_func(f"Error building API service: {e}")
                if threading.current_thread() is threading.main_thread():
                    messagebox.showerror("Service Build Error", f"Could not build API service: {e}")
                else:
                    print(f"CRITICAL ERROR (non-UI thread): Could not build API service: {e}")
                return None
        else:
            log_func("Failed to obtain valid credentials after all attempts.")
            if threading.current_thread() is threading.main_thread():
                messagebox.showerror("Authentication Failed", "Could not obtain valid credentials.")
            else:
                print("CRITICAL ERROR (non-UI thread): Could not obtain valid credentials.")
            return None