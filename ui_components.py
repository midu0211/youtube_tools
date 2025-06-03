# ui_components.py
import tkinter as tk
from tkinter import ttk

class StatusBar(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.label = ttk.Label(self, text="Ready", anchor=tk.W, padding=(5, 2))
        self.label.pack(fill=tk.X, expand=True, side=tk.LEFT)
        self.progress = ttk.Progressbar(self, orient=tk.HORIZONTAL, length=150, mode='indeterminate')

    def set_text(self, text):
        if self.winfo_exists(): # Check if widget exists before configuring
            self.label.config(text=text)

    def clear(self):
        self.set_text("Ready")

    def show_progress(self):
        if self.winfo_exists():
            self.progress.pack(side=tk.RIGHT, padx=5, pady=2)
            self.progress.start(20)

    def hide_progress(self):
        if self.winfo_exists():
            self.progress.stop()
            self.progress.pack_forget()