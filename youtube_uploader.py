# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import datetime
import json
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
import os
import threading
import time
import queue
import pytz
import random
from ttkthemes import ThemedTk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import matplotlib.ticker as mticker
import math
#   Constants and Globals
CLIENT_SECRETS_FILE = 'client_secret.json'
UPLOAD_READONLY_SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly'
]
COMMENT_SCOPE = ['https://www.googleapis.com/auth/youtube.force-ssl']

API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'
SCHEDULED_POSTS_FILE = 'scheduled_posts.json'
COMMENT_TEMPLATES_FILE = 'comment_templates.json'
VIETNAM_TZ_STR = 'Asia/Ho_Chi_Minh'

status_queue = queue.Queue()
youtube_service_global = None
auth_lock = threading.Lock()
scheduled_posts_data = []
comment_templates_list = []
vietnam_tz = None
current_random_comment = ""

# UI Element Globals
status_bar_instance = None
upload_now_btn = None
schedule_btn = None
clear_btn = None
fetch_trending_btn = None
post_comment_btn = None
pick_comment_btn = None
add_comment_btn = None
delete_comment_btn = None
analyze_video_btn = None
analytics_video_combobox = None
analytics_chart_frame = None
analytics_report_text = None
canvas_widget = None
num_comments_entry = None # Renamed from num_samples_entry
generate_comments_btn = None # Renamed from generate_samples_btn
analyze_custom_id_btn = None
custom_video_id_analytics_entry = None

# Meaningful Comment Templates
MEANINGFUL_COMMENT_BASES = [
    "Video tuyệt vời!", "Nội dung rất hay, cảm ơn bạn đã chia sẻ.", "Mình rất thích video này.",
    "Làm tốt lắm! Tiếp tục phát huy nhé.", "Video này thật sự hữu ích.", "Chất lượng video tuyệt vời.",
    "Wow, ấn tượng thật!", "Cảm ơn vì những thông tin giá trị.", "Rất sáng tạo!", "Hay lắm bạn ơi!",
    "Xem xong thấy có thêm động lực. Cảm ơn bạn!", "Chúc mừng bạn đã có một video thành công!", "Yêu bạn!",
    "Quá đỉnh!", "Hay quá đi mất!", "Tuyệt vời! Bạn làm rất tốt.", "Video này xứng đáng triệu view!", "Tuyệt cú mèo!",
    "Tuyệt!", "Hay!", "Chất!", "Đỉnh!", "Oke bạn ơi.", "Thích nha.", "Good job!", "Amazing!", "Perfect!", "Awesome!",
    "Cảm ơn bạn nhiều.", "Thanks for sharing!", "Rất biết ơn bạn.", "Cảm ơn vì đã làm video này.", "Thank you!",
    "Video hay, tiếp tục phát huy nhé kênh.", "Nội dung chất lượng, mình đã sub kênh.", "Video ý nghĩa quá.",
    "Mình đã học được nhiều điều từ video này.", "Xem giải trí mà vẫn có kiến thức.", "Đúng thứ mình đang tìm."
]
EMOJIS_LIST = ["👍", "❤️", "🎉", "💯", "🔥", "😮", "😂", "✨", "🌟", "😊", "😃", "😍", "🙏", "🙌", "👌", "💖", "🤣", "🤩"]
COMMENT_SUFFIXES = [
    "Rất mong video tiếp theo của bạn!", "Cố gắng lên nhé!", "Chúc kênh ngày càng phát triển!",
    "Tuyệt vời ông mặt trời!", "Luôn ủng hộ bạn!", "5 sao cho video này!"
]

#   StatusBar Class
class StatusBar(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.label = ttk.Label(self, text="Ready", anchor=tk.W, padding=(5, 2))
        self.label.pack(fill=tk.X, expand=True, side=tk.LEFT)
        self.progress = ttk.Progressbar(self, orient=tk.HORIZONTAL, length=150, mode='indeterminate')
    def set_text(self, text):
        self.label.config(text=text)

    def clear(self):
        self.set_text("Ready")

    def show_progress(self):
        self.progress.pack(side=tk.RIGHT, padx=5, pady=2)
        self.progress.start(20)

    def hide_progress(self):
        self.progress.stop()
        self.progress.pack_forget()

# Logging
def log_status(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    if status_bar_instance and root.winfo_exists():
        try:
            root.after(0, status_bar_instance.set_text, message)
        except Exception as e:
            print(f"Error updating status bar: {e}")

#   Timezone and Time Conversion
def initialize_timezone():
    global vietnam_tz
    try:
        vietnam_tz = pytz.timezone(VIETNAM_TZ_STR)
        log_status(f"Timezone '{VIETNAM_TZ_STR}' loaded successfully.")
        return True
    except pytz.exceptions.UnknownTimeZoneError:
        log_status(f"ERROR: Timezone '{VIETNAM_TZ_STR}' not found.")
        messagebox.showerror("Timezone Error",
                             f"Could not find the timezone '{VIETNAM_TZ_STR}'.\n"
                             f"Please ensure the 'pytz' library is installed correctly (`pip install pytz`).")
        return False
    except Exception as e:
        log_status(f"ERROR initializing timezone: {e}")
        messagebox.showerror("Timezone Error", f"An unexpected error occurred initializing timezone: {e}")
        return False

def convert_utc_to_vn_str(utc_iso_string, fmt='%Y-%m-%d %H:%M:%S'):
    if not utc_iso_string or not vietnam_tz:
        return "N/A"
    try:
        utc_dt = datetime.datetime.fromisoformat(utc_iso_string.replace('Z', '+00:00'))
        vn_dt = utc_dt.astimezone(vietnam_tz)
        return vn_dt.strftime(fmt)
    except (ValueError, TypeError) as e:
        log_status(f"Error converting UTC string '{utc_iso_string}' to VN time: {e}")
        return "Invalid Date"

def convert_vn_str_to_utc_iso(vn_time_str, fmt='%Y-%m-%d %H:%M:%S'):
    if not vietnam_tz:
        log_status("Error: Vietnam timezone not initialized.")
        return None, None
    try:
        naive_dt = datetime.datetime.strptime(vn_time_str, fmt)
        vn_dt = vietnam_tz.localize(naive_dt)
        utc_dt = vn_dt.astimezone(pytz.utc)
        utc_iso_str = utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        return utc_dt, utc_iso_str
    except ValueError:
        log_status(f"Invalid VN time format: '{vn_time_str}'. Expected: '{fmt}'")
        messagebox.showerror("Invalid Time Format",
                             f"Invalid time format.\nPlease use: {fmt} (Vietnam Time).")
        return None, None
    except Exception as e:
        log_status(f"Error converting VN time string '{vn_time_str}' to UTC: {e}")
        messagebox.showerror("Time Conversion Error", f"Error converting time: {e}")
        return None, None


#   Authentication
def get_authenticated_service(scopes=UPLOAD_READONLY_SCOPES):
    global youtube_service_global
    with auth_lock:
        cached_scopes_match = False
        if youtube_service_global and scopes == UPLOAD_READONLY_SCOPES:
             cached_scopes_match = True
        elif youtube_service_global and scopes == ['https://www.googleapis.com/auth/youtube.readonly'] and set(scopes).issubset(set(UPLOAD_READONLY_SCOPES)):
             cached_scopes_match = True

        if cached_scopes_match:
             log_status(f"Using existing authenticated service suitable for scopes: {scopes}")
             return youtube_service_global

        log_status(f"Authentication required. Scopes: {scopes}")
        if not os.path.exists(CLIENT_SECRETS_FILE):
            log_status(f"ERROR: Client secrets file not found: {CLIENT_SECRETS_FILE}")
            messagebox.showerror("Authentication Error",
                                 f"Client secrets file '{CLIENT_SECRETS_FILE}' not found.\n"
                                 "Please download it from Google Cloud Console and place it here.")
            return None
        try:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes)
            if COMMENT_SCOPE[0] in scopes:
                 messagebox.showinfo("Permission Request",
                                    "This action requires permission to 'Manage your YouTube account' (for posting comments).\n"
                                    "You will be prompted to grant this permission in your browser.")

            credentials = flow.run_local_server(port=0)
            service = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)

            if set(scopes) == set(UPLOAD_READONLY_SCOPES):
                 youtube_service_global = service
                 log_status("Authentication successful for default scopes. Service cached.")
            else:
                 log_status(f"Authentication successful for specific scopes: {scopes}. Service not cached globally.")

            return service
        except FileNotFoundError:
             log_status(f"ERROR: Client secrets file not found during flow: {CLIENT_SECRETS_FILE}")
             messagebox.showerror("Authentication Error", f"Client secrets file '{CLIENT_SECRETS_FILE}' not found.")
             return None
        except Exception as e:
            if 'access_denied' in str(e).lower():
                 log_status(f"Authentication Error: User denied access for scopes {scopes}.")
                 messagebox.showerror("Authentication Error", f"Permission denied.\nCould not get authorization for scopes:\n{scopes}")
            else:
                 log_status(f"Authentication Error for scopes {scopes}: {e}")
                 messagebox.showerror("Authentication Error", f"Could not authenticate with Google for scopes {scopes}: {e}")
            return None


