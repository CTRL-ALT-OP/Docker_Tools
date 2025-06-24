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
        """Safely append text to output window with race condition protection"""
        if not self.is_created or not self.text_area:
            return

        def update_text():
            try:
                # Double-check window still exists before updating
                if not (
                    self.window
                    and self.window.winfo_exists()
                    and self.text_area
                    and self.text_area.winfo_exists()
                ):
                    return

                self.text_area.config(state=tk.NORMAL)
                self.text_area.insert(tk.END, text)
                self.text_area.see(tk.END)
                self.text_area.config(state=tk.DISABLED)

            except tk.TclError:
                # Widget was destroyed - ignore silently
                pass
            except Exception as e:
                # Log unexpected errors but don't crash
                print(f"Unexpected error updating text area: {e}")

        try:
            if self.window:
                self.window.after(0, update_text)
        except tk.TclError:
            # Window was destroyed - ignore silently
            pass

    def update_status(self, status_text: str, color: str = None):
        """Update status label with race condition protection"""
        if color is None:
            color = COLORS["warning"]

        if not self.is_created or not self.status_label:
            return

        def update_label():
            try:
                # Double-check window and label still exist
                if not (
                    self.window
                    and self.window.winfo_exists()
                    and self.status_label
                    and self.status_label.winfo_exists()
                ):
                    return

                self.status_label.config(text=f"Status: {status_text}", fg=color)

            except tk.TclError:
                # Widget was destroyed - ignore silently
                pass
            except Exception as e:
                # Log unexpected errors but don't crash
                print(f"Unexpected error updating status label: {e}")

        try:
            if self.window:
                self.window.after(0, update_label)
        except tk.TclError:
            # Window was destroyed - ignore silently
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
        git_service=None,
        project_path=None,
    ):
        self.parent_window = parent_window
        self.project_name = project_name
        self.commits = commits
        self.on_checkout_callback = on_checkout_callback
        self.git_service = git_service
        self.project_path = project_path

        self.window = None
        self.commit_listbox = None
        self.status_label = None
        self.checkout_btn = None

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
        if "No remote repository" in fetch_message:
            status_text = f"Showing local commits ({len(self.commits)} total) - no remote configured"
        elif fetch_success:
            status_text = f"Showing all commits ({len(self.commits)} total)"
        else:
            status_text = "Showing local commits only"

        self.status_label = GuiUtils.create_styled_label(
            main_frame,
            text=status_text,
            font_key="info",
            bg=COLORS["terminal_bg"],
            fg=COLORS["muted"],
        )
        self.status_label.pack(pady=(0, 5))

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
        self.populate_commits()

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

        self.checkout_btn = GuiUtils.create_styled_button(
            buttons_frame,
            text="Checkout Selected",
            command=checkout_selected,
            style="git",
            font=FONTS["button_large"],
            padx=20,
            pady=5,
        )
        self.checkout_btn.pack(side="left", padx=(0, 10))

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

    def populate_commits(self):
        """Populate the listbox with current commits"""
        self.commit_listbox.delete(0, tk.END)
        for commit in self.commits:
            display_text = (
                commit.display
                if hasattr(commit, "display")
                else commit.get("display", str(commit))
            )
            self.commit_listbox.insert(tk.END, display_text)

    def create_window_with_loading(self, fetch_success: bool, fetch_message: str):
        """Create the git commit window with loading state"""
        self.create_window(fetch_success, fetch_message)

        # Show loading state
        self.status_label.config(
            text="Loading commits... (this may take a moment for large repositories)"
        )
        self.checkout_btn.config(state="disabled")

        # Add loading message to listbox
        self.commit_listbox.delete(0, tk.END)
        self.commit_listbox.insert(tk.END, "Loading commits...")
        self.commit_listbox.config(state="disabled")

    def update_status(self, status_text: str, color: str = None):
        """Update the status label with real-time progress"""
        if self.status_label and self.window:
            try:
                if self.window.winfo_exists():
                    self.status_label.config(text=status_text)
                    if color:
                        self.status_label.config(fg=color)
            except tk.TclError:
                # Window was destroyed - ignore silently
                pass

    def update_with_commits(self, commits):
        """Update window with loaded commits"""
        self.commits = commits
        self.commit_listbox.config(state="normal")
        self.populate_commits()
        self.status_label.config(text=f"Showing all commits ({len(commits)} total)")
        self.checkout_btn.config(state="normal")

    def update_with_error(self, error_message):
        """Update window with error state"""
        self.commit_listbox.config(state="normal")
        self.commit_listbox.delete(0, tk.END)
        self.commit_listbox.insert(tk.END, f"Error: {error_message}")
        self.status_label.config(text="Error loading commits")
        self.checkout_btn.config(state="disabled")

    def update_with_no_commits(self):
        """Update window when no commits found"""
        self.commit_listbox.config(state="normal")
        self.commit_listbox.delete(0, tk.END)
        self.commit_listbox.insert(tk.END, "No commits found")
        self.status_label.config(text="No commits found in this repository")
        self.checkout_btn.config(state="disabled")

    def destroy(self):
        """Destroy the window"""
        if self.window:
            self.window.destroy()


