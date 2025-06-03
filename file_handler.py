# file_handler.py
import os
import json
from tkinter import messagebox
from config import SCHEDULED_POSTS_FILE, COMMENT_TEMPLATES_FILE

def get_json_data(filepath, log_func=print, data_description="data"):
    if not os.path.exists(filepath):
        log_func(f"{data_description.capitalize()} file '{filepath}' not found. Creating empty.")
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump([], f)
            return []
        except IOError as e:
            log_func(f"Error creating empty {data_description} file '{filepath}': {e}")
            messagebox.showerror("File Error", f"Could not create {data_description} file:\n{e}")
            return []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        if not content.strip():
            return []
        data = json.loads(content)
        log_func(f"Loaded {len(data)} {data_description} from '{filepath}'.")
        return data
    except json.JSONDecodeError:
        log_func(f"ERROR reading JSON file: '{filepath}'. Corrupted?")
        messagebox.showerror("JSON Error", f"Error reading {data_description} file:\n'{filepath}'\nFile seems corrupted. Please check or delete.")
        return []
    except IOError as e:
         log_func(f"ERROR reading file '{filepath}': {e}")
         messagebox.showerror("File Error", f"Could not read {data_description} file:\n{e}")
         return []
    except Exception as e:
        log_func(f"Unknown error reading JSON file '{filepath}': {e}")
        messagebox.showerror("Error", f"Unexpected error reading {data_description} file:\n{e}")
        return []

def save_json_data(data, filepath, log_func=print, data_description="data"):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        log_func(f"Saved {len(data)} {data_description} to '{filepath}'.")
    except IOError as e:
        log_func(f"Error saving {data_description} file '{filepath}': {e}")
        messagebox.showerror("File Error", f"Could not save {data_description} file:\n{e}")
    except Exception as e:
        log_func(f"Unknown error saving JSON file '{filepath}': {e}")
        messagebox.showerror("Error", f"Unexpected error saving {data_description} file:\n{e}")

def get_scheduled_posts(log_func=print):
    return get_json_data(SCHEDULED_POSTS_FILE, log_func, "scheduled posts")

def save_scheduled_posts(posts, log_func=print):
    save_json_data(posts, SCHEDULED_POSTS_FILE, log_func, "scheduled posts")

def load_comment_templates(log_func=print):
    return get_json_data(COMMENT_TEMPLATES_FILE, log_func, "comment templates")

def save_comment_templates(templates, log_func=print):
    save_json_data(templates, COMMENT_TEMPLATES_FILE, log_func, "comment templates")