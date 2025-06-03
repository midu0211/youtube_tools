# tabs/comments_tab.py
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import random # For picking random comment

from file_handler import save_comment_templates
from youtube_api import post_comment
from config import MEANINGFUL_COMMENT_BASES, EMOJIS_LIST, COMMENT_SUFFIXES

# Module-level variable to store the currently picked random comment
current_random_comment_for_tab = ""

def create_comments_tab(notebook, root_ref, comment_templates_list_ref, log_func):
    global current_random_comment_for_tab # Allow modification
    interaction_tab = ttk.Frame(notebook, padding="15")
    interaction_tab.columnconfigure(0, weight=1)
    interaction_tab.rowconfigure(0, weight=3) # Templates area
    interaction_tab.rowconfigure(1, weight=1) # Post area

    status_bar = root_ref.status_bar

    # --- Comment Templates Frame ---
    comment_frame = ttk.LabelFrame(interaction_tab, text=" Comment Templates ", padding="10")
    comment_frame.grid(row=0, column=0, pady=10, padx=0, sticky="nsew")
    comment_frame.columnconfigure(0, weight=1)
    comment_frame.rowconfigure(0, weight=1) # Allow listbox area to expand
    comment_frame.rowconfigure(3, weight=0) # Generate frame fixed size

    comment_list_subframe = ttk.Frame(comment_frame) # For listbox and scrollbar
    comment_list_subframe.grid(row=0, column=0, pady=5, sticky='nsew')
    comment_list_subframe.columnconfigure(0, weight=1)
    comment_list_subframe.rowconfigure(1, weight=1)

    ttk.Label(comment_list_subframe, text="Saved Comments:").grid(row=0, column=0, sticky='w', padx=5)
    comment_scrollbar = ttk.Scrollbar(comment_list_subframe, orient=tk.VERTICAL)
    comment_template_listbox = tk.Listbox(comment_list_subframe, height=8, yscrollcommand=comment_scrollbar.set, relief=tk.SOLID, borderwidth=1, exportselection=False)
    comment_scrollbar.config(command=comment_template_listbox.yview)
    comment_template_listbox.grid(row=1, column=0, sticky='nsew', padx=(5,0), pady=5)
    comment_scrollbar.grid(row=1, column=1, sticky='ns', pady=5)

    comment_input_frame = ttk.Frame(comment_frame)
    comment_input_frame.grid(row=1, column=0, pady=5, sticky='ew')
    comment_input_frame.columnconfigure(1, weight=1)
    ttk.Label(comment_input_frame, text="New:").grid(row=0, column=0, padx=(5,2), pady=5, sticky='w')
    new_comment_entry = ttk.Entry(comment_input_frame)
    new_comment_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
    add_comment_btn = ttk.Button(comment_input_frame, text="Add", width=5)
    add_comment_btn.grid(row=0, column=2, padx=(0,5), pady=5)

    comment_button_frame = ttk.Frame(comment_frame)
    comment_button_frame.grid(row=2, column=0, pady=(5,0))
    delete_comment_btn = ttk.Button(comment_button_frame, text="Delete Selected")
    delete_comment_btn.pack(side=tk.LEFT, padx=10)

    generate_comments_frame = ttk.LabelFrame(comment_frame, text=" Generate New Comments ", padding="10")
    generate_comments_frame.grid(row=3, column=0, pady=(10,5), sticky="ew")
    generate_comments_frame.columnconfigure(2, weight=1) # Push button to right
    ttk.Label(generate_comments_frame, text="Number:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    num_comments_entry = ttk.Entry(generate_comments_frame, width=10)
    num_comments_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
    generate_comments_btn = ttk.Button(generate_comments_frame, text="Generate & Add")
    generate_comments_btn.grid(row=0, column=2, padx=5, pady=5, sticky="e")

    # --- Post Random Comment Frame ---
    post_frame = ttk.LabelFrame(interaction_tab, text=" Post Random Comment ", padding="10")
    post_frame.grid(row=1, column=0, pady=(15,0), padx=0, sticky="nsew")
    post_frame.columnconfigure(0, weight=1) # Make the random select frame expand

    random_select_frame = ttk.Frame(post_frame)
    random_select_frame.grid(row=0, column=0, columnspan=3, pady=5, sticky='ew')
    random_select_frame.columnconfigure(1, weight=1) # Text display expands
    pick_comment_btn = ttk.Button(random_select_frame, text="Pick Random Comment")
    pick_comment_btn.grid(row=0, column=0, padx=(5,10), pady=5)
    random_comment_display = scrolledtext.ScrolledText(random_select_frame, height=3, width=60, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1, font=('TkDefaultFont', 9), state=tk.DISABLED)
    random_comment_display.grid(row=0, column=1, sticky='ew', pady=5, padx=5)

    post_action_frame = ttk.Frame(post_frame)
    post_action_frame.grid(row=1, column=0, columnspan=3, pady=10, sticky='ew')
    ttk.Label(post_action_frame, text="Video ID:").pack(side=tk.LEFT, padx=(5, 5))
    video_id_entry = ttk.Entry(post_action_frame, width=20)
    video_id_entry.pack(side=tk.LEFT, padx=5)
    post_comment_btn = ttk.Button(post_action_frame, text="Post Selected Comment", state=tk.DISABLED)
    post_comment_btn.pack(side=tk.LEFT, padx=10)


    # --- Callbacks & Helpers ---
    def refresh_comment_template_listbox_local():
        comment_template_listbox.delete(0, tk.END)
        for template in comment_templates_list_ref:
            comment_template_listbox.insert(tk.END, template)
        log_func(f"Comments: Refreshed comment template listbox ({len(comment_templates_list_ref)} items).")

    def set_comment_manage_buttons_state_local(state=tk.NORMAL):
        add_comment_btn.config(state=state)
        delete_comment_btn.config(state=state)
        pick_comment_btn.config(state=state)
        generate_comments_btn.config(state=state)
        num_comments_entry.config(state=tk.NORMAL if state == tk.NORMAL else tk.DISABLED)

        post_is_enabled = state == tk.NORMAL and bool(current_random_comment_for_tab) and bool(video_id_entry.get().strip())
        post_comment_btn.config(state=tk.NORMAL if post_is_enabled else tk.DISABLED)

    def add_comment_template_local():
        new_template = new_comment_entry.get().strip()
        if not new_template: return
        if new_template in comment_templates_list_ref:
             messagebox.showwarning("Duplicate Entry", "This comment template already exists.")
             return
        comment_templates_list_ref.append(new_template)
        comment_template_listbox.insert(tk.END, new_template) # Add to UI
        new_comment_entry.delete(0, tk.END)
        log_func(f"Comments: Added comment template: '{new_template}'")
        save_comment_templates(comment_templates_list_ref, log_func)

    def delete_selected_comment_template_local():
        global current_random_comment_for_tab
        selected_indices = comment_template_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Select a comment template to delete.")
            return
        selected_index = selected_indices[0]
        template_to_delete = comment_template_listbox.get(selected_index)

        if messagebox.askyesno("Confirm Deletion", f"Delete this comment template?\n\n'{template_to_delete}'"):
            del comment_templates_list_ref[selected_index]
            comment_template_listbox.delete(selected_index) # Remove from UI
            log_func(f"Comments: Deleted comment template: '{template_to_delete}'")
            save_comment_templates(comment_templates_list_ref, log_func)
            if current_random_comment_for_tab == template_to_delete:
                pick_random_comment_local(force_clear=True)
            set_comment_manage_buttons_state_local(tk.NORMAL)


    def pick_random_comment_local(force_clear=False):
        global current_random_comment_for_tab
        if force_clear or not comment_templates_list_ref:
            current_random_comment_for_tab = ""
            display_text = "No comment templates available." if not comment_templates_list_ref else ""
            random_comment_display.config(state=tk.NORMAL)
            random_comment_display.delete("1.0", tk.END)
            random_comment_display.insert("1.0", display_text)
            random_comment_display.config(state=tk.DISABLED)
            if not comment_templates_list_ref and not force_clear:
                messagebox.showwarning("Empty List", "No comment templates to choose from.")
        else:
            current_random_comment_for_tab = random.choice(comment_templates_list_ref)
            random_comment_display.config(state=tk.NORMAL)
            random_comment_display.delete("1.0", tk.END)
            random_comment_display.insert("1.0", f"{current_random_comment_for_tab}")
            random_comment_display.config(state=tk.DISABLED)
            log_func(f"Comments: Randomly selected comment: '{current_random_comment_for_tab}'")
        set_comment_manage_buttons_state_local(tk.NORMAL)

    def post_comment_ui_local():
        video_id = video_id_entry.get().strip()
        comment_to_post = current_random_comment_for_tab
        if not video_id:
            messagebox.showwarning("Input Required", "Enter the Video ID.")
            return
        if not comment_to_post:
             messagebox.showwarning("No Comment Selected", "Click 'Pick Random Comment' first or ensure templates exist.")
             return

        confirm_msg = f"Post this comment:\n\n'{comment_to_post}'\n\nTo Video ID:\n{video_id}?"
        if messagebox.askyesno("Confirm Comment Post", confirm_msg):
            log_func(f"Comments: Starting background thread to post comment on Video ID: {video_id}")
            set_comment_manage_buttons_state_local(tk.DISABLED)
            if status_bar: status_bar.show_progress()

            def post_task():
                _, error = post_comment(video_id, comment_to_post, log_func=log_func)
                root_ref.after(0, set_comment_manage_buttons_state_local, tk.NORMAL)
                if status_bar:
                    root_ref.after(0, status_bar.hide_progress)
                    root_ref.after(0, status_bar.clear)
                if error:
                    root_ref.after(0, messagebox.showerror, "Comment Error", error)
                else:
                    root_ref.after(0, messagebox.showinfo, "Comment Posted", f"Successfully posted comment on Video ID: {video_id}")
            threading.Thread(target=post_task, daemon=True).start()

    def generate_meaningful_comments_local():
        try:
            num_str = num_comments_entry.get()
            if not num_str.isdigit():
                messagebox.showerror("Input Error", "Please enter a valid number for comments.")
                return
            num_to_generate = int(num_str)
            if num_to_generate <= 0:
                messagebox.showerror("Input Error", "Number of comments must be greater than 0.")
                return
            if num_to_generate > 5000:
                 if not messagebox.askyesno("Confirmation", f"Generating {num_to_generate:,} comments might take some time and could result in many similar templates if the base list is small. This will add to your existing templates. Proceed?"):
                    return
            elif not messagebox.askyesno("Confirm Generation", f"This will attempt to generate up to {num_to_generate} comment templates and add them to your list. Some may be duplicates if generated multiple times. Proceed?"):
                return
        except ValueError:
            messagebox.showerror("Input Error", "Invalid number entered.")
            return

        log_func(f"Comments: Generating up to {num_to_generate} comments...")
        if status_bar: status_bar.show_progress()
        set_comment_manage_buttons_state_local(tk.DISABLED)

        def generation_task():
            newly_generated_comments_set = set()
            existing_set = set(comment_templates_list_ref)
            generated_count, attempts, max_attempts = 0, 0, num_to_generate * 3

            while generated_count < num_to_generate and attempts < max_attempts:
                attempts += 1
                base_comment = random.choice(MEANINGFUL_COMMENT_BASES)
                comment_with_optional_emoji = base_comment
                if random.random() < 0.6 and not any(base_comment.endswith(e) for e in EMOJIS_LIST):
                    comment_with_optional_emoji += " " + random.choice(EMOJIS_LIST)
                final_comment = comment_with_optional_emoji
                if random.random() < 0.3 and not any(final_comment.endswith(s) for s in COMMENT_SUFFIXES):
                     final_comment += " " + random.choice(COMMENT_SUFFIXES)
                final_comment = final_comment.strip()[:490]
                if final_comment not in existing_set and final_comment not in newly_generated_comments_set:
                    newly_generated_comments_set.add(final_comment)
                    generated_count += 1

            added_to_main_list_count = 0
            if newly_generated_comments_set:
                for c_item in newly_generated_comments_set:
                    if c_item not in comment_templates_list_ref:
                        comment_templates_list_ref.append(c_item)
                        added_to_main_list_count +=1
                if added_to_main_list_count > 0:
                    save_comment_templates(comment_templates_list_ref, log_func)
                msg = f"{added_to_main_list_count} new comment templates added."
                log_func(f"Comments: {msg}")
                root_ref.after(0, messagebox.showinfo, "Success", msg)
            else:
                msg = "No new comments generated."
                log_func(f"Comments: {msg}")
                root_ref.after(0, messagebox.showinfo, "Info", msg)

            root_ref.after(0, refresh_comment_template_listbox_local)
            root_ref.after(0, lambda: num_comments_entry.delete(0, tk.END))
            if status_bar:
                root_ref.after(0, status_bar.hide_progress)
                root_ref.after(0, status_bar.clear)
            root_ref.after(0, set_comment_manage_buttons_state_local, tk.NORMAL)
        threading.Thread(target=generation_task, daemon=True).start()


    # Assign commands
    add_comment_btn.config(command=add_comment_template_local)
    delete_comment_btn.config(command=delete_selected_comment_template_local)
    pick_comment_btn.config(command=pick_random_comment_local)
    post_comment_btn.config(command=post_comment_ui_local)
    generate_comments_btn.config(command=generate_meaningful_comments_local)
    video_id_entry.bind("<KeyRelease>", lambda event: set_comment_manage_buttons_state_local(tk.NORMAL))


    # Initial population and setup
    refresh_comment_template_listbox_local()
    pick_random_comment_local(force_clear=True) # To set initial display
    set_comment_manage_buttons_state_local(tk.NORMAL) # Initial state of buttons

    # Add a method to the tab itself for external refresh
    interaction_tab.refresh_list = refresh_comment_template_listbox_local

    return interaction_tab