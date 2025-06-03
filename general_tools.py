"""
Refactored Project Control Panel - Main Application
"""

import os
import time
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from config.settings import WINDOW_TITLE, MAIN_WINDOW_SIZE, COLORS, FONTS, SOURCE_DIR
from services.project_service import ProjectService
from services.file_service import FileService
from services.git_service import GitService
from services.docker_service import DockerService
from gui.gui_utils import GuiUtils
from gui.popup_windows import TerminalOutputWindow, GitCommitWindow
from utils.threading_utils import run_in_thread
from models.project import Project


class ProjectControlPanel:
    """Main Project Control Panel application"""

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()

        # Initialize services
        self.project_service = ProjectService(root_dir)
        self.file_service = FileService()
        self.git_service = GitService()
        self.docker_service = DockerService()

        # Initialize GUI
        self.window = tk.Tk()
        self.window.title(WINDOW_TITLE)
        self.window.geometry(MAIN_WINDOW_SIZE)
        self.window.configure(bg=COLORS["background"])

        # GUI components
        self.scrollable_frame = None

        self.create_gui()
        self.populate_projects()

    def create_gui(self):
        """Create the main GUI layout"""
        # Title
        title_label = GuiUtils.create_styled_label(
            self.window, text=WINDOW_TITLE, font_key="title", color_key="project_header"
        )
        title_label.pack(pady=10)

        # Create main frame with scrollbar
        main_frame = GuiUtils.create_styled_frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create scrollable frame
        canvas, self.scrollable_frame, scrollbar = GuiUtils.create_scrollable_frame(
            main_frame
        )

    def populate_projects(self):
        """Populate the GUI with project controls"""
        projects = self.project_service.find_two_layer_projects()

        if not projects:
            no_projects_label = GuiUtils.create_styled_label(
                self.scrollable_frame,
                text=f"No 2-layer projects found in:\n{self.root_dir}",
                font_key="project_name",
            )
            no_projects_label.pack(pady=20)
            return

        # Group projects by parent folder
        current_parent = None

        for project in projects:
            # Add parent folder header if it's a new parent
            if project.parent != current_parent:
                current_parent = project.parent

                if project != projects[0]:  # Add some space between groups
                    tk.Frame(
                        self.scrollable_frame, height=10, bg=COLORS["background"]
                    ).pack()

                self._create_parent_header(project)

            self._create_project_row(project)

        # Add refresh button at the bottom
        self._create_refresh_button()

    def _create_parent_header(self, project: Project):
        """Create a parent folder header"""
        alias = self.project_service.get_folder_alias(project.parent)
        alias_text = f" ({alias})" if alias else ""

        # Create frame for parent label with alias
        parent_frame = GuiUtils.create_styled_frame(self.scrollable_frame)
        parent_frame.pack(anchor="w", padx=20, pady=(10, 5))

        # Main parent folder label
        parent_label = GuiUtils.create_styled_label(
            parent_frame,
            text=f"📁 {project.parent}/",
            font_key="header",
            color_key="project_header",
        )
        parent_label.pack(side="left")

        # Alias label if it exists
        if alias_text:
            alias_label = GuiUtils.create_styled_label(
                parent_frame,
                text=alias_text,
                font_key="project_name",
                color_key="muted",
            )
            alias_label.pack(side="left", padx=(5, 0))

    def _create_project_row(self, project: Project):
        """Create a project row with buttons"""
        # Create project frame
        project_frame = GuiUtils.create_styled_frame(
            self.scrollable_frame, bg_color="white", relief="raised", bd=1
        )
        project_frame.pack(fill="x", padx=40, pady=2)

        # Project info
        info_frame = GuiUtils.create_styled_frame(project_frame, bg_color="white")
        info_frame.pack(side="left", fill="x", expand=True, padx=10, pady=8)

        name_label = GuiUtils.create_styled_label(
            info_frame, text=project.name, font_key="project_name", bg=COLORS["white"]
        )
        name_label.pack(anchor="w")

        path_label = GuiUtils.create_styled_label(
            info_frame,
            text=f"Path: {project.relative_path}",
            font_key="info",
            color_key="muted",
            bg=COLORS["white"],
        )
        path_label.pack(anchor="w")

        # Buttons frame
        buttons_frame = GuiUtils.create_styled_frame(project_frame, bg_color="white")
        buttons_frame.pack(side="right", padx=10, pady=8)

        # Create buttons
        self._create_project_buttons(buttons_frame, project)

    def _create_project_buttons(self, parent, project: Project):
        """Create the action buttons for a project"""
        # Cleanup button
        cleanup_btn = GuiUtils.create_styled_button(
            parent,
            text="🧹 Cleanup",
            command=lambda: self.cleanup_project(project),
            style="cleanup",
        )
        cleanup_btn.pack(side="left", padx=(0, 5))

        # Archive button
        archive_btn = GuiUtils.create_styled_button(
            parent,
            text="📦 Archive",
            command=lambda: self.archive_project(project),
            style="archive",
        )
        archive_btn.pack(side="left", padx=(0, 5))

        # Docker button
        docker_btn = GuiUtils.create_styled_button(
            parent,
            text="🐳 Docker",
            command=lambda: self.docker_build_and_test(project),
            style="docker",
        )
        docker_btn.pack(side="left", padx=(0, 5))

        # Git View button
        git_btn = GuiUtils.create_styled_button(
            parent,
            text="🔀 Git View",
            command=lambda: self.git_view(project),
            style="git",
        )
        git_btn.pack(side="left")

    def _create_refresh_button(self):
        """Create the refresh button"""
        tk.Frame(self.scrollable_frame, height=20, bg=COLORS["background"]).pack()

        refresh_frame = GuiUtils.create_styled_frame(self.scrollable_frame)
        refresh_frame.pack(pady=10)

        refresh_btn = GuiUtils.create_styled_button(
            refresh_frame,
            text="🔄 Refresh Projects",
            command=self.refresh_projects,
            style="refresh",
            font=FONTS["button_large"],
            padx=15,
            pady=8,
        )
        refresh_btn.pack()

    def cleanup_project(self, project: Project):
        """Clean up specified directories in the project"""

        def cleanup_thread():
            try:
                deleted_items = self.file_service.cleanup_project_dirs(project.path)

                # Show results
                if deleted_items:
                    message = (
                        f"Cleanup completed for {project.name}!\n\nDeleted:\n"
                        + "\n".join(deleted_items)
                    )
                else:
                    message = f"Cleanup completed for {project.name}!\n\nNo cleanup directories found."

                messagebox.showinfo("Cleanup Complete", message)

            except Exception as e:
                messagebox.showerror("Cleanup Error", f"Error during cleanup: {str(e)}")

        run_in_thread(cleanup_thread)

    def archive_project(self, project: Project):
        """Create archive of the project"""

        def archive_thread():
            try:
                # First, scan for directories that need cleanup
                cleanup_needed_dirs = self.file_service.scan_for_cleanup_dirs(
                    project.path
                )

                # If cleanup directories found, prompt user
                proceed_with_archive = True
                if cleanup_needed_dirs:
                    cleanup_list = "\n".join(
                        [
                            f"• {os.path.relpath(d, project.path)}"
                            for d in cleanup_needed_dirs
                        ]
                    )
                    response = messagebox.askyesnocancel(
                        "Cleanup Before Archive",
                        f"Found directories to cleanup in {project.name}:\n\n{cleanup_list}\n\n"
                        f"Would you like to clean these up before creating the archive?\n\n"
                        f"• Yes: Clean up and then archive\n"
                        f"• No: Archive without cleanup\n"
                        f"• Cancel: Don't archive",
                    )

                    if response is None:  # Cancel
                        return
                    elif response:  # Yes - cleanup first
                        deleted_items = self.file_service.cleanup_project_dirs(
                            project.path
                        )
                        if deleted_items:
                            messagebox.showinfo(
                                "Cleanup Complete",
                                f"Cleaned up {len(deleted_items)} directories before archiving.",
                            )

                # Proceed with archiving
                if proceed_with_archive:
                    archive_name = self.project_service.get_archive_name(
                        project.parent, project.name
                    )
                    success, error_msg = self.file_service.create_archive(
                        project.path, archive_name
                    )

                    if success:
                        messagebox.showinfo(
                            "Archive Complete",
                            f"Successfully created archive:\n{archive_name}\n\nLocation: {project.path}",
                        )
                    else:
                        messagebox.showerror(
                            "Archive Error",
                            f"Failed to create archive.\nError: {error_msg}",
                        )

            except Exception as e:
                messagebox.showerror(
                    "Archive Error", f"Error during archiving: {str(e)}"
                )

        run_in_thread(archive_thread)

    def docker_build_and_test(self, project: Project):
        """Build Docker container and run tests"""

        def docker_thread():
            try:
                docker_tag = self.project_service.get_docker_tag(
                    project.parent, project.name
                )

                # Create terminal output window
                terminal_window = TerminalOutputWindow(
                    self.window, f"Docker Build & Test - {docker_tag}"
                )

                # Create window on main thread
                self.window.after(0, terminal_window.create_window)

                # Wait a moment for window to be created
                time.sleep(0.5)

                # Update initial status
                terminal_window.update_status(
                    "Building Docker image...", COLORS["warning"]
                )

                # Run Docker build and test
                success, raw_test_output = self.docker_service.build_and_test(
                    project.path,
                    docker_tag,
                    terminal_window.append_output,
                    terminal_window.update_status,
                )

                # Add final buttons
                terminal_window.add_final_buttons(copy_text=raw_test_output)

            except Exception as e:
                error_msg = f"Error during Docker build/test: {str(e)}"
                self.window.after(
                    0, lambda: messagebox.showerror("Docker Error", error_msg)
                )

        run_in_thread(docker_thread)

    def git_view(self, project: Project):
        """Show git commits and allow checkout"""

        def git_thread():
            try:
                # Fetch latest commits (no blocking message)
                fetch_success, fetch_message = self.git_service.fetch_latest_commits(
                    project.path
                )

                if not fetch_success and "No remote repository" not in fetch_message:
                    self.window.after(
                        0,
                        lambda: messagebox.showwarning(
                            "Fetch Warning",
                            f"Could not fetch latest commits:\n{fetch_message}\n\nShowing local commits only.",
                        ),
                    )

                # Get commits
                commits, error = self.git_service.get_git_commits(project.path)

                if error:
                    self.window.after(
                        0, lambda: messagebox.showerror("Git Error", error)
                    )
                    return

                if not commits:
                    self.window.after(
                        0,
                        lambda: messagebox.showinfo(
                            "No Commits", f"No git commits found for {project.name}"
                        ),
                    )
                    return

                # Create checkout callback
                def checkout_callback(commit_hash: str):
                    # Confirm checkout
                    response = messagebox.askyesno(
                        "Confirm Checkout",
                        f"Are you sure you want to checkout to commit {commit_hash}?\n\n"
                        f"This will change your working directory to that commit.\n"
                        f"Any uncommitted changes may be lost.",
                    )

                    if not response:
                        return

                    # Perform checkout
                    success, message = self.git_service.checkout_commit(
                        project.path, commit_hash
                    )

                    if success:
                        messagebox.showinfo(
                            "Checkout Success", f"{message}\n\nProject: {project.name}"
                        )
                        git_window.destroy()
                    else:
                        # Check if the error is due to local changes
                        if self.git_service.has_local_changes(project.path, message):
                            # Show warning and ask if user wants to discard changes
                            discard_response = messagebox.askyesnocancel(
                                "Local Changes Detected",
                                f"Cannot checkout because local changes would be overwritten:\n\n"
                                f"{message}\n\n"
                                f"Would you like to discard all local changes and force checkout?\n\n"
                                f"⚠️  WARNING: This will permanently delete all uncommitted changes!\n\n"
                                f"• Yes: Discard changes and checkout\n"
                                f"• No: Keep changes and cancel checkout\n"
                                f"• Cancel: Return to commit list",
                            )

                            if discard_response is True:  # Yes - discard changes
                                force_success, force_message = (
                                    self.git_service.force_checkout_commit(
                                        project.path, commit_hash
                                    )
                                )

                                if force_success:
                                    messagebox.showinfo(
                                        "Checkout Success",
                                        f"{force_message}\n\nProject: {project.name}",
                                    )
                                    git_window.destroy()
                                else:
                                    messagebox.showerror(
                                        "Force Checkout Failed",
                                        f"Failed to checkout even after discarding changes:\n\n{force_message}",
                                    )
                            elif discard_response is False:  # No - keep changes
                                messagebox.showinfo(
                                    "Checkout Cancelled",
                                    "Checkout cancelled. Your local changes have been preserved.",
                                )
                            # If None (Cancel), just return to commit list without message
                        else:
                            # Some other git error
                            messagebox.showerror(
                                "Checkout Error",
                                f"Failed to checkout commit {commit_hash}\n\n{message}",
                            )

                # Create git window on main thread
                def create_git_window():
                    nonlocal git_window
                    git_window = GitCommitWindow(
                        self.window, project.name, commits, checkout_callback
                    )
                    git_window.create_window(fetch_success, fetch_message)

                git_window = None
                self.window.after(0, create_git_window)

            except Exception as e:
                error_msg = f"Error accessing git repository: {str(e)}"
                self.window.after(
                    0, lambda: messagebox.showerror("Git Error", error_msg)
                )

        run_in_thread(git_thread)

    def refresh_projects(self):
        """Refresh the project list"""
        # Clear existing widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Repopulate
        self.populate_projects()

    def run(self):
        """Start the GUI"""
        self.window.mainloop()


def main():
    """Main function to run the control panel"""
    print("Starting Project Control Panel...")
    print(f"Source directory: {SOURCE_DIR}")

    app = ProjectControlPanel(SOURCE_DIR)
    app.run()


if __name__ == "__main__":
    main()
