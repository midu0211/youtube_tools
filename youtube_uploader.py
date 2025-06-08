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
import webbrowser
from PIL import Image, ImageTk
from urllib.parse import urlparse, parse_qs

# --- Hằng số và Biến toàn cục ---
CLIENT_SECRETS_FILE = 'client_secret.json'
ALL_SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/youtube.force-ssl' # Scope này bao gồm cả quyền xóa video
]
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'
SCHEDULED_POSTS_FILE = 'scheduled_posts.json'
COMMENT_TEMPLATES_FILE = 'comment_templates.json'
VIETNAM_TZ_STR = 'Asia/Ho_Chi_Minh'

status_queue = queue.Queue()
youtube_service_global = None
auth_lock = threading.Lock()
scheduled_posts_data = []
trending_videos_data = []
comment_templates_list = []
my_playlists = {}
vietnam_tz = None
current_random_comment = ""
icons = {}

# --- Các biến cho thành phần giao diện (UI) ---
status_bar_instance = None
upload_now_btn, schedule_btn, clear_btn = None, None, None
fetch_trending_btn = None
post_comment_btn, pick_comment_btn, add_comment_btn, delete_comment_btn = None, None, None, None
analyze_video_btn, analyze_comments_btn = None, None
analytics_video_combobox, analytics_chart_frame, analytics_report_text = None, None, None
canvas_widget = None
num_comments_entry, generate_comments_btn = None, None
custom_video_url_entry = None
log_text_widget = None
playlist_combobox, refresh_playlists_btn = None, None
video_id_entry_for_comment = None

# --- Mẫu bình luận và từ khóa phân tích cảm xúc ---
MEANINGFUL_COMMENT_BASES = ["Video tuyệt vời!", "Nội dung rất hay, cảm ơn bạn đã chia sẻ.", "Mình rất thích video này.", "Làm tốt lắm! Tiếp tục phát huy nhé.", "Video này thật sự hữu ích.", "Chất lượng video tuyệt vời.", "Wow, ấn tượng thật!", "Cảm ơn vì những thông tin giá trị.", "Rất sáng tạo!", "Hay lắm bạn ơi!", "Xem xong thấy có thêm động lực. Cảm ơn bạn!", "Chúc mừng bạn đã có một video thành công!", "Yêu bạn!", "Quá đỉnh!", "Hay quá đi mất!", "Tuyệt vời! Bạn làm rất tốt.", "Video này xứng đáng triệu view!", "Tuyệt cú mèo!", "Tuyệt!", "Hay!", "Chất!", "Đỉnh!", "Oke bạn ơi.", "Thích nha.", "Good job!", "Amazing!", "Perfect!", "Awesome!", "Cảm ơn bạn nhiều.", "Thanks for sharing!", "Rất biết ơn bạn.", "Cảm ơn vì đã làm video này.", "Thank you!", "Video hay, tiếp tục phát huy nhé kênh.", "Nội dung chất lượng, mình đã sub kênh.", "Video ý nghĩa quá.", "Mình đã học được nhiều điều từ video này.", "Xem giải trí mà vẫn có kiến thức.", "Đúng thứ mình đang tìm."]
EMOJIS_LIST = ["👍", "❤️", "🎉", "💯", "🔥", "😮", "😂", "✨", "🌟", "😊", "😃", "😍", "🙏", "🙌", "👌", "💖", "🤣", "🤩"]
COMMENT_SUFFIXES = ["Rất mong video tiếp theo của bạn!", "Cố gắng lên nhé!", "Chúc kênh ngày càng phát triển!", "Tuyệt vời ông mặt trời!", "Luôn ủng hộ bạn!", "5 sao cho video này!"]
POSITIVE_KEYWORDS_VI = ['tuyệt vời', 'hay', 'hữu ích', 'cảm ơn', 'thích', 'chất lượng', 'đỉnh', 'sáng tạo', 'tốt', 'ý nghĩa', 'yêu', 'good', 'amazing', 'perfect', 'awesome', 'nice']
NEGATIVE_KEYWORDS_VI = ['tệ', 'dở', 'chán', 'ghét', 'xấu', 'không hay', 'nhảm', 'bad', 'dislike', 'tốn thời gian']

# --- Lớp và Hàm hỗ trợ giao diện ---
class PlaceholderEntry(ttk.Entry):
    def __init__(self, master=None, placeholder="PLACEHOLDER", color='grey', **kwargs):
        super().__init__(master, **kwargs)
        self.placeholder = placeholder
        self.placeholder_color = color
        self.default_fg_color = self['foreground']
        self.bind("<FocusIn>", self.on_focus_in)
        self.bind("<FocusOut>", self.on_focus_out)
        self.put_placeholder()

    def put_placeholder(self):
        is_empty = not self.get()
        if is_empty:
            self.insert(0, self.placeholder)
            self['foreground'] = self.placeholder_color

    def on_focus_in(self, e):
        if self.get() == self.placeholder and self['foreground'] == self.placeholder_color:
            self.delete('0', 'end')
            self['foreground'] = self.default_fg_color

    def on_focus_out(self, e):
        if not self.get():
            self.put_placeholder()
    
    def get_value(self):
        content = self.get()
        if content == self.placeholder and self['foreground'] == self.placeholder_color:
            return ""
        return content

def load_icons():
    """Tải tất cả các icon cần thiết cho giao diện."""
    icon_files = ['browse', 'upload', 'schedule', 'clear', 'refresh', 'delete', 'trending', 'add', 'pick', 'post', 'generate', 'analyze', 'comment_analyze']
    try:
        for name in icon_files:
            icons[name] = ImageTk.PhotoImage(Image.open(f"icons/{name}.png").resize((16, 16), Image.LANCZOS))
        log_status("Tải icon thành công. (Yêu cầu có thư mục 'icons')")
    except Exception as e:
        log_status(f"Cảnh báo: Không thể tải icon. Lỗi: {e}. Ứng dụng sẽ chạy không có icon.")

def create_context_menu(widget):
    menu = tk.Menu(widget, tearoff=0)
    widget.bind("<Button-3>", lambda event: show_context_menu(event, menu, widget))
    return menu

def show_context_menu(event, menu, widget):
    iid = widget.identify_row(event.y)
    if iid:
        widget.selection_set(iid)
        menu.post(event.x_root, event.y_root)

