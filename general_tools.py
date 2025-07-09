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
from typing import List

from config.settings import WINDOW_TITLE, MAIN_WINDOW_SIZE, COLORS, FONTS, SOURCE_DIR
from services.project_service import ProjectService
from services.project_group_service import ProjectGroupService, ProjectGroup
from services.file_service import FileService
from services.git_service import GitService
from services.docker_service import DockerService
from services.sync_service import SyncService
from services.validation_service import ValidationService
from services.docker_files_service import DockerFilesService
from gui import (
    MainWindow,
    TerminalOutputWindow,
    GitCommitWindow,
    GitCheckoutAllWindow,
    AddProjectWindow,
    EditRunTestsWindow,
)
from utils.async_utils import (
    task_manager,
    shutdown_all,
    AsyncResourceManager,
    TkinterAsyncBridge,
    AsyncTaskGroup,
)
from utils.async_commands import (
    CleanupProjectCommand,
    ArchiveProjectCommand,
    DockerBuildAndTestCommand,
    GitViewCommand,
    GitCheckoutAllCommand,
    SyncRunTestsCommand,
    ValidateProjectGroupCommand,
    BuildDockerFilesCommand,
    AsyncTaskManager,
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
        self.validation_service = ValidationService()
        self.docker_files_service = DockerFilesService()

        # Initialize GUI
        self.main_window = MainWindow(root_dir)
        self.window = self.main_window.window  # For backward compatibility

        # Initialize async bridge for GUI coordination
        self.async_bridge = TkinterAsyncBridge(self.window, task_manager)

        # Initialize standardized async executor
        self.async_executor = AsyncTaskManager()

        # Set up proper event loop for async operations
        self._setup_async_integration()

        # Set up GUI callbacks
        self._setup_gui_callbacks()

        # Set up proper cleanup on window close
        self.main_window.setup_window_protocol(self._on_window_close)

        # Create GUI and load projects
        self.main_window.create_gui()
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

    def _setup_gui_callbacks(self):
        """Set up GUI event callbacks"""
        callbacks = {
            "on_project_selected": self.on_project_selected,
            "refresh_projects": self.refresh_projects,
            "open_add_project_window": self.open_add_project_window,
            "cleanup_project": self.cleanup_project,
            "archive_project": self.archive_project,
            "docker_build_and_test": self.docker_build_and_test,
            "git_view": self.git_view,
            "sync_run_tests_from_pre_edit": self.sync_run_tests_from_pre_edit,
            "edit_run_tests": self.edit_run_tests,
            "validate_project_group": self.validate_project_group,
            "build_docker_files_for_project_group": self.build_docker_files_for_project_group,
            "git_checkout_all": self.git_checkout_all,
        }
        self.main_window.set_callbacks(callbacks)

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

    def load_projects(self):
        """Load and populate project groups"""
        self.project_group_service.load_project_groups()
        self.update_project_selector()
        self.populate_current_project()

    def update_project_selector(self):
        """Update the project selector dropdown with available projects"""
        group_names = self.project_group_service.get_group_names()
        current_group_name = self.project_group_service.get_current_group_name()

        # Update the main window's project selector
        self.main_window.update_project_selector(group_names, current_group_name)

        # Set default if no current group but groups exist
        if not current_group_name and group_names:
            self.project_group_service.set_current_group_by_name(group_names[0])

    def on_project_selected(self, event=None):
        """Handle project selection from dropdown"""
        selected_name = self.main_window.get_selected_project()
        if selected_name and self.project_group_service.set_current_group_by_name(
            selected_name
        ):
            self.populate_current_project()

    def populate_current_project(self):
        """Populate the GUI with the current project group"""
        # Clear existing content
        self.main_window.clear_content()

        current_group = self.project_group_service.get_current_group()

        if not current_group:
            self.main_window.show_no_projects_message()
            return

        # Create project header
        self.main_window.create_project_header(current_group)

        # Create project actions frame
        self.main_window.create_project_actions_frame(current_group)

        # Display all versions of the current project
        versions = current_group.get_all_versions()

        if not versions:
            self.main_window.show_no_versions_message()
            return

        # Group versions for better display
        for i, project in enumerate(versions):
            if i > 0:  # Add spacing between versions
                self.main_window.add_version_spacing()

            self.main_window.create_version_section(project, self.project_service)

    def cleanup_project(self, project: Project):
        """Standardized async cleanup operation using command pattern"""
        command = CleanupProjectCommand(
            project=project,
            file_service=self.file_service,
            progress_callback=self._update_status,
            completion_callback=self._handle_cleanup_completion,
        )

        # Standard async execution
        task_manager.run_task(
            command.run_with_progress(), task_name=f"cleanup-{project.name}"
        )

    def _update_status(self, message: str, level: str):
        """Standard progress callback for async operations"""
        color_map = {
            "info": COLORS["info"],
            "warning": COLORS["warning"],
            "success": COLORS["success"],
            "error": COLORS["error"],
        }
        color = color_map.get(level, COLORS["info"])

        # Update GUI status safely from any thread
        self.window.after(0, lambda: self._safe_status_update(message, color))

    def _safe_status_update(self, message: str, color: str):
        """Safely update status in GUI thread"""
        # This would update a status bar or label in the GUI
        # Only log significant status changes, not all progress messages
        if any(
            keyword in message.lower()
            for keyword in ["completed", "failed", "error", "started", "finished"]
        ):
            logger.info(f"Status: {message} ({color})")

    def _handle_cleanup_completion(self, result):
        """Standard completion callback for cleanup operations"""
        if result.is_success:
            self._show_cleanup_success(result.data)
        else:
            self._show_cleanup_error(result.error)

    def _show_cleanup_success(self, data):
        """Show cleanup success message"""
        message = data.get("message", "Cleanup completed successfully")
        if deleted_items := data.get("deleted_directories", []) + data.get(
            "deleted_files", []
        ):
            item_list = "\n".join(
                [f"  • {item}" for item in deleted_items[:10]]
            )  # Show first 10
            if len(deleted_items) > 10:
                item_list += f"\n  ... and {len(deleted_items) - 10} more items"
            full_message = f"{message}\n\nDeleted items:\n{item_list}"
        else:
            full_message = f"{message}\n\nNo items needed cleanup."

        self.window.after(
            0, lambda: messagebox.showinfo("Cleanup Complete", full_message)
        )

    def _show_cleanup_error(self, error):
        """Show cleanup error message"""
        error_message = f"Cleanup failed: {error.message}"
        self.window.after(
            0, lambda: messagebox.showerror("Cleanup Error", error_message)
        )

    def _handle_archive_completion(self, result):
        """Standard completion callback for archive operations"""
        if result.is_success:
            self._show_archive_success(result.data)
        else:
            self._show_archive_error(result.error)

    def _show_archive_success(self, data):
        """Show archive success message"""
        message = data.get("message", "Archive created successfully")
        archive_path = data.get("archive_path", "")
        cleanup_needed = data.get("cleanup_needed", False)
        cleanup_message = data.get("cleanup_message", "")

        if cleanup_needed:
            response = messagebox.askyesnocancel(
                "Cleanup Before Archive",
                f"Found items to cleanup:\n\n{cleanup_message}\n\n"
                f"Would you like to clean these up before creating the archive?\n\n"
                f"• Yes: Clean up and then archive\n"
                f"• No: Archive without cleanup\n"
                f"• Cancel: Don't archive",
            )

            if response is None:  # Cancel
                return
            elif response:  # Yes - cleanup first
                self.window.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Cleanup Complete",
                        "Cleaned up items before archiving.",
                    ),
                )

        self.window.after(
            0,
            lambda: messagebox.showinfo(
                "Archive Complete",
                f"{message}\n\nLocation: {archive_path}",
            ),
        )

    def _show_archive_error(self, error):
        """Show archive error message"""
        error_message = f"Archive failed: {error.message}"
        self.window.after(
            0, lambda: messagebox.showerror("Archive Error", error_message)
        )

    def archive_project(self, project: Project):
        """Standardized async archive operation using command pattern"""
        command = ArchiveProjectCommand(
            project=project,
            file_service=self.file_service,
            project_service=self.project_service,
            progress_callback=self._update_status,
            completion_callback=self._handle_archive_completion,
        )

        # Standard async execution
        task_manager.run_task(
            command.run_with_progress(), task_name=f"archive-{project.name}"
        )

    def docker_build_and_test(self, project: Project):
        """Standardized async Docker build and test operation using command pattern"""
        command = DockerBuildAndTestCommand(
            project=project,
            docker_service=self.docker_service,
            window=self.window,
            progress_callback=self._update_status,
            completion_callback=self._handle_docker_completion,
        )

        # Standard async execution
        task_manager.run_task(
            command.run_with_progress(), task_name=f"docker-{project.name}"
        )

    def _handle_docker_completion(self, result):
        """Standard completion callback for Docker operations"""
        # The command creates its own terminal window with real-time streaming output,
        # so we don't need to create additional popup windows.
        # The Docker output is already being streamed to the terminal window in real-time.
        pass

    def _show_docker_results(self, data):
        """Show Docker build and test results in terminal window"""

        def create_window():
            # Extract relevant information from result data
            docker_tag = data.get("docker_tag", "unknown")
            project_name = data.get("project_name", "unknown")

            # Create terminal window with correct constructor arguments
            terminal_window = TerminalOutputWindow(
                self.window,
                f"Docker Build & Test - {project_name}",
            )
            terminal_window.create_window()

            # Combine build and test output
            build_data = data.get("build_data", {})
            test_data = data.get("test_data", {})

            build_output = (
                build_data.get("build_output", "")
                if isinstance(build_data, dict)
                else str(build_data)
            )
            test_output = (
                test_data.get("raw_output", "")
                if isinstance(test_data, dict)
                else str(test_data)
            )

            # Add the output to the terminal window
            if build_output:
                terminal_window.append_output("=== BUILD OUTPUT ===\n")
                terminal_window.append_output(build_output)
                terminal_window.append_output("\n\n")

            if test_output:
                terminal_window.append_output("=== TEST OUTPUT ===\n")
                terminal_window.append_output(test_output)
                terminal_window.append_output("\n")

            # Add final buttons with copy functionality
            combined_output = f"=== BUILD OUTPUT ===\n{build_output}\n\n=== TEST OUTPUT ===\n{test_output}"
            terminal_window.add_final_buttons(copy_text=combined_output)

            # Update final status
            terminal_window.update_status(
                "Docker operation completed", COLORS["success"]
            )

        self.window.after(0, create_window)

    def _show_docker_error(self, error):
        """Show Docker error message"""
        error_message = f"Docker operation failed: {error.message}"
        self.window.after(
            0, lambda: messagebox.showerror("Docker Error", error_message)
        )

    def git_view(self, project: Project):
        """Standardized async Git view operation using command pattern"""
        command = GitViewCommand(
            project=project,
            git_service=self.git_service,
            window=self.window,
            checkout_callback=lambda commit_hash, git_window: self.checkout_commit_callback(
                project.path, project.name, commit_hash, git_window
            ),
            progress_callback=self._update_status,
            completion_callback=self._handle_git_completion,
        )

        # Standard async execution
        task_manager.run_task(
            command.run_with_progress(), task_name=f"git-{project.name}"
        )

    def _handle_git_completion(self, result):
        """Standard completion callback for Git operations"""
        # Check if the command already created a git window
        if result.data and result.data.get("git_window_created", False):
            # Git window already exists with real-time output, no need for additional handling
            return

        # Only show messages if the command didn't create a window
        if result.is_success:
            self._show_git_success(result.data)
        else:
            self._show_git_error(result.error)

    def _show_git_success(self, data):
        """Show Git success message"""
        commits_count = len(data.get("commits", []))
        fetch_success = data.get("fetch_success", False)
        fetch_message = data.get("fetch_message", "")

        if not fetch_success and "No remote repository" not in fetch_message:
            self.window.after(
                0,
                lambda: messagebox.showwarning(
                    "Fetch Warning",
                    f"Could not fetch latest commits:\n{fetch_message}\n\nShowing local commits only.",
                ),
            )

    def _show_git_error(self, error):
        """Show Git error message"""
        error_message = f"Error accessing git repository: {error.message}"
        self.window.after(0, lambda: messagebox.showerror("Git Error", error_message))

    def checkout_commit_callback(
        self, project_path, project_name, commit_hash, git_window
    ):
        """Handle commit checkout with proper async pattern"""
        # Confirm checkout
        response = messagebox.askyesno(
            "Confirm Checkout",
            f"Are you sure you want to checkout to commit {commit_hash}?\n\n"
            f"This will change your working directory to that commit.\n"
            f"Any uncommitted changes may be lost.",
        )

        if not response:
            return

        # Run checkout as async task
        async def checkout_async():
            try:
                # Perform checkout
                checkout_result = await self.git_service.checkout_commit(
                    project_path, commit_hash
                )
                success = checkout_result.is_success
                message = checkout_result.message or (
                    checkout_result.error.message
                    if checkout_result.error
                    else "Unknown error"
                )

                if success:
                    self.window.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Checkout Success",
                            f"{message}\n\nProject: {project_name}",
                        ),
                    )
                    if git_window:
                        self.window.after(0, git_window.destroy)
                else:
                    # Check if the error is due to local changes
                    if (
                        "would be overwritten" in message
                        or "local changes" in message.lower()
                    ):
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
                            force_result = await self.git_service.force_checkout_commit(
                                project_path, commit_hash
                            )
                            force_success = force_result.is_success
                            force_message = force_result.message or (
                                force_result.error.message
                                if force_result.error
                                else "Unknown error"
                            )

                            if force_success:
                                self.window.after(
                                    0,
                                    lambda: messagebox.showinfo(
                                        "Checkout Success",
                                        f"{force_message}\n\nProject: {project_name}",
                                    ),
                                )
                                if git_window:
                                    self.window.after(0, git_window.destroy)
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
            except Exception as e:
                logger.exception("Error during checkout for %s", project_name)
                error_msg = f"Error during checkout: {str(e)}"
                self.window.after(
                    0, lambda: messagebox.showerror("Checkout Error", error_msg)
                )

        # Run with proper task naming
        task_manager.run_task(
            checkout_async(), task_name=f"checkout-{project_name}-{commit_hash[:8]}"
        )

    def git_checkout_all(self, project_group: ProjectGroup):
        """Standardized async Git checkout all operation using command pattern"""
        command = GitCheckoutAllCommand(
            project_group=project_group,
            git_service=self.git_service,
            window=self.window,
            progress_callback=self._update_status,
            completion_callback=self._handle_git_checkout_all_completion,
        )

        # Standard async execution
        task_manager.run_task(
            command.run_with_progress(),
            task_name=f"git-checkout-all-{project_group.name}",
        )

    def _handle_git_checkout_all_completion(self, result):
        """Standard completion callback for Git checkout all operations"""
        # Check if the command already created a git window
        if result.data and result.data.get("git_window_created", False):
            # Git window already exists with real-time output, no need for additional handling
            return

        # Only show messages if the command didn't create a window
        if result.is_success:
            self._show_git_checkout_all_success(result.data)
        else:
            self._show_git_checkout_all_error(result.error)

    def _show_git_checkout_all_success(self, data):
        """Show Git checkout all success message"""
        commits_count = len(data.get("commits", []))
        versions_count = len(data.get("all_versions", []))
        fetch_success = data.get("fetch_success", False)
        fetch_message = data.get("fetch_message", "")

        if not fetch_success and "No remote repository" not in fetch_message:
            self.window.after(
                0,
                lambda: messagebox.showwarning(
                    "Fetch Warning",
                    f"Could not fetch latest commits:\n{fetch_message}\n\n"
                    f"Showing local commits only for {versions_count} versions.",
                ),
            )

    def _show_git_checkout_all_error(self, error):
        """Show Git checkout all error message"""
        error_message = f"Error accessing git repository: {error.message}"
        self.window.after(
            0, lambda: messagebox.showerror("Git Checkout All Error", error_message)
        )

    def sync_run_tests_from_pre_edit(self, project_group: ProjectGroup):
        """Standardized async sync operation using command pattern"""
        command = SyncRunTestsCommand(
            project_group=project_group,
            sync_service=self.sync_service,
            progress_callback=self._update_status,
            completion_callback=self._handle_sync_completion,
        )

        # Standard async execution
        task_manager.run_task(
            command.run_with_progress(), task_name=f"sync-{project_group.name}"
        )

    def _handle_sync_completion(self, result):
        """Standard completion callback for sync operations"""
        if result.is_success:
            self._show_sync_success(result.data)
        elif result.is_partial:
            self._show_sync_partial(result.data, result.error)
        else:
            self._show_sync_error(result.error)

    def _show_sync_success(self, data):
        """Show sync success message"""
        synced_count = data.get("success_count", 0)
        total_targets = data.get("total_targets", 0)
        synced_paths = data.get("synced_paths", [])

        paths_text = "\n".join([f"• {path}" for path in synced_paths[:10]])
        if len(synced_paths) > 10:
            paths_text += f"\n... and {len(synced_paths) - 10} more"

        self.window.after(
            0,
            lambda: messagebox.showinfo(
                "Sync Complete",
                f"Successfully synced run_tests.sh from pre-edit!\n\n"
                f"Synced to {synced_count}/{total_targets} versions:\n{paths_text}",
            ),
        )

    def _show_sync_partial(self, data, error):
        """Show partial sync message"""
        synced_count = data.get("success_count", 0)
        total_targets = data.get("total_targets", 0)
        failed_syncs = data.get("failed_syncs", [])

        failed_text = "\n".join([f"• {item}" for item in failed_syncs[:5]])
        if len(failed_syncs) > 5:
            failed_text += f"\n... and {len(failed_syncs) - 5} more"

        self.window.after(
            0,
            lambda: messagebox.showwarning(
                "Partial Sync",
                f"Partially synced run_tests.sh ({synced_count}/{total_targets})\n\n"
                f"Failed syncs:\n{failed_text}\n\nError: {error.message}",
            ),
        )

    def _show_sync_error(self, error):
        """Show sync error message"""
        error_message = f"Failed to sync run_tests.sh: {error.message}"
        self.window.after(0, lambda: messagebox.showerror("Sync Error", error_message))

    def edit_run_tests(self, project_group: ProjectGroup):
        """Open the edit run_tests.sh window"""
        edit_window = EditRunTestsWindow(
            self.window, project_group, self._handle_run_tests_edit
        )
        edit_window.create_window()

    def _handle_run_tests_edit(
        self,
        project_group: ProjectGroup,
        selected_tests: List[str],
        language: str = "python",
    ):
        """Handle the run_tests.sh edit operation"""

        async def edit_run_tests_async():
            output_window = None
            try:
                # Create output window for showing progress
                output_window = TerminalOutputWindow(
                    self.window, f"Editing run_tests.sh - {project_group.name}"
                )
                output_window.create_window()
                output_window.update_status(
                    "Updating run_tests.sh files...", COLORS["warning"]
                )

                # Get all versions in the project group
                all_versions = project_group.get_all_versions()

                if not all_versions:
                    output_window.update_status(
                        "Error: No versions found", COLORS["error"]
                    )
                    output_window.append_output("No versions found in project group\n")
                    return

                output_window.append_output(
                    f"Found {len(all_versions)} versions to update:\n"
                )
                for version in all_versions:
                    output_window.append_output(
                        f"  • {version.parent}/{version.name}\n"
                    )
                output_window.append_output("\n")

                # Create the new test command with forward slashes
                if len(selected_tests) == 1:
                    # Single test file
                    test_paths = selected_tests[0].replace("\\", "/")
                else:
                    # Multiple test files - join them with spaces, ensure forward slashes
                    test_paths = " ".join(
                        [test.replace("\\", "/") for test in selected_tests]
                    )

                # Generate language-specific command
                new_test_command = self._generate_test_command(language, test_paths)

                output_window.append_output(
                    f"New {language} test command: {new_test_command}\n\n"
                )

                successful_updates = []
                failed_updates = []

                # Update run_tests.sh in each version
                for i, version in enumerate(all_versions):
                    output_window.update_status(
                        f"Updating {version.parent} ({i+1}/{len(all_versions)})",
                        COLORS["warning"],
                    )
                    output_window.append_output(
                        f"📝 Updating {version.parent}/{version.name}...\n"
                    )

                    run_tests_path = version.path / "run_tests.sh"

                    try:
                        if run_tests_path.exists():
                            # Read current content
                            current_content = run_tests_path.read_text()

                            # Import regex for pytest command parsing
                            import re

                            # Replace pytest command line, preserving other lines
                            lines = current_content.split("\n")
                            new_lines = []

                            # Ensure proper shebang line
                            if lines and lines[0].startswith("#!"):
                                # Already has shebang, validate it's appropriate
                                shebang = lines[0].strip()
                                if shebang not in [
                                    "#!/bin/sh",
                                    "#!/bin/bash",
                                    "#!/usr/bin/env bash",
                                ]:
                                    # Fix shebang to use /bin/sh for maximum compatibility
                                    lines[0] = "#!/bin/sh"
                                    output_window.append_output(
                                        f"   🔧 Fixed shebang: {shebang} -> #!/bin/sh\n"
                                    )
                            else:
                                # No shebang, add one
                                lines.insert(0, "#!/bin/sh")
                                output_window.append_output(
                                    f"   🔧 Added shebang: #!/bin/sh\n"
                                )

                            updated_line = False
                            for line in lines:
                                stripped_line = line.strip()
                                # Check if line contains test command for this language
                                if self._is_test_command_line(stripped_line, language):
                                    # Generate new command preserving prefixes
                                    old_command = stripped_line
                                    final_command = self._preserve_command_prefix(
                                        old_command, new_test_command, language
                                    )
                                    new_lines.append(final_command)

                                    output_window.append_output(
                                        f"   🔄 Updated {language} test command\n"
                                    )
                                    output_window.append_output(
                                        f"      Old: {old_command}\n"
                                    )
                                    output_window.append_output(
                                        f"      New: {final_command}\n"
                                    )
                                    updated_line = True
                                else:
                                    # Keep other lines as-is
                                    new_lines.append(line)

                            # If no test command was found, append the new command
                            if not updated_line:
                                new_lines.append(new_test_command)
                                output_window.append_output(
                                    f"   ➕ Added new {language} test command: {new_test_command}\n"
                                )

                            # Write updated content with Unix line endings
                            new_content = "\n".join(new_lines)
                            # Ensure Unix line endings (LF only) for compatibility with Docker containers
                            run_tests_path.write_text(new_content, newline="\n")
                            # Ensure the file has execute permissions
                            run_tests_path.chmod(0o755)

                            output_window.append_output(
                                f"   ✅ Successfully updated {run_tests_path}\n"
                            )
                            successful_updates.append(
                                f"{version.parent}/{version.name}"
                            )
                        else:
                            # Create new run_tests.sh file with Unix line endings
                            run_tests_content = f"#!/bin/sh\n{new_test_command}\n"
                            # Ensure Unix line endings (LF only) for compatibility with Docker containers
                            run_tests_path.write_text(run_tests_content, newline="\n")
                            run_tests_path.chmod(0o755)  # Make executable

                            output_window.append_output(
                                f"   ✅ Created new {run_tests_path}\n"
                            )
                            successful_updates.append(
                                f"{version.parent}/{version.name}"
                            )

                    except Exception as e:
                        error_msg = str(e)
                        output_window.append_output(f"   ❌ Failed: {error_msg}\n")
                        failed_updates.append(
                            f"{version.parent}/{version.name} ({error_msg})"
                        )

                # Final summary
                output_window.append_output("\n" + "=" * 50 + "\n")
                output_window.append_output("SUMMARY:\n")
                output_window.append_output(
                    f"✅ Successful updates: {len(successful_updates)}\n"
                )
                output_window.append_output(
                    f"❌ Failed updates: {len(failed_updates)}\n"
                )

                if successful_updates:
                    output_window.append_output("\nSuccessful updates:\n")
                    for update in successful_updates:
                        output_window.append_output(f"  • {update}\n")

                if failed_updates:
                    output_window.append_output("\nFailed updates:\n")
                    for update in failed_updates:
                        output_window.append_output(f"  • {update}\n")

                # Update status
                if len(successful_updates) == len(all_versions):
                    output_window.update_status(
                        "All run_tests.sh files updated successfully!",
                        COLORS["success"],
                    )
                elif successful_updates:
                    output_window.update_status(
                        "Partially completed with some failures", COLORS["warning"]
                    )
                else:
                    output_window.update_status("All updates failed", COLORS["error"])

                # Add final buttons
                output_window.add_final_buttons(
                    copy_text=(
                        output_window.text_area.get("1.0", "end-1c")
                        if output_window.text_area
                        else ""
                    )
                )

            except asyncio.CancelledError:
                logger.info("Edit run_tests was cancelled for %s", project_group.name)
                if output_window:
                    output_window.update_status("Operation cancelled", COLORS["error"])
                raise
            except Exception as e:
                logger.exception("Error editing run_tests for %s", project_group.name)
                if output_window:
                    output_window.update_status("Error occurred", COLORS["error"])
                    output_window.append_output(f"\nError: {str(e)}\n")
                else:
                    self.window.after(
                        0,
                        lambda: messagebox.showerror(
                            "Edit run_tests Error",
                            f"Error editing run_tests.sh: {str(e)}",
                        ),
                    )

        # Run the async operation
        task_manager.run_task(
            edit_run_tests_async(), task_name=f"edit-run-tests-{project_group.name}"
        )

    def _generate_test_command(self, language: str, test_paths: str) -> str:
        """Generate language-specific test command"""
        from config.commands import TEST_COMMAND_TEMPLATES, DEFAULT_TEST_COMMANDS

        if not test_paths or not test_paths.strip():
            # Use default command for the language
            return DEFAULT_TEST_COMMANDS.get(language, "pytest -vv -s tests/")
        # Use template with specific test paths
        template = TEST_COMMAND_TEMPLATES.get(language, "pytest -vv -s {test_paths}")
        return template.format(test_paths=test_paths)

    def _is_test_command_line(self, line: str, language: str) -> bool:
        """Check if a line contains a test command for the specified language"""
        from config.commands import TEST_COMMAND_PATTERNS

        if line.startswith("#"):
            return False

        patterns = TEST_COMMAND_PATTERNS.get(language, ["pytest"])

        # For languages with multiple patterns, check appropriately
        if language == "java":
            return "mvn" in line and "test" in line
        elif language == "typescript":
            return ("npm run build" in line and "npm test" in line) or (
                "npm test" in line
            )
        else:
            return any(pattern in line for pattern in patterns)

    def _preserve_command_prefix(
        self, old_command: str, new_command: str, language: str
    ) -> str:
        """Preserve command prefixes when updating test commands"""
        # Language-specific prefix preservation
        if language == "python":
            if "python" not in old_command or "-m pytest" not in old_command:
                return new_command
            python_prefix = old_command.split("pytest")[0] + "pytest"
            # Replace the base command but keep the prefix
            return new_command.replace("pytest", python_prefix, 1)
        elif language in {"javascript", "typescript"}:
            # Handle cases like "export CI=true && npm test"
            if "export" in old_command and "CI=true" in old_command:
                return f"export CI=true\n{new_command}"
            else:
                return new_command
        elif language == "java":
            if "mvn" not in old_command:
                return new_command
            prefix = old_command[: old_command.find("mvn")]
            return f"{prefix}{new_command}" if prefix.strip() else new_command
        else:
            # For other languages, return as-is
            return new_command

    def validate_project_group(self, project_group: ProjectGroup):
        """Standardized async validation operation using command pattern"""
        command = ValidateProjectGroupCommand(
            project_group=project_group,
            validation_service=self.validation_service,
            window=self.window,
            async_bridge=self.async_bridge,
            progress_callback=self._update_status,
            completion_callback=self._handle_validation_completion,
        )

        # Standard async execution
        task_manager.run_task(
            command.run_with_progress(), task_name=f"validate-{project_group.name}"
        )

    def _handle_validation_completion(self, result):
        """Standard completion callback for validation operations"""
        # The command creates its own terminal window with real-time streaming output
        # and includes the Copy Validation ID button functionality.
        # No additional popup windows are needed.
        pass

    def _show_validation_success(self, data):
        """Show validation success message"""
        validation_id = data.get("validation_id", "")
        if validation_id:
            message = (
                f"Validation completed successfully!\nValidation ID: {validation_id}"
            )
        else:
            message = "Validation completed successfully!"

        self.window.after(
            0,
            lambda: messagebox.showinfo("Validation Complete", message),
        )

    def _show_validation_error(self, error):
        """Show validation error message"""
        error_message = f"Validation failed: {error.message}"
        self.window.after(
            0, lambda: messagebox.showerror("Validation Error", error_message)
        )

    def build_docker_files_for_project_group(self, project_group: ProjectGroup):
        """Standardized async Docker files build operation using command pattern"""
        command = BuildDockerFilesCommand(
            project_group=project_group,
            docker_files_service=self.docker_files_service,
            window=self.window,
            async_bridge=self.async_bridge,
            progress_callback=self._update_status,
            completion_callback=self._handle_build_completion,
        )

        # Standard async execution
        task_manager.run_task(
            command.run_with_progress(), task_name=f"build-docker-{project_group.name}"
        )

    def _handle_build_completion(self, result):
        """Standard completion callback for Docker files build operations"""
        # The command creates its own terminal window with real-time streaming output
        # and handles user prompts for existing files.
        # No additional popup windows are needed.
        pass

    def _show_build_success(self, data):
        """Show Docker files build success message"""
        message = f"Docker files build completed successfully for {data.get('project_group_name', 'project group')}"
        self.window.after(
            0,
            lambda: messagebox.showinfo("Build Complete", message),
        )

    def _show_build_error(self, error):
        """Show Docker files build error message"""
        error_message = f"Docker files build failed: {error.message}"
        self.window.after(0, lambda: messagebox.showerror("Build Error", error_message))

    def _extract_validation_id(self, raw_output: str) -> str:
        """
        Extract the validation ID from the validation output
        Returns the ID string or empty string if not found
        """
        import re

        # Look for the validation ID in the format "UNIQUE VALIDATION ID: xxxxxxxxx"
        pattern = r"UNIQUE VALIDATION ID:\s*([a-f0-9]+)"
        if match := re.search(pattern, raw_output, re.IGNORECASE):
            return match.group(1)

        # Fallback: look for the ID in the box format (standalone hex string)
        # Look for lines that contain only hexadecimal characters (the ID in the box)
        lines = raw_output.split("\n")
        for line in lines:
            line = line.strip()
            # Remove any container prefixes like "codebase-validator  | "
            clean_line = re.sub(r"^.*\|\s*", "", line).strip()
            # Check if it's a hex string of reasonable length (validation IDs are typically 16 chars)
            if re.match(r"^[a-f0-9]{8,32}$", clean_line):
                return clean_line

        return ""

    def open_add_project_window(self):
        """Open the add project window"""
        add_project_window = AddProjectWindow(self.window, self.add_project)
        add_project_window.create_window()

    def add_project(self, repo_url: str, project_name: str):
        """Add a new project by cloning it into all subdirectories"""

        async def add_project_async():
            output_window = None
            try:
                # Create output window for showing progress
                output_window = TerminalOutputWindow(
                    self.window, f"Adding Project: {project_name}"
                )
                output_window.create_window()
                output_window.update_status("Initializing...", COLORS["warning"])

                # Get all subdirectories from SOURCE_DIR
                source_path = Path(SOURCE_DIR)
                subdirs = [
                    d
                    for d in source_path.iterdir()
                    if d.is_dir() and not d.name.startswith(".")
                ]

                if not subdirs:
                    output_window.update_status(
                        "Error: No subdirectories found", COLORS["error"]
                    )
                    output_window.append_output(
                        f"No subdirectories found in {SOURCE_DIR}\n"
                    )
                    return

                output_window.append_output(
                    f"Found {len(subdirs)} subdirectories to clone into:\n"
                )
                for subdir in subdirs:
                    output_window.append_output(f"  • {subdir.name}\n")
                output_window.append_output("\n")

                successful_clones = []
                failed_clones = []

                # Clone repository into each subdirectory
                for i, subdir in enumerate(subdirs):
                    output_window.update_status(
                        f"Cloning into {subdir.name} ({i+1}/{len(subdirs)})",
                        COLORS["warning"],
                    )
                    output_window.append_output(f"📁 Cloning into {subdir.name}/...\n")

                    # Check if project already exists
                    target_path = subdir / project_name
                    if target_path.exists():
                        output_window.append_output(
                            f"   ⚠️  Project already exists at {target_path}\n"
                        )
                        failed_clones.append(f"{subdir.name} (already exists)")
                        continue

                    # Perform the clone
                    clone_result = await self.git_service.clone_repository(
                        repo_url, project_name, subdir
                    )
                    success = clone_result.is_success
                    message = clone_result.message or (
                        clone_result.error.message
                        if clone_result.error
                        else "Unknown error"
                    )

                    if success:
                        output_window.append_output(f"   ✅ {message}\n")
                        successful_clones.append(subdir.name)
                    else:
                        output_window.append_output(f"   ❌ {message}\n")
                        failed_clones.append(f"{subdir.name} ({message})")

                # Final summary
                output_window.append_output("\n" + "=" * 50 + "\n")
                output_window.append_output("SUMMARY:\n")
                output_window.append_output(
                    f"✅ Successful clones: {len(successful_clones)}\n"
                )
                output_window.append_output(f"❌ Failed clones: {len(failed_clones)}\n")

                if successful_clones:
                    output_window.append_output("\nSuccessful clones:\n")
                    for clone in successful_clones:
                        output_window.append_output(f"  • {clone}\n")

                if failed_clones:
                    output_window.append_output("\nFailed clones:\n")
                    for clone in failed_clones:
                        output_window.append_output(f"  • {clone}\n")

                # Update status
                if len(successful_clones) == len(subdirs):
                    output_window.update_status(
                        "All clones completed successfully!", COLORS["success"]
                    )
                    # Trigger refresh after successful completion
                    self.window.after(1000, self.refresh_projects)
                elif successful_clones:
                    output_window.update_status(
                        "Partially completed with some failures", COLORS["warning"]
                    )
                    # Trigger refresh after partial completion
                    self.window.after(1000, self.refresh_projects)
                else:
                    output_window.update_status("All clones failed", COLORS["error"])

                # Add final buttons
                output_window.add_final_buttons(
                    copy_text=(
                        output_window.text_area.get("1.0", "end-1c")
                        if output_window.text_area
                        else ""
                    ),
                    additional_buttons=[
                        {
                            "text": "Refresh Projects",
                            "command": lambda: (
                                self.refresh_projects(),
                                output_window.destroy(),
                            ),
                            "style": "refresh",
                        }
                    ],
                )

            except asyncio.CancelledError:
                logger.info("Add project was cancelled for %s", project_name)
                if output_window:
                    output_window.update_status("Operation cancelled", COLORS["error"])
                raise
            except Exception as e:
                logger.exception("Error adding project %s", project_name)
                if output_window:
                    output_window.update_status("Error occurred", COLORS["error"])
                    output_window.append_output(f"\nError: {str(e)}\n")
                else:
                    self.window.after(
                        0,
                        lambda: messagebox.showerror(
                            "Add Project Error", f"Error adding project: {str(e)}"
                        ),
                    )

        # Run the async operation
        task_manager.run_task(
            add_project_async(), task_name=f"add-project-{project_name}"
        )

    def refresh_projects(self):
        """Refresh the project list"""
        # Clear existing widgets using MainWindow's interface
        self.main_window.clear_content()

        # Repopulate
        self.load_projects()

    def run(self):
        """Start the GUI"""
        self.main_window.run()


def main():
    """Main function to run the control panel"""
    print("Starting Project Control Panel...")
    print(f"Source directory: {SOURCE_DIR}")

    app = ProjectControlPanel(SOURCE_DIR)
    app.run()


if __name__ == "__main__":
    main()