#   YouTube API Actions
def upload_video(youtube, video_file_path, title, description, thumbnail_path=None, publish_time_utc_iso=None):
    if not youtube:
        log_status("Upload Error: YouTube service object is invalid.")
        messagebox.showerror("Upload Error", "Authentication is needed or has failed for upload scopes.")
        return None

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'categoryId': '22'
        },
        'status': {
            'privacyStatus': 'private' if publish_time_utc_iso else 'public',
            'publishAt': publish_time_utc_iso,
            'selfDeclaredMadeForKids': False,
        }
    }
    log_status(f"Starting upload: '{title}' (Schedule: {publish_time_utc_iso if publish_time_utc_iso else 'Immediate'})")
    try:
        media = MediaFileUpload(video_file_path, mimetype='video/*', resumable=True)
        request = youtube.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media
        )

        response = None
        last_progress = -1
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    if progress > last_progress:
                       log_status(f"Uploading '{title}': {progress}%")
                       last_progress = progress
            except HttpError as http_error:
                if http_error.resp.status in [500, 502, 503, 504]:
                    log_status(f"Resumable upload error for '{title}': {http_error}. Retrying...")
                    time.sleep(5)
                else:
                    log_status(f"Non-resumable API Error during upload chunk for '{title}': {http_error}")
                    raise
            except Exception as chunk_error:
                 log_status(f"Error during upload chunk for '{title}': {chunk_error}")
                 raise

        video_id = response['id']
        log_status(f"Successfully uploaded video '{title}'. Video ID: {video_id}")

        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                log_status(f"Starting thumbnail upload for video ID: {video_id}")
                request_thumbnail = youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path, mimetype='image/*')
                )
                request_thumbnail.execute()
                log_status(f"Successfully uploaded thumbnail for video ID: {video_id}")
            except HttpError as e_thumb_http:
                 log_status(f"API error uploading thumbnail for video ID {video_id}: {e_thumb_http}")
                 messagebox.showwarning("Thumbnail Error", f"Could not upload thumbnail for '{title}':\n{e_thumb_http}\nVideo was uploaded successfully.")
            except Exception as e_thumb:
                 log_status(f"Error uploading thumbnail for video ID {video_id}: {e_thumb}")
                 messagebox.showwarning("Thumbnail Error", f"Could not upload thumbnail for '{title}':\n{e_thumb}")
        elif thumbnail_path:
             log_status(f"Thumbnail file not found, skipping: {thumbnail_path}")
             messagebox.showwarning("Thumbnail Warning", f"Thumbnail file not found:\n{thumbnail_path}\nSkipping thumbnail upload for '{title}'.")

        return response

    except FileNotFoundError as fnf_error:
        log_status(f"File Error during upload setup for '{title}': {fnf_error}")
        messagebox.showerror("File Error", f"File not found:\n{fnf_error}")
        return None
    except HttpError as http_error:
        log_status(f"API Error during upload '{title}': {http_error}")
        messagebox.showerror("API Error", f"Could not upload video '{title}':\n{http_error}")
        return None
    except Exception as e:
        log_status(f"General Error during upload '{title}': {e}")
        messagebox.showerror("Upload Error", f"An unexpected error occurred uploading '{title}':\n{e}")
        return None


def fetch_trending_videos_api(region_code, max_results=25):
    service = get_authenticated_service(scopes=['https://www.googleapis.com/auth/youtube.readonly'])
    if not service:
        log_status("Trending: Authentication failed for readonly scopes.")
        return None

    log_status(f"Fetching trending videos for region: {region_code}...")
    try:
        request = service.videos().list(
            part="snippet,statistics",
            chart="mostPopular",
            regionCode=region_code,
            maxResults=max_results
        )
        response = request.execute()
        items = response.get('items', [])
        log_status(f"Fetched {len(items)} trending videos for region: {region_code}")
        return items
    except HttpError as e:
        log_status(f"API Error fetching trending videos for '{region_code}': {e}")
        messagebox.showerror("API Error", f"Could not fetch trending videos for region '{region_code}':\n{e}")
        return None
    except Exception as e:
        log_status(f"Error fetching trending videos for '{region_code}': {e}")
        messagebox.showerror("Error", f"An error occurred fetching trending videos: {e}")
        return None


def post_comment_api(video_id, comment_text):
    log_status(f"Attempting to post comment on Video ID: {video_id}")
    service = get_authenticated_service(scopes=COMMENT_SCOPE)

    def final_update(success_message=None, error_message=None):
        if success_message:
             log_status(success_message)
             root.after(0, messagebox.showinfo, "Comment Posted", f"Successfully posted comment on Video ID: {video_id}")
        if error_message:
             log_status(error_message)
             root.after(0, messagebox.showerror, "Comment Error", error_message)

        root.after(0, set_comment_manage_buttons_state, tk.NORMAL)
        if status_bar_instance:
            root.after(0, status_bar_instance.hide_progress)
            root.after(0, status_bar_instance.clear)


    if not service:
        final_update(error_message="Comment Posting Error: Authentication failed for comment scope.")
        return

    try:
        request_body = {
          "snippet": {
            "videoId": video_id,
            "topLevelComment": {
              "snippet": {
                "textOriginal": comment_text
              }
            }
          }
        }
        request = service.commentThreads().insert(
            part="snippet",
            body=request_body
        )
        response = request.execute()
        final_update(success_message=f"Successfully posted comment on Video ID {video_id}. Comment ID: {response['id']}")

    except HttpError as e:
        error_content = e.content.decode('utf-8')
        log_status(f"API Error posting comment on Video ID {video_id}: {e}")
        log_status(f"Error details: {error_content}")
        display_error = f"API Error posting comment on Video ID {video_id}:\n{e}"
        try:
            error_json = json.loads(error_content)
            error_reason = error_json.get('error', {}).get('errors', [{}])[0].get('reason', 'Unknown API Error')
            error_message_detail = error_json.get('error', {}).get('message', str(e))

            if error_reason == 'commentsDisabled':
                 display_error = f"Could not post comment.\nReason: Comments are disabled for Video ID {video_id}."
            elif error_reason == 'forbidden':
                 display_error = f"Could not post comment.\nReason: Permission denied. Check API key/OAuth scope or video status for Video ID {video_id}."
            elif error_reason == 'videoNotFound':
                 display_error = f"Could not post comment.\nReason: Video not found for ID {video_id}."
            else:
                 display_error = f"API Error posting comment:\n{error_message_detail}\n(Reason: {error_reason})"
        except json.JSONDecodeError:
            pass
        final_update(error_message=display_error)

    except Exception as e:
        final_update(error_message=f"General Error posting comment on Video ID {video_id}: {e}")

def fetch_video_stats_api(video_id):
    service = get_authenticated_service(scopes=['https://www.googleapis.com/auth/youtube.readonly'])
    if not service:
        log_status(f"Analytics Error: Authentication failed for readonly scopes (Video ID: {video_id}).")
        return None, "Authentication failed"

    log_status(f"Fetching stats for Video ID: {video_id}...")
    try:
        request = service.videos().list(
            part="snippet,statistics",
            id=video_id
        )
        response = request.execute()

        items = response.get('items', [])
        if not items:
            log_status(f"Analytics Error: Video not found (ID: {video_id})")
            return None, "Video not found"

        log_status(f"Successfully fetched stats for Video ID: {video_id}")
        return items[0], None

    except HttpError as e:
        log_status(f"API Error fetching stats for Video ID {video_id}: {e}")
        error_detail = f"API Error: {e}"
        try:
            error_content = e.content.decode('utf-8')
            error_json = json.loads(error_content)
            error_message_detail = error_json.get('error', {}).get('message', str(e))
            error_detail = f"API Error: {error_message_detail}"
        except Exception:
            pass
        return None, error_detail
    except Exception as e:
        log_status(f"General Error fetching stats for Video ID {video_id}: {e}")
        return None, f"Unexpected Error: {e}"


#   File Handling
def get_scheduled_posts_from_json(filepath):
    if not os.path.exists(filepath):
        log_status(f"Schedule file '{filepath}' not found. Creating empty.")
        try:
            with open(filepath, 'w', encoding='utf-8') as f: json.dump([], f)
            return []
        except IOError as e:
            log_status(f"Error creating empty schedule file '{filepath}': {e}")
            messagebox.showerror("File Error", f"Could not create schedule file:\n{e}")
            return []

    try:
        with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
        if not content.strip(): return []
        posts = json.loads(content)
        log_status(f"Loaded {len(posts)} scheduled posts from '{filepath}'.")
        return posts
    except json.JSONDecodeError:
        log_status(f"ERROR reading JSON file: '{filepath}'. Corrupted?")
        messagebox.showerror("JSON Error", f"Error reading schedule file:\n'{filepath}'\nFile seems corrupted. Please check or delete.")
        return []
    except IOError as e:
         log_status(f"ERROR reading file '{filepath}': {e}")
         messagebox.showerror("File Error", f"Could not read schedule file:\n{e}")
         return []
    except Exception as e:
        log_status(f"Unknown error reading JSON file '{filepath}': {e}")
        messagebox.showerror("Error", f"Unexpected error reading schedule file:\n{e}")
        return []