# --- Thanh trạng thái và Ghi nhật ký ---
class StatusBar(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.label = ttk.Label(self, text="Ready", anchor=tk.W, padding=(5, 2))
        self.label.pack(fill=tk.X, expand=True, side=tk.LEFT)
        self.progress = ttk.Progressbar(self, orient=tk.HORIZONTAL, length=150, mode='indeterminate')
    def set_text(self, text): self.label.config(text=text)
    def clear(self): self.set_text("Ready")
    def show_progress(self):
        self.progress.pack(side=tk.RIGHT, padx=5, pady=2)
        self.progress.start(20)
    def hide_progress(self):
        self.progress.stop()
        self.progress.pack_forget()

def log_status(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    if status_bar_instance and root.winfo_exists():
        try:
            root.after(0, status_bar_instance.set_text, message)
        except Exception: pass
    if log_text_widget and root.winfo_exists():
        try:
            root.after(0, append_to_log_widget, log_message + "\n")
        except Exception: pass

def append_to_log_widget(message):
    log_text_widget.config(state=tk.NORMAL)
    log_text_widget.insert(tk.END, message)
    log_text_widget.see(tk.END)
    log_text_widget.config(state=tk.DISABLED)

# --- Chuyển đổi múi giờ ---
def initialize_timezone():
    global vietnam_tz
    try:
        vietnam_tz = pytz.timezone(VIETNAM_TZ_STR)
        log_status(f"Múi giờ '{VIETNAM_TZ_STR}' đã được tải.")
        return True
    except pytz.exceptions.UnknownTimeZoneError:
        log_status(f"LỖI: Không tìm thấy múi giờ '{VIETNAM_TZ_STR}'.")
        messagebox.showerror("Lỗi Múi Giờ", f"Không thể tìm thấy múi giờ '{VIETNAM_TZ_STR}'.")
        return False

def convert_utc_to_vn_str(utc_iso_string, fmt='%Y-%m-%d %H:%M:%S'):
    if not utc_iso_string or not vietnam_tz: return "N/A"
    try:
        utc_dt = datetime.datetime.fromisoformat(utc_iso_string.replace('Z', '+00:00'))
        return utc_dt.astimezone(vietnam_tz).strftime(fmt)
    except (ValueError, TypeError): return "Invalid Date"

def convert_vn_str_to_utc_iso(vn_time_str, fmt='%Y-%m-%d %H:%M:%S'):
    if not vietnam_tz: return None, None
    try:
        vn_dt = vietnam_tz.localize(datetime.datetime.strptime(vn_time_str, fmt))
        utc_dt = vn_dt.astimezone(pytz.utc)
        return utc_dt, utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    except ValueError:
        messagebox.showerror("Định Dạng Thời Gian Sai", f"Định dạng thời gian không hợp lệ.\nVui lòng sử dụng: YYYY-MM-DD HH:MM:SS.")
        return None, None

def extract_video_id_from_url(url):
    """Trích xuất Video ID từ một URL YouTube hoặc trả về chính nó nếu đã là ID."""
    if not url: return None
    if len(url) == 11 and not url.startswith("http"):
        return url
    parsed_url = urlparse(url)
    if 'youtube.com' in parsed_url.hostname:
        video_id = parse_qs(parsed_url.query).get('v')
        if video_id: return video_id[0]
    elif 'youtu.be' in parsed_url.hostname:
        return parsed_url.path[1:]
    return None

# --- Xác thực người dùng ---
def get_authenticated_service():
    global youtube_service_global
    with auth_lock:
        if youtube_service_global:
            return youtube_service_global

        log_status(f"Yêu cầu xác thực...")
        if not os.path.exists(CLIENT_SECRETS_FILE):
            log_status(f"LỖI: Không tìm thấy file client secrets: {CLIENT_SECRETS_FILE}")
            messagebox.showerror("Lỗi Xác Thực", f"Không tìm thấy file '{CLIENT_SECRETS_FILE}'.")
            return None
        try:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, ALL_SCOPES)
            messagebox.showinfo("Yêu Cầu Quyền", "Ứng dụng cần quyền quản lý video, playlist và bình luận của bạn.\nBạn sẽ được chuyển hướng tới trình duyệt để cấp quyền.")
            credentials = flow.run_local_server(port=0)
            service = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)
            
            youtube_service_global = service
            log_status("Xác thực thành công. Dịch vụ đã được lưu.")
            
            threading.Thread(target=fetch_my_playlists, daemon=True).start()
            return service
        except Exception as e:
            log_status(f"Lỗi xác thực: {e}")
            messagebox.showerror("Lỗi Xác Thực", f"Could not authenticate with Google: {e}")
            return None

# --- Các hàm tương tác với YouTube API ---
def add_video_to_playlist(youtube, video_id, playlist_id):
    if not playlist_id: return
    log_status(f"Đang thêm video {video_id} vào playlist {playlist_id}...")
    try:
        youtube.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()
        log_status(f"Đã thêm video {video_id} vào playlist {playlist_id} thành công.")
    except HttpError as e:
        log_status(f"Lỗi API khi thêm video vào playlist: {e}")
        messagebox.showwarning("Lỗi Playlist", f"Video đã được upload, nhưng không thể thêm vào playlist:\n{e}")

def upload_video(youtube, video_file_path, title, description, thumbnail_path=None, publish_time_utc_iso=None, playlist_id=None):
    if not youtube:
        messagebox.showerror("Lỗi Upload", "Cần xác thực trước khi upload.")
        return None
    body = {'snippet': {'title': title, 'description': description, 'categoryId': '22'}, 'status': {'privacyStatus': 'private' if publish_time_utc_iso else 'public', 'publishAt': publish_time_utc_iso, 'selfDeclaredMadeForKids': False}}
    log_status(f"Bắt đầu upload: '{title}'")
    try:
        media = MediaFileUpload(video_file_path, mimetype='video/*', resumable=True)
        request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
        response, last_progress = None, -1
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                if progress > last_progress: log_status(f"Đang upload '{title}': {progress}%"); last_progress = progress
        
        video_id = response['id']
        log_status(f"Upload video '{title}' thành công. Video ID: {video_id}")
        if playlist_id: add_video_to_playlist(youtube, video_id, playlist_id)
        if thumbnail_path and os.path.exists(thumbnail_path):
            log_status(f"Bắt đầu upload thumbnail cho video ID: {video_id}")
            youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumbnail_path, mimetype='image/*')).execute()
            log_status(f"Upload thumbnail thành công cho video ID: {video_id}")
        return response
    except Exception as e:
        log_status(f"Lỗi trong quá trình upload '{title}': {e}")
        messagebox.showerror("Lỗi Upload", f"Đã xảy ra lỗi khi upload '{title}':\n{e}")
        return None

def delete_video_api(service, video_id):
    """Gửi yêu cầu xóa video vĩnh viễn trên YouTube."""
    try:
        service.videos().delete(id=video_id).execute()
        log_status(f"Đã gửi yêu cầu xóa Video ID: {video_id} trên YouTube.")
        return True
    except HttpError as e:
        log_status(f"Lỗi API khi xóa video {video_id}: {e}")
        messagebox.showerror("Lỗi API", f"Không thể xóa video trên YouTube:\n{e}")
        return False

def fetch_trending_videos_api(region_code, max_results=25):
    service = get_authenticated_service()
    if not service: return None
    try:
        response = service.videos().list(part="snippet,statistics,id", chart="mostPopular", regionCode=region_code, maxResults=max_results).execute()
        items = response.get('items', [])
        log_status(f"Đã lấy {len(items)} video thịnh hành cho khu vực: {region_code}")
        return items
    except HttpError as e:
        messagebox.showerror("Lỗi API", f"Không thể lấy video thịnh hành cho khu vực '{region_code}':\n{e}")
        return None

def post_comment_api(video_id, comment_text):
    log_status(f"Đang thử đăng bình luận trên Video ID: {video_id}")
    service = get_authenticated_service()
    if not service:
        messagebox.showerror("Lỗi Bình Luận", "Yêu cầu xác thực để đăng bình luận.")
        return
    try:
        request_body = { "snippet": { "videoId": video_id, "topLevelComment": { "snippet": { "textOriginal": comment_text }}}}
        response = service.commentThreads().insert(part="snippet", body=request_body).execute()
        log_status(f"Đăng bình luận thành công. Comment ID: {response['id']}")
        messagebox.showinfo("Thành Công", f"Đã đăng bình luận thành công trên Video ID: {video_id}")
    except HttpError as e:
        log_status(f"Lỗi API khi đăng bình luận: {e}")
        error_content = json.loads(e.content.decode('utf-8'))
        error_message = error_content.get('error', {}).get('message', str(e))
        messagebox.showerror("Lỗi Đăng Bình Luận", f"Không thể đăng bình luận:\n{error_message}")
    finally:
        if root.winfo_exists():
            root.after(0, set_comment_manage_buttons_state, tk.NORMAL)
            if status_bar_instance:
                root.after(0, status_bar_instance.hide_progress)
                root.after(0, status_bar_instance.clear)

