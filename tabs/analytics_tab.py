# tabs/analytics_tab.py
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import math
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import matplotlib.ticker as mticker

from youtube_api import fetch_video_stats
from time_utils import convert_utc_to_vn_str

# Module-level variable for the canvas widget to manage its destruction
canvas_widget_analytics = None

def create_analytics_tab(notebook, root_ref, scheduled_posts_data_ref, log_func):
    analytics_tab = ttk.Frame(notebook, padding="15")
    status_bar = root_ref.status_bar

    # --- Controls Frame ---
    analytics_controls_frame = ttk.Frame(analytics_tab)
    analytics_controls_frame.pack(pady=10, fill="x")

    combobox_frame = ttk.Frame(analytics_controls_frame)
    combobox_frame.pack(side=tk.LEFT, fill='x', expand=False, padx=(0,10))
    ttk.Label(combobox_frame, text="Select Uploaded Video:").pack(side=tk.LEFT, padx=(0, 5))
    analytics_video_combobox = ttk.Combobox(combobox_frame, width=45, state='disabled')
    analytics_video_combobox.pack(side=tk.LEFT, padx=5)
    analytics_video_combobox.video_map = {} # To store display_title -> video_id
    analyze_video_btn = ttk.Button(combobox_frame, text="Analyze Selected", state=tk.DISABLED)
    analyze_video_btn.pack(side=tk.LEFT, padx=10)

    custom_id_controls_frame = ttk.Frame(analytics_controls_frame)
    custom_id_controls_frame.pack(side=tk.LEFT, fill='x', expand=True)
    ttk.Label(custom_id_controls_frame, text="Or Enter Video ID:").pack(side=tk.LEFT, padx=(0,5))
    custom_video_id_analytics_entry = ttk.Entry(custom_id_controls_frame, width=15)
    custom_video_id_analytics_entry.pack(side=tk.LEFT, padx=5)
    analyze_custom_id_btn = ttk.Button(custom_id_controls_frame, text="Analyze Custom ID")
    analyze_custom_id_btn.pack(side=tk.LEFT, padx=5)

    # --- Display Frame ---
    analytics_display_frame = ttk.Frame(analytics_tab)
    analytics_display_frame.pack(pady=10, fill="both", expand=True)
    analytics_display_frame.columnconfigure(0, weight=1) # Chart
    analytics_display_frame.columnconfigure(1, weight=1) # Report
    analytics_display_frame.rowconfigure(0, weight=1)

    analytics_chart_labelframe = ttk.LabelFrame(analytics_display_frame, text=" Performance Chart ", padding="5")
    analytics_chart_labelframe.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="nsew")
    analytics_chart_frame = ttk.Frame(analytics_chart_labelframe) # Actual frame for canvas
    analytics_chart_frame.pack(fill="both", expand=True)

    analytics_report_labelframe = ttk.LabelFrame(analytics_display_frame, text=" Statistics Report ", padding="5")
    analytics_report_labelframe.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="nsew")
    analytics_report_text = scrolledtext.ScrolledText(analytics_report_labelframe, height=10, width=40, wrap=tk.WORD, state=tk.DISABLED, relief=tk.SOLID, borderwidth=1)
    analytics_report_text.pack(fill="both", expand=True, padx=5, pady=5)

    # --- Callbacks & Helpers ---
    def clear_analytics_results_local():
        global canvas_widget_analytics
        if canvas_widget_analytics:
            canvas_widget_analytics.get_tk_widget().destroy()
            canvas_widget_analytics = None
            plt.close('all') # Close all matplotlib figures
        if analytics_report_text.winfo_exists():
            analytics_report_text.config(state=tk.NORMAL)
            analytics_report_text.delete("1.0", tk.END)
            analytics_report_text.config(state=tk.DISABLED)

    def update_analyzable_videos_list_local():
        uploaded_videos = []
        analytics_video_combobox.video_map.clear()

        for post in scheduled_posts_data_ref: # Use the ref
            if post.get('status') == 'uploaded' and post.get('video_id'):
                title = post.get('title', 'Untitled Video')
                video_id = post.get('video_id')
                display_title = f"{title} ({video_id})"
                uploaded_videos.append(display_title)
                analytics_video_combobox.video_map[display_title] = video_id
        
        current_selection = analytics_video_combobox.get()
        if uploaded_videos:
            analytics_video_combobox['values'] = uploaded_videos
            if current_selection in uploaded_videos:
                 analytics_video_combobox.set(current_selection)
            else:
                 analytics_video_combobox.current(0)
            analytics_video_combobox.config(state='readonly')
            analyze_video_btn.config(state=tk.NORMAL)
        else:
            analytics_video_combobox['values'] = []
            analytics_video_combobox.set("No uploaded videos found")
            analytics_video_combobox.config(state='disabled')
            analyze_video_btn.config(state=tk.DISABLED)
            clear_analytics_results_local()
        log_func(f"Analytics: Updated analyzable videos list: {len(uploaded_videos)} items.")

    def display_analysis_results_local(video_data, error_msg, display_identifier):
        clear_analytics_results_local()
        global canvas_widget_analytics

        if error_msg:
            log_func(f"Analytics: Failed to display analysis for '{display_identifier}': {error_msg}")
            messagebox.showerror("Analysis Error", f"Could not get data for '{display_identifier}':\n{error_msg}")
            report_content = f"Error fetching data for '{display_identifier}':\n\n{error_msg}"
            if analytics_report_text.winfo_exists():
                analytics_report_text.config(state=tk.NORMAL)
                analytics_report_text.insert("1.0", report_content)
                analytics_report_text.config(state=tk.DISABLED)
            return

        if not video_data:
            log_func(f"Analytics: No video data returned for '{display_identifier}', cannot display.")
            if analytics_report_text.winfo_exists():
                analytics_report_text.config(state=tk.NORMAL)
                analytics_report_text.insert("1.0", f"No data returned for '{display_identifier}'. The video might be private, deleted, or the ID is incorrect.")
                analytics_report_text.config(state=tk.DISABLED)
            return

        snippet = video_data.get('snippet', {})
        stats = video_data.get('statistics', {})
        video_api_title = snippet.get('title', display_identifier) # Use API title if available
        publish_time_utc = snippet.get('publishedAt')
        publish_time_vn = convert_utc_to_vn_str(publish_time_utc, log_func=log_func) if publish_time_utc else "N/A"

        def safe_int(value):
            try: return int(value)
            except (ValueError, TypeError): return 0
        views, likes, comments = safe_int(stats.get('viewCount')), safe_int(stats.get('likeCount')), safe_int(stats.get('commentCount'))

        # Chart
        try:
            data = {'Metric': ['Views', 'Likes', 'Comments'], 'Count': [views, likes, comments]}
            df = pd.DataFrame(data)
            fig, ax = plt.subplots(figsize=(6, 3.5), dpi=100) # Adjusted figsize
            bars = ax.bar(df['Metric'], df['Count'], color=['skyblue', 'lightcoral', 'lightgreen'])
            ax.set_ylabel('Count')
            chart_title_text = video_api_title[:45] + ("..." if len(video_api_title) > 45 else "") # Shorter title for chart
            ax.set_title(f'Metrics for: {chart_title_text}', fontsize=10)
            ax.tick_params(axis='x', rotation=0, labelsize=9)
            ax.tick_params(axis='y', labelsize=9)
            ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)

            max_val_for_ylim = max(views, likes, comments, 1) # Ensure at least 1 for ylim
            top_limit = max(math.ceil(max_val_for_ylim * 1.20), 5) # More headroom
            ax.set_ylim(bottom=0, top=top_limit)

            if top_limit <= 10 and top_limit > 0: ax.yaxis.set_major_locator(mticker.MultipleLocator(1))
            elif top_limit > 10 and top_limit <= 50: ax.yaxis.set_major_locator(mticker.MultipleLocator(math.ceil(top_limit / 10.0)))
            else: ax.yaxis.set_major_locator(mticker.AutoLocator())

            for bar in bars:
                 yval = bar.get_height()
                 if yval > 0 or (yval == 0 and max_val_for_ylim <=1): # Show 0 if all are 0
                     ax.text(bar.get_x() + bar.get_width()/2.0, yval, f'{yval:,}', va='bottom', ha='center', fontsize=8)

            plt.tight_layout(pad=0.5) # Reduce padding
            canvas_widget_analytics = FigureCanvasTkAgg(fig, master=analytics_chart_frame)
            canvas_widget_analytics.draw()
            canvas_widget_analytics.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        except Exception as e_chart:
            log_func(f"Analytics: Error creating chart: {e_chart}")
            if analytics_report_text.winfo_exists():
                 analytics_report_text.config(state=tk.NORMAL)
                 analytics_report_text.insert(tk.END, f"\n\nError generating chart: {e_chart}")
                 analytics_report_text.config(state=tk.DISABLED)
        # Report
        if analytics_report_text.winfo_exists():
            report_content = f"Video: {display_identifier}\n"
            if video_api_title != display_identifier : 
                 report_content += f"Title: {video_api_title}\n"
            report_content += f"ID: {video_data.get('id', 'N/A')}\nPublished (VN): {publish_time_vn}\n\n"
            report_content += f"Views: {views:,}\nLikes: {likes:,}\nComments: {comments:,}\n"
            analytics_report_text.config(state=tk.NORMAL)
            analytics_report_text.delete("1.0", tk.END)
            analytics_report_text.insert("1.0", report_content)
            analytics_report_text.config(state=tk.DISABLED)
        log_func(f"Analytics: Displayed analytics for '{display_identifier}'")


    def trigger_analysis_task(video_id_to_analyze, display_id_for_ui):
        log_func(f"Analytics: Analysis requested for: {display_id_for_ui} (Actual ID: {video_id_to_analyze})")
        clear_analytics_results_local()
        analyze_video_btn.config(state=tk.DISABLED)
        analyze_custom_id_btn.config(state=tk.DISABLED)
        if status_bar: status_bar.show_progress()

        def analysis_thread_task():
            video_data, error = fetch_video_stats(video_id_to_analyze, log_func=log_func)
            root_ref.after(0, display_analysis_results_local, video_data, error, display_id_for_ui)
            
            is_combobox_valid = analytics_video_combobox.get() and analytics_video_combobox.cget('state') != 'disabled'
            root_ref.after(0, lambda: analyze_video_btn.config(state=tk.NORMAL if is_combobox_valid else tk.DISABLED))
            root_ref.after(0, lambda: analyze_custom_id_btn.config(state=tk.NORMAL))
            if status_bar:
                root_ref.after(0, status_bar.hide_progress)
                if error:
                    root_ref.after(0, status_bar.set_text, f"Analytics failed for {video_id_to_analyze}. {error[:50]}...")
                else:
                    root_ref.after(0, status_bar.clear)
        threading.Thread(target=analysis_thread_task, daemon=True).start()

    def analyze_selected_video_ui_local():
        if not analytics_video_combobox.get() or analytics_video_combobox.cget('state') == 'disabled':
            messagebox.showwarning("No Selection", "Please select a video from the list.")
            return
        selected_display_title = analytics_video_combobox.get()
        video_id = analytics_video_combobox.video_map.get(selected_display_title)
        if not video_id:
            messagebox.showerror("Error", "Could not find Video ID for the selected item.")
            return
        trigger_analysis_task(video_id, selected_display_title)

    def analyze_custom_video_id_ui_local():
        video_id = custom_video_id_analytics_entry.get().strip()
        if not video_id:
            messagebox.showwarning("Input Required", "Please enter a Video ID to analyze.")
            return
        if len(video_id) != 11: # Basic check
             messagebox.showwarning("Invalid Format", "Video ID usually has 11 characters. Please check.")
        trigger_analysis_task(video_id, f"Custom ID: {video_id}")

    # Assign commands
    analyze_video_btn.config(command=analyze_selected_video_ui_local)
    analyze_custom_id_btn.config(command=analyze_custom_video_id_ui_local)

    # Initial population
    update_analyzable_videos_list_local()
    analytics_tab.update_list = update_analyzable_videos_list_local 

    return analytics_tab