class GitCheckoutAllWindow:
    """Window for displaying git commits and allowing checkout to all project versions"""

    def __init__(
        self,
        parent_window: tk.Tk,
        project_group_name: str,
        commits: List,
        on_checkout_all_callback: Callable[[str], None],
        git_service=None,
        project_group=None,
        all_versions=None,
    ):
        self.parent_window = parent_window
        self.project_group_name = project_group_name
        self.commits = commits
        self.on_checkout_all_callback = on_checkout_all_callback
        self.git_service = git_service
        self.project_group = project_group
        self.all_versions = all_versions or []

        self.window = None
        self.commit_listbox = None
        self.status_label = None
        self.checkout_all_btn = None
        self.versions_info_label = None

    def create_window(self, fetch_success: bool, fetch_message: str):
        """Create the git checkout all window"""
        self.window = tk.Toplevel(self.parent_window)
        self.window.title(f"Git Checkout All - {self.project_group_name}")
        self.window.geometry("1000x700")  # Larger window for more information
        self.window.configure(bg=COLORS["terminal_bg"])

        # Main frame
        main_frame = GuiUtils.create_styled_frame(self.window, bg_color="terminal_bg")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        title_label = GuiUtils.create_styled_label(
            main_frame,
            text=f"Git Checkout All - {self.project_group_name}",
            font_key="header",
            bg=COLORS["terminal_bg"],
            fg=COLORS["terminal_text"],
        )
        title_label.pack(pady=(0, 10))

        # Versions info
        versions_count = len(self.all_versions)
        version_names = [f"{v.parent}/{v.name}" for v in self.all_versions]
        versions_text = ", ".join(version_names[:5])
        if len(version_names) > 5:
            versions_text += f" (and {len(version_names) - 5} more)"

        self.versions_info_label = GuiUtils.create_styled_label(
            main_frame,
            text=f"Will checkout to {versions_count} versions: {versions_text}",
            font_key="info",
            bg=COLORS["terminal_bg"],
            fg=COLORS["info"],
        )
        self.versions_info_label.pack(pady=(0, 5))

        # Status message
        if "No remote repository" in fetch_message:
            status_text = f"Showing local commits ({len(self.commits)} total) - no remote configured"
        elif fetch_success:
            status_text = f"Showing all commits ({len(self.commits)} total)"
        else:
            status_text = "Showing local commits only"

        self.status_label = GuiUtils.create_styled_label(
            main_frame,
            text=status_text,
            font_key="info",
            bg=COLORS["terminal_bg"],
            fg=COLORS["muted"],
        )
        self.status_label.pack(pady=(0, 5))

        # Instructions
        info_label = GuiUtils.create_styled_label(
            main_frame,
            text="⚠️  Select a commit and click 'Checkout All Versions' to checkout ALL project versions to that commit",
            font_key="button",
            bg=COLORS["terminal_bg"],
            fg="#e67e22",  # Orange warning color
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
        self.populate_commits()

        # Handle double-click on commit
        def on_commit_select(event):
            selection = self.commit_listbox.curselection()
            if selection:
                self.checkout_all_selected()

        self.commit_listbox.bind("<Double-1>", on_commit_select)

        # Buttons frame
        buttons_frame = GuiUtils.create_styled_frame(main_frame, bg_color="terminal_bg")
        buttons_frame.pack(pady=(10, 0))

        # Checkout All button
        self.checkout_all_btn = GuiUtils.create_styled_button(
            buttons_frame,
            text=f"🔀 Checkout All {versions_count} Versions",
            command=self.checkout_all_selected,
            style="git",
            font=FONTS["button_large"],
            padx=20,
            pady=5,
        )
        self.checkout_all_btn.pack(side="left", padx=(0, 10))

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
        GuiUtils.center_window(self.window, 1000, 700)

    def checkout_all_selected(self):
        """Handle checkout all for selected commit"""
        selection = self.commit_listbox.curselection()
        if selection:
            index = selection[0]
            selected_commit = self.commits[index]
            commit_hash = (
                selected_commit.hash
                if hasattr(selected_commit, "hash")
                else selected_commit.get("hash")
            )
            self.on_checkout_all_callback(commit_hash)
        else:
            messagebox.showwarning(
                "No Selection", "Please select a commit to checkout all versions to"
            )

    def populate_commits(self):
        """Populate the listbox with current commits"""
        self.commit_listbox.delete(0, tk.END)
        for commit in self.commits:
            display_text = (
                commit.display
                if hasattr(commit, "display")
                else commit.get("display", str(commit))
            )
            self.commit_listbox.insert(tk.END, display_text)

    def create_window_with_loading(self, fetch_success: bool, fetch_message: str):
        """Create the git checkout all window with loading state"""
        self.create_window(fetch_success, fetch_message)

        # Show loading state
        self.status_label.config(
            text="Loading commits... (this may take a moment for large repositories)"
        )
        self.checkout_all_btn.config(state="disabled")

        # Add loading message to listbox
        self.commit_listbox.delete(0, tk.END)
        self.commit_listbox.insert(tk.END, "Loading commits...")
        self.commit_listbox.config(state="disabled")

    def update_status(self, status_text: str, color: str = None):
        """Update the status label with real-time progress"""
        if self.status_label and self.window:
            try:
                if self.window.winfo_exists():
                    self.status_label.config(text=status_text)
                    if color:
                        self.status_label.config(fg=color)
                    self.window.update_idletasks()
            except tk.TclError:
                # Window was destroyed
                pass

    def update_with_commits(self, commits):
        """Update the window with loaded commits"""
        self.commits = commits
        if self.commit_listbox and self.window:
            try:
                if self.window.winfo_exists():
                    self.commit_listbox.config(state="normal")
                    self.populate_commits()
                    self.checkout_all_btn.config(state="normal")
                    self.window.update_idletasks()
            except tk.TclError:
                # Window was destroyed
                pass

    def update_with_error(self, error_message):
        """Update the window with an error message"""
        if self.commit_listbox and self.window:
            try:
                if self.window.winfo_exists():
                    self.commit_listbox.delete(0, tk.END)
                    self.commit_listbox.insert(tk.END, f"Error: {error_message}")
                    self.checkout_all_btn.config(state="disabled")
                    self.status_label.config(
                        text="Failed to load commits", fg=COLORS["error"]
                    )
                    self.window.update_idletasks()
            except tk.TclError:
                # Window was destroyed
                pass

    def update_with_no_commits(self):
        """Update the window when no commits are found"""
        if self.commit_listbox and self.window:
            try:
                if self.window.winfo_exists():
                    self.commit_listbox.delete(0, tk.END)
                    self.commit_listbox.insert(tk.END, "No commits found in repository")
                    self.checkout_all_btn.config(state="disabled")
                    self.status_label.config(
                        text="No commits available", fg=COLORS["muted"]
                    )
                    self.window.update_idletasks()
            except tk.TclError:
                # Window was destroyed
                pass

    def destroy(self):
        """Destroy the git checkout all window"""
        if self.window:
            self.window.destroy()


class AddProjectWindow:
    """A popup window for adding new projects by cloning from GitHub"""

    def __init__(
        self, parent_window: tk.Tk, on_add_callback: Callable[[str, str], None]
    ):
        self.parent_window = parent_window
        self.on_add_callback = on_add_callback
        self.window = None
        self.repo_url_entry = None
        self.project_name_entry = None
        self._last_auto_filled_name = ""

    def create_window(self):
        """Create the add project window"""
        if self.window:
            return

        self.window = tk.Toplevel(self.parent_window)
        self.window.title("Add New Project")
        self.window.geometry("500x300")
        self.window.configure(bg=COLORS["background"])

        # Make window modal and center it
        self.window.transient(self.parent_window)
        self.window.grab_set()
        GuiUtils.center_window(self.window, 500, 300)

        # Create main frame
        main_frame = GuiUtils.create_styled_frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        title_label = GuiUtils.create_styled_label(
            main_frame,
            text="Add New Project from GitHub",
            font_key="header",
            fg=COLORS["project_header"],
        )
        title_label.pack(pady=(0, 20))

        # Repository URL input
        repo_frame = GuiUtils.create_styled_frame(main_frame)
        repo_frame.pack(fill="x", pady=(0, 15))

        repo_label = GuiUtils.create_styled_label(
            repo_frame, text="GitHub Repository URL:", font_key="info"
        )
        repo_label.pack(anchor="w")

        self.repo_url_entry = tk.Entry(
            repo_frame, font=FONTS["info"], width=60, relief="solid", bd=1
        )
        self.repo_url_entry.pack(fill="x", pady=(5, 0))
        self.repo_url_entry.insert(0, "https://github.com/user/repository.git")
        self.repo_url_entry.focus()

        # Project name input
        name_frame = GuiUtils.create_styled_frame(main_frame)
        name_frame.pack(fill="x", pady=(0, 20))

        name_label = GuiUtils.create_styled_label(
            name_frame, text="Project Name:", font_key="info"
        )
        name_label.pack(anchor="w")

        self.project_name_entry = tk.Entry(
            name_frame, font=FONTS["info"], width=60, relief="solid", bd=1
        )
        self.project_name_entry.pack(fill="x", pady=(5, 0))

        # Auto-fill project name when URL changes
        self.repo_url_entry.bind("<KeyRelease>", self._auto_fill_project_name)

        # Instructions
        instructions = GuiUtils.create_styled_label(
            main_frame,
            text="This will clone the repository into all project subdirectories\n(pre-edit, post-edit, post-edit2, correct-edit)",
            font_key="info",
            fg=COLORS["muted"],
        )
        instructions.pack(pady=(0, 20))

        # Buttons frame
        buttons_frame = GuiUtils.create_styled_frame(main_frame)
        buttons_frame.pack(fill="x")

        # Cancel button
        cancel_btn = GuiUtils.create_styled_button(
            buttons_frame,
            text="Cancel",
            command=self._cancel,
            style="close",
            font=FONTS["button_large"],
            padx=20,
            pady=5,
        )
        cancel_btn.pack(side="right", padx=(10, 0))

        # Add button
        add_btn = GuiUtils.create_styled_button(
            buttons_frame,
            text="Add Project",
            command=self._add_project,
            style="git",
            font=FONTS["button_large"],
            padx=20,
            pady=5,
        )
        add_btn.pack(side="right")

        # Bind Enter key to add project
        self.window.bind("<Return>", lambda e: self._add_project())
        self.window.bind("<Escape>", lambda e: self._cancel())

    def _auto_fill_project_name(self, event=None):
        """Auto-fill project name based on repository URL"""
        url = self.repo_url_entry.get().strip()

        if url and "/" in url:
            # Extract project name from URL
            project_name = url.split("/")[-1]
            if project_name.endswith(".git"):
                project_name = project_name[:-4]

            # Clean up project name
            project_name = project_name.replace("_", "-").lower()

            # Update project name entry if it's empty or contains default text
            current_name = self.project_name_entry.get().strip()
            if not current_name or current_name == self._last_auto_filled_name:
                self.project_name_entry.delete(0, tk.END)
                self.project_name_entry.insert(0, project_name)
                self._last_auto_filled_name = project_name

    def _add_project(self):
        """Handle add project button click"""
        repo_url = self.repo_url_entry.get().strip()
        project_name = self.project_name_entry.get().strip()

        # Validate inputs
        if not repo_url:
            messagebox.showerror("Error", "Please enter a repository URL")
            return

        if not project_name:
            messagebox.showerror("Error", "Please enter a project name")
            return

        # Basic URL validation
        if not (repo_url.startswith("https://") or repo_url.startswith("git@")):
            messagebox.showerror("Error", "Please enter a valid Git repository URL")
            return

        # Call the callback function
        self.on_add_callback(repo_url, project_name)
        self.destroy()

    def _cancel(self):
        """Handle cancel button click"""
        self.destroy()

    def destroy(self):
        """Clean up and destroy the window"""
        if self.window:
            self.window.destroy()
            self.window = None
