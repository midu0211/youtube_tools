# tabs/trending_tab.py
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from youtube_api import fetch_trending_videos

def create_trending_tab(notebook, root_ref, log_func):
    trending_tab = ttk.Frame(notebook, padding="15")
    status_bar = root_ref.status_bar # Get from main app

    # --- Controls Frame ---
    trending_controls_frame = ttk.Frame(trending_tab)
    trending_controls_frame.pack(pady=10, fill="x")

    ttk.Label(trending_controls_frame, text="Region Code:").pack(side=tk.LEFT, padx=(0, 5))
    region_code_entry = ttk.Entry(trending_controls_frame, width=5)
    region_code_entry.insert(0, "VN")
    region_code_entry.pack(side=tk.LEFT, padx=5)

    fetch_trending_btn = ttk.Button(trending_controls_frame, text="Get Trending")
    fetch_trending_btn.pack(side=tk.LEFT, padx=10)

    trending_status_label = ttk.Label(trending_controls_frame, text="Enter 2-letter code (e.g., VN, US)")
    trending_status_label.pack(side=tk.LEFT, padx=10, fill='x', expand=True)

    # --- List Frame ---
    trending_list_frame = ttk.LabelFrame(trending_tab, text=" Top Trending Videos ", padding="10")
    trending_list_frame.pack(pady=10, fill="both", expand=True)

    columns_trend = ('title', 'channel', 'views')
    trending_list_treeview = ttk.Treeview(trending_list_frame, columns=columns_trend, show='headings')
    trending_list_treeview.heading('title', text='Title', anchor=tk.W) # Changed to W
    trending_list_treeview.heading('channel', text='Channel', anchor=tk.W) # Changed to W
    trending_list_treeview.heading('views', text='View Count', anchor=tk.E) # Changed to E

    trending_list_treeview.column('title', width=550, stretch=tk.YES, anchor='w')
    trending_list_treeview.column('channel', width=200, stretch=tk.NO, anchor='w')
    trending_list_treeview.column('views', width=150, stretch=tk.NO, anchor='e')

    scrollbar_trend = ttk.Scrollbar(trending_list_frame, orient=tk.VERTICAL, command=trending_list_treeview.yview)
    trending_list_treeview.configure(yscroll=scrollbar_trend.set)
    trending_list_treeview.pack(side=tk.LEFT, fill="both", expand=True)
    scrollbar_trend.pack(side=tk.RIGHT, fill="y")

    # --- Callbacks & Helpers ---
    def clear_trending_results_local(message=""):
        for item in trending_list_treeview.get_children():
            trending_list_treeview.delete(item)
        if message:
             trending_list_treeview.insert('', tk.END, values=(message, "", ""))

    def display_trending_results_local(videos, region):
        clear_trending_results_local()
        trending_list_treeview.tag_configure('oddrow', background='#F0F0F0')
        trending_list_treeview.tag_configure('evenrow', background='white')

        if videos is None:
            log_func(f"Trending: Failed to display trending for {region} (fetch error).")
            trending_list_treeview.insert('', tk.END, values=(f"Error fetching videos for {region}", "", ""))
            trending_status_label.config(text=f"Region: {region} (Error)")
            return

        if not videos:
            log_func(f"Trending: No trending videos found for region: {region}.")
            trending_list_treeview.insert('', tk.END, values=(f"No trending videos found for {region}", "", ""))
            trending_status_label.config(text=f"Region: {region} (No videos)")
            return

        log_func(f"Trending: Displaying {len(videos)} trending videos for region: {region}.")
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

    def fetch_and_display_trending_local():
        region = region_code_entry.get().strip().upper()
        if not region or len(region) != 2 or not region.isalpha():
            messagebox.showwarning("Invalid Input", "Region Code must be 2 letters (e.g., VN, US).")
            return

        def fetch_task():
            root_ref.after(0, lambda: fetch_trending_btn.config(state=tk.DISABLED))
            if status_bar: root_ref.after(0, status_bar.show_progress)
            log_func(f"Trending: Starting fetch for trending videos (Region: {region})...")

            trending_videos_data = fetch_trending_videos(region, log_func=log_func) # Pass log_func
            fetch_successful = trending_videos_data is not None

            root_ref.after(0, display_trending_results_local, trending_videos_data, region)
            root_ref.after(0, lambda: fetch_trending_btn.config(state=tk.NORMAL))
            if status_bar:
                 root_ref.after(0, status_bar.hide_progress)
                 if not fetch_successful:
                     root_ref.after(0, status_bar.set_text, f"Failed to fetch trending for {region}.")
                 else:
                     root_ref.after(0, status_bar.clear)

        trending_status_label.config(text=f"Fetching for {region}...")
        clear_trending_results_local("Loading...")
        threading.Thread(target=fetch_task, daemon=True).start()

    fetch_trending_btn.config(command=fetch_and_display_trending_local)
    clear_trending_results_local() 

    return trending_tab