def fetch_video_stats_api(video_id):
    service = get_authenticated_service()
    if not service: return None, "Chưa xác thực."
    try:
        response = service.videos().list(part="snippet,statistics", id=video_id).execute()
        items = response.get('items', [])
        return (items[0], None) if items else (None, "Không tìm thấy video.")
    except HttpError as e:
        return None, f"Lỗi API: {e}"

def fetch_my_playlists_api():
    service = get_authenticated_service()
    if not service: return None
    log_status("Đang lấy danh sách playlist...")
    playlists = []
    try:
        request = service.playlists().list(part="snippet", mine=True, maxResults=50)
        while request:
            response = request.execute()
            playlists.extend(response.get('items', []))
            request = service.playlists().list_next(request, response)
        log_status(f"Đã lấy {len(playlists)} playlist.")
        return playlists
    except HttpError as e:
        messagebox.showerror("Lỗi API", f"Không thể lấy danh sách playlist của bạn:\n{e}")
        return None

def fetch_video_comments_api(video_id, max_results=100):
    service = get_authenticated_service()
    if not service: return None, "Chưa xác thực."
    log_status(f"Đang lấy bình luận cho Video ID: {video_id}...")
    try:
        response = service.commentThreads().list(part="snippet", videoId=video_id, maxResults=min(max_results, 100), textFormat="plainText", order="relevance").execute()
        comments = [item['snippet']['topLevelComment']['snippet']['textDisplay'] for item in response.get('items', [])]
        log_status(f"Đã lấy {len(comments)} bình luận thành công.")
        return comments, None
    except HttpError as e:
        error_detail = "Bình luận đã bị tắt cho video này." if "disabled comments" in str(e).lower() else f"Lỗi API: {e}"
        return None, error_detail

# --- Xử lý file JSON ---
def get_json_data(filepath):
    if not os.path.exists(filepath): return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
        return json.loads(content) if content.strip() else []
    except (json.JSONDecodeError, IOError) as e:
        messagebox.showerror("Lỗi File", f"Lỗi đọc file '{filepath}':\n{e}")
        return []

def save_json_data(data, filepath):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        messagebox.showerror("Lỗi File", f"Không thể lưu file '{filepath}':\n{e}")

# --- Logic của bộ lập lịch ---
def process_scheduled_posts():
    global scheduled_posts_data
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    posts_to_process_indices = [i for i, post in enumerate(scheduled_posts_data) if post.get('status') == 'pending' and datetime.datetime.fromisoformat(post.get('scheduled_time', '9999-01-01T00:00:00Z').replace('Z', '+00:00')) <= now_utc + datetime.timedelta(minutes=1)]
    if not posts_to_process_indices: return
    
    service = get_authenticated_service()
    if not service: return
    
    processed_something = False
    for index in posts_to_process_indices:
        post = scheduled_posts_data[index]
        response = upload_video(service, post['video_path'], post['title'], post['description'], post.get('thumbnail_path'), post['scheduled_time'], post.get('playlist_id'))
        if response:
            scheduled_posts_data[index]['status'] = 'uploaded'
            scheduled_posts_data[index]['video_id'] = response.get('id')
        else:
            scheduled_posts_data[index]['status'] = 'error_upload'
        processed_something = True
    
    if processed_something:
        save_json_data(scheduled_posts_data, SCHEDULED_POSTS_FILE)
        status_queue.put("update_ui")

def run_scheduler():
    log_status("Tiến trình lập lịch đã bắt đầu.")
    while threading.main_thread().is_alive():
        if vietnam_tz: process_scheduled_posts()
        time.sleep(60)
    log_status("Tiến trình lập lịch đã dừng.")

# --- Các hàm Callback và Hỗ trợ cho Giao diện ---
def browse_file(entry_widget, filetypes):
    file_path = filedialog.askopenfilename(initialdir=os.path.expanduser("~"), filetypes=filetypes)
    if file_path:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, file_path)

def validate_inputs(check_time=True):
    video_path = video_path_entry.get_value()
    title = title_entry.get_value()
    if not video_path or not os.path.exists(video_path):
        messagebox.showerror("Lỗi Đầu Vào", f"File video không hợp lệ:\n{video_path}")
        return False, None, None
    if not title:
        messagebox.showerror("Lỗi Đầu Vào", "Vui lòng nhập tiêu đề.")
        return False, None, None
    
    utc_dt, utc_iso_str = None, None
    if check_time:
        scheduled_time_str_vn = datetime_entry.get_value()
        if not scheduled_time_str_vn:
            messagebox.showerror("Lỗi Đầu Vào", "Vui lòng nhập thời gian lên lịch.")
            return False, None, None
        utc_dt, utc_iso_str = convert_vn_str_to_utc_iso(scheduled_time_str_vn)
        if utc_dt is None: return False, None, None
    return True, utc_dt, utc_iso_str

def set_uploader_buttons_state(state=tk.NORMAL):
    for btn in [upload_now_btn, schedule_btn, clear_btn, refresh_playlists_btn]:
        if btn: btn.config(state=state)

def schedule_upload_ui():
    is_valid, utc_dt, scheduled_time_utc_iso = validate_inputs(check_time=True)
    if not is_valid: return
    if utc_dt <= datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=2):
        messagebox.showerror("Lỗi Đầu Vào", "Thời gian lên lịch phải ở trong tương lai ít nhất vài phút.")
        return

    selected_playlist_name = playlist_combobox.get()
    new_post = {"video_path": video_path_entry.get_value(), "title": title_entry.get_value(), "description": description_text.get("1.0", tk.END).strip(), "scheduled_time": scheduled_time_utc_iso, "thumbnail_path": thumbnail_path_entry.get_value(), "playlist_id": my_playlists.get(selected_playlist_name), "status": "pending", "video_id": None}
    scheduled_posts_data.append(new_post)
    save_json_data(scheduled_posts_data, SCHEDULED_POSTS_FILE)
    messagebox.showinfo("Thành Công", f"Đã lên lịch upload video '{new_post['title']}'.")
    clear_input_fields()
    refresh_scheduled_list()

def upload_now_ui():
    is_valid, _, _ = validate_inputs(check_time=False)
    if not is_valid or not messagebox.askyesno("Xác Nhận", "Bạn có muốn upload video này ngay lập tức với chế độ Công khai?"): return

    video_path, title, description, thumbnail_path = video_path_entry.get_value(), title_entry.get_value(), description_text.get("1.0", tk.END).strip(), thumbnail_path_entry.get_value()
    playlist_id = my_playlists.get(playlist_combobox.get())
    
    def upload_task():
        set_uploader_buttons_state(tk.DISABLED)
        status_bar_instance.show_progress()
        service = get_authenticated_service()
        if service:
            response = upload_video(service, video_path, title, description, thumbnail_path, None, playlist_id)
            if response:
                messagebox.showinfo("Upload Thành Công", f"Đã upload thành công video '{title}'.")
                new_post = {"video_path": video_path, "title": title, "description": description, "scheduled_time": None, "thumbnail_path": thumbnail_path, "playlist_id": playlist_id, "status": "uploaded", "video_id": response.get('id')}
                scheduled_posts_data.append(new_post)
                save_json_data(scheduled_posts_data, SCHEDULED_POSTS_FILE)
                status_queue.put("update_ui")
                root.after(0, clear_input_fields)
        
        root.after(0, set_uploader_buttons_state, tk.NORMAL)
        root.after(0, status_bar_instance.hide_progress)
        root.after(0, status_bar_instance.clear)

    threading.Thread(target=upload_task, daemon=True).start()

