# youtube_api.py
import os
import time
import json # For parsing HttpError content
from tkinter import messagebox
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from auth import get_authenticated_service
from config import API_SERVICE_NAME, API_VERSION

def upload_video(video_file_path, title, description, thumbnail_path=None, publish_time_utc_iso=None, log_func=print):
    youtube = get_authenticated_service(API_SERVICE_NAME, API_VERSION, log_func)
    if not youtube:
        log_func("Upload Error: YouTube service object is invalid (authentication failed).")
        messagebox.showerror("Upload Error", "Authentication is needed or has failed for upload scopes.")
        return None

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'categoryId': '22' # People & Blogs. Change if needed.
        },
        'status': {
            'privacyStatus': 'private' if publish_time_utc_iso else 'public',
            'publishAt': publish_time_utc_iso,
            'selfDeclaredMadeForKids': False,
        }
    }
    log_func(f"Starting upload: '{title}' (Schedule: {publish_time_utc_iso if publish_time_utc_iso else 'Immediate'})")
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
                       log_func(f"Uploading '{title}': {progress}%")
                       last_progress = progress
            except HttpError as http_error_chunk:
                if http_error_chunk.resp.status in [500, 502, 503, 504]:
                    log_func(f"Resumable upload error for '{title}': {http_error_chunk}. Retrying...")
                    time.sleep(random.randint(1,5)) # Add some jitter
                else:
                    log_func(f"Non-resumable API Error during upload chunk for '{title}': {http_error_chunk}")
                    raise
            except Exception as chunk_error:
                 log_func(f"Error during upload chunk for '{title}': {chunk_error}")
                 raise

        video_id = response['id']
        log_func(f"Successfully uploaded video '{title}'. Video ID: {video_id}")

        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                log_func(f"Starting thumbnail upload for video ID: {video_id}")
                request_thumbnail = youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path, mimetype='image/*')
                )
                request_thumbnail.execute()
                log_func(f"Successfully uploaded thumbnail for video ID: {video_id}")
            except HttpError as e_thumb_http:
                 log_func(f"API error uploading thumbnail for video ID {video_id}: {e_thumb_http}")
                 messagebox.showwarning("Thumbnail Error", f"Could not upload thumbnail for '{title}':\n{e_thumb_http}\nVideo was uploaded successfully.")
            except Exception as e_thumb:
                 log_func(f"Error uploading thumbnail for video ID {video_id}: {e_thumb}")
                 messagebox.showwarning("Thumbnail Error", f"Could not upload thumbnail for '{title}':\n{e_thumb}")
        elif thumbnail_path:
             log_func(f"Thumbnail file not found, skipping: {thumbnail_path}")
             messagebox.showwarning("Thumbnail Warning", f"Thumbnail file not found:\n{thumbnail_path}\nSkipping thumbnail upload for '{title}'.")
        return response

    except FileNotFoundError as fnf_error:
        log_func(f"File Error during upload setup for '{title}': {fnf_error}")
        messagebox.showerror("File Error", f"File not found:\n{fnf_error}")
        return None
    except HttpError as http_error:
        log_func(f"API Error during upload '{title}': {http_error}")
        messagebox.showerror("API Error", f"Could not upload video '{title}':\n{http_error}")
        return None
    except Exception as e:
        log_func(f"General Error during upload '{title}': {e}")
        messagebox.showerror("Upload Error", f"An unexpected error occurred uploading '{title}':\n{e}")
        return None

def fetch_trending_videos(region_code, max_results=25, log_func=print):
    youtube = get_authenticated_service(API_SERVICE_NAME, API_VERSION, log_func)
    if not youtube:
        log_func("Trending: Authentication failed for readonly scopes.")
        return None

    log_func(f"Fetching trending videos for region: {region_code}...")
    try:
        request = youtube.videos().list(
            part="snippet,statistics",
            chart="mostPopular",
            regionCode=region_code,
            maxResults=max_results
        )
        response = request.execute()
        items = response.get('items', [])
        log_func(f"Fetched {len(items)} trending videos for region: {region_code}")
        return items
    except HttpError as e:
        log_func(f"API Error fetching trending videos for '{region_code}': {e}")
        messagebox.showerror("API Error", f"Could not fetch trending videos for region '{region_code}':\n{e}")
        return None
    except Exception as e:
        log_func(f"Error fetching trending videos for '{region_code}': {e}")
        messagebox.showerror("Error", f"An error occurred fetching trending videos: {e}")
        return None

def post_comment(video_id, comment_text, log_func=print):
    youtube = get_authenticated_service(API_SERVICE_NAME, API_VERSION, log_func)
    if not youtube:
        log_func("Comment Posting Error: Authentication failed.")
        return None, "Authentication failed for comment scope."

    log_func(f"Attempting to post comment on Video ID: {video_id}")
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
        request = youtube.commentThreads().insert(
            part="snippet",
            body=request_body
        )
        response = request.execute()
        log_func(f"Successfully posted comment on Video ID {video_id}. Comment ID: {response['id']}")
        return response, None

    except HttpError as e:
        error_content = e.content.decode('utf-8')
        log_func(f"API Error posting comment on Video ID {video_id}: {e}")
        log_func(f"Error details: {error_content}")
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
        return None, display_error
    except Exception as e:
        log_func(f"General Error posting comment on Video ID {video_id}: {e}")
        return None, f"General Error posting comment on Video ID {video_id}: {e}"

def fetch_video_stats(video_id, log_func=print):
    youtube = get_authenticated_service(API_SERVICE_NAME, API_VERSION, log_func)
    if not youtube:
        log_func(f"Analytics Error: Authentication failed (Video ID: {video_id}).")
        return None, "Authentication failed"

    log_func(f"Fetching stats for Video ID: {video_id}...")
    try:
        request = youtube.videos().list(
            part="snippet,statistics",
            id=video_id
        )
        response = request.execute()

        items = response.get('items', [])
        if not items:
            log_func(f"Analytics Error: Video not found (ID: {video_id})")
            return None, "Video not found"

        log_func(f"Successfully fetched stats for Video ID: {video_id}")
        return items[0], None

    except HttpError as e:
        log_func(f"API Error fetching stats for Video ID {video_id}: {e}")
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
        log_func(f"General Error fetching stats for Video ID {video_id}: {e}")
        return None, f"Unexpected Error: {e}"