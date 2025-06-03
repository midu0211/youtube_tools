# main_app.py
import tkinter as tk
from tkinter import ttk, messagebox
from ttkthemes import ThemedTk
import threading
import queue
import datetime
import os

import config
from time_utils import initialize_timezone
from file_handler import get_scheduled_posts, load_comment_templates
from scheduler import set_scheduler_refs, run_scheduler_loop
from ui_components import StatusBar

from tabs.uploader_tab import create_uploader_tab
from tabs.trending_tab import create_trending_tab
from tabs.comments_tab import create_comments_tab
from tabs.analytics_tab import create_analytics_tab

status_queue = queue.Queue()
scheduled_posts_data = []
comment_templates_list = []

class YouTubeToolApp:
    def __init__(self, master_root):
        self.root = master_root
        self.shutdown_event = threading.Event()
        self.status_bar = None
        self.notebook = None
        self.uploader_tab_ref = None
        self.analytics_tab_ref = None
        self.comments_tab_ref = None
        self.scheduler_thread_instance = None

        self._setup_logging()
        if not initialize_timezone(self.log_status):
            messagebox.showerror("Critical Error", "Timezone initialization failed. Application cannot start.")
            self.root.destroy()
            return

        self._load_initial_data()
        self._setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self._start_background_tasks()
        self.log_status("Application started. Ready.")

    def _setup_logging(self):
        pass

    def log_status(self, message):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        print(log_message)

        if hasattr(self, 'root') and self.root and \
           hasattr(self, 'status_bar') and self.status_bar and \
           self.root.winfo_exists() and self.status_bar.winfo_exists():
            try:
                self.root.after(0, self.status_bar.set_text, message)
            except tk.TclError as e:
                if "application has been destroyed" not in str(e).lower():
                    print(f"Error updating status bar from log_status (TclError): {e}")
            except Exception as e:
                print(f"Generic error updating status bar from log_status: {e}")

    def _load_initial_data(self):
        global scheduled_posts_data, comment_templates_list
        scheduled_posts_data = get_scheduled_posts(self.log_status)
        comment_templates_list = load_comment_templates(self.log_status)
        self.log_status(f"Initial data loaded: {len(scheduled_posts_data)} scheduled, {len(comment_templates_list)} templates.")

    def _setup_ui(self):
        self.root.title("YouTube Tool Enhanced")
        self.root.geometry("1050x850")

        style = ttk.Style(self.root)
        try:
            if "arc" in style.theme_names():
                self.root.set_theme("arc")
            else:
                self.log_status("Warning: ttktheme 'arc' not found. Using default.")
        except tk.TclError:
             self.log_status("Warning: ttktheme 'arc' not found (TclError). Using default.")

        style.configure("Treeview.Heading", font=('Helvetica', 10, 'bold'))
        style.configure("TButton", padding=5)
        style.configure("TLabelframe.Label", font=('Helvetica', 11, 'bold'))

        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(5, 0))
        self.root.status_bar = self.status_bar

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(pady=10, padx=10, fill="both", expand=True)

        self.uploader_tab_ref = create_uploader_tab(self.notebook, self.root, scheduled_posts_data, status_queue, self.log_status, self.refresh_dependent_tabs)
        self.notebook.add(self.uploader_tab_ref, text=' Upload & Schedule ')

        trending_tab = create_trending_tab(self.notebook, self.root, self.log_status)
        self.notebook.add(trending_tab, text=' Trending Videos ')

        self.comments_tab_ref = create_comments_tab(self.notebook, self.root, comment_templates_list, self.log_status)
        self.notebook.add(self.comments_tab_ref, text=' Comment Tools ')

        self.analytics_tab_ref = create_analytics_tab(self.notebook, self.root, scheduled_posts_data, self.log_status)
        self.notebook.add(self.analytics_tab_ref, text=' Analytics ')

    def refresh_dependent_tabs(self):
        self.log_status("MainApp: Refreshing dependent tabs...")
        if self.analytics_tab_ref and hasattr(self.analytics_tab_ref, 'update_list'):
            self.analytics_tab_ref.update_list()

    def _check_status_queue(self):
        try:
            message = status_queue.get_nowait()
            if message == "update_ui":
                self.log_status("MainApp: UI Update requested via queue.")
                if self.uploader_tab_ref and hasattr(self.uploader_tab_ref, 'refresh_list'):
                    self.uploader_tab_ref.refresh_list()
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error in _check_status_queue processing: {e}")
        finally:
            if hasattr(self, 'root') and self.root and self.root.winfo_exists() and not self.shutdown_event.is_set():
                self.root.after(1500, self._check_status_queue)

    def _start_background_tasks(self):
        set_scheduler_refs(scheduled_posts_data, status_queue, self.log_status, self.shutdown_event)
        self.scheduler_thread_instance = threading.Thread(target=run_scheduler_loop, daemon=True)
        self.scheduler_thread_instance.start()

        if self.root.winfo_exists():
            self.root.after(1500, self._check_status_queue)

        self.log_status(f"App config: Timezone '{config.VIETNAM_TZ_STR}'. Client Secret: '{os.path.basename(config.CLIENT_SECRETS_FILE)}'.")
        self.log_status(f"Initial auth uses scopes: {config.ALL_APP_SCOPES}")

    def on_closing(self):
        self.log_status("Application is closing...")
        self.shutdown_event.set()

        if self.scheduler_thread_instance and self.scheduler_thread_instance.is_alive():
            self.log_status("Waiting for scheduler thread to finish...")
            self.scheduler_thread_instance.join(timeout=2.0)
            if self.scheduler_thread_instance.is_alive():
                self.log_status("Scheduler thread did not finish in time.")
        
        self.log_status("Destroying root window.")
        self.root.destroy()

if __name__ == "__main__":
    root = None
    try:
        root = ThemedTk()
    except tk.TclError:
        print("ThemedTk not available or theme engine issue, falling back to standard tk.Tk.")
        root = tk.Tk()

    app = YouTubeToolApp(root)
    if app and hasattr(app, 'root') and app.root.winfo_exists():
        root.mainloop()
    print("Exiting application.")