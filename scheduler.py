# scheduler.py
import datetime
import time
import os
import threading

from file_handler import save_scheduled_posts
from youtube_api import upload_video
from auth import get_authenticated_service
from config import API_SERVICE_NAME, API_VERSION
from time_utils import vietnam_tz

scheduled_posts_data_ref = []
status_queue_ref = None
log_func_ref = print
shutdown_event_ref = None

def set_scheduler_refs(posts_data, queue, logger, shutdown_event):
    global scheduled_posts_data_ref, status_queue_ref, log_func_ref, shutdown_event_ref
    scheduled_posts_data_ref = posts_data
    status_queue_ref = queue
    log_func_ref = logger
    shutdown_event_ref = shutdown_event

def process_scheduled_posts():
    posts_to_process_indices = []
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    needs_saving = False

    for i, post in enumerate(scheduled_posts_data_ref):
        if shutdown_event_ref and shutdown_event_ref.is_set(): break
        if post.get('status') == 'pending':
            scheduled_time_utc_str = post.get('scheduled_time')
            if not scheduled_time_utc_str:
                log_func_ref(f"Scheduler: Skipping post '{post.get('title', 'Untitled')}' due to missing 'scheduled_time'. Marked error.")
                scheduled_posts_data_ref[i]['status'] = 'error_format'
                needs_saving = True
                continue
            try:
                scheduled_time_utc = datetime.datetime.fromisoformat(scheduled_time_utc_str.replace('Z', '+00:00'))
                if scheduled_time_utc <= now_utc + datetime.timedelta(minutes=1):
                     if scheduled_time_utc >= now_utc - datetime.timedelta(minutes=5):
                         log_func_ref(f"Scheduler: Post '{post.get('title', 'Untitled')}' is due (Scheduled: {scheduled_time_utc_str}). Queuing.")
                         posts_to_process_indices.append(i)
                     else:
                         log_func_ref(f"Scheduler: Post '{post.get('title', 'Untitled')}' scheduled time {scheduled_time_utc_str} is too old. Marked error.")
                         scheduled_posts_data_ref[i]['status'] = 'error_too_old'
                         needs_saving = True
            except ValueError:
                log_func_ref(f"Scheduler: Format error in 'scheduled_time' for post '{post.get('title', 'Untitled')}': '{scheduled_time_utc_str}'. Marked error.")
                scheduled_posts_data_ref[i]['status'] = 'error_format'
                needs_saving = True
            except KeyError:
                 log_func_ref(f"Scheduler: Missing 'scheduled_time' key for post index {i}. Marked error.")
                 scheduled_posts_data_ref[i]['status'] = 'error_format'
                 needs_saving = True

    if not posts_to_process_indices or (shutdown_event_ref and shutdown_event_ref.is_set()):
        if needs_saving:
             save_scheduled_posts(scheduled_posts_data_ref, log_func_ref)
             if status_queue_ref: status_queue_ref.put("update_ui")
        return False

    youtube = get_authenticated_service(API_SERVICE_NAME, API_VERSION, log_func_ref)
    if not youtube:
        log_func_ref("Scheduler: Authentication failed or service not available. Cannot process scheduled posts.")
        if needs_saving:
             save_scheduled_posts(scheduled_posts_data_ref, log_func_ref)
             if status_queue_ref: status_queue_ref.put("update_ui")
        return False

    processed_at_least_one = False
    for index in posts_to_process_indices:
        if shutdown_event_ref and shutdown_event_ref.is_set(): break
        if index >= len(scheduled_posts_data_ref) or scheduled_posts_data_ref[index].get('status') != 'pending':
            continue
        post_data = scheduled_posts_data_ref[index]
        title = post_data.get('title', 'Untitled')
        video_path = post_data.get('video_path')
        thumb_path = post_data.get('thumbnail_path')
        description = post_data.get('description', '')
        scheduled_time_utc_iso = post_data.get('scheduled_time')

        log_func_ref(f"Scheduler: Processing scheduled post: '{title}' (Index: {index})")

        file_error = False
        if not video_path or not os.path.exists(video_path):
            log_func_ref(f"Scheduler: Video file not found for '{title}': {video_path}. Marked error.")
            scheduled_posts_data_ref[index]['status'] = 'error_file'
            file_error = True
        if thumb_path and not os.path.exists(thumb_path):
            log_func_ref(f"Scheduler: Thumbnail file not found for '{title}': {thumb_path}. Uploading without custom thumbnail.")

        if file_error:
            needs_saving = True
            continue
        try:
            upload_response = upload_video(
                video_path, title, description, thumb_path,
                publish_time_utc_iso=scheduled_time_utc_iso,
                log_func=log_func_ref
            )
            if upload_response and 'id' in upload_response:
                scheduled_posts_data_ref[index]['status'] = 'uploaded'
                scheduled_posts_data_ref[index]['video_id'] = upload_response.get('id')
                log_func_ref(f"Scheduler: Successfully uploaded scheduled post: '{title}' (ID: {upload_response.get('id')})")
            else:
                 if scheduled_posts_data_ref[index]['status'] == 'pending':
                     scheduled_posts_data_ref[index]['status'] = 'error_upload'
                 log_func_ref(f"Scheduler: Upload failed for scheduled post '{title}'. Status is now '{scheduled_posts_data_ref[index]['status']}'.")
            processed_at_least_one = True
            needs_saving = True
        except Exception as e:
            log_func_ref(f"Scheduler: Unexpected error during scheduled upload processing for '{title}': {e}")
            scheduled_posts_data_ref[index]['status'] = 'error_unknown'
            processed_at_least_one = True
            needs_saving = True

    if needs_saving:
        save_scheduled_posts(scheduled_posts_data_ref, log_func_ref)
        if status_queue_ref and not (shutdown_event_ref and shutdown_event_ref.is_set()):
            status_queue_ref.put("update_ui")
    return processed_at_least_one

def run_scheduler_loop():
    log_func_ref("Scheduler thread started.")
    while not (shutdown_event_ref and shutdown_event_ref.is_set()):
        if not vietnam_tz:
            log_func_ref("Scheduler: Waiting for timezone initialization...")
            if shutdown_event_ref and shutdown_event_ref.wait(timeout=10):
                log_func_ref("Scheduler: Shutdown during timezone wait. Exiting.")
                break
            if not vietnam_tz:
                continue

        processed_something_in_cycle = False
        try:
            if not (shutdown_event_ref and shutdown_event_ref.is_set()):
                processed_something_in_cycle = process_scheduled_posts()
        except Exception as e:
            if not (shutdown_event_ref and shutdown_event_ref.is_set()):
                log_func_ref(f"SCHEDULER CRITICAL ERROR in loop: {e}")

        if shutdown_event_ref and shutdown_event_ref.is_set():
            log_func_ref("Scheduler: Shutdown detected post-processing or error. Exiting loop.")
            break

        if not threading.main_thread().is_alive():
            log_func_ref("Scheduler: Main thread closed. Stopping scheduler thread.")
            break

        sleep_time = 30 if processed_something_in_cycle else 60
        if shutdown_event_ref and shutdown_event_ref.wait(timeout=sleep_time):
            log_func_ref("Scheduler: Shutdown during sleep. Exiting.")
            break
    log_func_ref("Scheduler thread finished.")