def save_scheduled_posts_to_json(posts, filepath):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(posts, f, indent=4, ensure_ascii=False)
    except IOError as e:
        log_status(f"Error saving schedule file '{filepath}': {e}")
        messagebox.showerror("File Error", f"Could not save schedule file:\n{e}")
    except Exception as e:
        log_status(f"Unknown error saving JSON file '{filepath}': {e}")
        messagebox.showerror("Error", f"Unexpected error saving schedule file:\n{e}")

def load_comment_templates(filepath=COMMENT_TEMPLATES_FILE):
    global comment_templates_list
    if not os.path.exists(filepath):
        log_status(f"Comment template file '{filepath}' not found.")
        comment_templates_list = []
        return comment_templates_list
    try:
        with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
        if not content.strip():
            comment_templates_list = []
        else:
            data = json.loads(content)
            if isinstance(data, list):
                comment_templates_list = data
                log_status(f"Loaded {len(comment_templates_list)} comment templates from '{filepath}'.")
            else:
                log_status(f"Warning: Content in '{filepath}' is not a list. Resetting.")
                comment_templates_list = []
        return comment_templates_list
    except json.JSONDecodeError:
        log_status(f"ERROR reading JSON file: '{filepath}'. Corrupted?")
        messagebox.showwarning("JSON Error", f"Error reading comment template file:\n'{filepath}'. Corrupted? Using empty list.")
        comment_templates_list = []
        return comment_templates_list
    except IOError as e:
         log_status(f"ERROR reading file '{filepath}': {e}")
         messagebox.showerror("File Error", f"Could not read comment template file:\n{e}")
         comment_templates_list = []
         return comment_templates_list
    except Exception as e:
        log_status(f"Unknown error reading JSON file '{filepath}': {e}")
        messagebox.showerror("Error", f"Unexpected error reading comment template file:\n{e}")
        comment_templates_list = []
        return comment_templates_list

def save_comment_templates(templates, filepath=COMMENT_TEMPLATES_FILE):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(templates, f, indent=4, ensure_ascii=False)
        log_status(f"Saved {len(templates)} comment templates to '{filepath}'.")
    except IOError as e:
        log_status(f"Error saving comment template file '{filepath}': {e}")
        messagebox.showerror("File Error", f"Could not save comment template file:\n{e}")
    except Exception as e:
        log_status(f"Unknown error saving JSON file '{filepath}': {e}")
        messagebox.showerror("Error", f"Unexpected error saving comment template file:\n{e}")


#   Scheduler Logic
def process_scheduled_posts():
    global scheduled_posts_data

    posts_to_process_indices = []
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    needs_processing = False

    for i, post in enumerate(scheduled_posts_data):
        if post.get('status') == 'pending':
            scheduled_time_utc_str = post.get('scheduled_time')
            if not scheduled_time_utc_str:
                log_status(f"Skipping post '{post.get('title', 'Untitled')}' due to missing 'scheduled_time'. Marked error.")
                scheduled_posts_data[i]['status'] = 'error_format'
                needs_processing = True
                continue

            try:
                scheduled_time_utc = datetime.datetime.fromisoformat(scheduled_time_utc_str.replace('Z', '+00:00'))
                if scheduled_time_utc <= now_utc + datetime.timedelta(minutes=1):
                     if scheduled_time_utc >= now_utc - datetime.timedelta(minutes=5):
                         log_status(f"Post '{post.get('title', 'Untitled')}' is due (Scheduled: {scheduled_time_utc_str}). Queuing.")
                         posts_to_process_indices.append(i)
                         needs_processing = True
                     else:
                         log_status(f"Post '{post.get('title', 'Untitled')}' scheduled time {scheduled_time_utc_str} is too old. Skipping.")
                         scheduled_posts_data[i]['status'] = 'error_too_old'
                         needs_processing = True

            except ValueError:
                log_status(f"Format error in 'scheduled_time' for post '{post.get('title', 'Untitled')}': '{scheduled_time_utc_str}'. Marked error.")
                scheduled_posts_data[i]['status'] = 'error_format'
                needs_processing = True
            except KeyError:
                 log_status(f"Missing 'scheduled_time' key for post index {i}. Marked error.")
                 scheduled_posts_data[i]['status'] = 'error_format'
                 needs_processing = True

    if not posts_to_process_indices:
        if needs_processing:
             save_scheduled_posts_to_json(scheduled_posts_data, SCHEDULED_POSTS_FILE)
             status_queue.put("update_ui")
        return False

    service = get_authenticated_service(scopes=UPLOAD_READONLY_SCOPES)
    if not service:
        log_status("Scheduler: Authentication failed for upload scopes. Cannot process.")
        return False

    processed_something = False
    for index in posts_to_process_indices:
        if index >= len(scheduled_posts_data) or scheduled_posts_data[index].get('status') != 'pending':
            continue
        post_data = scheduled_posts_data[index]
        title = post_data.get('title', 'Untitled')
        video_path = post_data.get('video_path')
        thumb_path = post_data.get('thumbnail_path')
        description = post_data.get('description', '')
        scheduled_time_utc_iso = post_data.get('scheduled_time')

        log_status(f"Processing scheduled post: '{title}' (Index: {index})")

        file_error = False
        if not video_path or not os.path.exists(video_path):
            log_status(f"Video file not found for '{title}': {video_path}. Marked error.")
            scheduled_posts_data[index]['status'] = 'error_file'
            file_error = True
        if thumb_path and not os.path.exists(thumb_path):
            log_status(f"Thumbnail file not found for '{title}': {thumb_path}. Uploading without thumbnail.")

        if file_error:
            processed_something = True
            continue

        try:
            upload_response = upload_video(
                service,
                video_path,
                title,
                description,
                thumb_path,
                publish_time_utc_iso=scheduled_time_utc_iso
            )

            if upload_response:
                scheduled_posts_data[index]['status'] = 'uploaded'
                scheduled_posts_data[index]['video_id'] = upload_response.get('id')
                log_status(f"Successfully uploaded scheduled post: '{title}' (ID: {upload_response.get('id')})")
            else:
                 if scheduled_posts_data[index]['status'] == 'pending':
                     scheduled_posts_data[index]['status'] = 'error_upload'
                 log_status(f"Upload failed for scheduled post '{title}'. Status is now '{scheduled_posts_data[index]['status']}'.")

            processed_something = True

        except Exception as e:
            log_status(f"Unexpected error during scheduled upload processing for '{title}': {e}")
            scheduled_posts_data[index]['status'] = 'error_unknown'
            processed_something = True

    if processed_something or needs_processing:
        save_scheduled_posts_to_json(scheduled_posts_data, SCHEDULED_POSTS_FILE)
        status_queue.put("update_ui")

    return processed_something

def run_scheduler():
    log_status("Scheduler thread started.")
    while True:
        processed = False
        try:
            if not vietnam_tz:
                time.sleep(5)
                continue

            processed = process_scheduled_posts()
        except Exception as e:
            log_status(f"CRITICAL ERROR in scheduler loop: {e}")

        if threading.main_thread().is_alive():
            sleep_time = 30 if processed else 60
            time.sleep(sleep_time)
        else:
            log_status("Main thread closed. Stopping scheduler thread.")
            break
    log_status("Scheduler thread finished.")

#   GUI Callbacks and Helpers
def browse_file(entry_widget, filetypes):
    initial_dir = os.path.dirname(entry_widget.get()) if entry_widget.get() else os.path.expanduser("~")
    file_path = filedialog.askopenfilename(
        initialdir=initial_dir,
        filetypes=filetypes,
        title=f"Select {'Video' if 'Video' in filetypes[0][0] else 'Image'} File"
    )
    if file_path:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, file_path)

def validate_inputs(check_time=True):
    video_path = video_path_entry.get()
    title = title_entry.get()
    scheduled_time_str_vn = datetime_entry.get()

    if not video_path or not os.path.exists(video_path):
        messagebox.showerror("Input Error", f"Invalid or non-existent video file:\n{video_path}")
        return False, None, None
    if not title.strip():
        messagebox.showerror("Input Error", "Please enter a title.")
        return False, None, None
    thumbnail_path = thumbnail_path_entry.get()
    if thumbnail_path and not os.path.exists(thumbnail_path):
        messagebox.showerror("Input Error", f"Thumbnail file does not exist:\n{thumbnail_path}")
        return False, None, None

    utc_dt = None
    utc_iso_str = None
    if check_time:
        if not scheduled_time_str_vn.strip():
            messagebox.showerror("Input Error", "Please enter the schedule time (Vietnam Time).")
            return False, None, None
        utc_dt, utc_iso_str = convert_vn_str_to_utc_iso(scheduled_time_str_vn.strip())
        if utc_dt is None: return False, None, None
        log_status(f"VN time '{scheduled_time_str_vn}' validated and converted to UTC: {utc_iso_str}")

    return True, utc_dt, utc_iso_str

