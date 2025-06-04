"""
Refactored Project Control Panel - Main Application
"""

import os
import time
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

from config.settings import WINDOW_TITLE, MAIN_WINDOW_SIZE, COLORS, FONTS, SOURCE_DIR
from services.project_service import ProjectService
from services.project_group_service import ProjectGroupService, ProjectGroup
from services.file_service import FileService
from services.git_service import GitService
from services.docker_service import DockerService
from services.sync_service import SyncService
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
        self.project_group_service = ProjectGroupService(self.project_service)
        self.file_service = FileService()
        self.git_service = GitService()
        self.docker_service = DockerService()
        self.sync_service = SyncService()

        # Initialize GUI
        self.window = tk.Tk()
        self.window.title(WINDOW_TITLE)
        self.window.geometry(MAIN_WINDOW_SIZE)
        self.window.configure(bg=COLORS["background"])

        # GUI components
        self.scrollable_frame = None
        self.project_selector = None
        self.navigation_frame = None

        self.create_gui()
        self.load_projects()

    def create_gui(self):
        """Create the main GUI layout"""

        # Create navigation frame
        self._create_navigation_frame()

        # Create main frame with scrollbar
        main_frame = GuiUtils.create_styled_frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create scrollable frame
        canvas, self.scrollable_frame, scrollbar = GuiUtils.create_scrollable_frame(
            main_frame
        )

    def _create_navigation_frame(self):
        """Create the navigation frame with project selector and navigation buttons"""
        self.navigation_frame = GuiUtils.create_styled_frame(self.window)
        self.navigation_frame.pack(fill="x", padx=10, pady=(0, 10))

        # Project selection row
        selection_frame = GuiUtils.create_styled_frame(self.navigation_frame)
        selection_frame.pack(fill="x", pady=5)

        # Project selector label
        selector_label = GuiUtils.create_styled_label(
            selection_frame, text="Project:", font_key="project_name"
        )
        selector_label.pack(side="left", padx=(0, 10))

        # Project selector dropdown
        self.project_selector = ttk.Combobox(
            selection_frame, state="readonly", font=FONTS["project_name"], width=30
        )
        self.project_selector.pack(side="left", padx=(0, 10))
        self.project_selector.bind("<<ComboboxSelected>>", self.on_project_selected)

        # Refresh button
        refresh_btn = GuiUtils.create_styled_button(
            selection_frame,
            text="🔄 Refresh",
            command=self.refresh_projects,
            style="refresh",
        )
        refresh_btn.pack(side="right")

    def load_projects(self):
        """Load and populate project groups"""
        self.project_group_service.load_project_groups()
        self.update_project_selector()
        self.populate_current_project()

    def update_project_selector(self):
        """Update the project selector dropdown with available projects"""
        group_names = self.project_group_service.get_group_names()

        # Update combobox values
        self.project_selector["values"] = group_names

        if current_group_name := self.project_group_service.get_current_group_name():
            self.project_selector.set(current_group_name)
        elif group_names:
            self.project_selector.set(group_names[0])
            self.project_group_service.set_current_group_by_name(group_names[0])

    def on_project_selected(self, event=None):
        """Handle project selection from dropdown"""
        selected_name = self.project_selector.get()
        if selected_name and self.project_group_service.set_current_group_by_name(
            selected_name
        ):
            self.populate_current_project()

    def populate_current_project(self):
        """Populate the GUI with the current project group"""
        # Clear existing content
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        current_group = self.project_group_service.get_current_group()

        if not current_group:
            no_projects_label = GuiUtils.create_styled_label(
                self.scrollable_frame,
                text=f"No projects found in:\n{self.root_dir}",
                font_key="project_name",
            )
            no_projects_label.pack(pady=20)
            return

        # Create project header
        self._create_project_header(current_group)

        # Create project actions frame
        self._create_project_actions_frame(current_group)

        # Display all versions of the current project
        versions = current_group.get_all_versions()

        if not versions:
            no_versions_label = GuiUtils.create_styled_label(
                self.scrollable_frame,
                text="No versions found for this project",
                font_key="project_name",
            )
            no_versions_label.pack(pady=20)
            return

        # Group versions for better display
        for i, project in enumerate(versions):
            if i > 0:  # Add spacing between versions
                tk.Frame(
                    self.scrollable_frame, height=10, bg=COLORS["background"]
                ).pack()

            self._create_version_section(project)

    def _create_project_header(self, project_group: ProjectGroup):
        """Create a header for the current project group"""
        header_frame = GuiUtils.create_styled_frame(
            self.scrollable_frame, bg_color="white", relief="raised", bd=2
        )
        header_frame.pack(fill="x", padx=20, pady=(10, 0))

        # Project name
        name_label = GuiUtils.create_styled_label(
            header_frame,
            text=f"📁 Project: {project_group.name}",
            font_key="title",
            color_key="project_header",
            bg=COLORS["white"],
        )
        name_label.pack(pady=15)

    def _create_project_actions_frame(self, project_group: ProjectGroup):
        """Create a frame for project-level action buttons"""
        actions_frame = GuiUtils.create_styled_frame(
            self.scrollable_frame, bg_color="background", relief="flat"
        )
        actions_frame.pack(fill="x", padx=20, pady=(0, 10))

        # Buttons container
        buttons_container = GuiUtils.create_styled_frame(
            actions_frame,
            bg_color="background",
        )
        buttons_container.pack(fill="x")

        # Sync button
        sync_btn = GuiUtils.create_styled_button(
            buttons_container,
            text="🔄 Sync run_tests.sh",
            command=lambda: self.sync_run_tests_from_pre_edit(project_group),
            style="sync",
        )
        sync_btn.pack(side="left", padx=(0, 10))

    def _create_version_section(self, project: Project):
        """Create a version section for a project"""
        # Get alias for better display
        alias = self.project_service.get_folder_alias(project.parent)

        # Version header
        version_header_frame = GuiUtils.create_styled_frame(self.scrollable_frame)
        version_header_frame.pack(anchor="w", padx=30, pady=(10, 5))

        # Main version name
        version_label = GuiUtils.create_styled_label(
            version_header_frame,
            text=f"📂 {project.parent}",
            font_key="header",
            color_key="project_header",
        )
        version_label.pack(side="left")

        # Alias in faded text if it exists
        if alias:
            alias_label = GuiUtils.create_styled_label(
                version_header_frame,
                text=f" ({alias})",
                font_key="info",
                color_key="muted",
            )
            alias_label.pack(side="left")

        # Project row
        self._create_project_row(project)

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

                # Create git window immediately with loading state
                git_window = None

                def create_git_window():
                    nonlocal git_window
                    git_window = GitCommitWindow(
                        self.window,
                        project.name,
                        [],  # Start with empty commits
                        lambda commit_hash: self.checkout_commit_callback(
                            project.path, project.name, commit_hash, git_window
                        ),
                        git_service=self.git_service,
                        project_path=project.path,
                    )
                    git_window.create_window_with_loading(fetch_success, fetch_message)

                self.window.after(0, create_git_window)

                # Wait a moment for window to be created
                time.sleep(0.2)

                # Get commits in background
                commits, error = self.git_service.get_git_commits(project.path)

                if error:
                    self.window.after(0, lambda: git_window.update_with_error(error))
                    return

                if not commits:
                    self.window.after(0, lambda: git_window.update_with_no_commits())
                    return

                # Update window with commits
                self.window.after(0, lambda: git_window.update_with_commits(commits))

            except Exception as e:
                error_msg = f"Error accessing git repository: {str(e)}"
                if "git_window" in locals() and git_window:
                    self.window.after(
                        0, lambda: git_window.update_with_error(error_msg)
                    )
                else:
                    self.window.after(
                        0, lambda: messagebox.showerror("Git Error", error_msg)
                    )

        # Create checkout callback
        def checkout_commit_callback(
            project_path, project_name, commit_hash, git_window
        ):
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
                project_path, commit_hash
            )

            if success:
                messagebox.showinfo(
                    "Checkout Success", f"{message}\n\nProject: {project_name}"
                )
                git_window.destroy()
            else:
                # Check if the error is due to local changes
                if self.git_service.has_local_changes(project_path, message):
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
                                project_path, commit_hash
                            )
                        )

                        if force_success:
                            messagebox.showinfo(
                                "Checkout Success",
                                f"{force_message}\n\nProject: {project_name}",
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

        # Store the callback method for use in the git_thread
        self.checkout_commit_callback = checkout_commit_callback

        run_in_thread(git_thread)

    def sync_run_tests_from_pre_edit(self, project_group: ProjectGroup):
        """Sync run_tests.sh from pre-edit to all other versions"""

        def sync_run_tests_thread():
            try:
                # Sync run_tests.sh from pre-edit to other versions
                success, message, synced_paths = (
                    self.sync_service.sync_file_from_pre_edit(
                        project_group, "run_tests.sh"
                    )
                )

                if success:
                    paths_text = "\n".join([f"• {path}" for path in synced_paths])
                    messagebox.showinfo(
                        "Sync Complete",
                        f"Successfully synced run_tests.sh from pre-edit!\n\n"
                        f"Synced to {len(synced_paths)} versions:\n{paths_text}",
                    )
                else:
                    messagebox.showerror(
                        "Sync Error", f"Failed to sync run_tests.sh:\n\n{message}"
                    )

            except Exception as e:
                messagebox.showerror("Sync Error", f"Error during sync: {str(e)}")

        run_in_thread(sync_run_tests_thread)

    def refresh_projects(self):
        """Refresh the project list"""
        # Clear existing widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Repopulate
        self.load_projects()

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
