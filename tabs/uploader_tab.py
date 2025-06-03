# tabs/uploader_tab.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import threading

from file_handler import save_scheduled_posts
from youtube_api import upload_video
from time_utils import convert_vn_str_to_utc_iso, convert_utc_to_vn_str
import datetime # For min_schedule_time

def create_uploader_tab(notebook, root_ref, scheduled_posts_data_ref, status_queue_ref, log_func, refresh_all_tabs_func):
    uploader_tab = ttk.Frame(notebook, padding="15")
    uploader_tab.columnconfigure(0, weight=1)
    uploader_tab.rowconfigure(1, weight=1) # Allow list frame to expand

    # --- Input Frame 
    input_frame = ttk.LabelFrame(uploader_tab, text=" Video Details ", padding="15")
    input_frame.grid(row=0, column=0, padx=0, pady=0, sticky="ew")
    input_frame.columnconfigure(1, weight=1)

    ttk.Label(input_frame, text="Video File:").grid(row=0, column=0, padx=5, pady=6, sticky="w")
    video_path_entry = ttk.Entry(input_frame, width=60)
    video_path_entry.grid(row=0, column=1, padx=5, pady=6, sticky="ew")
    browse_video_btn = ttk.Button(input_frame, text="Browse...")
    browse_video_btn.grid(row=0, column=2, padx=5, pady=6)

    ttk.Label(input_frame, text="Title:").grid(row=1, column=0, padx=5, pady=6, sticky="w")
    title_entry = ttk.Entry(input_frame)
    title_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=6, sticky="ew")

    ttk.Label(input_frame, text="Description:").grid(row=2, column=0, padx=5, pady=6, sticky="nw")
    description_text = scrolledtext.ScrolledText(input_frame, height=5, width=50, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1, font=('TkDefaultFont', 9))
    description_text.grid(row=2, column=1, columnspan=2, padx=5, pady=6, sticky="ew")

    ttk.Label(input_frame, text="Thumbnail:").grid(row=3, column=0, padx=5, pady=6, sticky="w")
    thumbnail_path_entry = ttk.Entry(input_frame)
    thumbnail_path_entry.grid(row=3, column=1, padx=5, pady=6, sticky="ew")
    browse_thumb_btn = ttk.Button(input_frame, text="Browse...")
    browse_thumb_btn.grid(row=3, column=2, padx=5, pady=6)

    time_label = ttk.Label(input_frame, text="Schedule (VN Time):")
    time_label.grid(row=4, column=0, padx=5, pady=6, sticky="w")
    datetime_entry = ttk.Entry(input_frame)
    datetime_entry.grid(row=4, column=1, padx=5, pady=6, sticky="ew")
    time_format_label = ttk.Label(input_frame, text="YYYY-MM-DD HH:MM:SS", foreground="grey")
    time_format_label.grid(row=4, column=2, padx=5, pady=6, sticky="w")

    button_frame_input = ttk.Frame(input_frame)
    button_frame_input.grid(row=5, column=0, columnspan=3, pady=(20, 5))
    upload_now_btn = ttk.Button(button_frame_input, text="Upload Now (Public)")
    upload_now_btn.pack(side=tk.LEFT, padx=10)
    schedule_btn = ttk.Button(button_frame_input, text="Schedule Upload")
    schedule_btn.pack(side=tk.LEFT, padx=10)
    clear_btn = ttk.Button(button_frame_input, text="Clear Fields")
    clear_btn.pack(side=tk.LEFT, padx=10)

    # --- List Frame ---
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
    refresh_list_btn = ttk.Button(button_frame_list, text="Refresh List")
    refresh_list_btn.pack(side=tk.LEFT, padx=10)
    delete_post_btn = ttk.Button(button_frame_list, text="Delete Selected (List Only)")
    delete_post_btn.pack(side=tk.LEFT, padx=10)

    # --- Helper Functions & Callbacks ---
    status_bar = root_ref.status_bar # Get from main app

    def browse_file_ui(entry_widget, filetypes_desc, filetypes_ext):
        initial_dir = os.path.dirname(entry_widget.get()) if entry_widget.get() else os.path.expanduser("~")
        file_path = filedialog.askopenfilename(
            initialdir=initial_dir,
            filetypes=[(filetypes_desc, filetypes_ext), ("All Files", "*.*")],
            title=f"Select {filetypes_desc.split(' ')[0]} File"
        )
        if file_path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, file_path)

    browse_video_btn.config(command=lambda: browse_file_ui(video_path_entry, "Video Files", "*.mp4 *.avi *.mov *.mkv *.webm"))
    browse_thumb_btn.config(command=lambda: browse_file_ui(thumbnail_path_entry, "Image Files", "*.png *.jpg *.jpeg *.webp"))

    def validate_inputs_local(check_time=True):
        video_path_val = video_path_entry.get()
        title_val = title_entry.get()
        scheduled_time_str_vn = datetime_entry.get()

        if not video_path_val or not os.path.exists(video_path_val):
            messagebox.showerror("Input Error", f"Invalid or non-existent video file:\n{video_path_val}")
            return False, None, None
        if not title_val.strip():
            messagebox.showerror("Input Error", "Please enter a title.")
            return False, None, None
        thumbnail_path_val = thumbnail_path_entry.get()
        if thumbnail_path_val and not os.path.exists(thumbnail_path_val):
            messagebox.showerror("Input Error", f"Thumbnail file does not exist:\n{thumbnail_path_val}")
            return False, None, None

        utc_dt, utc_iso_str = None, None
        if check_time:
            if not scheduled_time_str_vn.strip():
                messagebox.showerror("Input Error", "Please enter the schedule time (Vietnam Time).")
                return False, None, None
            utc_dt, utc_iso_str = convert_vn_str_to_utc_iso(scheduled_time_str_vn.strip(), log_func=log_func)
            if utc_dt is None: return False, None, None
            log_func(f"Uploader: VN time '{scheduled_time_str_vn}' validated and converted to UTC: {utc_iso_str}")
        return True, utc_dt, utc_iso_str

    def set_uploader_buttons_state_local(state=tk.NORMAL):
        upload_now_btn.config(state=state)
        schedule_btn.config(state=state)
        clear_btn.config(state=state)
        # Potentially disable other buttons during operation
        refresh_list_btn.config(state=state)
        delete_post_btn.config(state=state)


    def clear_input_fields_local():
        video_path_entry.delete(0, tk.END)
        title_entry.delete(0, tk.END)
        description_text.delete("1.0", tk.END)
        thumbnail_path_entry.delete(0, tk.END)
        datetime_entry.delete(0, tk.END)
        if scheduled_list_treeview.selection():
             scheduled_list_treeview.selection_remove(scheduled_list_treeview.selection())

    def refresh_scheduled_list_local():
        scheduled_list_treeview.tag_configure('oddrow', background='#F0F0F0')
        scheduled_list_treeview.tag_configure('evenrow', background='white')
        scheduled_list_treeview.tag_configure('uploaded', foreground='green')
        scheduled_list_treeview.tag_configure('error', foreground='red')
        scheduled_list_treeview.tag_configure('pending', foreground='blue')
        scheduled_list_treeview.tag_configure('processing', foreground='orange') # Might be set by scheduler

        for item in scheduled_list_treeview.get_children():
            scheduled_list_treeview.delete(item)

        for i, post in enumerate(scheduled_posts_data_ref):
            title_val = post.get('title', 'N/A')
            status_val = post.get('status', 'N/A')
            time_utc_str = post.get('scheduled_time', '')
            time_vn_str = convert_utc_to_vn_str(time_utc_str, log_func=log_func) if time_utc_str else "Uploaded Now"

            row_tag = 'oddrow' if i % 2 else 'evenrow'
            status_tag_map = {'uploaded': 'uploaded', 'pending': 'pending', 'processing': 'processing'}
            status_tag = status_tag_map.get(status_val)
            if not status_tag and status_val and status_val.startswith('error'):
                status_tag = 'error'
            tags = (row_tag, status_tag) if status_tag else (row_tag,)
            scheduled_list_treeview.insert('', tk.END, values=(title_val, time_vn_str, status_val), iid=str(i), tags=tags)
        # After refreshing this list, tell main app to refresh other dependent lists (like analytics)
        refresh_all_tabs_func()


    def on_scheduled_item_select_local(event):
        selected_items = scheduled_list_treeview.selection()
        if not selected_items: return
        try:
            index = int(selected_items[0])
            if 0 <= index < len(scheduled_posts_data_ref):
                post_data = scheduled_posts_data_ref[index]
                clear_input_fields_local() # Clear first
                video_path_entry.insert(0, post_data.get('video_path', ''))
                title_entry.insert(0, post_data.get('title', ''))
                description_text.insert("1.0", post_data.get('description', ''))
                thumbnail_path_entry.insert(0, post_data.get('thumbnail_path', ''))
                utc_time_str = post_data.get('scheduled_time', '')
                if utc_time_str:
                    vn_time_str = convert_utc_to_vn_str(utc_time_str, log_func=log_func)
                    if vn_time_str != "N/A" and vn_time_str != "Invalid Date":
                        datetime_entry.insert(0, vn_time_str)
            else: clear_input_fields_local()
        except (ValueError, IndexError): clear_input_fields_local()

    def schedule_upload_ui_local():
        is_valid, utc_dt, scheduled_time_utc_iso = validate_inputs_local(check_time=True)
        if not is_valid: return

        min_schedule_time_utc = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=2)
        if utc_dt <= min_schedule_time_utc:
             messagebox.showerror("Input Error", "Schedule time must be at least a few minutes in the future (UTC).")
             return

        new_post = {
            "video_path": video_path_entry.get(), "title": title_entry.get().strip(),
            "description": description_text.get("1.0", tk.END).strip(),
            "scheduled_time": scheduled_time_utc_iso,
            "thumbnail_path": thumbnail_path_entry.get() or None,
            "status": "pending", "video_id": None
        }
        scheduled_posts_data_ref.append(new_post)
        save_scheduled_posts(scheduled_posts_data_ref, log_func)
        log_func(f"Uploader: Scheduled '{new_post['title']}' for {datetime_entry.get().strip()} (VN) / {scheduled_time_utc_iso} (UTC).")
        messagebox.showinfo("Success", f"Video upload scheduled:\nTitle: '{new_post['title']}'\nAt: {datetime_entry.get().strip()} (VN)")
        clear_input_fields_local()
        refresh_scheduled_list_local()

    def upload_now_ui_local():
        is_valid, _, _ = validate_inputs_local(check_time=False)
        if not is_valid: return
        if not messagebox.askyesno("Confirm Upload", "Upload this video immediately as Public?"):
            return

        video_p = video_path_entry.get()
        title_v = title_entry.get().strip()
        desc_v = description_text.get("1.0", tk.END).strip()
        thumb_p = thumbnail_path_entry.get()

        def upload_task():
            root_ref.after(0, set_uploader_buttons_state_local, tk.DISABLED)
            if status_bar: root_ref.after(0, status_bar.show_progress)
            log_func(f"Uploader: Starting immediate upload task for '{title_v}'...")

            response = upload_video(video_p, title_v, desc_v, thumb_p, publish_time_utc_iso=None, log_func=log_func)
            upload_successful = False
            if response and 'id' in response:
                video_id = response.get('id')
                log_func(f"Uploader: Immediate upload successful: '{title_v}', Video ID: {video_id}")
                root_ref.after(0, messagebox.showinfo, "Upload Successful", f"Successfully uploaded video '{title_v}'\nVideo ID: {video_id}")
                upload_successful = True
                uploaded_post_entry = {
                    "video_path": video_p, "title": title_v, "description": desc_v,
                    "scheduled_time": None, "thumbnail_path": thumb_p or None,
                    "status": "uploaded", "video_id": video_id
                }
                scheduled_posts_data_ref.append(uploaded_post_entry)
                save_scheduled_posts(scheduled_posts_data_ref, log_func)
                # status_queue_ref.put("update_ui") # This will trigger refresh_all_tabs_func
                root_ref.after(0, refresh_scheduled_list_local) # Directly refresh this tab's list

            root_ref.after(0, set_uploader_buttons_state_local, tk.NORMAL)
            if status_bar:
                root_ref.after(0, status_bar.hide_progress)
                if not upload_successful:
                    root_ref.after(0, status_bar.set_text, f"Upload failed for '{title_v}'. Check logs.")
                else:
                    root_ref.after(0, status_bar.clear)
                    root_ref.after(0, clear_input_fields_local)

        threading.Thread(target=upload_task, daemon=True).start()
        log_func("Uploader: Background thread for immediate upload started.")

    def delete_selected_post_local():
        selected_items = scheduled_list_treeview.selection()
        if not selected_items:
            messagebox.showwarning("No Selection", "Please select a post to delete.")
            return
        try:
            index_to_delete = int(selected_items[0])
            if 0 <= index_to_delete < len(scheduled_posts_data_ref):
                post_to_delete = scheduled_posts_data_ref[index_to_delete]
                title_val = post_to_delete.get('title', 'Untitled')
                status_val = post_to_delete.get('status', 'N/A')
                confirm_msg = f"Delete '{title_val}' from this list?\nStatus: {status_val}\n\n"
                if status_val == 'pending': confirm_msg += "(This removes it from the schedule.)"
                elif status_val == 'uploaded': confirm_msg += "(Removes from list only, the YouTube video is NOT deleted.)"
                else: confirm_msg += "(Removes from list.)"

                if messagebox.askyesno("Confirm Deletion", confirm_msg):
                    del scheduled_posts_data_ref[index_to_delete]
                    save_scheduled_posts(scheduled_posts_data_ref, log_func)
                    refresh_scheduled_list_local()
                    clear_input_fields_local()
                    log_func(f"Uploader: Deleted '{title_val}' from schedule list.")
            else:
                messagebox.showerror("Error", "Could not delete (invalid index). Please refresh.")
        except (ValueError, IndexError) as e:
            messagebox.showerror("Error", f"Could not delete selected post:\n{e}")

    # Assign commands
    upload_now_btn.config(command=upload_now_ui_local)
    schedule_btn.config(command=schedule_upload_ui_local)
    clear_btn.config(command=clear_input_fields_local)
    refresh_list_btn.config(command=refresh_scheduled_list_local)
    delete_post_btn.config(command=delete_selected_post_local)
    scheduled_list_treeview.bind('<<TreeviewSelect>>', on_scheduled_item_select_local)

    # Initial population of the list
    refresh_scheduled_list_local()

    # Add a method to the tab itself for external refresh, if needed by main_app
    uploader_tab.refresh_list = refresh_scheduled_list_local

    return uploader_tab