def set_uploader_buttons_state(state=tk.NORMAL):
    if upload_now_btn: upload_now_btn.config(state=state)
    if schedule_btn: schedule_btn.config(state=state)
    if clear_btn: clear_btn.config(state=state)

def schedule_upload_ui():
    is_valid, utc_dt, scheduled_time_utc_iso = validate_inputs(check_time=True)
    if not is_valid: return

    min_schedule_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=2)
    if utc_dt <= min_schedule_time:
         messagebox.showerror("Input Error", "Schedule time must be at least a few minutes in the future.")
         return

    video_path = video_path_entry.get()
    title = title_entry.get().strip()
    description = description_text.get("1.0", tk.END).strip()
    thumbnail_path = thumbnail_path_entry.get()
    scheduled_time_str_vn = datetime_entry.get().strip()

    new_post = {
        "video_path": video_path, "title": title, "description": description,
        "scheduled_time": scheduled_time_utc_iso,
        "thumbnail_path": thumbnail_path if thumbnail_path else None,
        "status": "pending", "video_id": None
    }

    scheduled_posts_data.append(new_post)
    save_scheduled_posts_to_json(scheduled_posts_data, SCHEDULED_POSTS_FILE)

    log_status(f"Scheduled '{title}' for {scheduled_time_str_vn} (VN) / {scheduled_time_utc_iso} (UTC).")
    messagebox.showinfo("Success", f"Video upload scheduled:\nTitle: '{title}'\nAt: {scheduled_time_str_vn} (VN)")

    clear_input_fields()
    refresh_scheduled_list()

def upload_now_ui():
    is_valid, _, _ = validate_inputs(check_time=False)
    if not is_valid: return

    if not messagebox.askyesno("Confirm Upload", "Upload this video immediately as Public?"):
        return

    video_path = video_path_entry.get()
    title = title_entry.get().strip()
    description = description_text.get("1.0", tk.END).strip()
    thumbnail_path = thumbnail_path_entry.get()

    def upload_task():
        set_uploader_buttons_state(tk.DISABLED)
        if status_bar_instance: root.after(0, status_bar_instance.show_progress)
        log_status(f"Starting immediate upload task for '{title}'...")

        service = get_authenticated_service(scopes=UPLOAD_READONLY_SCOPES)
        upload_successful = False
        if service:
            response = upload_video(service, video_path, title, description, thumbnail_path, publish_time_utc_iso=None)
            if response:
                video_id = response.get('id')
                log_status(f"Immediate upload successful: '{title}', Video ID: {video_id}")
                root.after(0, messagebox.showinfo, "Upload Successful", f"Successfully uploaded video '{title}'\nVideo ID: {video_id}")
                upload_successful = True

                uploaded_post_entry = {
                    "video_path": video_path, "title": title, "description": description,
                    "scheduled_time": None,
                    "thumbnail_path": thumbnail_path if thumbnail_path else None,
                    "status": "uploaded",
                    "video_id": video_id
                }
                scheduled_posts_data.append(uploaded_post_entry)
                save_scheduled_posts_to_json(scheduled_posts_data, SCHEDULED_POSTS_FILE)
                status_queue.put("update_ui")


        else:
            log_status("Upload Now: Authentication failed. Aborting.")

        root.after(0, set_uploader_buttons_state, tk.NORMAL)
        if status_bar_instance:
             root.after(0, status_bar_instance.hide_progress)
             if not upload_successful:
                root.after(0, status_bar_instance.set_text, f"Upload failed for '{title}'. Check logs.")
             else:
                root.after(0, status_bar_instance.clear)
                root.after(0, clear_input_fields)

    threading.Thread(target=upload_task, daemon=True).start()
    log_status("Background thread for immediate upload started.")


def refresh_scheduled_list():
    scheduled_list_treeview.tag_configure('oddrow', background='#F0F0F0')
    scheduled_list_treeview.tag_configure('evenrow', background='white')
    scheduled_list_treeview.tag_configure('uploaded', foreground='green')
    scheduled_list_treeview.tag_configure('error', foreground='red')
    scheduled_list_treeview.tag_configure('pending', foreground='blue')
    scheduled_list_treeview.tag_configure('processing', foreground='orange')

    for item in scheduled_list_treeview.get_children():
        scheduled_list_treeview.delete(item)

    for i, post in enumerate(scheduled_posts_data):
        title = post.get('title', 'N/A')
        status = post.get('status', 'N/A')
        time_utc_str = post.get('scheduled_time', '')
        time_vn_str = convert_utc_to_vn_str(time_utc_str) if time_utc_str else "Uploaded Now"

        row_tag = 'oddrow' if i % 2 else 'evenrow'
        status_tag_map = {
            'uploaded': 'uploaded',
            'pending': 'pending',
            'processing': 'processing',
        }
        status_tag = status_tag_map.get(status)
        if not status_tag and status and status.startswith('error'):
            status_tag = 'error'

        tags = (row_tag, status_tag) if status_tag else (row_tag,)

        scheduled_list_treeview.insert('', tk.END, values=(title, time_vn_str, status), iid=str(i), tags=tags)

    update_analyzable_videos_list()

def on_scheduled_item_select(event):
    selected_items = scheduled_list_treeview.selection()
    if not selected_items: return
    selected_iid = selected_items[0]
    try:
        index = int(selected_iid)
        if 0 <= index < len(scheduled_posts_data):
            load_post_details(scheduled_posts_data[index])
        else:
            clear_input_fields()
    except (ValueError, IndexError):
        clear_input_fields()

def load_post_details(post_data):
    clear_input_fields()
    video_path_entry.insert(0, post_data.get('video_path', ''))
    title_entry.insert(0, post_data.get('title', ''))
    description_text.insert("1.0", post_data.get('description', ''))
    thumbnail_path_entry.insert(0, post_data.get('thumbnail_path', ''))
    utc_time_str = post_data.get('scheduled_time', '')
    if utc_time_str:
        vn_time_str = convert_utc_to_vn_str(utc_time_str)
        if vn_time_str != "N/A" and vn_time_str != "Invalid Date":
            datetime_entry.insert(0, vn_time_str)

def delete_selected_post():
    selected_items = scheduled_list_treeview.selection()
    if not selected_items:
        messagebox.showwarning("No Selection", "Please select a post to delete.")
        return
    selected_iid = selected_items[0]
    try:
        index_to_delete = int(selected_iid)
        if 0 <= index_to_delete < len(scheduled_posts_data):
            post_to_delete = scheduled_posts_data[index_to_delete]
            title = post_to_delete.get('title', 'Untitled')
            status = post_to_delete.get('status', 'N/A')

            confirm_msg = f"Delete '{title}' from this list?\nStatus: {status}\n\n"
            if status == 'pending': confirm_msg += "(This removes it from the schedule.)"
            elif status == 'uploaded': confirm_msg += "(Removes from list only, the YouTube video is NOT deleted.)"
            else: confirm_msg += "(Removes from list.)"

            if messagebox.askyesno("Confirm Deletion", confirm_msg):
                log_status(f"Deleting post index {index_to_delete}: '{title}' (Status: {status})")
                del scheduled_posts_data[index_to_delete]
                save_scheduled_posts_to_json(scheduled_posts_data, SCHEDULED_POSTS_FILE)
                refresh_scheduled_list()
                clear_input_fields()
                log_status(f"Deleted '{title}' from schedule list.")
        else:
            log_status(f"Error: Invalid index ({index_to_delete}) for deletion.")
            messagebox.showerror("Error", "Could not delete (invalid index). Please refresh.")
    except (ValueError, IndexError) as e:
        log_status(f"Error deleting post: {e}")
        messagebox.showerror("Error", f"Could not delete selected post:\n{e}")

def clear_input_fields():
    video_path_entry.delete(0, tk.END)
    title_entry.delete(0, tk.END)
    description_text.delete("1.0", tk.END)
    thumbnail_path_entry.delete(0, tk.END)
    datetime_entry.delete(0, tk.END)
    if scheduled_list_treeview.selection():
         scheduled_list_treeview.selection_remove(scheduled_list_treeview.selection())


def check_status_queue():
    try:
        message = status_queue.get_nowait()
        if message == "update_ui":
            log_status("UI Update requested.")
            refresh_scheduled_list()

    except queue.Empty:
        pass
    finally:
        root.after(1500, check_status_queue)


