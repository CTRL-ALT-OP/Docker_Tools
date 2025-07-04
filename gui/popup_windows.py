"""
Popup window modules for displaying terminal output and other information
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from typing import Optional, Callable, Dict, Any, List
from pathlib import Path

from config.settings import COLORS, FONTS, OUTPUT_WINDOW_SIZE, GIT_WINDOW_SIZE
from gui.gui_utils import GuiUtils
from services.project_group_service import ProjectGroup


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


class EditRunTestsWindow:
    """Window for editing run_tests.sh file by selecting test files"""

    def __init__(
        self,
        parent_window: tk.Tk,
        project_group: ProjectGroup,
        on_save_callback: Callable[[ProjectGroup, List[str]], None],
    ):
        self.parent_window = parent_window
        self.project_group = project_group
        self.on_save_callback = on_save_callback
        self.window = None
        self.test_checkboxes = {}
        self.test_vars = {}
        self.all_test_files = []
        self.current_pytest_command = ""
        self.canvas = None  # Keep reference to canvas for proper cleanup
        self.detected_language = None

    def create_window(self):
        """Create the edit run_tests.sh window"""
        self.window = tk.Toplevel(self.parent_window)
        self.window.title(f"Edit run_tests.sh - {self.project_group.name}")
        self.window.geometry("600x550")
        self.window.configure(bg=COLORS["background"])

        # Create frame for the content
        main_frame = GuiUtils.create_styled_frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        title_label = GuiUtils.create_styled_label(
            main_frame,
            text=f"Edit run_tests.sh for {self.project_group.name}",
            font_key="title",
            color_key="project_header",
        )
        title_label.pack(pady=(0, 20))

        # Language detection
        self._detect_language()

        # Current command info
        info_frame = GuiUtils.create_styled_frame(
            main_frame, bg_color="white", relief="raised", bd=1
        )
        info_frame.pack(fill="x", pady=(0, 20))

        language_info = f"Language: {self.detected_language.title()}"
        info_label = GuiUtils.create_styled_label(
            info_frame,
            text=f"{language_info}\nSelect test files to run. Paths will use forward slashes for cross-platform compatibility.",
            font_key="info",
            color_key="muted",
            bg=COLORS["white"],
        )
        info_label.pack(pady=10)

        # Test files selection frame
        selection_frame = GuiUtils.create_styled_frame(main_frame)
        selection_frame.pack(fill="both", expand=True, pady=(0, 20))

        # Test files label
        test_label = GuiUtils.create_styled_label(
            selection_frame,
            text="Select test files to include:",
            font_key="header",
        )
        test_label.pack(anchor="w", pady=(0, 10))

        # Scrollable frame for test files
        self.canvas, scrollable_frame, scrollbar = GuiUtils.create_scrollable_frame(
            selection_frame
        )

        # Load test files and create checkboxes
        self._load_test_files()
        self._create_test_checkboxes(scrollable_frame)

        # Buttons frame
        buttons_frame = GuiUtils.create_styled_frame(main_frame)
        buttons_frame.pack(fill="x", pady=(10, 0))

        # Select All button
        select_all_btn = GuiUtils.create_styled_button(
            buttons_frame,
            text="Select All",
            command=self._select_all_tests,
            style="secondary",
        )
        select_all_btn.pack(side="left", padx=(0, 10))

        # Deselect All button
        deselect_all_btn = GuiUtils.create_styled_button(
            buttons_frame,
            text="Deselect All",
            command=self._deselect_all_tests,
            style="secondary",
        )
        deselect_all_btn.pack(side="left", padx=(0, 10))

        # Save button
        save_btn = GuiUtils.create_styled_button(
            buttons_frame,
            text="💾 Save Changes",
            command=self._save_changes,
            style="save",
        )
        save_btn.pack(side="right", padx=(10, 0))

        # Cancel button
        cancel_btn = GuiUtils.create_styled_button(
            buttons_frame,
            text="❌ Cancel",
            command=self._cancel,
            style="cancel",
        )
        cancel_btn.pack(side="right")

        # Make window modal and center it
        self.window.transient(self.parent_window)
        self.window.grab_set()
        GuiUtils.center_window(self.window, 600, 550)

    def _detect_language(self):
        """Detect the programming language of the project"""
        from utils.language_detection import detect_project_language_sync

        # Get pre-edit version (source of truth for language detection)
        pre_edit_version = self._get_pre_edit_version()
        if not pre_edit_version:
            self.detected_language = "python"  # Default fallback
            return

        # Use the generalized language detection utility
        self.detected_language = detect_project_language_sync(pre_edit_version.path)

    def _get_pre_edit_version(self):
        """Get the pre-edit version of the project"""
        for version in self.project_group.get_all_versions():
            if "pre-edit" in version.parent.lower():
                return version

        # If no pre-edit version, use the first version
        versions = self.project_group.get_all_versions()
        return versions[0] if versions else None

    def _get_test_file_patterns(self):
        """Get test file patterns based on the detected language"""
        from config.commands import TEST_FILE_PATTERNS

        return TEST_FILE_PATTERNS.get(
            self.detected_language, [("test_*.py", "*_test.py")]
        )

    def _get_test_directories(self):
        """Get test directories based on the detected language"""
        from config.commands import TEST_DIRECTORIES

        return TEST_DIRECTORIES.get(self.detected_language, ["tests/"])

    def _load_test_files(self):
        """Load test files from the appropriate directories based on language"""
        self.all_test_files = []

        pre_edit_version = self._get_pre_edit_version()
        if not pre_edit_version:
            return

        test_patterns = self._get_test_file_patterns()
        test_directories = self._get_test_directories()

        # Search for test files in language-specific directories
        for test_dir in test_directories:
            dir_path = pre_edit_version.path / test_dir.rstrip("/")
            if dir_path.exists() and dir_path.is_dir():
                for pattern_group in test_patterns:
                    for pattern in pattern_group:
                        for test_file in dir_path.rglob(pattern):
                            if test_file.is_file():
                                rel_path = test_file.relative_to(pre_edit_version.path)
                                # Normalize to forward slashes
                                normalized_path = str(rel_path).replace("\\", "/")
                                if normalized_path not in self.all_test_files:
                                    self.all_test_files.append(normalized_path)

        # Sort the test files for consistent display
        self.all_test_files.sort()

    def _get_currently_selected_tests(self):
        """Parse current run_tests.sh to determine which tests are currently selected"""
        currently_selected = set()

        pre_edit_version = self._get_pre_edit_version()
        if not pre_edit_version:
            return currently_selected

        run_tests_path = pre_edit_version.path / "run_tests.sh"
        if not run_tests_path.exists():
            return currently_selected

        try:
            content = run_tests_path.read_text()

            # Language-specific parsing
            if self.detected_language == "python":
                currently_selected = self._parse_python_tests(content)
            elif self.detected_language in ["javascript", "typescript"]:
                currently_selected = self._parse_npm_tests(content)
            elif self.detected_language == "java":
                currently_selected = self._parse_maven_tests(content)
            elif self.detected_language == "rust":
                currently_selected = self._parse_cargo_tests(content)
            elif self.detected_language in ["c", "cpp"]:
                currently_selected = self._parse_cmake_tests(content)
            elif self.detected_language == "csharp":
                currently_selected = self._parse_dotnet_tests(content)
            elif self.detected_language == "go":
                currently_selected = self._parse_go_tests(content)
            else:
                # Default to python-style parsing
                currently_selected = self._parse_python_tests(content)

        except Exception as e:
            # If we can't parse the file, just return empty set
            print(f"Warning: Could not parse run_tests.sh: {e}")

        return currently_selected

    def _parse_python_tests(self, content):
        """Parse Python pytest commands"""
        currently_selected = set()

        for line in content.split("\n"):
            stripped_line = line.strip()
            if "pytest" in stripped_line and not stripped_line.startswith("#"):
                # Find where pytest starts
                pytest_index = stripped_line.find("pytest")
                pytest_part = stripped_line[pytest_index:]

                # Split to get the parts
                parts = pytest_part.split()

                # Look for test paths
                for part in parts[1:]:  # Skip "pytest" itself
                    normalized_part = part.replace("\\", "/")
                    if normalized_part == "tests/" or normalized_part == "tests":
                        # If it's just "tests/" then all tests are selected
                        currently_selected.update(self.all_test_files)
                        break
                    elif normalized_part.startswith("tests/"):
                        # Remove any test method specifications (::MethodName)
                        clean_path = normalized_part.split("::")[0]
                        if clean_path.endswith(".py"):
                            currently_selected.add(clean_path)

        return currently_selected

    def _parse_npm_tests(self, content):
        """Parse npm test commands for JavaScript/TypeScript"""
        currently_selected = set()

        # For npm test, we need to check if there are specific test files mentioned
        # This is tricky because npm test usually runs all tests by default
        # We'll look for patterns like "npm test path/to/test.js"
        for line in content.split("\n"):
            stripped_line = line.strip()
            if "npm test" in stripped_line and not stripped_line.startswith("#"):
                # Split the line to look for test file arguments
                parts = stripped_line.split()
                npm_test_index = -1
                for i, part in enumerate(parts):
                    if part == "test" and i > 0 and parts[i - 1] == "npm":
                        npm_test_index = i
                        break

                if npm_test_index >= 0:
                    # Look for test file paths after "npm test"
                    for part in parts[npm_test_index + 1 :]:
                        normalized_part = part.replace("\\", "/")
                        # Check if it's a test file
                        if any(
                            normalized_part.endswith(ext)
                            for ext in [".js", ".ts", ".jsx", ".tsx"]
                        ):
                            if normalized_part in self.all_test_files:
                                currently_selected.add(normalized_part)

        # If no specific tests found, assume all tests are selected
        if not currently_selected:
            currently_selected.update(self.all_test_files)

        return currently_selected

    def _parse_maven_tests(self, content):
        """Parse Maven test commands for Java"""
        currently_selected = set()

        for line in content.split("\n"):
            stripped_line = line.strip()
            if (
                "mvn" in stripped_line
                and "test" in stripped_line
                and not stripped_line.startswith("#")
            ):
                # Maven typically runs all tests unless specific test classes are mentioned
                # Look for -Dtest=TestClassName patterns
                if "-Dtest=" in stripped_line:
                    # Extract test class names
                    test_part = stripped_line.split("-Dtest=")[1].split()[0]
                    # Convert class names to file paths
                    for test_file in self.all_test_files:
                        if test_part in test_file:
                            currently_selected.add(test_file)
                else:
                    # If no specific test mentioned, all tests are selected
                    currently_selected.update(self.all_test_files)

        # If no test command found, assume all tests are selected
        if not currently_selected:
            currently_selected.update(self.all_test_files)

        return currently_selected

    def _parse_cargo_tests(self, content):
        """Parse Cargo test commands for Rust"""
        currently_selected = set()

        for line in content.split("\n"):
            stripped_line = line.strip()
            if "cargo test" in stripped_line and not stripped_line.startswith("#"):
                # Cargo test can specify specific test names or modules
                parts = stripped_line.split()
                cargo_test_index = -1
                for i, part in enumerate(parts):
                    if part == "test" and i > 0 and parts[i - 1] == "cargo":
                        cargo_test_index = i
                        break

                if cargo_test_index >= 0:
                    # Look for specific test names after "cargo test"
                    test_args = parts[cargo_test_index + 1 :]
                    if test_args:
                        # If specific test names are mentioned, try to match them
                        for test_file in self.all_test_files:
                            for arg in test_args:
                                if arg in test_file:
                                    currently_selected.add(test_file)
                    else:
                        # If no specific tests mentioned, all tests are selected
                        currently_selected.update(self.all_test_files)

        # If no test command found, assume all tests are selected
        if not currently_selected:
            currently_selected.update(self.all_test_files)

        return currently_selected

    def _parse_cmake_tests(self, content):
        """Parse CTest commands for C/C++"""
        currently_selected = set()

        for line in content.split("\n"):
            stripped_line = line.strip()
            if "ctest" in stripped_line and not stripped_line.startswith("#"):
                # CTest typically runs all tests unless specific tests are mentioned
                # Look for -R patterns to specify test regex
                if "-R" in stripped_line:
                    # Extract test regex patterns
                    parts = stripped_line.split()
                    for i, part in enumerate(parts):
                        if part == "-R" and i + 1 < len(parts):
                            test_pattern = parts[i + 1]
                            # Match test files containing the pattern
                            for test_file in self.all_test_files:
                                if test_pattern in test_file:
                                    currently_selected.add(test_file)
                else:
                    # If no specific test mentioned, all tests are selected
                    currently_selected.update(self.all_test_files)

        # If no test command found, assume all tests are selected
        if not currently_selected:
            currently_selected.update(self.all_test_files)

        return currently_selected

    def _parse_dotnet_tests(self, content):
        """Parse dotnet test commands for C#"""
        currently_selected = set()

        for line in content.split("\n"):
            stripped_line = line.strip()
            if "dotnet test" in stripped_line and not stripped_line.startswith("#"):
                # Dotnet test can specify specific test files or filters
                parts = stripped_line.split()
                dotnet_test_index = -1
                for i, part in enumerate(parts):
                    if part == "test" and i > 0 and parts[i - 1] == "dotnet":
                        dotnet_test_index = i
                        break

                if dotnet_test_index >= 0:
                    # Look for test file paths after "dotnet test"
                    for part in parts[dotnet_test_index + 1 :]:
                        normalized_part = part.replace("\\", "/")
                        if normalized_part.endswith(".cs") or normalized_part.endswith(
                            ".csproj"
                        ):
                            if normalized_part in self.all_test_files:
                                currently_selected.add(normalized_part)

                # If no specific tests found, assume all tests are selected
                if not currently_selected:
                    currently_selected.update(self.all_test_files)

        # If no test command found, assume all tests are selected
        if not currently_selected:
            currently_selected.update(self.all_test_files)

        return currently_selected

    def _parse_go_tests(self, content):
        """Parse go test commands for Go"""
        currently_selected = set()

        for line in content.split("\n"):
            stripped_line = line.strip()
            if "go test" in stripped_line and not stripped_line.startswith("#"):
                # Go test can specify specific packages or test files
                parts = stripped_line.split()
                go_test_index = -1
                for i, part in enumerate(parts):
                    if part == "test" and i > 0 and parts[i - 1] == "go":
                        go_test_index = i
                        break

                if go_test_index >= 0:
                    # Look for package paths or test files after "go test"
                    test_args = parts[go_test_index + 1 :]
                    if test_args:
                        for arg in test_args:
                            if arg.startswith("./"):
                                # Package path - select all tests in that path
                                for test_file in self.all_test_files:
                                    if test_file.startswith(arg.lstrip("./")):
                                        currently_selected.add(test_file)
                            elif arg.endswith("_test.go"):
                                # Specific test file
                                if arg in self.all_test_files:
                                    currently_selected.add(arg)
                    else:
                        # If no specific tests mentioned, all tests are selected
                        currently_selected.update(self.all_test_files)

        # If no test command found, assume all tests are selected
        if not currently_selected:
            currently_selected.update(self.all_test_files)

        return currently_selected

    def _create_test_checkboxes(self, parent):
        """Create checkboxes for each test file"""
        if not self.all_test_files:
            no_tests_label = GuiUtils.create_styled_label(
                parent,
                text=f"No test files found for {self.detected_language} project",
                font_key="info",
                color_key="muted",
            )
            no_tests_label.pack(pady=20)
            return

        # Get currently selected tests from run_tests.sh
        currently_selected = self._get_currently_selected_tests()

        for test_file in self.all_test_files:
            # Create variable for checkbox
            var = tk.BooleanVar()
            # Set initial state based on current run_tests.sh content
            var.set(test_file in currently_selected)
            self.test_vars[test_file] = var

            # Create checkbox frame
            checkbox_frame = GuiUtils.create_styled_frame(
                parent, bg_color="white", relief="flat"
            )
            checkbox_frame.pack(fill="x", padx=5, pady=2)

            # Checkbox
            checkbox = tk.Checkbutton(
                checkbox_frame,
                text=test_file,
                variable=var,
                font=FONTS["info"],
                bg=COLORS["white"],
                fg=COLORS["text"],
                selectcolor=COLORS["white"],
                relief="flat",
                borderwidth=0,
            )
            checkbox.pack(anchor="w", padx=10, pady=5)

            self.test_checkboxes[test_file] = checkbox

    def _select_all_tests(self):
        """Select all test files"""
        for var in self.test_vars.values():
            var.set(True)

    def _deselect_all_tests(self):
        """Deselect all test files"""
        for var in self.test_vars.values():
            var.set(False)

    def _save_changes(self):
        """Save the selected test files and update run_tests.sh"""
        selected_tests = []
        for test_file, var in self.test_vars.items():
            if var.get():
                selected_tests.append(test_file)

        if not selected_tests:
            messagebox.showwarning(
                "No Tests Selected", "Please select at least one test file."
            )
            return

        # Call the callback with selected tests and language
        if self.on_save_callback:
            self.on_save_callback(
                self.project_group, selected_tests, self.detected_language
            )

        self.destroy()

    def _cancel(self):
        """Cancel the edit operation"""
        self.destroy()

    def destroy(self):
        """Destroy the window"""
        if self.window:
            self.window.destroy()
            self.canvas = None