def refresh_scheduled_list():
    scheduled_list_treeview.delete(*scheduled_list_treeview.get_children())
    for i, post in enumerate(scheduled_posts_data):
        time_vn_str = convert_utc_to_vn_str(post['scheduled_time']) if post.get('scheduled_time') else "Uploaded Now"
        playlist_name = next((name for name, pid in my_playlists.items() if pid == post.get('playlist_id')), "None")
        tags = ('oddrow' if i % 2 else 'evenrow', post.get('status', 'unknown'))
        scheduled_list_treeview.insert('', tk.END, values=(post['title'], time_vn_str, post['status'], playlist_name), iid=str(i), tags=tags)
    update_analyzable_videos_list()

def clear_input_fields():
    for entry in [video_path_entry, title_entry, thumbnail_path_entry, datetime_entry]:
        entry.delete(0, tk.END)
        if isinstance(entry, PlaceholderEntry): entry.put_placeholder()
    description_text.delete("1.0", tk.END)
    playlist_combobox.set('')
    if scheduled_list_treeview.selection(): scheduled_list_treeview.selection_remove(scheduled_list_treeview.selection())

def fetch_my_playlists():
    if refresh_playlists_btn: root.after(0, lambda: refresh_playlists_btn.config(state=tk.DISABLED))
    def task():
        global my_playlists
        playlists_data = fetch_my_playlists_api()
        if playlists_data is not None:
            my_playlists = {p['snippet']['title']: p['id'] for p in playlists_data}
            root.after(0, update_playlist_combobox, list(my_playlists.keys()))
        if refresh_playlists_btn: root.after(0, lambda: refresh_playlists_btn.config(state=tk.NORMAL))
    threading.Thread(target=task, daemon=True).start()

def update_playlist_combobox(playlist_names):
    if playlist_combobox:
        playlist_combobox['values'] = playlist_names
        state = 'readonly' if playlist_names else 'disabled'
        default_text = '' if playlist_names else "Không tìm thấy playlist"
        playlist_combobox.config(state=state)
        playlist_combobox.set(default_text)

def fetch_and_display_trending():
    region = region_code_entry.get().strip().upper()
    if len(region) != 2 or not region.isalpha():
        messagebox.showwarning("Đầu vào không hợp lệ", "Mã vùng phải là 2 chữ cái (ví dụ: VN, US).")
        return
    
    if fetch_trending_btn: fetch_trending_btn.config(state=tk.DISABLED)
    status_bar_instance.show_progress()
    trending_status_label.config(text=f"Đang lấy dữ liệu cho {region}...")
    
    def fetch_task():
        global trending_videos_data
        trending_videos_data = fetch_trending_videos_api(region)
        root.after(0, display_trending_results, trending_videos_data, region)
        if fetch_trending_btn: root.after(0, lambda: fetch_trending_btn.config(state=tk.NORMAL))
        root.after(0, status_bar_instance.hide_progress)
        root.after(0, status_bar_instance.clear)

    threading.Thread(target=fetch_task, daemon=True).start()

def display_trending_results(videos, region):
    trending_list_treeview.delete(*trending_list_treeview.get_children())
    if videos is None:
        trending_status_label.config(text=f"Lỗi khi lấy dữ liệu cho {region}")
        return
    if not videos:
        trending_status_label.config(text=f"Không có video thịnh hành cho {region}")
        return

    trending_status_label.config(text=f"Thịnh hành: {region} ({len(videos)} video)")
    for i, video in enumerate(videos):
        title = video['snippet']['title']
        channel = video['snippet']['channelTitle']
        views = f"{int(video['statistics'].get('viewCount', 0)):,}"
        tags = ('oddrow' if i % 2 else 'evenrow',)
        trending_list_treeview.insert('', tk.END, values=(title, channel, views), iid=str(i), tags=tags)

def refresh_comment_template_listbox():
    comment_template_listbox.delete(0, tk.END)
    for template in comment_templates_list:
        comment_template_listbox.insert(tk.END, template)

def set_comment_manage_buttons_state(state=tk.NORMAL):
    for btn in [add_comment_btn, delete_comment_btn, pick_comment_btn, generate_comments_btn, post_comment_btn]:
        if btn: btn.config(state=state)
    if num_comments_entry: num_comments_entry.config(state='normal' if state == tk.NORMAL else 'disabled')
    if post_comment_btn and not (current_random_comment and video_id_entry_for_comment.get_value()):
        post_comment_btn.config(state=tk.DISABLED)

def add_comment_template():
    new_template = new_comment_entry.get_value().strip()
    if not new_template: return
    if new_template not in comment_templates_list:
        comment_templates_list.append(new_template)
        save_json_data(comment_templates_list, COMMENT_TEMPLATES_FILE)
        refresh_comment_template_listbox()
        new_comment_entry.delete(0, tk.END)

def delete_selected_comment_template():
    selected_indices = comment_template_listbox.curselection()
    if not selected_indices: return
    if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa mẫu bình luận này?"):
        del comment_templates_list[selected_indices[0]]
        save_json_data(comment_templates_list, COMMENT_TEMPLATES_FILE)
        refresh_comment_template_listbox()

def pick_random_comment():
    global current_random_comment
    if not comment_templates_list:
        messagebox.showwarning("Danh sách rỗng", "Không có mẫu bình luận nào để chọn.")
        current_random_comment = ""
    else:
        current_random_comment = random.choice(comment_templates_list)
    
    random_comment_display.config(state=tk.NORMAL)
    random_comment_display.delete("1.0", tk.END)
    random_comment_display.insert("1.0", current_random_comment or "Chưa có bình luận nào được chọn.")
    random_comment_display.config(state=tk.DISABLED)
    set_comment_manage_buttons_state(tk.NORMAL)

def post_comment_ui():
    url_or_id = video_id_entry_for_comment.get_value()
    video_id = extract_video_id_from_url(url_or_id)

    if not video_id:
        messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập URL hoặc ID video hợp lệ.")
        return
    if not current_random_comment:
        messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn một bình luận.")
        return
        
    if messagebox.askyesno("Xác nhận", f"Đăng bình luận này lên video {video_id}?"):
        set_comment_manage_buttons_state(tk.DISABLED)
        status_bar_instance.show_progress()
        threading.Thread(target=post_comment_api, args=(video_id, current_random_comment), daemon=True).start()

def generate_meaningful_comments_ui():
    try:
        num_to_generate = int(num_comments_entry.get_value())
        if num_to_generate <= 0: raise ValueError
    except ValueError:
        messagebox.showerror("Lỗi", "Vui lòng nhập một số dương.")
        return
    
    set_comment_manage_buttons_state(tk.DISABLED)
    status_bar_instance.show_progress()
    
    def task():
        existing_comments_set = set(comment_templates_list)
        newly_generated_comments = set()
        
        attempts = 0
        max_attempts = num_to_generate * 5 + 100

        while len(newly_generated_comments) < num_to_generate and attempts < max_attempts:
            attempts += 1
            base = random.choice(MEANINGFUL_COMMENT_BASES)
            if random.random() < 0.6: base += " " + random.choice(EMOJIS_LIST)
            if random.random() < 0.3: base += " " + random.choice(COMMENT_SUFFIXES)
            final_comment = base.strip()

            if final_comment not in existing_comments_set and final_comment not in newly_generated_comments:
                newly_generated_comments.add(final_comment)
        
        added_count = len(newly_generated_comments)
        if added_count > 0:
            comment_templates_list.extend(list(newly_generated_comments))
            save_json_data(comment_templates_list, COMMENT_TEMPLATES_FILE)
        
        root.after(0, refresh_comment_template_listbox)
        root.after(0, set_comment_manage_buttons_state, tk.NORMAL)
        root.after(0, status_bar_instance.hide_progress)
        root.after(0, status_bar_instance.clear)
        root.after(0, messagebox.showinfo, "Hoàn tất", f"Đã tạo và thêm mới {added_count}/{num_to_generate} bình luận được yêu cầu.")

    threading.Thread(target=task, daemon=True).start()