def fetch_and_display_trending():
    region = region_code_entry.get().strip().upper()
    if not region or len(region) != 2 or not region.isalpha():
        messagebox.showwarning("Invalid Input", "Region Code must be 2 letters (e.g., VN, US).")
        return

    def fetch_task():
        if fetch_trending_btn: root.after(0, lambda: fetch_trending_btn.config(state=tk.DISABLED))
        if status_bar_instance: root.after(0, status_bar_instance.show_progress)
        log_status(f"Starting fetch for trending videos (Region: {region})...")

        trending_videos = fetch_trending_videos_api(region)
        fetch_successful = trending_videos is not None

        root.after(0, display_trending_results, trending_videos, region)
        if fetch_trending_btn: root.after(0, lambda: fetch_trending_btn.config(state=tk.NORMAL))
        if status_bar_instance:
             root.after(0, status_bar_instance.hide_progress)
             if not fetch_successful:
                 root.after(0, status_bar_instance.set_text, f"Failed to fetch trending for {region}.")
             else:
                 root.after(0, status_bar_instance.clear)

    trending_status_label.config(text=f"Fetching for {region}...")
    clear_trending_results("Loading...")
    threading.Thread(target=fetch_task, daemon=True).start()

def clear_trending_results(message=""):
    for item in trending_list_treeview.get_children():
        trending_list_treeview.delete(item)
    if message:
         trending_list_treeview.insert('', tk.END, values=(message, "", ""))

def display_trending_results(videos, region):
    clear_trending_results()
    trending_list_treeview.tag_configure('oddrow', background='#F0F0F0')
    trending_list_treeview.tag_configure('evenrow', background='white')

    if videos is None:
        log_status(f"Failed to display trending for {region} (fetch error).")
        trending_list_treeview.insert('', tk.END, values=(f"Error fetching videos for {region}", "", ""))
        trending_status_label.config(text=f"Region: {region} (Error)")
        return

    if not videos:
        log_status(f"No trending videos found for region: {region}.")
        trending_list_treeview.insert('', tk.END, values=(f"No trending videos found for {region}", "", ""))
        trending_status_label.config(text=f"Region: {region} (No videos)")
        return

    log_status(f"Displaying {len(videos)} trending videos for region: {region}.")
    trending_status_label.config(text=f"Trending: {region} ({len(videos)} videos)")
    for i, video in enumerate(videos):
        snippet = video.get('snippet', {})
        stats = video.get('statistics', {})
        title = snippet.get('title', 'N/A')
        channel = snippet.get('channelTitle', 'N/A')
        view_count_str = stats.get('viewCount')
        view_count_formatted = f"{int(view_count_str):,}" if view_count_str and view_count_str.isdigit() else 'N/A'

        row_tag = 'oddrow' if i % 2 else 'evenrow'
        trending_list_treeview.insert('', tk.END, values=(title, channel, view_count_formatted), iid=f"trend_{i}", tags=(row_tag,))



def refresh_comment_template_listbox():
    comment_template_listbox.delete(0, tk.END)
    for template in comment_templates_list:
        comment_template_listbox.insert(tk.END, template)
    log_status(f"Refreshed comment template listbox ({len(comment_templates_list)} items).")

def set_comment_manage_buttons_state(state=tk.NORMAL):
     if add_comment_btn: add_comment_btn.config(state=state)
     if delete_comment_btn: delete_comment_btn.config(state=state)
     if pick_comment_btn: pick_comment_btn.config(state=state)

     if generate_comments_btn: generate_comments_btn.config(state=state)
     if num_comments_entry: num_comments_entry.config(state=tk.NORMAL if state == tk.NORMAL else tk.DISABLED)


     post_enabled = state == tk.NORMAL and bool(current_random_comment) and bool(video_id_entry.get().strip())
     if post_comment_btn: post_comment_btn.config(state=tk.NORMAL if post_enabled else tk.DISABLED)

def add_comment_template():
    new_template = new_comment_entry.get().strip()
    if not new_template: return
    if new_template in comment_templates_list:
         messagebox.showwarning("Duplicate Entry", "This comment template already exists.")
         return

    comment_templates_list.append(new_template)
    comment_template_listbox.insert(tk.END, new_template)
    new_comment_entry.delete(0, tk.END)
    log_status(f"Added comment template: '{new_template}'")
    save_comment_templates(comment_templates_list)

def delete_selected_comment_template():
    selected_indices = comment_template_listbox.curselection()
    if not selected_indices:
        messagebox.showwarning("No Selection", "Select a comment template to delete.")
        return
    selected_index = selected_indices[0]
    template_to_delete = comment_template_listbox.get(selected_index)

    if messagebox.askyesno("Confirm Deletion", f"Delete this comment template?\n\n'{template_to_delete}'"):
        del comment_templates_list[selected_index]
        comment_template_listbox.delete(selected_index)
        log_status(f"Deleted comment template: '{template_to_delete}'")
        save_comment_templates(comment_templates_list)
        if current_random_comment == template_to_delete:
            pick_random_comment(force_clear=True)
            set_comment_manage_buttons_state(tk.NORMAL)

def pick_random_comment(force_clear=False):
    global current_random_comment
    if force_clear or not comment_templates_list:
        current_random_comment = ""
        display_text = "No comment templates available." if not comment_templates_list else "Comment display cleared."
        random_comment_display.config(state=tk.NORMAL)
        random_comment_display.delete("1.0", tk.END)
        random_comment_display.insert("1.0", display_text)
        random_comment_display.config(state=tk.DISABLED)
        if not comment_templates_list and not force_clear:
            messagebox.showwarning("Empty List", "No comment templates to choose from.")
        set_comment_manage_buttons_state(tk.NORMAL)
        return

    chosen_comment = random.choice(comment_templates_list)
    current_random_comment = chosen_comment
    random_comment_display.config(state=tk.NORMAL)
    random_comment_display.delete("1.0", tk.END)
    random_comment_display.insert("1.0", f"{chosen_comment}")
    random_comment_display.config(state=tk.DISABLED)
    log_status(f"Randomly selected comment: '{chosen_comment}'")
    set_comment_manage_buttons_state(tk.NORMAL)

def post_comment_ui():
    video_id = video_id_entry.get().strip()
    comment_to_post = current_random_comment

    if not video_id:
        messagebox.showwarning("Input Required", "Enter the Video ID.")
        return
    if not comment_to_post:
         messagebox.showwarning("No Comment Selected", "Click 'Pick Random Comment' first or ensure templates exist.")
         return

    confirm_msg = f"Post this comment:\n\n'{comment_to_post}'\n\nTo Video ID:\n{video_id}?"
    if messagebox.askyesno("Confirm Comment Post", confirm_msg):
        log_status(f"Starting background thread to post comment on Video ID: {video_id}")
        set_comment_manage_buttons_state(tk.DISABLED)
        if status_bar_instance: status_bar_instance.show_progress()
        log_status(f"Posting comment to {video_id}...")

        comment_thread = threading.Thread(target=post_comment_api, args=(video_id, comment_to_post), daemon=True)
        comment_thread.start()

def generate_meaningful_comments_ui():
    try:
        num_str = num_comments_entry.get()
        if not num_str.isdigit():
            messagebox.showerror("Input Error", "Please enter a valid number for comments.")
            return
        num_to_generate = int(num_str)
        if num_to_generate <= 0:
            messagebox.showerror("Input Error", "Number of comments must be greater than 0.")
            return
        if num_to_generate > 5000: # Limit for practical reasons
             if not messagebox.askyesno("Confirmation", f"Generating {num_to_generate:,} comments might take some time and could result in many similar templates if the base list is small. This will add to your existing templates. Proceed?"):
                return
        elif not messagebox.askyesno("Confirm Generation", f"This will attempt to generate up to {num_to_generate} meaningful comment templates and add them to your list. Some may be duplicates if generated multiple times. Proceed?"):
            return

    except ValueError:
        messagebox.showerror("Input Error", "Invalid number entered.")
        return

    log_status(f"Generating up to {num_to_generate} meaningful comments...")
    if status_bar_instance: status_bar_instance.show_progress()
    set_comment_manage_buttons_state(tk.DISABLED)

    def generation_task():
        newly_generated_comments_set = set() # Use set to avoid duplicates within this generation batch
        existing_set = set(comment_templates_list)

        generated_count = 0
        attempts = 0
        max_attempts = num_to_generate * 3 # Try a bit harder to get unique comments

        while generated_count < num_to_generate and attempts < max_attempts:
            attempts += 1
            base_comment = random.choice(MEANINGFUL_COMMENT_BASES)
            comment_with_optional_emoji = base_comment

            if random.random() < 0.6: # 60% chance to add an emoji
                already_has_emoji = any(base_comment.endswith(e) for e in EMOJIS_LIST)
                if not already_has_emoji:
                    comment_with_optional_emoji += " " + random.choice(EMOJIS_LIST)

            final_comment = comment_with_optional_emoji
            if random.random() < 0.3: # 30% chance to add a suffix
                already_has_suffix = any(final_comment.endswith(s) for s in COMMENT_SUFFIXES)
                if not already_has_suffix:
                     final_comment += " " + random.choice(COMMENT_SUFFIXES)

            final_comment = final_comment.strip()
            final_comment = final_comment[:490] # YouTube comment limit is 10000, but practically shorter is better. 500 is a good limit.

            if final_comment not in existing_set and final_comment not in newly_generated_comments_set:
                newly_generated_comments_set.add(final_comment)
                generated_count += 1

        added_to_main_list_count = 0
        if newly_generated_comments_set:
            for c in newly_generated_comments_set:
                if c not in comment_templates_list: # Final check before adding to global list
                    comment_templates_list.append(c)
                    added_to_main_list_count +=1
            if added_to_main_list_count > 0:
                save_comment_templates(comment_templates_list)
            log_status(f"Generated {len(newly_generated_comments_set)} unique comments. Added {added_to_main_list_count} new comments to the global list.")
            root.after(0, messagebox.showinfo, "Success", f"{added_to_main_list_count} new meaningful comment templates added (out of {len(newly_generated_comments_set)} unique generated this run).")
        else:
            log_status("No new unique meaningful comments were generated in this batch.")
            root.after(0, messagebox.showinfo, "Info", "No new unique meaningful comments generated (all might exist or number was 0).")

        root.after(0, refresh_comment_template_listbox)
        root.after(0, lambda: num_comments_entry.delete(0, tk.END))
        if status_bar_instance:
            root.after(0, status_bar_instance.hide_progress)
            root.after(0, status_bar_instance.clear)
        root.after(0, set_comment_manage_buttons_state, tk.NORMAL)

    threading.Thread(target=generation_task, daemon=True).start()

