"""
Popup window modules for displaying terminal output and other information
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from typing import Optional, Callable, Dict, Any, List
from pathlib import Path

from config.settings import COLORS, FONTS, OUTPUT_WINDOW_SIZE, GIT_WINDOW_SIZE
from gui.gui_utils import GuiUtils


class TerminalOutputWindow:
    """A reusable terminal output window with real-time updates"""

    def __init__(
        self, parent_window: tk.Tk, title: str, size: str = OUTPUT_WINDOW_SIZE
    ):
        self.parent_window = parent_window
        self.window = None
        self.text_area = None
        self.status_label = None
        self.title_label = None
        self.buttons_frame = None

        self.title = title
        self.size = size
        self.is_created = False

    def create_window(self):
        """Create the terminal output window"""
        if self.is_created:
            return

        self.window = tk.Toplevel(self.parent_window)
        self.window.title(self.title)
        self.window.geometry(self.size)
        self.window.configure(bg=COLORS["terminal_bg"])

        # Create frame for the content
        main_frame = GuiUtils.create_styled_frame(self.window, bg_color="terminal_bg")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title label
        self.title_label = GuiUtils.create_styled_label(
            main_frame,
            text=self.title,
            font_key="console_title",
            bg=COLORS["terminal_bg"],
            fg=COLORS["terminal_text"],
        )
        self.title_label.pack(pady=(0, 10))

        # Status label (will be updated during process)
        self.status_label = GuiUtils.create_styled_label(
            main_frame,
            text="Status: Initializing...",
            font_key="console_status",
            bg=COLORS["terminal_bg"],
            fg=COLORS["warning"],
        )
        self.status_label.pack(pady=(0, 10))

        # Output text area
        self.text_area = GuiUtils.create_console_text_area(main_frame)
        self.text_area.pack(fill=tk.BOTH, expand=True)

        # Make window modal and center it
        self.window.transient(self.parent_window)
        self.window.grab_set()

        # Center the window
        GuiUtils.center_window(self.window, *[int(x) for x in self.size.split("x")])

        self.is_created = True

    def append_output(self, text: str):
        """Safely append text to output window"""
        if self.text_area and self.window and self.window.winfo_exists():

            def update_text():
                self.text_area.config(state=tk.NORMAL)
                self.text_area.insert(tk.END, text)
                self.text_area.see(tk.END)
                self.text_area.config(state=tk.DISABLED)
                self.text_area.update()

            try:
                self.window.after(0, update_text)
            except:
                pass

    def update_status(self, status_text: str, color: str = None):
        """Update status label"""
        if color is None:
            color = COLORS["warning"]

        if self.status_label and self.window and self.window.winfo_exists():

            def update_label():
                self.status_label.config(text=f"Status: {status_text}", fg=color)

            try:
                self.window.after(0, update_label)
            except:
                pass

    def add_final_buttons(
        self,
        copy_text: Optional[str] = None,
        additional_buttons: Optional[List[Dict]] = None,
    ):
        """Add final buttons to the window"""
        if not (self.window and self.window.winfo_exists()):
            return

        def add_buttons():
            # Find the main frame (first child)
            main_frame = list(self.window.children.values())[0]

            self.buttons_frame = GuiUtils.create_styled_frame(
                main_frame, bg_color="terminal_bg"
            )
            self.buttons_frame.pack(pady=(10, 0))

            # Copy button if copy_text provided
            if copy_text:

                def copy_output():
                    try:
                        self.window.clipboard_clear()
                        self.window.clipboard_append(copy_text)
                        copy_btn.config(text="Copied!", bg=COLORS["success"])
                        self.window.after(
                            2000,
                            lambda: copy_btn.config(
                                text="Copy Test Output", bg=COLORS["secondary"]
                            ),
                        )
                    except Exception as e:
                        messagebox.showerror(
                            "Copy Error", f"Failed to copy to clipboard: {str(e)}"
                        )

                copy_btn = GuiUtils.create_styled_button(
                    self.buttons_frame,
                    text="Copy Test Output",
                    command=copy_output,
                    style="copy",
                    font=FONTS["button_large"],
                    padx=20,
                    pady=5,
                )
                copy_btn.pack(side="left", padx=(0, 10))

            # Additional buttons
            if additional_buttons:
                for btn_config in additional_buttons:
                    btn = GuiUtils.create_styled_button(
                        self.buttons_frame, **btn_config
                    )
                    btn.pack(side="left", padx=(0, 10))

            # Close button
            close_btn = GuiUtils.create_styled_button(
                self.buttons_frame,
                text="Close",
                command=self.window.destroy,
                style="close",
                font=FONTS["button_large"],
                padx=20,
                pady=5,
            )
            close_btn.pack(side="right")

        self.window.after(0, add_buttons)

    def destroy(self):
        """Destroy the window"""
        if self.window:
            self.window.destroy()


class GitCommitWindow:
    """Window for displaying git commits and allowing checkout"""

    def __init__(
        self,
        parent_window: tk.Tk,
        project_name: str,
        commits: List,
        on_checkout_callback: Callable[[str], None],
    ):
        self.parent_window = parent_window
        self.project_name = project_name
        self.commits = commits
        self.on_checkout_callback = on_checkout_callback

        self.window = None
        self.commit_listbox = None

    def create_window(self, fetch_success: bool, fetch_message: str):
        """Create the git commit window"""
        self.window = tk.Toplevel(self.parent_window)
        self.window.title(f"Git Commits - {self.project_name}")
        self.window.geometry(GIT_WINDOW_SIZE)
        self.window.configure(bg=COLORS["terminal_bg"])

        # Main frame
        main_frame = GuiUtils.create_styled_frame(self.window, bg_color="terminal_bg")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        title_label = GuiUtils.create_styled_label(
            main_frame,
            text=f"Git Commits - {self.project_name}",
            font_key="header",
            bg=COLORS["terminal_bg"],
            fg=COLORS["terminal_text"],
        )
        title_label.pack(pady=(0, 10))

        # Status message
        status_text = (
            "Showing latest commits (fetched from remote)"
            if fetch_success
            else "Showing local commits only"
        )
        if "No remote repository" in fetch_message:
            status_text = "Showing local commits (no remote configured)"

        status_label = GuiUtils.create_styled_label(
            main_frame,
            text=status_text,
            font_key="info",
            bg=COLORS["terminal_bg"],
            fg=COLORS["muted"],
        )
        status_label.pack(pady=(0, 5))

        # Instructions
        info_label = GuiUtils.create_styled_label(
            main_frame,
            text="Double-click on a commit to checkout to that version",
            font_key="button",
            bg=COLORS["terminal_bg"],
            fg="#bdc3c7",
        )
        info_label.pack(pady=(0, 10))

        # Create frame for listbox and scrollbar
        list_frame = GuiUtils.create_styled_frame(main_frame, bg_color="terminal_bg")
        list_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbar
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Listbox for commits
        self.commit_listbox = tk.Listbox(
            list_frame,
            font=FONTS["mono"],
            bg=COLORS["secondary"],
            fg=COLORS["terminal_text"],
            selectbackground=COLORS["info"],
            selectforeground=COLORS["terminal_text"],
            yscrollcommand=scrollbar.set,
            activestyle="none",
        )
        self.commit_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.commit_listbox.yview)

        # Populate listbox
        for commit in self.commits:
            display_text = (
                commit.display
                if hasattr(commit, "display")
                else commit.get("display", str(commit))
            )
            self.commit_listbox.insert(tk.END, display_text)

        # Handle double-click on commit
        def on_commit_select(event):
            selection = self.commit_listbox.curselection()
            if selection:
                index = selection[0]
                selected_commit = self.commits[index]
                commit_hash = (
                    selected_commit.hash
                    if hasattr(selected_commit, "hash")
                    else selected_commit.get("hash")
                )
                self.on_checkout_callback(commit_hash)

        self.commit_listbox.bind("<Double-1>", on_commit_select)

        # Buttons frame
        buttons_frame = GuiUtils.create_styled_frame(main_frame, bg_color="terminal_bg")
        buttons_frame.pack(pady=(10, 0))

        # Checkout button
        def checkout_selected():
            selection = self.commit_listbox.curselection()
            if selection:
                index = selection[0]
                selected_commit = self.commits[index]
                commit_hash = (
                    selected_commit.hash
                    if hasattr(selected_commit, "hash")
                    else selected_commit.get("hash")
                )
                self.on_checkout_callback(commit_hash)
            else:
                messagebox.showwarning(
                    "No Selection", "Please select a commit to checkout"
                )

        checkout_btn = GuiUtils.create_styled_button(
            buttons_frame,
            text="Checkout Selected",
            command=checkout_selected,
            style="git",
            font=FONTS["button_large"],
            padx=20,
            pady=5,
        )
        checkout_btn.pack(side="left", padx=(0, 10))

        # Close button
        close_btn = GuiUtils.create_styled_button(
            buttons_frame,
            text="Close",
            command=self.window.destroy,
            style="close",
            font=FONTS["button_large"],
            padx=20,
            pady=5,
        )
        close_btn.pack(side="right")

        # Make window modal and center it
        self.window.transient(self.parent_window)
        self.window.grab_set()

        # Center the window
        GuiUtils.center_window(
            self.window, *[int(x) for x in GIT_WINDOW_SIZE.split("x")]
        )

    def destroy(self):
        """Destroy the window"""
        if self.window:
            self.window.destroy()
