"""
Refactored Project Control Panel - Main Application with Improved Async Architecture
"""

import os
import time
import asyncio
import tkinter as tk
import logging
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
from utils.async_utils import (
    task_manager,
    shutdown_all,
    AsyncResourceManager,
    TkinterAsyncBridge,
    AsyncTaskGroup,
)
from models.project import Project

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ProjectControlPanel:
    """Main Project Control Panel application with improved async architecture"""

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()

        # Initialize services (all now async-capable)
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

        # Initialize async bridge for GUI coordination
        self.async_bridge = TkinterAsyncBridge(self.window, task_manager)

        # Set up proper event loop for async operations
        self._setup_async_integration()

        # Set up proper cleanup on window close
        self.window.protocol("WM_DELETE_WINDOW", self._on_window_close)

        # GUI components
        self.scrollable_frame = None
        self.project_selector = None
        self.navigation_frame = None

        self.create_gui()
        self.load_projects()

        # Setup improved async event processing
        self._setup_async_processing()

    def _setup_async_integration(self):
        """Set up async integration with tkinter"""
        try:
            # Set up event loop for async operations
            task_manager.setup_event_loop()
            logger.info("Async integration setup complete")
        except Exception as e:
            logger.error("Failed to setup async integration: %s", e)
            # Continue without async support

    def _setup_async_processing(self):
        """Setup improved async event processing with better timing"""

        def process_async_events():
            """Process async events and schedule next processing"""
            try:
                # Get task statistics for monitoring
                stats = task_manager.get_task_stats()

                # Log task statistics periodically (every 10 seconds)
                current_time = time.time()
                if not hasattr(self, "_last_stats_log"):
                    self._last_stats_log = current_time

                if current_time - self._last_stats_log > 10:
                    if stats["running"] > 0:
                        logger.debug(
                            "Async task stats - Running: %d, Total: %d",
                            stats["running"],
                            stats["total"],
                        )
                    self._last_stats_log = current_time

                # Warn if too many tasks are running
                if stats["running"] > 20:
                    logger.warning(
                        "High number of running async tasks: %d", stats["running"]
                    )

            except Exception as e:
                logger.exception("Error processing async events")
            finally:
                # Schedule next processing - using adaptive timing
                # More frequent processing when tasks are active
                interval = 25 if task_manager.get_task_count() > 0 else 100
                self.window.after(interval, process_async_events)

        # Start the processing loop
        process_async_events()

    def _on_window_close(self):
        """Handle window close event with proper cleanup"""
        logger.info("Application shutdown initiated")
        try:
            # Cancel any pending async operations with timeout
            shutdown_all(timeout=3.0)  # Shorter timeout for better UX
        except Exception as e:
            logger.exception("Error during shutdown cleanup")
        finally:
            # Destroy the window
            self.window.destroy()

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
        """Create cleanup of the project (async)"""

        async def cleanup_async():
            try:
                async with AsyncResourceManager(f"cleanup-{project.name}"):
                    # First, scan for directories and files that need cleanup
                    cleanup_needed_dirs, cleanup_needed_files = (
                        await self.file_service.scan_for_cleanup_items(project.path)
                    )

                    # If cleanup items found, prompt user
                    proceed_with_cleanup = True
                    if cleanup_needed_dirs or cleanup_needed_files:
                        cleanup_items = []

                        if cleanup_needed_dirs:
                            cleanup_items.append("Directories:")
                            cleanup_items.extend(
                                [
                                    f"  • {os.path.relpath(d, project.path)}"
                                    for d in cleanup_needed_dirs
                                ]
                            )

                        if cleanup_needed_files:
                            if cleanup_items:
                                cleanup_items.append("")  # Empty line separator
                            cleanup_items.append("Files:")
                            cleanup_items.extend(
                                [
                                    f"  • {os.path.relpath(f, project.path)}"
                                    for f in cleanup_needed_files
                                ]
                            )

                        cleanup_list = "\n".join(cleanup_items)
                        response = messagebox.askyesno(
                            "Confirm Cleanup",
                            f"Found items to cleanup in {project.name}:\n\n{cleanup_list}\n\n"
                            f"Are you sure you want to delete these items?\n\n"
                            f"⚠️  This action cannot be undone!",
                        )

                        if not response:
                            return

                    # Proceed with cleanup
                    if proceed_with_cleanup:
                        deleted_items = await self.file_service.cleanup_project_items(
                            project.path
                        )

                    if deleted_items:
                        message = (
                            f"Cleanup completed for {project.name}!\n\nDeleted:\n"
                            + "\n".join(
                                [
                                    os.path.relpath(item, project.path)
                                    for item in deleted_items
                                ]
                            )
                        )
                    else:
                        message = f"Cleanup completed for {project.name}!\n\nNo cleanup items found."

                    # Use window.after to safely update GUI from async context
                    self.window.after(
                        0, lambda: messagebox.showinfo("Cleanup Complete", message)
                    )

            except FileNotFoundError as e:
                logger.error("Project directory not found: %s", project.path)
                error_msg = f"Project directory not found: {project.path}"
                self.window.after(
                    0, lambda: messagebox.showerror("Cleanup Error", error_msg)
                )
            except PermissionError as e:
                logger.error(
                    "Permission denied during cleanup for %s: %s", project.path, e
                )
                error_msg = f"Permission denied during cleanup. Please check file permissions for: {project.path}"
                self.window.after(
                    0, lambda: messagebox.showerror("Permission Error", error_msg)
                )
            except OSError as e:
                logger.error(
                    "File system error during cleanup for %s: %s", project.path, e
                )
                error_msg = f"File system error during cleanup: {str(e)}"
                self.window.after(
                    0, lambda: messagebox.showerror("File System Error", error_msg)
                )
            except asyncio.CancelledError:
                logger.info("Cleanup task was cancelled for %s", project.path)
                raise  # Always re-raise CancelledError
            except RuntimeError as e:
                logger.error(
                    "Task execution error during cleanup for %s: %s", project.path, e
                )
                error_msg = f"Task execution error: {str(e)}"
                self.window.after(
                    0, lambda: messagebox.showerror("Runtime Error", error_msg)
                )
            except Exception as e:
                # Only for truly unexpected errors - log for debugging
                logger.exception(
                    "Unexpected error in cleanup_project for %s", project.path
                )
                error_msg = f"An unexpected error occurred during cleanup: {str(e)}"
                self.window.after(
                    0, lambda: messagebox.showerror("Cleanup Error", error_msg)
                )

        # Run the async operation with proper task naming
        task_manager.run_task(cleanup_async(), task_name=f"cleanup-{project.name}")

    def archive_project(self, project: Project):
        """Create archive of the project (async)"""

        async def archive_async():
            try:
                # First, scan for directories and files that need cleanup
                cleanup_needed_dirs, cleanup_needed_files = (
                    await self.file_service.scan_for_cleanup_items(project.path)
                )

                # If cleanup items found, prompt user
                proceed_with_archive = True
                if cleanup_needed_dirs or cleanup_needed_files:
                    cleanup_items = []

                    if cleanup_needed_dirs:
                        cleanup_items.append("Directories:")
                        cleanup_items.extend(
                            [
                                f"  • {os.path.relpath(d, project.path)}"
                                for d in cleanup_needed_dirs
                            ]
                        )

                    if cleanup_needed_files:
                        if cleanup_items:
                            cleanup_items.append("")  # Empty line separator
                        cleanup_items.append("Files:")
                        cleanup_items.extend(
                            [
                                f"  • {os.path.relpath(f, project.path)}"
                                for f in cleanup_needed_files
                            ]
                        )

                    cleanup_list = "\n".join(cleanup_items)
                    response = messagebox.askyesnocancel(
                        "Cleanup Before Archive",
                        f"Found items to cleanup in {project.name}:\n\n{cleanup_list}\n\n"
                        f"Would you like to clean these up before creating the archive?\n\n"
                        f"• Yes: Clean up and then archive\n"
                        f"• No: Archive without cleanup\n"
                        f"• Cancel: Don't archive",
                    )

                    if response is None:  # Cancel
                        return
                    elif response:  # Yes - cleanup first
                        deleted_items = await self.file_service.cleanup_project_items(
                            project.path
                        )
                        if deleted_items:
                            self.window.after(
                                0,
                                lambda: messagebox.showinfo(
                                    "Cleanup Complete",
                                    f"Cleaned up {len(deleted_items)} items before archiving.",
                                ),
                            )

                # Proceed with archiving
                if proceed_with_archive:
                    archive_name = self.project_service.get_archive_name(
                        project.parent, project.name
                    )
                    success, error_msg = await self.file_service.create_archive(
                        project.path, archive_name
                    )

                    if success:
                        self.window.after(
                            0,
                            lambda: messagebox.showinfo(
                                "Archive Complete",
                                f"Successfully created archive:\n{archive_name}\n\nLocation: {project.path}",
                            ),
                        )
                    else:
                        self.window.after(
                            0,
                            lambda: messagebox.showerror(
                                "Archive Error",
                                f"Failed to create archive.\nError: {error_msg}",
                            ),
                        )

            except FileNotFoundError as e:
                logger.error("Project directory not found: %s", project.path)
                error_msg = f"Project directory not found: {project.path}"
                self.window.after(
                    0, lambda: messagebox.showerror("Archive Error", error_msg)
                )
            except PermissionError as e:
                logger.error(
                    "Permission denied during archiving for %s: %s", project.path, e
                )
                error_msg = f"Permission denied during archiving. Please check file permissions for: {project.path}"
                self.window.after(
                    0, lambda: messagebox.showerror("Permission Error", error_msg)
                )
            except OSError as e:
                logger.error(
                    "File system error during archiving for %s: %s", project.path, e
                )
                error_msg = f"File system error during archiving: {str(e)}"
                self.window.after(
                    0, lambda: messagebox.showerror("File System Error", error_msg)
                )
            except asyncio.CancelledError:
                logger.info("Archive task was cancelled for %s", project.path)
                raise  # Always re-raise CancelledError
            except RuntimeError as e:
                logger.error(
                    "Task execution error during archiving for %s: %s", project.path, e
                )
                error_msg = f"Task execution error: {str(e)}"
                self.window.after(
                    0, lambda: messagebox.showerror("Runtime Error", error_msg)
                )
            except Exception as e:
                # Only for truly unexpected errors - log for debugging
                logger.exception(
                    "Unexpected error in archive_project for %s", project.path
                )
                error_msg = f"An unexpected error occurred during archiving: {str(e)}"
                self.window.after(
                    0, lambda: messagebox.showerror("Archive Error", error_msg)
                )

        # Run the async operation with proper task naming
        task_manager.run_task(archive_async(), task_name=f"archive-{project.name}")

    def docker_build_and_test(self, project: Project):
        """Build Docker container and run tests (async) with improved synchronization"""

        async def docker_async():
            try:
                docker_tag = self.project_service.get_docker_tag(
                    project.parent, project.name
                )

                # Create synchronization event to coordinate with GUI
                event_id, window_ready_event = self.async_bridge.create_sync_event()

                # Create terminal output window on main thread
                terminal_window = None

                def create_window():
                    nonlocal terminal_window
                    terminal_window = TerminalOutputWindow(
                        self.window, f"Docker Build & Test - {docker_tag}"
                    )
                    terminal_window.create_window()
                    # Signal that window is ready
                    self.async_bridge.signal_from_gui(event_id)

                self.window.after(0, create_window)

                # Wait for window to be properly created (no hardcoded sleep!)
                await window_ready_event.wait()

                # Clean up the synchronization event
                self.async_bridge.cleanup_event(event_id)

                # Update initial status
                terminal_window.update_status(
                    "Building Docker image...", COLORS["warning"]
                )
                # Run Docker build and test
                success, raw_test_output = await self.docker_service.build_and_test(
                    project.path,
                    docker_tag,
                    terminal_window.append_output,
                    terminal_window.update_status,
                )

                # Add final buttons
                terminal_window.add_final_buttons(copy_text=raw_test_output)

            except asyncio.CancelledError:
                logger.info("Docker build/test was cancelled for %s", project.name)
                raise  # Always re-raise CancelledError
            except Exception as e:
                logger.exception("Error during Docker build/test for %s", project.name)
                error_msg = f"Error during Docker build/test: {str(e)}"
                self.window.after(
                    0, lambda: messagebox.showerror("Docker Error", error_msg)
                )

        # Run the async operation with proper task naming
        task_manager.run_task(docker_async(), task_name=f"docker-{project.name}")

    def git_view(self, project: Project):
        """Show git commits and allow checkout (async) with improved synchronization"""

        async def git_async():
            try:
                # Fetch latest commits (no blocking message)
                fetch_success, fetch_message = (
                    await self.git_service.fetch_latest_commits(project.path)
                )

                if not fetch_success and "No remote repository" not in fetch_message:
                    self.window.after(
                        0,
                        lambda: messagebox.showwarning(
                            "Fetch Warning",
                            f"Could not fetch latest commits:\n{fetch_message}\n\nShowing local commits only.",
                        ),
                    )

                # Create synchronization event for window creation
                event_id, window_ready_event = self.async_bridge.create_sync_event()

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
                    # Signal that window is ready
                    self.async_bridge.signal_from_gui(event_id)

                self.window.after(0, create_git_window)

                # Wait for window to be properly created (no hardcoded sleep!)
                await window_ready_event.wait()

                # Clean up the synchronization event
                self.async_bridge.cleanup_event(event_id)

                # Get commits in background
                commits, error = await self.git_service.get_git_commits(project.path)

                if error:
                    self.window.after(0, lambda: git_window.update_with_error(error))
                    return

                if not commits:
                    self.window.after(0, lambda: git_window.update_with_no_commits())
                    return

                # Update window with commits
                self.window.after(0, lambda: git_window.update_with_commits(commits))

            except asyncio.CancelledError:
                logger.info("Git view was cancelled for %s", project.name)
                raise  # Always re-raise CancelledError
            except Exception as e:
                logger.exception("Error accessing git repository for %s", project.name)
                error_msg = f"Error accessing git repository: {str(e)}"
                if "git_window" in locals() and git_window:
                    self.window.after(
                        0, lambda: git_window.update_with_error(error_msg)
                    )
                else:
                    self.window.after(
                        0, lambda: messagebox.showerror("Git Error", error_msg)
                    )

        # Create checkout callback (async) - using task groups for better management
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

            # Run checkout as async task with task group
            async def checkout_async():
                try:
                    # Perform checkout
                    success, message = await self.git_service.checkout_commit(
                        project_path, commit_hash
                    )

                    if success:
                        self.window.after(
                            0,
                            lambda: messagebox.showinfo(
                                "Checkout Success",
                                f"{message}\n\nProject: {project_name}",
                            ),
                        )
                        self.window.after(0, git_window.destroy)
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
                                    await self.git_service.force_checkout_commit(
                                        project_path, commit_hash
                                    )
                                )

                                if force_success:
                                    self.window.after(
                                        0,
                                        lambda: messagebox.showinfo(
                                            "Checkout Success",
                                            f"{force_message}\n\nProject: {project_name}",
                                        ),
                                    )
                                    self.window.after(0, git_window.window.destroy)
                                else:
                                    self.window.after(
                                        0,
                                        lambda: messagebox.showerror(
                                            "Force Checkout Failed",
                                            f"Failed to checkout even after discarding changes:\n\n{force_message}",
                                        ),
                                    )
                            elif discard_response is False:  # No - keep changes
                                self.window.after(
                                    0,
                                    lambda: messagebox.showinfo(
                                        "Checkout Cancelled",
                                        "Checkout cancelled. Your local changes have been preserved.",
                                    ),
                                )
                            # If None (Cancel), just return to commit list without message
                        else:
                            # Some other git error
                            self.window.after(
                                0,
                                lambda: messagebox.showerror(
                                    "Checkout Error",
                                    f"Failed to checkout commit {commit_hash}\n\n{message}",
                                ),
                            )
                except asyncio.CancelledError:
                    logger.info("Checkout was cancelled for %s", project_name)
                    raise  # Always re-raise CancelledError
                except Exception as e:
                    logger.exception("Error during checkout for %s", project_name)
                    error_msg = f"Error during checkout: {str(e)}"
                    self.window.after(
                        0, lambda: messagebox.showerror("Checkout Error", error_msg)
                    )

            # Run the checkout operation with proper task naming
            task_manager.run_task(
                checkout_async(), task_name=f"checkout-{project_name}-{commit_hash[:8]}"
            )

        # Store the callback method for use in the git_async
        self.checkout_commit_callback = checkout_commit_callback

        # Run the async operation with proper task naming
        task_manager.run_task(git_async(), task_name=f"git-view-{project.name}")

    def sync_run_tests_from_pre_edit(self, project_group: ProjectGroup):
        """Sync run_tests.sh from pre-edit to all other versions (async)"""

        async def sync_run_tests_async():
            try:
                # Sync run_tests.sh from pre-edit to other versions
                success, message, synced_paths = (
                    await self.sync_service.sync_file_from_pre_edit(
                        project_group, "run_tests.sh"
                    )
                )

                if success:
                    paths_text = "\n".join([f"• {path}" for path in synced_paths])
                    self.window.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Sync Complete",
                            f"Successfully synced run_tests.sh from pre-edit!\n\n"
                            f"Synced to {len(synced_paths)} versions:\n{paths_text}",
                        ),
                    )
                else:
                    self.window.after(
                        0,
                        lambda: messagebox.showerror(
                            "Sync Error", f"Failed to sync run_tests.sh:\n\n{message}"
                        ),
                    )

            except asyncio.CancelledError:
                logger.info(
                    "Sync was cancelled for project group %s", project_group.name
                )
                raise  # Always re-raise CancelledError
            except Exception as e:
                logger.exception(
                    "Error during sync for project group %s", project_group.name
                )
                error_msg = f"Error during sync: {str(e)}"
                self.window.after(
                    0, lambda: messagebox.showerror("Sync Error", error_msg)
                )

        # Run the async operation with proper task naming
        task_manager.run_task(
            sync_run_tests_async(), task_name=f"sync-{project_group.name}"
        )

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