def update_analyzable_videos_list():
    if not analytics_video_combobox: return

    uploaded_videos = []
    analytics_video_combobox.video_map = {}

    for post in scheduled_posts_data:
        if post.get('status') == 'uploaded' and post.get('video_id'):
            title = post.get('title', 'Untitled Video')
            video_id = post.get('video_id')
            display_title = f"{title} ({video_id})"
            uploaded_videos.append(display_title)
            analytics_video_combobox.video_map[display_title] = video_id

    if uploaded_videos:
        current_selection = analytics_video_combobox.get()
        analytics_video_combobox['values'] = uploaded_videos
        if current_selection in uploaded_videos:
            analytics_video_combobox.set(current_selection)
        else:
            analytics_video_combobox.current(0)
        analytics_video_combobox.config(state='readonly')
        if analyze_video_btn: analyze_video_btn.config(state=tk.NORMAL)
    else:
        analytics_video_combobox['values'] = []
        analytics_video_combobox.set("No uploaded videos found")
        analytics_video_combobox.config(state='disabled')
        if analyze_video_btn: analyze_video_btn.config(state=tk.DISABLED)
        clear_analytics_results()

    log_status(f"Updated analyzable videos list: {len(uploaded_videos)} items.")

def clear_analytics_results():
    global canvas_widget
    if canvas_widget:
        canvas_widget.get_tk_widget().destroy()
        canvas_widget = None
        plt.close('all')
    if analytics_report_text:
        analytics_report_text.config(state=tk.NORMAL)
        analytics_report_text.delete("1.0", tk.END)
        analytics_report_text.config(state=tk.DISABLED)

def _trigger_analysis_task(video_id, display_identifier_for_ui):
    log_status(f"Analysis requested for: {display_identifier_for_ui} (Actual ID: {video_id})")
    clear_analytics_results()

    if analyze_video_btn: root.after(0, lambda: analyze_video_btn.config(state=tk.DISABLED))
    if analyze_custom_id_btn: root.after(0, lambda: analyze_custom_id_btn.config(state=tk.DISABLED))
    if status_bar_instance: root.after(0, status_bar_instance.show_progress)
    log_status(f"Fetching analytics data for {video_id}...")

    def analysis_task_internal():
        video_data, error = fetch_video_stats_api(video_id)
        analysis_successful = video_data is not None

        root.after(0, display_analysis_results, video_data, error, display_identifier_for_ui)

        if analyze_video_btn:
             is_combobox_valid = analytics_video_combobox.get() and analytics_video_combobox.cget('state') != 'disabled'
             root.after(0, lambda: analyze_video_btn.config(state=tk.NORMAL if is_combobox_valid else tk.DISABLED))
        if analyze_custom_id_btn: root.after(0, lambda: analyze_custom_id_btn.config(state=tk.NORMAL))

        if status_bar_instance:
             root.after(0, status_bar_instance.hide_progress)
             if not analysis_successful:
                 root.after(0, status_bar_instance.set_text, f"Analytics failed for {video_id}. {error}")
             else:
                 root.after(0, status_bar_instance.clear)

    threading.Thread(target=analysis_task_internal, daemon=True).start()

def analyze_selected_video_ui():
    if not analytics_video_combobox or analytics_video_combobox.current() == -1 or analytics_video_combobox.cget('state') == 'disabled':
        messagebox.showwarning("No Selection", "Please select a video from the list.")
        return

    selected_display_title = analytics_video_combobox.get()
    video_id = analytics_video_combobox.video_map.get(selected_display_title)

    if not video_id:
        messagebox.showerror("Error", "Could not find Video ID for the selected item.")
        log_status(f"Error: Video ID not found for display title '{selected_display_title}'")
        return

    _trigger_analysis_task(video_id, selected_display_title)


def analyze_custom_video_id_ui():
    video_id = custom_video_id_analytics_entry.get().strip()
    if not video_id:
        messagebox.showwarning("Input Required", "Please enter a Video ID to analyze.")
        return

    if len(video_id) != 11 :
         messagebox.showwarning("Invalid Format", "Video ID usually has 11 characters. Please check.")


    _trigger_analysis_task(video_id, f"Custom ID: {video_id}")


def display_analysis_results(video_data, error, display_identifier):
    clear_analytics_results()

    if error:
        log_status(f"Failed to display analysis for '{display_identifier}': {error}")
        messagebox.showerror("Analysis Error", f"Could not get data for '{display_identifier}':\n{error}")
        report_content = f"Error fetching data for '{display_identifier}':\n\n{error}"
        if analytics_report_text:
            analytics_report_text.config(state=tk.NORMAL)
            analytics_report_text.insert("1.0", report_content)
            analytics_report_text.config(state=tk.DISABLED)
        return

    if not video_data:
        log_status(f"No video data returned for '{display_identifier}', cannot display.")
        if analytics_report_text:
            analytics_report_text.config(state=tk.NORMAL)
            analytics_report_text.insert("1.0", f"No data returned for '{display_identifier}'. The video might be private, deleted, or the ID is incorrect.")
            analytics_report_text.config(state=tk.DISABLED)
        return

    snippet = video_data.get('snippet', {})
    stats = video_data.get('statistics', {})

    video_api_title = snippet.get('title', display_identifier)

    publish_time_utc = snippet.get('publishedAt')
    publish_time_vn = convert_utc_to_vn_str(publish_time_utc) if publish_time_utc else "N/A"

    def safe_int(value):
        try: return int(value)
        except (ValueError, TypeError): return 0

    views = safe_int(stats.get('viewCount'))
    likes = safe_int(stats.get('likeCount'))
    comments = safe_int(stats.get('commentCount'))

    if analytics_chart_frame:
        try:
            data = {'Metric': ['Views', 'Likes', 'Comments'],
                    'Count': [views, likes, comments]}
            df = pd.DataFrame(data)

            fig, ax = plt.subplots(figsize=(6, 3.5), dpi=100)
            bars = ax.bar(df['Metric'], df['Count'], color=['skyblue', 'lightcoral', 'lightgreen'])

            ax.set_ylabel('Count')
            chart_title_text = video_api_title[:50] + ("..." if len(video_api_title) > 50 else "")
            ax.set_title(f'Video Performance Metrics\n({chart_title_text})')

            ax.tick_params(axis='x', rotation=0)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

            max_val_for_ylim = max(views, likes, comments, 1)
            top_limit = max(math.ceil(max_val_for_ylim * 1.15), 5)
            ax.set_ylim(bottom=0, top=top_limit)

            if top_limit <= 10 and top_limit > 0 :
                 ax.yaxis.set_major_locator(mticker.MultipleLocator(1))
            elif top_limit > 10 and top_limit <= 50:
                 ax.yaxis.set_major_locator(mticker.MultipleLocator(math.ceil(top_limit / 10.0)))
            else:
                 ax.yaxis.set_major_locator(mticker.AutoLocator())


            for bar in bars:
                 yval = bar.get_height()
                 if yval > 0 or (yval == 0 and max_val_for_ylim <=1):
                     ax.text(bar.get_x() + bar.get_width()/2.0, yval, f'{yval:,}', va='bottom', ha='center', fontsize=9)

            global canvas_widget
            canvas_widget = FigureCanvasTkAgg(fig, master=analytics_chart_frame)
            canvas_widget.draw()
            canvas_widget.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            plt.tight_layout()

        except Exception as e:
            log_status(f"Error creating analytics chart: {e}")
            if analytics_report_text:
                analytics_report_text.config(state=tk.NORMAL)
                analytics_report_text.insert(tk.END, f"\n\nError generating chart: {e}")
                analytics_report_text.config(state=tk.DISABLED)

    if analytics_report_text:
        report_content = f"--- Statistics Report for: {display_identifier} ---\n\n"
        if video_api_title != display_identifier and 'Custom ID' not in display_identifier:
             report_content += f"Video Title (from API): {video_api_title}\n"
        elif 'Custom ID' in display_identifier and video_api_title != display_identifier:
             report_content += f"Video Title (from API): {video_api_title}\n"

        report_content += f"Video ID: {video_data.get('id', 'N/A')}\n"
        report_content += f"Published (VN Time): {publish_time_vn}\n\n"
        report_content += f"Views: {views:,}\n"
        report_content += f"Likes: {likes:,}\n"
        report_content += f"Comments: {comments:,}\n"

        analytics_report_text.config(state=tk.NORMAL)
        analytics_report_text.delete("1.0", tk.END)
        analytics_report_text.insert("1.0", report_content)
        analytics_report_text.config(state=tk.DISABLED)

    log_status(f"Displayed analytics for '{display_identifier}'")