def analyze_sentiment(comment):
    comment_lower = comment.lower()
    if any(word in comment_lower for word in NEGATIVE_KEYWORDS_VI): return "Tiêu cực"
    if any(word in comment_lower for word in POSITIVE_KEYWORDS_VI): return "Tích cực"
    return "Trung tính"

def display_comment_analysis_results(video_data, comments, error):
    clear_analytics_results()
    if error:
        messagebox.showerror("Lỗi Phân Tích Bình Luận", f"Không thể lấy bình luận:\n{error}")
        return
    if not comments:
        messagebox.showinfo("Phân Tích Bình Luận", "Không tìm thấy bình luận nào cho video này.")
        return

    sentiments = [analyze_sentiment(c) for c in comments]
    sentiment_counts = pd.Series(sentiments).value_counts()
    
    fig, ax = plt.subplots(figsize=(6, 3.5), dpi=100)
    colors = {'Tích cực': 'lightgreen', 'Tiêu cực': 'lightcoral', 'Trung tính': 'lightskyblue'}
    ax.pie(sentiment_counts, labels=sentiment_counts.index, autopct='%1.1f%%', startangle=140, colors=[colors.get(label, 'grey') for label in sentiment_counts.index])
    ax.axis('equal')
    ax.set_title(f'Phân Tích Cảm Xúc Bình Luận\n(Trên {len(comments)} bình luận)')
    
    global canvas_widget
    canvas_widget = FigureCanvasTkAgg(fig, master=analytics_chart_frame)
    canvas_widget.draw(); canvas_widget.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    plt.tight_layout()
    
    pos, neg, neu, total = sentiment_counts.get("Tích cực", 0), sentiment_counts.get("Tiêu cực", 0), sentiment_counts.get("Trung tính", 0), len(comments)
    
    analytics_report_text.config(state=tk.NORMAL)
    analytics_report_text.delete("1.0", tk.END)
    
    analytics_report_text.insert(tk.END, "Báo Cáo Cảm Xúc\n", "h1")
    analytics_report_text.insert(tk.END, f"{video_data['snippet']['title']}\n\n", "h2")
    analytics_report_text.insert(tk.END, "Tổng bình luận phân tích: ", "bold")
    analytics_report_text.insert(tk.END, f"{total}\n\n")
    
    analytics_report_text.insert(tk.END, "Tích cực: ", "bold")
    analytics_report_text.insert(tk.END, f"{pos} ({pos/total:.1%})\n", "positive")
    
    analytics_report_text.insert(tk.END, "Tiêu cực: ", "bold")
    analytics_report_text.insert(tk.END, f"{neg} ({neg/total:.1%})\n", "negative")
    
    analytics_report_text.insert(tk.END, "Trung tính: ", "bold")
    analytics_report_text.insert(tk.END, f"{neu} ({neu/total:.1%})", "neutral")
    
    analytics_report_text.config(state=tk.DISABLED)

def analyze_selected_video_ui():
    video_id, _ = get_video_id_for_analysis()
    if not video_id: return
    _trigger_analysis_task(video_id)

def analyze_comments_ui():
    video_id, _ = get_video_id_for_analysis()
    if not video_id: return
    set_analytics_buttons_state(tk.DISABLED)
    status_bar_instance.show_progress()
    def task():
        video_data, error1 = fetch_video_stats_api(video_id)
        if error1:
            root.after(0, lambda: messagebox.showerror("Lỗi", f"Không thể lấy thông tin video:\n{error1}"))
            root.after(0, set_analytics_buttons_state, tk.NORMAL)
            root.after(0, status_bar_instance.hide_progress)
            return
            
        comments, error2 = fetch_video_comments_api(video_id)
        root.after(0, display_comment_analysis_results, video_data, comments, error2)
        root.after(0, set_analytics_buttons_state, tk.NORMAL)
        root.after(0, status_bar_instance.hide_progress)
    threading.Thread(target=task, daemon=True).start()

def get_video_id_for_analysis():
    custom_url = custom_video_url_entry.get_value()
    if custom_url:
        video_id = extract_video_id_from_url(custom_url)
        if not video_id:
            messagebox.showerror("URL không hợp lệ", "Không thể trích xuất ID video từ URL hoặc ID đã nhập.")
            return None, None
        return video_id, f"Custom ID: {video_id}"
    elif analytics_video_combobox.current() != -1:
        selected_title = analytics_video_combobox.get()
        return analytics_video_combobox.video_map.get(selected_title), selected_title
    else:
        messagebox.showwarning("Chưa Chọn Video", "Vui lòng chọn một video từ danh sách hoặc nhập URL/ID tùy chỉnh.")
        return None, None

def _trigger_analysis_task(video_id):
    clear_analytics_results()
    set_analytics_buttons_state(tk.DISABLED)
    status_bar_instance.show_progress()
    def task():
        video_data, error = fetch_video_stats_api(video_id)
        root.after(0, lambda: display_analysis_results(video_data, error))
        root.after(0, set_analytics_buttons_state, tk.NORMAL)
        root.after(0, status_bar_instance.hide_progress)
    threading.Thread(target=task, daemon=True).start()

def display_analysis_results(video_data, error):
    clear_analytics_results()
    if error or not video_data:
        messagebox.showerror("Lỗi Phân Tích", f"Không thể lấy dữ liệu: {error}")
        return
    stats = video_data.get('statistics', {})
    views = int(stats.get('viewCount', 0))
    likes = int(stats.get('likeCount', 0))
    comments = int(stats.get('commentCount', 0))
    
    fig, ax = plt.subplots(figsize=(6, 3.5), dpi=100)
    metrics, counts = ['Lượt xem', 'Thích', 'Bình luận'], [views, likes, comments]
    ax.bar(metrics, counts, color=['skyblue', 'lightcoral', 'lightgreen'])
    ax.set_ylabel('Số lượng')
    ax.set_title(f'Thống Kê Hiệu Suất Video')
    plt.tight_layout()

    global canvas_widget
    canvas_widget = FigureCanvasTkAgg(fig, master=analytics_chart_frame)
    canvas_widget.draw(); canvas_widget.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    
    analytics_report_text.config(state=tk.NORMAL)
    analytics_report_text.delete("1.0", tk.END)
    analytics_report_text.insert(tk.END, "Báo Cáo Thống Kê\n", "h1")
    analytics_report_text.insert(tk.END, f"{video_data['snippet']['title']}\n\n", "h2")
    analytics_report_text.insert(tk.END, "Lượt xem: ", "bold")
    analytics_report_text.insert(tk.END, f"{views:,}\n")
    analytics_report_text.insert(tk.END, "Lượt thích: ", "bold")
    analytics_report_text.insert(tk.END, f"{likes:,}\n")
    analytics_report_text.insert(tk.END, "Bình luận: ", "bold")
    analytics_report_text.insert(tk.END, f"{comments:,}")
    analytics_report_text.config(state=tk.DISABLED)

def update_analyzable_videos_list():
    uploaded_videos = [f"{post['title']} ({post['video_id']})" for post in scheduled_posts_data if post.get('status') == 'uploaded' and post.get('video_id')]
    analytics_video_combobox.video_map = {f"{post['title']} ({post['video_id']})": post['video_id'] for post in scheduled_posts_data if post.get('status') == 'uploaded' and post.get('video_id')}
    
    state = 'readonly' if uploaded_videos else 'disabled'
    default_text = '' if uploaded_videos else "Không có video đã upload"
    analytics_video_combobox['values'] = uploaded_videos
    analytics_video_combobox.config(state=state)
    analytics_video_combobox.set(default_text)
    set_analytics_buttons_state(tk.NORMAL)

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

def set_analytics_buttons_state(state):
    can_analyze = (analytics_video_combobox.current() != -1) or (custom_video_url_entry.get_value())
    final_state = state if can_analyze else tk.DISABLED
    if analyze_video_btn: analyze_video_btn.config(state=final_state)
    if analyze_comments_btn: analyze_comments_btn.config(state=final_state)

def check_status_queue():
    try:
        message = status_queue.get_nowait()
        if message == "update_ui":
            refresh_scheduled_list()
    except queue.Empty: pass
    finally:
        root.after(1500, check_status_queue)
        