#   Main Application Setup
if __name__ == "__main__":
    try:
        root = ThemedTk(theme="arc")
    except tk.TclError:
        print("WARNING: ttktheme 'arc' not found, falling back to default Tk.")
        root = tk.Tk()

    root.title("YouTube Tool")
    root.geometry("1000x800")

    style = ttk.Style(root)
    style.configure("Treeview.Heading", font=('Helvetica', 10, 'bold'))
    style.configure("TButton", padding=5)
    style.configure("TLabelframe.Label", font=('Helvetica', 11, 'bold'))

    if not initialize_timezone():
        root.destroy()
        exit()

    scheduled_posts_data = get_scheduled_posts_from_json(SCHEDULED_POSTS_FILE)
    comment_templates_list = load_comment_templates()

    status_bar_instance = StatusBar(root)
    status_bar_instance.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(5, 0))

    notebook = ttk.Notebook(root)
    notebook.pack(pady=10, padx=10, fill="both", expand=True)

    # === Tab 1: Uploader & Scheduler ===
    uploader_tab = ttk.Frame(notebook, padding="15")
    notebook.add(uploader_tab, text=' Upload & Schedule ')
    input_frame = ttk.LabelFrame(uploader_tab, text=" Video Details ", padding="15")
    input_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
    input_frame.columnconfigure(1, weight=1)
    ttk.Label(input_frame, text="Video File:").grid(row=0, column=0, padx=5, pady=6, sticky="w")
    video_path_entry = ttk.Entry(input_frame, width=60)
    video_path_entry.grid(row=0, column=1, padx=5, pady=6, sticky="ew")
    ttk.Button(input_frame, text="Browse...", command=lambda: browse_file(video_path_entry, [("Video Files", "*.mp4 *.avi *.mov *.mkv *.webm"), ("All Files", "*.*")])).grid(row=0, column=2, padx=5, pady=6)
    ttk.Label(input_frame, text="Title:").grid(row=1, column=0, padx=5, pady=6, sticky="w")
    title_entry = ttk.Entry(input_frame)
    title_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=6, sticky="ew")
    ttk.Label(input_frame, text="Description:").grid(row=2, column=0, padx=5, pady=6, sticky="nw")
    description_text = scrolledtext.ScrolledText(input_frame, height=5, width=50, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1, font=('TkDefaultFont', 9))
    description_text.grid(row=2, column=1, columnspan=2, padx=5, pady=6, sticky="ew")
    ttk.Label(input_frame, text="Thumbnail:").grid(row=3, column=0, padx=5, pady=6, sticky="w")
    thumbnail_path_entry = ttk.Entry(input_frame)
    thumbnail_path_entry.grid(row=3, column=1, padx=5, pady=6, sticky="ew")
    ttk.Button(input_frame, text="Browse...", command=lambda: browse_file(thumbnail_path_entry, [("Image Files", "*.png *.jpg *.jpeg *.webp"), ("All Files", "*.*")])).grid(row=3, column=2, padx=5, pady=6)
    time_label = ttk.Label(input_frame, text="Schedule (VN Time):")
    time_label.grid(row=4, column=0, padx=5, pady=6, sticky="w")
    datetime_entry = ttk.Entry(input_frame)
    datetime_entry.grid(row=4, column=1, padx=5, pady=6, sticky="ew")
    time_format_label = ttk.Label(input_frame, text="YYYY-MM-DD HH:MM:SS", foreground="grey")
    time_format_label.grid(row=4, column=2, padx=5, pady=6, sticky="w")
    button_frame_input = ttk.Frame(input_frame)
    button_frame_input.grid(row=5, column=0, columnspan=3, pady=(20, 5))
    upload_now_btn = ttk.Button(button_frame_input, text="Upload Now (Public)", command=upload_now_ui)
    upload_now_btn.pack(side=tk.LEFT, padx=10)
    schedule_btn = ttk.Button(button_frame_input, text="Schedule Upload", command=schedule_upload_ui)
    schedule_btn.pack(side=tk.LEFT, padx=10)
    clear_btn = ttk.Button(button_frame_input, text="Clear Fields", command=clear_input_fields)
    clear_btn.pack(side=tk.LEFT, padx=10)
    list_frame = ttk.LabelFrame(uploader_tab, text=" Scheduled & Uploaded Posts ", padding="10")
    list_frame.grid(row=1, column=0, padx=0, pady=15, sticky="nsew")
    list_frame.rowconfigure(0, weight=1)
    list_frame.columnconfigure(0, weight=1)
    columns_sched = ('title', 'time_vn', 'status')
    scheduled_list_treeview = ttk.Treeview(list_frame, columns=columns_sched, show='headings', height=8)
    scheduled_list_treeview.heading('title', text='Title', anchor='w')
    scheduled_list_treeview.heading('time_vn', text='Time (VN) / Status', anchor='center')
    scheduled_list_treeview.heading('status', text='Status', anchor='center')
    scheduled_list_treeview.column('title', width=350, stretch=tk.YES, anchor='w')
    scheduled_list_treeview.column('time_vn', width=160, stretch=tk.NO, anchor='center')
    scheduled_list_treeview.column('status', width=100, stretch=tk.NO, anchor='center')
    scrollbar_sched = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=scheduled_list_treeview.yview)
    scheduled_list_treeview.configure(yscroll=scrollbar_sched.set)
    scheduled_list_treeview.grid(row=0, column=0, sticky="nsew")
    scrollbar_sched.grid(row=0, column=1, sticky="ns")
    button_frame_list = ttk.Frame(list_frame)
    button_frame_list.grid(row=1, column=0, columnspan=2, pady=(10, 0))
    ttk.Button(button_frame_list, text="Refresh List", command=refresh_scheduled_list).pack(side=tk.LEFT, padx=10)
    ttk.Button(button_frame_list, text="Delete Selected (List Only)", command=delete_selected_post).pack(side=tk.LEFT, padx=10)
    scheduled_list_treeview.bind('<<TreeviewSelect>>', on_scheduled_item_select)
    uploader_tab.rowconfigure(1, weight=1)
    uploader_tab.columnconfigure(0, weight=1)

    # === Tab 2: Trending Videos ===
    trending_tab = ttk.Frame(notebook, padding="15")
    notebook.add(trending_tab, text=' Trending Videos ')
    trending_controls_frame = ttk.Frame(trending_tab)
    trending_controls_frame.pack(pady=10, fill="x")
    ttk.Label(trending_controls_frame, text="Region Code:").pack(side=tk.LEFT, padx=(0, 5))
    region_code_entry = ttk.Entry(trending_controls_frame, width=5)
    region_code_entry.insert(0, "VN")
    region_code_entry.pack(side=tk.LEFT, padx=5)
    fetch_trending_btn = ttk.Button(trending_controls_frame, text="Get Trending", command=fetch_and_display_trending)
    fetch_trending_btn.pack(side=tk.LEFT, padx=10)
    trending_status_label = ttk.Label(trending_controls_frame, text="Enter 2-letter code (e.g., VN, US)")
    trending_status_label.pack(side=tk.LEFT, padx=10, fill='x', expand=True)
    trending_list_frame = ttk.LabelFrame(trending_tab, text=" Top Trending Videos ", padding="10")
    trending_list_frame.pack(pady=10, fill="both", expand=True)
    columns_trend = ('title', 'channel', 'views')
    trending_list_treeview = ttk.Treeview(trending_list_frame, columns=columns_trend, show='headings')
    trending_list_treeview.heading('title', text='Title', anchor=tk.CENTER)
    trending_list_treeview.heading('channel', text='Channel', anchor=tk.CENTER)
    trending_list_treeview.heading('views', text='View Count', anchor=tk.CENTER)
    trending_list_treeview.column('title', width=600, stretch=tk.YES, anchor='w')
    trending_list_treeview.column('channel', width=200, stretch=tk.NO, anchor='w')
    trending_list_treeview.column('views', width=150, stretch=tk.NO, anchor='e')
    scrollbar_trend = ttk.Scrollbar(trending_list_frame, orient=tk.VERTICAL, command=trending_list_treeview.yview)
    trending_list_treeview.configure(yscroll=scrollbar_trend.set)
    trending_list_treeview.pack(side=tk.LEFT, fill="both", expand=True)
    scrollbar_trend.pack(side=tk.RIGHT, fill="y")

    # === Tab 3: Auto Interaction ===
    interaction_tab = ttk.Frame(notebook, padding="15")
    notebook.add(interaction_tab, text=' Comment Tools ')
    comment_frame = ttk.LabelFrame(interaction_tab, text=" Comment Templates ", padding="10")
    comment_frame.grid(row=0, column=0, pady=10, padx=0, sticky="nsew")
    comment_frame.columnconfigure(0, weight=1)
    comment_list_frame = ttk.Frame(comment_frame)
    comment_list_frame.grid(row=0, column=0, pady=5, sticky='nsew')
    comment_list_frame.columnconfigure(0, weight=1)
    comment_list_frame.rowconfigure(1, weight=1)
    ttk.Label(comment_list_frame, text="Saved Comments:").grid(row=0, column=0, sticky='w', padx=5)
    comment_scrollbar = ttk.Scrollbar(comment_list_frame, orient=tk.VERTICAL)
    comment_template_listbox = tk.Listbox(comment_list_frame, height=8, yscrollcommand=comment_scrollbar.set, relief=tk.SOLID, borderwidth=1, exportselection=False)
    comment_scrollbar.config(command=comment_template_listbox.yview)
    comment_template_listbox.grid(row=1, column=0, sticky='nsew', padx=(5,0), pady=5)
    comment_scrollbar.grid(row=1, column=1, sticky='ns', pady=5)
    comment_input_frame = ttk.Frame(comment_frame)
    comment_input_frame.grid(row=1, column=0, pady=5, sticky='ew')
    comment_input_frame.columnconfigure(1, weight=1)
    ttk.Label(comment_input_frame, text="New:").grid(row=0, column=0, padx=(5,2), pady=5, sticky='w')
    new_comment_entry = ttk.Entry(comment_input_frame)
    new_comment_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
    add_comment_btn = ttk.Button(comment_input_frame, text="Add", command=add_comment_template, width=5)
    add_comment_btn.grid(row=0, column=2, padx=(0,5), pady=5)
    comment_button_frame = ttk.Frame(comment_frame)
    comment_button_frame.grid(row=2, column=0, pady=(5, 0))
    delete_comment_btn = ttk.Button(comment_button_frame, text="Delete Selected", command=delete_selected_comment_template)
    delete_comment_btn.pack(side=tk.LEFT, padx=10)

    generate_comments_frame = ttk.LabelFrame(comment_frame, text=" Generate Meaningful Comments ", padding="10")
    generate_comments_frame.grid(row=3, column=0, pady=(10,5), sticky="ew")
    generate_comments_frame.columnconfigure(1, weight=0)

    ttk.Label(generate_comments_frame, text="Number to generate:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    num_comments_entry = ttk.Entry(generate_comments_frame, width=10)
    num_comments_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

    generate_comments_btn = ttk.Button(generate_comments_frame, text="Generate & Add", command=generate_meaningful_comments_ui)
    generate_comments_btn.grid(row=0, column=2, padx=5, pady=5, sticky="e")


    post_frame = ttk.LabelFrame(interaction_tab, text=" Post Random Comment ", padding="10")
    post_frame.grid(row=1, column=0, pady=15, padx=0, sticky="nsew")
    post_frame.columnconfigure(1, weight=1)
    random_select_frame = ttk.Frame(post_frame)
    random_select_frame.grid(row=0, column=0, columnspan=3, pady=5, sticky='ew')
    random_select_frame.columnconfigure(1, weight=1)
    pick_comment_btn = ttk.Button(random_select_frame, text="Pick Random Comment", command=pick_random_comment)
    pick_comment_btn.grid(row=0, column=0, padx=(5,10), pady=5)
    random_comment_display = scrolledtext.ScrolledText(random_select_frame, height=3, width=60, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1, font=('TkDefaultFont', 9), state=tk.DISABLED)
    random_comment_display.grid(row=0, column=1, sticky='ew', pady=5, padx=5)
    pick_random_comment(force_clear=True)
    post_action_frame = ttk.Frame(post_frame)
    post_action_frame.grid(row=1, column=0, columnspan=3, pady=10, sticky='ew')
    ttk.Label(post_action_frame, text="Video ID:").pack(side=tk.LEFT, padx=(5, 5))
    video_id_entry = ttk.Entry(post_action_frame, width=20)
    video_id_entry.pack(side=tk.LEFT, padx=5)
    video_id_entry.bind("<KeyRelease>", lambda event: set_comment_manage_buttons_state(tk.NORMAL))
    post_comment_btn = ttk.Button(post_action_frame, text="Post Selected Comment", command=post_comment_ui, state=tk.DISABLED)
    post_comment_btn.pack(side=tk.LEFT, padx=10)
    interaction_tab.rowconfigure(0, weight=3)
    interaction_tab.rowconfigure(1, weight=1)
    interaction_tab.columnconfigure(0, weight=1)

    # === Tab 4: Analytics ===
    analytics_tab = ttk.Frame(notebook, padding="15")
    notebook.add(analytics_tab, text=' Analytics ')
    analytics_controls_frame = ttk.Frame(analytics_tab)
    analytics_controls_frame.pack(pady=10, fill="x")

    combobox_frame = ttk.Frame(analytics_controls_frame)
    combobox_frame.pack(side=tk.LEFT, fill='x', expand=False, padx=(0,10))
    ttk.Label(combobox_frame, text="Select Uploaded Video:").pack(side=tk.LEFT, padx=(0, 5))
    analytics_video_combobox = ttk.Combobox(combobox_frame, width=45, state='disabled')
    analytics_video_combobox.pack(side=tk.LEFT, padx=5)
    analyze_video_btn = ttk.Button(combobox_frame, text="Analyze Selected", command=analyze_selected_video_ui, state=tk.DISABLED)
    analyze_video_btn.pack(side=tk.LEFT, padx=10)

    custom_id_controls_frame = ttk.Frame(analytics_controls_frame)
    custom_id_controls_frame.pack(side=tk.LEFT, fill='x', expand=True)
    ttk.Label(custom_id_controls_frame, text="Or Enter Video ID:").pack(side=tk.LEFT, padx=(0,5))
    custom_video_id_analytics_entry = ttk.Entry(custom_id_controls_frame, width=15)
    custom_video_id_analytics_entry.pack(side=tk.LEFT, padx=5)
    analyze_custom_id_btn = ttk.Button(custom_id_controls_frame, text="Analyze Custom ID", command=analyze_custom_video_id_ui)
    analyze_custom_id_btn.pack(side=tk.LEFT, padx=5)


    analytics_display_frame = ttk.Frame(analytics_tab)
    analytics_display_frame.pack(pady=10, fill="both", expand=True)
    analytics_display_frame.columnconfigure(0, weight=1)
    analytics_display_frame.columnconfigure(1, weight=1)
    analytics_display_frame.rowconfigure(0, weight=1)
    analytics_chart_labelframe = ttk.LabelFrame(analytics_display_frame, text=" Performance Chart ", padding="5")
    analytics_chart_labelframe.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="nsew")
    analytics_chart_frame = ttk.Frame(analytics_chart_labelframe)
    analytics_chart_frame.pack(fill="both", expand=True)
    analytics_report_labelframe = ttk.LabelFrame(analytics_display_frame, text=" Statistics Report ", padding="5")
    analytics_report_labelframe.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="nsew")
    analytics_report_text = scrolledtext.ScrolledText(analytics_report_labelframe, height=10, width=40, wrap=tk.WORD, state=tk.DISABLED, relief=tk.SOLID, borderwidth=1)
    analytics_report_text.pack(fill="both", expand=True, padx=5, pady=5)


    # === Initialize UI and Start Background Threads ===
    refresh_scheduled_list()
    refresh_comment_template_listbox()
    set_comment_manage_buttons_state(tk.NORMAL)

    log_status("Application started. Ready.")
    log_status(f"Schedule Time Format: YYYY-MM-DD HH:MM:SS (Vietnam Time)")
    log_status(f"Comment posting requires 'Manage YouTube' permission.")
    log_status(f"Analytics require 'YouTube Data API v3' enabled and readonly permission.")

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    root.after(1500, check_status_queue)

    root.mainloop()

    log_status("Application closed.")
    print("Exiting application.")