# --- Main Application Setup ---
if __name__ == "__main__":
    try: root = ThemedTk(theme="arc")
    except tk.TclError: root = tk.Tk()

    root.title("YouTube Automation Tool Pro")
    root.geometry("1100x850")
    
    style = ttk.Style(root)
    style.configure("Treeview.Heading", font=('Helvetica', 10, 'bold'))
    style.configure("TButton", padding=6, font=('Helvetica', 9))
    style.configure("TLabelframe.Label", font=('Helvetica', 11, 'bold'))
    style.configure("TNotebook.Tab", padding=(12, 8), font=('Helvetica', 10, 'bold'))

    if not initialize_timezone(): root.destroy(); exit()
    load_icons()

    scheduled_posts_data = get_json_data(SCHEDULED_POSTS_FILE)
    comment_templates_list = get_json_data(COMMENT_TEMPLATES_FILE)
    
    status_bar_instance = StatusBar(root)
    status_bar_instance.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(5, 0))
    notebook = ttk.Notebook(root)
    notebook.pack(pady=10, padx=10, fill="both", expand=True)

    # === Tab 1: Upload & Lên lịch ===
    uploader_tab = ttk.Frame(notebook, padding="15")
    notebook.add(uploader_tab, text=' Upload & Lên lịch ')
    input_frame = ttk.LabelFrame(uploader_tab, text=" Chi Tiết Video ", padding="15")
    input_frame.grid(row=0, column=0, sticky="nsew")
    input_frame.columnconfigure(1, weight=1)
    
    ttk.Label(input_frame, text="File Video:").grid(row=0, column=0, padx=5, pady=8, sticky="w")
    video_path_entry = PlaceholderEntry(input_frame, placeholder="Nhấn Browse để chọn file video")
    video_path_entry.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
    ttk.Button(input_frame, text="Browse...", image=icons.get('browse'), compound="left", command=lambda: browse_file(video_path_entry, [("Video Files", "*.mp4 *.avi *.mov")])).grid(row=0, column=2, padx=5, pady=8)
    
    ttk.Label(input_frame, text="Tiêu đề:").grid(row=1, column=0, padx=5, pady=8, sticky="w")
    title_entry = PlaceholderEntry(input_frame, placeholder="Nhập tiêu đề video")
    title_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=8, sticky="ew")

    ttk.Label(input_frame, text="Mô tả:").grid(row=2, column=0, padx=5, pady=8, sticky="nw")
    description_text = scrolledtext.ScrolledText(input_frame, height=5, width=50, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1)
    description_text.grid(row=2, column=1, columnspan=2, padx=5, pady=8, sticky="ew")
    
    ttk.Label(input_frame, text="Thumbnail:").grid(row=3, column=0, padx=5, pady=8, sticky="w")
    thumbnail_path_entry = PlaceholderEntry(input_frame, placeholder="Tùy chọn: Chọn ảnh thumbnail")
    thumbnail_path_entry.grid(row=3, column=1, padx=5, pady=8, sticky="ew")
    ttk.Button(input_frame, text="Browse...", image=icons.get('browse'), compound="left", command=lambda: browse_file(thumbnail_path_entry, [("Image Files", "*.png *.jpg")])).grid(row=3, column=2, padx=5, pady=8)
    
    ttk.Label(input_frame, text="Playlist:").grid(row=4, column=0, padx=5, pady=8, sticky="w")
    playlist_combobox = ttk.Combobox(input_frame, state='disabled')
    playlist_combobox.grid(row=4, column=1, sticky="ew", padx=5, pady=8)
    refresh_playlists_btn = ttk.Button(input_frame, text="Làm mới", image=icons.get('refresh'), compound="left", command=fetch_my_playlists)
    refresh_playlists_btn.grid(row=4, column=2, padx=5, pady=8)
    
    ttk.Label(input_frame, text="Lên lịch (VN):").grid(row=5, column=0, padx=5, pady=8, sticky="w")
    datetime_entry = PlaceholderEntry(input_frame, placeholder="YYYY-MM-DD HH:MM:SS")
    datetime_entry.grid(row=5, column=1, padx=5, pady=8, sticky="ew")

    button_frame_input = ttk.Frame(input_frame)
    button_frame_input.grid(row=6, column=0, columnspan=3, pady=(20, 5))
    upload_now_btn = ttk.Button(button_frame_input, text="Upload Ngay", image=icons.get('upload'), compound="left", command=upload_now_ui)
    upload_now_btn.pack(side=tk.LEFT, padx=10)
    schedule_btn = ttk.Button(button_frame_input, text="Lên Lịch", image=icons.get('schedule'), compound="left", command=schedule_upload_ui)
    schedule_btn.pack(side=tk.LEFT, padx=10)
    clear_btn = ttk.Button(button_frame_input, text="Xóa Form", image=icons.get('clear'), compound="left", command=clear_input_fields)
    clear_btn.pack(side=tk.LEFT, padx=10)
    
    list_frame = ttk.LabelFrame(uploader_tab, text=" Video đã lên lịch & Upload ", padding="10")
    list_frame.grid(row=1, column=0, sticky="nsew", pady=(20, 0))
    list_frame.rowconfigure(0, weight=1); list_frame.columnconfigure(0, weight=1)
    
    columns_sched = ('title', 'time_vn', 'status', 'playlist')
    scheduled_list_treeview = ttk.Treeview(list_frame, columns=columns_sched, show='headings', height=8)
    scheduled_list_treeview.heading('title', text='Tiêu đề', anchor='w'); scheduled_list_treeview.column('title', width=350, stretch=tk.YES, anchor='w')
    scheduled_list_treeview.heading('time_vn', text='Thời gian (VN)', anchor='c'); scheduled_list_treeview.column('time_vn', width=160, stretch=tk.NO, anchor='c')
    scheduled_list_treeview.heading('status', text='Trạng thái', anchor='c'); scheduled_list_treeview.column('status', width=100, stretch=tk.NO, anchor='c')
    scheduled_list_treeview.heading('playlist', text='Playlist', anchor='w'); scheduled_list_treeview.column('playlist', width=150, stretch=tk.NO, anchor='w')
    
    scheduled_list_treeview.tag_configure('uploaded', foreground='green'); scheduled_list_treeview.tag_configure('pending', foreground='blue'); scheduled_list_treeview.tag_configure('error_upload', foreground='red')
    scheduled_list_treeview.tag_configure('oddrow', background='#F0F0F0')

    scrollbar_sched = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=scheduled_list_treeview.yview)
    scheduled_list_treeview.configure(yscroll=scrollbar_sched.set)
    scheduled_list_treeview.grid(row=0, column=0, sticky="nsew"); scrollbar_sched.grid(row=0, column=1, sticky="ns")
    
    scheduled_context_menu = create_context_menu(scheduled_list_treeview)
    def handle_scheduled_context(action):
        if not scheduled_list_treeview.selection(): return
        selected_iid = scheduled_list_treeview.selection()[0]
        post_index = int(selected_iid)
        post = scheduled_posts_data[post_index]
        video_id = post.get('video_id')

        if action == 'copy_id' and video_id:
            root.clipboard_clear(); root.clipboard_append(video_id)
            log_status(f"Đã sao chép Video ID: {video_id}")
        
        elif action == 'delete_from_list':
            del scheduled_posts_data[post_index]
            save_json_data(scheduled_posts_data, SCHEDULED_POSTS_FILE)
            refresh_scheduled_list()

        elif action == 'delete_on_yt' and video_id:
            title = post.get('title', 'video này')
            if messagebox.askyesno("XÁC NHẬN XÓA VĨNH VIỄN", f"Bạn có chắc chắn muốn xóa '{title}' khỏi YouTube không?\nHÀNH ĐỘNG NÀY KHÔNG THỂ HOÀN TÁC!", icon='warning'):
                service = get_authenticated_service()
                if service and delete_video_api(service, video_id):
                    scheduled_posts_data[post_index]['status'] = 'deleted_on_youtube'
                    save_json_data(scheduled_posts_data, SCHEDULED_POSTS_FILE)
                    refresh_scheduled_list()
                    messagebox.showinfo("Thành công", f"Đã xóa video '{title}' khỏi YouTube.")

    scheduled_context_menu.add_command(label="Sao chép Video ID", command=lambda: handle_scheduled_context('copy_id'))
    scheduled_context_menu.add_command(label="Xóa khỏi danh sách này", command=lambda: handle_scheduled_context('delete_from_list'))
    scheduled_context_menu.add_separator()
    scheduled_context_menu.add_command(label="Xóa trên YouTube (Vĩnh viễn)", command=lambda: handle_scheduled_context('delete_on_yt'))


    uploader_tab.rowconfigure(1, weight=1); uploader_tab.columnconfigure(0, weight=1)

    # === Tab 2: Video Thịnh Hành ===
    trending_tab = ttk.Frame(notebook, padding="15")
    notebook.add(trending_tab, text=' Video Thịnh Hành ')
    trending_controls_frame = ttk.Frame(trending_tab)
    trending_controls_frame.pack(pady=10, fill="x")
    ttk.Label(trending_controls_frame, text="Mã vùng:").pack(side=tk.LEFT, padx=(0, 5))
    region_code_entry = ttk.Entry(trending_controls_frame, width=5)
    region_code_entry.insert(0, "VN")
    region_code_entry.pack(side=tk.LEFT, padx=5)
    fetch_trending_btn = ttk.Button(trending_controls_frame, text="Lấy Video", image=icons.get('trending'), compound="left", command=fetch_and_display_trending)
    fetch_trending_btn.pack(side=tk.LEFT, padx=10)
    trending_status_label = ttk.Label(trending_controls_frame, text="Nhập mã vùng gồm 2 chữ cái (ví dụ: VN, US, JP)")
    trending_status_label.pack(side=tk.LEFT, padx=10, fill='x', expand=True)

    trending_list_frame = ttk.LabelFrame(trending_tab, text=" Top Video Thịnh Hành ", padding="10")
    trending_list_frame.pack(pady=10, fill="both", expand=True)
    columns_trend = ('title', 'channel', 'views')
    trending_list_treeview = ttk.Treeview(trending_list_frame, columns=columns_trend, show='headings')
    trending_list_treeview.heading('title', text='Tiêu đề', anchor='w'); trending_list_treeview.column('title', width=500, stretch=tk.YES, anchor='w')
    trending_list_treeview.heading('channel', text='Kênh', anchor='w'); trending_list_treeview.column('channel', width=200, stretch=tk.NO, anchor='w')
    trending_list_treeview.heading('views', text='Lượt xem', anchor='e'); trending_list_treeview.column('views', width=120, stretch=tk.NO, anchor='e')
    trending_list_treeview.tag_configure('oddrow', background='#F0F0F0')

    scrollbar_trend = ttk.Scrollbar(trending_list_frame, orient=tk.VERTICAL, command=trending_list_treeview.yview)
    trending_list_treeview.configure(yscroll=scrollbar_trend.set)
    trending_list_treeview.pack(side=tk.LEFT, fill="both", expand=True); scrollbar_trend.pack(side=tk.RIGHT, fill="y")
    
    trending_context_menu = create_context_menu(trending_list_treeview)
    def handle_trending_context(action):
        if not trending_list_treeview.selection(): return
        video_index = int(trending_list_treeview.selection()[0])
        video_id = trending_videos_data[video_index]['id']
        if action == 'open':
            webbrowser.open_new_tab(f"https://www.youtube.com/watch?v={video_id}")
        elif action == 'copy':
            root.clipboard_clear(); root.clipboard_append(video_id)
    trending_context_menu.add_command(label="Mở trên trình duyệt", command=lambda: handle_trending_context('open'))
    trending_context_menu.add_command(label="Sao chép Video ID", command=lambda: handle_trending_context('copy'))

    # === Tab 3: Công Cụ Bình Luận ===
    interaction_tab = ttk.Frame(notebook, padding="15")
    notebook.add(interaction_tab, text=' Công Cụ Bình Luận ')
    comment_frame = ttk.LabelFrame(interaction_tab, text=" Quản lý Mẫu Bình Luận ", padding="10")
    comment_frame.grid(row=0, column=0, pady=10, padx=0, sticky="nsew")
    comment_frame.columnconfigure(0, weight=1)

    comment_list_frame = ttk.Frame(comment_frame); comment_list_frame.grid(row=0, column=0, pady=5, sticky='nsew')
    comment_list_frame.columnconfigure(0, weight=1); comment_list_frame.rowconfigure(1, weight=1)
    ttk.Label(comment_list_frame, text="Các mẫu đã lưu:").grid(row=0, column=0, sticky='w', padx=5)
    comment_scrollbar = ttk.Scrollbar(comment_list_frame, orient=tk.VERTICAL)
    comment_template_listbox = tk.Listbox(comment_list_frame, height=8, yscrollcommand=comment_scrollbar.set, relief=tk.SOLID, borderwidth=1, exportselection=False)
    comment_scrollbar.config(command=comment_template_listbox.yview)
    comment_template_listbox.grid(row=1, column=0, sticky='nsew', padx=(5,0), pady=5); comment_scrollbar.grid(row=1, column=1, sticky='ns', pady=5)
    
    comment_input_frame = ttk.Frame(comment_frame); comment_input_frame.grid(row=1, column=0, pady=5, sticky='ew')
    comment_input_frame.columnconfigure(1, weight=1)
    ttk.Label(comment_input_frame, text="Thêm mới:").grid(row=0, column=0, padx=(5,2), pady=5, sticky='w')
    new_comment_entry = PlaceholderEntry(comment_input_frame, placeholder="Nhập mẫu bình luận mới...")
    new_comment_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
    add_comment_btn = ttk.Button(comment_input_frame, text="Thêm", image=icons.get('add'), compound="left", command=add_comment_template)
    add_comment_btn.grid(row=0, column=2, padx=(0,5), pady=5)
    
    delete_comment_btn = ttk.Button(comment_frame, text="Xóa mẫu đã chọn", image=icons.get('delete'), compound="left", command=delete_selected_comment_template)
    delete_comment_btn.grid(row=2, column=0, pady=(5, 0), sticky='w', padx=5)
    
    generate_comments_frame = ttk.LabelFrame(comment_frame, text=" Tạo Bình Luận Tự Động ", padding="10")
    generate_comments_frame.grid(row=3, column=0, pady=(15,5), sticky="ew")
    ttk.Label(generate_comments_frame, text="Số lượng cần tạo:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    num_comments_entry = PlaceholderEntry(generate_comments_frame, placeholder="VD: 50", width=10)
    num_comments_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
    generate_comments_btn = ttk.Button(generate_comments_frame, text="Tạo & Thêm", image=icons.get('generate'), compound="left", command=generate_meaningful_comments_ui)
    generate_comments_btn.grid(row=0, column=2, padx=5, pady=5, sticky="e")
    generate_comments_frame.columnconfigure(2, weight=1)

    post_frame = ttk.LabelFrame(interaction_tab, text=" Đăng Bình Luận ", padding="10")
    post_frame.grid(row=1, column=0, pady=15, padx=0, sticky="nsew")
    post_frame.columnconfigure(1, weight=1)
    
    pick_comment_btn = ttk.Button(post_frame, text="Chọn Ngẫu Nhiên", image=icons.get('pick'), compound="left", command=pick_random_comment)
    pick_comment_btn.grid(row=0, column=0, padx=5, pady=5, sticky='w')
    random_comment_display = scrolledtext.ScrolledText(post_frame, height=3, width=60, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1, state=tk.DISABLED)
    random_comment_display.grid(row=1, column=0, columnspan=2, sticky='ew', pady=5, padx=5)
    
    post_action_frame = ttk.Frame(post_frame); post_action_frame.grid(row=2, column=0, columnspan=2, pady=10, sticky='ew')
    ttk.Label(post_action_frame, text="URL/ID Video:").pack(side=tk.LEFT, padx=(5, 5))
    video_id_entry_for_comment = PlaceholderEntry(post_action_frame, placeholder="Dán URL hoặc ID video cần đăng", width=40)
    video_id_entry_for_comment.pack(side=tk.LEFT, padx=5, expand=True, fill='x')
    video_id_entry_for_comment.bind("<KeyRelease>", lambda event: set_comment_manage_buttons_state(tk.NORMAL))
    post_comment_btn = ttk.Button(post_action_frame, text="Đăng Bình Luận", image=icons.get('post'), compound="left", command=post_comment_ui, state=tk.DISABLED)
    post_comment_btn.pack(side=tk.LEFT, padx=10)
    
    interaction_tab.rowconfigure(0, weight=1); interaction_tab.columnconfigure(0, weight=1)
    
    # === Tab 4: Phân Tích ===
    analytics_tab = ttk.Frame(notebook, padding="15")
    notebook.add(analytics_tab, text=' Phân Tích ')
    analytics_controls_frame = ttk.LabelFrame(analytics_tab, text="Chọn Video để Phân tích", padding="15")
    analytics_controls_frame.pack(pady=10, fill="x")
    ttk.Label(analytics_controls_frame, text="Từ danh sách đã Upload:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
    analytics_video_combobox = ttk.Combobox(analytics_controls_frame, width=45, state='disabled')
    analytics_video_combobox.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
    ttk.Label(analytics_controls_frame, text="Hoặc nhập URL/ID video:").grid(row=1, column=0, padx=5, pady=5, sticky='w')
    custom_video_url_entry = PlaceholderEntry(analytics_controls_frame, placeholder="https://www.youtube.com/watch?v=...", width=48)
    custom_video_url_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
    
    analytics_buttons_frame = ttk.Frame(analytics_controls_frame)
    analytics_buttons_frame.grid(row=2, column=0, columnspan=2, pady=10)
    analyze_video_btn = ttk.Button(analytics_buttons_frame, text="Phân Tích Thống Kê", image=icons.get('analyze'), compound="left", command=analyze_selected_video_ui, state=tk.DISABLED)
    analyze_video_btn.pack(side=tk.LEFT, padx=10)
    analyze_comments_btn = ttk.Button(analytics_buttons_frame, text="Phân Tích Bình Luận", image=icons.get('comment_analyze'), compound="left", command=analyze_comments_ui, state=tk.DISABLED)
    analyze_comments_btn.pack(side=tk.LEFT, padx=10)
    for w in [analytics_video_combobox, custom_video_url_entry]:
        w.bind("<KeyRelease>", lambda e: set_analytics_buttons_state(tk.NORMAL))
        w.bind("<<ComboboxSelected>>", lambda e: set_analytics_buttons_state(tk.NORMAL))

    analytics_controls_frame.columnconfigure(1, weight=1)
    analytics_display_frame = ttk.Frame(analytics_tab); analytics_display_frame.pack(pady=10, fill="both", expand=True)
    analytics_display_frame.columnconfigure(0, weight=1); analytics_display_frame.columnconfigure(1, weight=1); analytics_display_frame.rowconfigure(0, weight=1)
    
    analytics_chart_labelframe = ttk.LabelFrame(analytics_display_frame, text=" Biểu đồ ", padding="5")
    analytics_chart_labelframe.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="nsew")
    analytics_chart_frame = ttk.Frame(analytics_chart_labelframe); analytics_chart_frame.pack(fill="both", expand=True)
    
    analytics_report_labelframe = ttk.LabelFrame(analytics_display_frame, text=" Báo cáo Chi tiết ", padding="5")
    analytics_report_labelframe.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="nsew")
    analytics_report_text = scrolledtext.ScrolledText(analytics_report_labelframe, wrap=tk.WORD, state=tk.DISABLED, relief=tk.SOLID, borderwidth=1, font=("Helvetica", 10))
    analytics_report_text.pack(fill="both", expand=True, padx=5, pady=5)
    
    analytics_report_text.tag_configure("h1", font=("Helvetica", 14, "bold"), justify='center', spacing3=10)
    analytics_report_text.tag_configure("h2", font=("Helvetica", 11, "italic"), justify='center', spacing3=10)
    analytics_report_text.tag_configure("bold", font=("Helvetica", 10, "bold"))
    analytics_report_text.tag_configure("positive", foreground="#008000")
    analytics_report_text.tag_configure("negative", foreground="#CC0000")
    analytics_report_text.tag_configure("neutral", foreground="#0000CC")

    # === Tab 5: Nhật Ký ===
    log_tab = ttk.Frame(notebook, padding="15")
    notebook.add(log_tab, text=' Nhật Ký (Log) ')
    log_frame = ttk.LabelFrame(log_tab, text="Nhật ký hoạt động của ứng dụng", padding="10")
    log_frame.pack(fill="both", expand=True)
    log_text_widget = scrolledtext.ScrolledText(log_frame, state='disabled', wrap=tk.WORD, font=("Consolas", 9))
    log_text_widget.pack(fill="both", expand=True)

    # === Khởi tạo và Bắt đầu các tiến trình ---
    get_authenticated_service()
    refresh_scheduled_list()
    refresh_comment_template_listbox()
    pick_random_comment()
    set_analytics_buttons_state(tk.NORMAL)
    
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    root.after(1500, check_status_queue)
    root.mainloop()

    log_status("Ứng dụng đã đóng.")