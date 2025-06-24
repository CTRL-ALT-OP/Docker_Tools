"""
Standardized Async Commands for GUI Operations
Implements the AsyncCommand pattern for all GUI-triggered async operations
"""

import uuid
import asyncio
from pathlib import Path
from typing import Dict, Any, Callable

from utils.async_base import AsyncCommand, AsyncResult, ProcessError, ValidationError
from models.project import Project
from services.project_group_service import ProjectGroup


class CleanupProjectCommand(AsyncCommand):
    """Standardized command for project cleanup operations"""

    def __init__(self, project: Project, file_service, **kwargs):
        super().__init__(**kwargs)
        self.project = project
        self.file_service = file_service

    async def execute(self) -> AsyncResult[Dict[str, Any]]:
        """Execute the cleanup command"""
        try:
            # Update progress
            self._update_progress("Scanning for cleanup items...", "info")

            # Scan for items to cleanup
            scan_result = await self.file_service.scan_for_cleanup_items(
                self.project.path
            )
            if scan_result.is_error:
                return AsyncResult.error_result(scan_result.error)

            cleanup_data = scan_result.data

            # Check if there are items to cleanup
            if not cleanup_data.directories and not cleanup_data.files:
                return AsyncResult.success_result(
                    {"message": "No items found to cleanup", "deleted_items": []},
                    message="No cleanup needed",
                )

            self._update_progress("Removing cleanup items...", "warning")

            # Perform cleanup
            cleanup_result = await self.file_service.cleanup_project_items(
                self.project.path
            )

            if cleanup_result.is_error:
                return AsyncResult.error_result(cleanup_result.error)

            result_data = {
                "message": f"Cleanup completed for {self.project.name}",
                "deleted_directories": cleanup_result.data.deleted_directories,
                "deleted_files": cleanup_result.data.deleted_files,
                "total_deleted_size": cleanup_result.data.total_deleted_size,
                "failed_deletions": cleanup_result.data.failed_deletions,
            }

            self._update_progress("Cleanup completed successfully", "success")

            return AsyncResult.success_result(
                result_data, message=f"Successfully cleaned up {self.project.name}"
            )

        except Exception as e:
            self.logger.exception(f"Cleanup command failed for {self.project.name}")
            return AsyncResult.error_result(
                ProcessError(f"Cleanup failed: {str(e)}", error_code="CLEANUP_ERROR")
            )


class ArchiveProjectCommand(AsyncCommand):
    """Standardized command for project archive operations"""

    def __init__(self, project: Project, file_service, project_service, **kwargs):
        super().__init__(**kwargs)
        self.project = project
        self.file_service = file_service
        self.project_service = project_service

    async def execute(self) -> AsyncResult[Dict[str, Any]]:
        """Execute the archive command"""
        try:
            self._update_progress("Scanning for cleanup items...", "info")

            # First, scan for directories and files that need cleanup
            scan_result = await self.file_service.scan_for_cleanup_items(
                self.project.path
            )

            cleanup_needed = False
            cleanup_message = ""

            if scan_result.is_success and scan_result.data.item_count > 0:
                cleanup_needed = True
                cleanup_items = []

                if scan_result.data.directories:
                    cleanup_items.append("Directories:")
                    cleanup_items.extend(
                        [f"  • {d.name}" for d in scan_result.data.directories[:5]]
                    )
                    if len(scan_result.data.directories) > 5:
                        cleanup_items.append(
                            f"  ... and {len(scan_result.data.directories) - 5} more"
                        )

                if scan_result.data.files:
                    if cleanup_items:
                        cleanup_items.append("")
                    cleanup_items.append("Files:")
                    cleanup_items.extend(
                        [f"  • {f.name}" for f in scan_result.data.files[:5]]
                    )
                    if len(scan_result.data.files) > 5:
                        cleanup_items.append(
                            f"  ... and {len(scan_result.data.files) - 5} more"
                        )

                cleanup_message = "\n".join(cleanup_items)

            # Get archive name
            archive_name = self.project_service.get_archive_name(
                self.project.parent, self.project.name
            )

            self._update_progress("Creating archive...", "info")

            # Create archive
            archive_result = await self.file_service.create_archive(
                self.project.path, archive_name
            )

            if archive_result.is_error:
                return AsyncResult.error_result(archive_result.error)

            result_data = {
                "message": f"Archive created for {self.project.name}",
                "archive_path": str(archive_result.data.archive_path),
                "archive_size": archive_result.data.archive_size,
                "files_archived": archive_result.data.files_archived,
                "compression_ratio": archive_result.data.compression_ratio,
                "cleanup_needed": cleanup_needed,
                "cleanup_message": cleanup_message,
            }

            self._update_progress("Archive created successfully", "success")

            return AsyncResult.success_result(
                result_data, message=f"Successfully archived {self.project.name}"
            )

        except Exception as e:
            self.logger.exception(f"Archive command failed for {self.project.name}")
            return AsyncResult.error_result(
                ProcessError(f"Archive failed: {str(e)}", error_code="ARCHIVE_ERROR")
            )


class DockerBuildAndTestCommand(AsyncCommand):
    """Standardized command for Docker build and test operations with real-time streaming"""

    def __init__(self, project: Project, docker_service, window=None, **kwargs):
        super().__init__(**kwargs)
        self.project = project
        self.docker_service = docker_service
        self.docker_tag = f"{self.project.parent}_{self.project.name}".lower()
        self.window = window
        self.terminal_window = None

    async def execute(self) -> AsyncResult[Dict[str, Any]]:
        """Execute the Docker build and test command with real-time streaming"""
        try:
            # Import here to avoid circular imports
            from gui import TerminalOutputWindow
            import asyncio

            self._update_progress("Starting Docker build and test...", "info")

            # Create terminal window immediately (before starting operation)
            def create_window():
                self.terminal_window = TerminalOutputWindow(
                    self.window, f"Docker Build & Test - {self.project.name}"
                )
                self.terminal_window.create_window()
                self.terminal_window.update_status(
                    "Starting Docker build...", "#f39c12"
                )

            if self.window:
                self.window.after(0, create_window)
                await asyncio.sleep(0.1)  # Wait for window creation

            # Define streaming callbacks that update the GUI in real-time
            def streaming_output_callback(message: str):
                """Real-time output streaming to GUI"""
                if self.terminal_window:
                    self.terminal_window.append_output(message)

            def streaming_status_callback(status: str, color: str):
                """Real-time status updates to GUI"""
                if self.terminal_window:
                    self.terminal_window.update_status(status, color)

            # Execute Docker build and test with real-time streaming
            result = await self.docker_service.build_and_test(
                self.project.path,
                self.docker_tag,
                progress_callback=streaming_output_callback,
                status_callback=streaming_status_callback,
            )

            # Handle results and update terminal window
            if result.is_success:
                if self.terminal_window:
                    self.terminal_window.update_status(
                        "Build and test completed successfully!", "#27ae60"
                    )
                    self.terminal_window.append_output(
                        "\n✅ All operations completed successfully!\n"
                    )
            elif result.is_partial:
                if self.terminal_window:
                    self.terminal_window.update_status(
                        "Build successful, some tests failed", "#f39c12"
                    )
                    self.terminal_window.append_output(
                        "\n⚠️ Build completed but some tests failed.\n"
                    )
            else:
                if self.terminal_window:
                    self.terminal_window.update_status(
                        "Build and test failed", "#e74c3c"
                    )
                    self.terminal_window.append_output("\n❌ Build and test failed.\n")

            # Add final buttons for interaction
            if self.terminal_window and self.window:

                def add_buttons():
                    if self.terminal_window.text_area:
                        full_output = self.terminal_window.text_area.get(
                            "1.0", "end-1c"
                        )
                        self.terminal_window.add_final_buttons(copy_text=full_output)

                self.window.after(0, add_buttons)

            result_data = {
                "message": f"Docker build and test completed for {self.project.name}",
                "docker_tag": self.docker_tag,
                "build_data": result.data.get("build_data", {}) if result.data else {},
                "test_data": result.data.get("test_data", {}) if result.data else {},
                "project_name": self.project.name,
                "terminal_created": self.terminal_window is not None,
            }

            if result.is_error:
                return AsyncResult.error_result(result.error)
            elif result.is_partial:
                return AsyncResult.partial_result(result_data, result.error)
            else:
                return AsyncResult.success_result(result_data)

        except Exception as e:
            self.logger.exception(f"Docker command failed for {self.project.name}")
            if self.terminal_window:
                self.terminal_window.update_status("Error occurred", "#e74c3c")
                self.terminal_window.append_output(f"\n❌ Error: {str(e)}\n")

            return AsyncResult.error_result(
                ProcessError(
                    f"Docker build and test failed: {str(e)}", error_code="DOCKER_ERROR"
                )
            )


class GitViewCommand(AsyncCommand):
    """Standardized command for Git operations with real-time window coordination"""

    def __init__(
        self,
        project: Project,
        git_service,
        window=None,
        checkout_callback=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.project = project
        self.git_service = git_service
        self.window = window
        self.checkout_callback = checkout_callback
        self.git_window = None

    async def execute(self) -> AsyncResult[Dict[str, Any]]:
        """Execute the Git view command with real-time streaming"""
        try:
            # Import here to avoid circular imports
            from gui import GitCommitWindow
            import asyncio

            self._update_progress("Initializing Git view...", "info")

            # Create git window immediately with loading state
            def create_git_window():
                # Create a wrapper callback that passes the git window reference
                def checkout_wrapper(commit_hash):
                    if self.checkout_callback:
                        # Call the original callback with the git window reference
                        self.checkout_callback(commit_hash, self.git_window)

                self.git_window = GitCommitWindow(
                    self.window,
                    self.project.name,
                    [],  # Start with empty commits
                    checkout_wrapper,
                    git_service=self.git_service,
                    project_path=self.project.path,
                )
                # Show window immediately with loading animation
                self.git_window.create_window_with_loading(True, "Initializing...")

            if self.window:
                self.window.after(0, create_git_window)
                await asyncio.sleep(0.1)  # Wait for window creation

            # Update status to show fetching
            if self.git_window:
                self.git_window.update_status("Fetching latest commits...")

            self._update_progress("Fetching latest commits...", "info")

            # Fetch latest commits
            fetch_result = await self.git_service.fetch_latest_commits(
                self.project.path
            )

            fetch_success = fetch_result.is_success
            fetch_message = fetch_result.message or (
                fetch_result.error.message if fetch_result.error else "Unknown error"
            )

            if (
                not fetch_success
                and "No remote repository" not in fetch_message
                and self.git_window
            ):
                self.git_window.update_status(f"Fetch warning: {fetch_message}")

            # Update status to show loading commits
            if self.git_window:
                self.git_window.update_status("Loading commit history...")

            self._update_progress("Loading commit history...", "info")

            # Get commits
            commits_result = await self.git_service.get_git_commits(self.project.path)

            if commits_result.is_error:
                error_msg = commits_result.error.message
                if self.git_window:
                    self.git_window.update_with_error(error_msg)
                return AsyncResult.error_result(commits_result.error)

            commits = commits_result.data or []

            if not commits:
                if self.git_window:
                    self.git_window.update_with_no_commits()
                return AsyncResult.success_result(
                    {
                        "message": "No commits found in repository",
                        "project_name": self.project.name,
                        "commits": [],
                        "git_window_created": self.git_window is not None,
                    }
                )

            # Update window with commits (streaming complete)
            if self.git_window:
                self.git_window.update_with_commits(commits)
                self.git_window.update_status(
                    f"Loaded all {len(commits)} commits from repository"
                )

            result_data = {
                "message": f"Git information loaded for {self.project.name}",
                "project_path": str(self.project.path),
                "project_name": self.project.name,
                "fetch_success": fetch_success,
                "fetch_message": fetch_message,
                "commits": commits,
                "git_window_created": self.git_window is not None,
            }

            self._update_progress(f"Loaded {len(commits)} commits", "success")

            return AsyncResult.success_result(
                result_data,
                message=f"Successfully loaded Git information for {self.project.name}",
            )

        except Exception as e:
            self.logger.exception(f"Git command failed for {self.project.name}")
            error_msg = f"Error accessing git repository: {str(e)}"
            if self.git_window:
                self.git_window.update_with_error(error_msg)

            return AsyncResult.error_result(
                ProcessError(f"Git operation failed: {str(e)}", error_code="GIT_ERROR")
            )


class GitCheckoutAllCommand(AsyncCommand):
    """Standardized command for Git checkout operations across all project versions"""

    def __init__(
        self,
        project_group: ProjectGroup,
        git_service,
        window=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.project_group = project_group
        self.git_service = git_service
        self.window = window
        self.git_window = None

    async def execute(self) -> AsyncResult[Dict[str, Any]]:
        """Execute the Git checkout all command with real-time streaming"""
        try:
            # Import here to avoid circular imports
            from gui.popup_windows import GitCheckoutAllWindow
            import asyncio

            self._update_progress("Initializing Git checkout all view...", "info")

            # Get all project versions
            all_versions = self.project_group.get_all_versions()
            if not all_versions:
                return AsyncResult.error_result(
                    ProcessError("No project versions found", error_code="NO_VERSIONS")
                )

            # Use the first version to get the git commits (they should all be the same repo)
            representative_project = all_versions[0]

            # Create git checkout all window immediately with loading state
            def create_git_window():
                def checkout_all_callback(commit_hash):
                    # This will handle checkout to all versions
                    self._checkout_all_versions(commit_hash, all_versions)

                self.git_window = GitCheckoutAllWindow(
                    self.window,
                    self.project_group.name,
                    [],  # Start with empty commits
                    checkout_all_callback,
                    git_service=self.git_service,
                    project_group=self.project_group,
                    all_versions=all_versions,
                )
                # Show window immediately with loading animation
                self.git_window.create_window_with_loading(True, "Initializing...")

            if self.window:
                self.window.after(0, create_git_window)
                await asyncio.sleep(0.1)  # Wait for window creation

            # Update status to show fetching
            if self.git_window:
                self.git_window.update_status("Fetching latest commits...")

            self._update_progress("Fetching latest commits...", "info")

            # Fetch latest commits from the representative project
            fetch_result = await self.git_service.fetch_latest_commits(
                representative_project.path
            )

            fetch_success = fetch_result.is_success
            fetch_message = fetch_result.message or (
                fetch_result.error.message if fetch_result.error else "Unknown error"
            )

            if (
                not fetch_success
                and "No remote repository" not in fetch_message
                and self.git_window
            ):
                self.git_window.update_status(f"Fetch warning: {fetch_message}")

            # Update status to show loading commits
            if self.git_window:
                self.git_window.update_status("Loading commit history...")

            self._update_progress("Loading commit history...", "info")

            # Get commits from the representative project
            commits_result = await self.git_service.get_git_commits(
                representative_project.path
            )

            if commits_result.is_error:
                error_msg = commits_result.error.message
                if self.git_window:
                    self.git_window.update_with_error(error_msg)
                return AsyncResult.error_result(commits_result.error)

            commits = commits_result.data or []

            if not commits:
                if self.git_window:
                    self.git_window.update_with_no_commits()
                return AsyncResult.success_result(
                    {
                        "message": "No commits found in repository",
                        "project_group_name": self.project_group.name,
                        "commits": [],
                        "git_window_created": self.git_window is not None,
                    }
                )

            # Update window with commits (streaming complete)
            if self.git_window:
                self.git_window.update_with_commits(commits)
                self.git_window.update_status(
                    f"Loaded all {len(commits)} commits. Ready to checkout to {len(all_versions)} versions."
                )

            result_data = {
                "message": f"Git information loaded for {self.project_group.name}",
                "project_group_name": self.project_group.name,
                "fetch_success": fetch_success,
                "fetch_message": fetch_message,
                "commits": commits,
                "all_versions": all_versions,
                "git_window_created": self.git_window is not None,
            }

            self._update_progress(
                f"Loaded {len(commits)} commits for {len(all_versions)} versions",
                "success",
            )

            return AsyncResult.success_result(
                result_data,
                message=f"Successfully loaded Git information for {self.project_group.name}",
            )

        except Exception as e:
            self.logger.exception(
                f"Git checkout all command failed for {self.project_group.name}"
            )
            error_msg = f"Error accessing git repository: {str(e)}"
            if self.git_window:
                self.git_window.update_with_error(error_msg)

            return AsyncResult.error_result(
                ProcessError(
                    f"Git checkout all operation failed: {str(e)}",
                    error_code="GIT_CHECKOUT_ALL_ERROR",
                )
            )

    def _checkout_all_versions(self, commit_hash: str, all_versions):
        """Handle checkout to all versions of the project"""
        # Import here to avoid circular imports
        import tkinter as tk
        from tkinter import messagebox
        import asyncio

        # Confirm checkout to all versions
        version_names = [f"{v.parent}/{v.name}" for v in all_versions]
        versions_text = "\n".join([f"• {name}" for name in version_names[:10]])
        if len(version_names) > 10:
            versions_text += f"\n... and {len(version_names) - 10} more versions"

        response = messagebox.askyesno(
            "Confirm Checkout All",
            f"Are you sure you want to checkout ALL versions to commit {commit_hash}?\n\n"
            f"This will affect {len(all_versions)} project versions:\n{versions_text}\n\n"
            f"⚠️  Any uncommitted changes in these projects may be lost.\n\n"
            f"Continue with checkout to all versions?",
        )

        if not response:
            return

        # Run checkout as async task for all versions
        async def checkout_all_async():
            try:
                # Import here to avoid circular imports
                from gui import TerminalOutputWindow

                # Create terminal window for showing progress
                terminal_window = TerminalOutputWindow(
                    self.window, f"Git Checkout All - {self.project_group.name}"
                )
                terminal_window.create_window()
                terminal_window.update_status(
                    "Starting checkout to all versions...", "#f39c12"
                )

                terminal_window.append_output(
                    f"🔀 Git Checkout All - {self.project_group.name}\n"
                )
                terminal_window.append_output(f"Target commit: {commit_hash}\n")
                terminal_window.append_output(
                    f"Versions to checkout: {len(all_versions)}\n\n"
                )

                successful_checkouts = []
                failed_checkouts = []

                # Checkout each version
                for i, project in enumerate(all_versions):
                    terminal_window.update_status(
                        f"Checking out {project.parent}/{project.name} ({i+1}/{len(all_versions)})",
                        "#f39c12",
                    )
                    terminal_window.append_output(
                        f"📁 Checking out {project.parent}/{project.name}...\n"
                    )

                    # Perform the checkout
                    checkout_result = await self.git_service.checkout_commit(
                        project.path, commit_hash
                    )
                    success = checkout_result.is_success
                    message = checkout_result.message or (
                        checkout_result.error.message
                        if checkout_result.error
                        else "Unknown error"
                    )

                    if success:
                        terminal_window.append_output(f"   ✅ {message}\n")
                        successful_checkouts.append(f"{project.parent}/{project.name}")
                    else:
                        # Check if the error is due to local changes
                        if (
                            "would be overwritten" in message
                            or "local changes" in message.lower()
                        ):
                            # Ask if user wants to force checkout for this specific version
                            force_response = messagebox.askyesnocancel(
                                "Local Changes Detected",
                                f"Cannot checkout {project.parent}/{project.name} because local changes would be overwritten:\n\n"
                                f"{message}\n\n"
                                f"Would you like to discard changes and force checkout for this version?\n\n"
                                f"• Yes: Force checkout this version\n"
                                f"• No: Skip this version\n"
                                f"• Cancel: Stop all checkouts",
                            )

                            if force_response is True:  # Yes - force checkout
                                terminal_window.append_output(
                                    f"   ⚠️  Forcing checkout (discarding local changes)...\n"
                                )
                                force_result = (
                                    await self.git_service.force_checkout_commit(
                                        project.path, commit_hash
                                    )
                                )
                                force_success = force_result.is_success
                                force_message = force_result.message or (
                                    force_result.error.message
                                    if force_result.error
                                    else "Unknown error"
                                )

                                if force_success:
                                    terminal_window.append_output(
                                        f"   ✅ {force_message}\n"
                                    )
                                    successful_checkouts.append(
                                        f"{project.parent}/{project.name}"
                                    )
                                else:
                                    terminal_window.append_output(
                                        f"   ❌ Force checkout failed: {force_message}\n"
                                    )
                                    failed_checkouts.append(
                                        f"{project.parent}/{project.name} (force failed: {force_message})"
                                    )
                            elif force_response is False:  # No - skip
                                terminal_window.append_output(
                                    f"   ⏭️  Skipped (preserving local changes)\n"
                                )
                                failed_checkouts.append(
                                    f"{project.parent}/{project.name} (skipped: local changes)"
                                )
                            else:  # Cancel - stop all
                                terminal_window.append_output(
                                    f"   🛑 Checkout cancelled by user\n"
                                )
                                break
                        else:
                            # Some other git error
                            terminal_window.append_output(f"   ❌ {message}\n")
                            failed_checkouts.append(
                                f"{project.parent}/{project.name} ({message})"
                            )

                # Final summary
                terminal_window.append_output("\n" + "=" * 50 + "\n")
                terminal_window.append_output("CHECKOUT SUMMARY:\n")
                terminal_window.append_output(
                    f"✅ Successful checkouts: {len(successful_checkouts)}\n"
                )
                terminal_window.append_output(
                    f"❌ Failed/skipped checkouts: {len(failed_checkouts)}\n"
                )

                if successful_checkouts:
                    terminal_window.append_output("\nSuccessful checkouts:\n")
                    for checkout in successful_checkouts:
                        terminal_window.append_output(f"  • {checkout}\n")

                if failed_checkouts:
                    terminal_window.append_output("\nFailed/skipped checkouts:\n")
                    for checkout in failed_checkouts:
                        terminal_window.append_output(f"  • {checkout}\n")

                # Update final status
                if len(successful_checkouts) == len(all_versions):
                    terminal_window.update_status(
                        "All checkouts completed successfully!", "#27ae60"
                    )
                elif successful_checkouts:
                    terminal_window.update_status(
                        "Partially completed with some failures/skips", "#f39c12"
                    )
                else:
                    terminal_window.update_status(
                        "All checkouts failed or were skipped", "#e74c3c"
                    )

                # Add final buttons
                terminal_window.add_final_buttons(
                    copy_text=(
                        terminal_window.text_area.get("1.0", "end-1c")
                        if terminal_window.text_area
                        else ""
                    )
                )

                # Close the git window if checkout was successful for all versions
                if len(successful_checkouts) == len(all_versions) and self.git_window:
                    self.window.after(0, self.git_window.destroy)

            except asyncio.CancelledError:
                self.logger.info(
                    "Checkout all was cancelled for %s", self.project_group.name
                )
                if "terminal_window" in locals():
                    terminal_window.update_status("Operation cancelled", "#e74c3c")
                raise
            except Exception as e:
                self.logger.exception(
                    "Error during checkout all for %s", self.project_group.name
                )
                error_msg = f"Error during checkout all: {str(e)}"
                if "terminal_window" in locals():
                    terminal_window.update_status("Error occurred", "#e74c3c")
                    terminal_window.append_output(f"\nError: {error_msg}\n")

        # Import task manager and run the async operation
        from utils.async_utils import task_manager

        task_manager.run_task(
            checkout_all_async(),
            task_name=f"checkout-all-{self.project_group.name}-{commit_hash[:8]}",
        )


class SyncRunTestsCommand(AsyncCommand):
    """Standardized command for syncing run_tests.sh from pre-edit"""

    def __init__(self, project_group: ProjectGroup, sync_service, **kwargs):
        super().__init__(**kwargs)
        self.project_group = project_group
        self.sync_service = sync_service

    async def execute(self) -> AsyncResult[Dict[str, Any]]:
        """Execute the sync run tests command"""
        try:
            self._update_progress("Syncing run_tests.sh from pre-edit...", "info")

            # Sync run_tests.sh from pre-edit to other versions
            sync_result = await self.sync_service.sync_file_from_pre_edit(
                self.project_group, "run_tests.sh"
            )

            if sync_result.is_error:
                return AsyncResult.error_result(sync_result.error)

            result_data = {
                "message": f"Sync completed for {self.project_group.name}",
                "file_name": "run_tests.sh",
                "synced_paths": (
                    sync_result.data.synced_paths if sync_result.data else []
                ),
                "failed_syncs": (
                    sync_result.data.failed_syncs if sync_result.data else []
                ),
                "success_count": (
                    sync_result.data.success_count if sync_result.data else 0
                ),
                "total_targets": (
                    sync_result.data.total_targets if sync_result.data else 0
                ),
            }

            if sync_result.is_partial:
                self._update_progress("Sync partially completed", "warning")
                return AsyncResult.partial_result(result_data, sync_result.error)
            else:
                self._update_progress("Sync completed successfully", "success")
                return AsyncResult.success_result(result_data)

        except Exception as e:
            self.logger.exception(f"Sync command failed for {self.project_group.name}")
            return AsyncResult.error_result(
                ProcessError(f"Sync failed: {str(e)}", error_code="SYNC_ERROR")
            )


class ValidateProjectGroupCommand(AsyncCommand):
    """Standardized command for project group validation with complex output processing"""

    def __init__(
        self,
        project_group: ProjectGroup,
        validation_service,
        window=None,
        async_bridge=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.project_group = project_group
        self.validation_service = validation_service
        self.window = window
        self.async_bridge = async_bridge
        self.terminal_window = None

    async def execute(self) -> AsyncResult[Dict[str, Any]]:
        """Execute the validation command with terminal window"""
        try:
            # Import here to avoid circular imports
            from gui import TerminalOutputWindow
            import asyncio

            self._update_progress("Starting validation process...", "info")

            # Create terminal window immediately if window is available
            if self.window and self.async_bridge:
                event_id, window_ready_event = self.async_bridge.create_sync_event()

                def create_window():
                    self.terminal_window = TerminalOutputWindow(
                        self.window, f"Validation - {self.project_group.name}"
                    )
                    self.terminal_window.create_window()
                    self.terminal_window.update_status(
                        "Starting validation...", "#f39c12"
                    )
                    # Signal that window is ready
                    self.async_bridge.signal_from_gui(event_id)

                self.window.after(0, create_window)
                await window_ready_event.wait()
                self.async_bridge.cleanup_event(event_id)

            # Capture all streaming output for validation ID extraction
            captured_output = []

            # Define progress callbacks that stream to terminal window
            def validation_progress_callback(message: str):
                # Capture all output for later processing
                captured_output.append(message)
                if self.terminal_window:
                    self.terminal_window.append_output(message)
                # Only update progress for significant messages, not every line
                if any(
                    keyword in message.lower()
                    for keyword in [
                        "started",
                        "building",
                        "testing",
                        "completed",
                        "failed",
                        "error",
                        "warning",
                    ]
                ):
                    self._update_progress(message.strip(), "info")

            def validation_status_callback(status: str, color: str):
                # Also capture status messages
                captured_output.append(f"STATUS: {status}\n")
                if self.terminal_window:
                    self.terminal_window.update_status(status, color)
                level = (
                    "success"
                    if color == "#27ae60"
                    else "warning" if color == "#f39c12" else "error"
                )
                # Always update progress for status changes since these are significant
                self._update_progress(status, level)

            # Run validation process
            validation_result = (
                await self.validation_service.archive_and_validate_project_group(
                    self.project_group,
                    validation_progress_callback,
                    validation_status_callback,
                )
            )

            if validation_result.is_error:
                if self.terminal_window:
                    self.terminal_window.update_status("Validation failed", "#e74c3c")
                    self.terminal_window.append_output(
                        f"\n❌ Error: {validation_result.error.message}\n"
                    )
                    # Add final buttons even on error so user can copy error output
                    if self.terminal_window.text_area:
                        terminal_content = self.terminal_window.text_area.get(
                            "1.0", "end-1c"
                        )
                        self.terminal_window.add_final_buttons(
                            copy_text=terminal_content
                        )
                return AsyncResult.error_result(validation_result.error)

            # Handle partial results (validation completed with issues)
            if validation_result.is_partial and self.terminal_window:
                self.terminal_window.update_status(
                    "Validation completed with issues", "#f39c12"
                )
                self.terminal_window.append_output(
                    f"\n⚠️ Validation completed with some issues: {validation_result.error.message}\n"
                )

            # Combine all captured output for validation ID extraction
            full_output = "".join(captured_output)

            # Also try to get output from the validation result data
            result_output = ""
            if validation_result.data:
                if hasattr(validation_result.data, "validation_output"):
                    result_output = validation_result.data.validation_output
                elif hasattr(validation_result.data, "raw_output"):
                    result_output = validation_result.data.raw_output
                elif hasattr(validation_result.data, "get"):
                    result_output = validation_result.data.get("raw_output", "")
                else:
                    result_output = str(validation_result.data)

            # Use the most comprehensive output available
            raw_output = (
                full_output + "\n" + result_output if result_output else full_output
            )

            validation_id = self._extract_validation_id(raw_output)

            # Update terminal window with success
            if self.terminal_window:
                self.terminal_window.update_status(
                    "Validation completed successfully", "#27ae60"
                )
                self.terminal_window.append_output(
                    "\n✅ Validation completed successfully!\n"
                )

                # Add validation ID to output if found
                if validation_id:
                    self.terminal_window.append_output(
                        f"\n📋 Validation ID: {validation_id}\n"
                    )

                # Add final buttons for complex interactions
                additional_buttons = []

                # Add validation ID copy button if we found an ID
                if validation_id:

                    def copy_validation_id():
                        try:
                            import pyperclip

                            pyperclip.copy(validation_id)
                            import tkinter.messagebox as messagebox

                            messagebox.showinfo(
                                "Copied!",
                                f"Validation ID copied to clipboard:\n{validation_id}",
                            )
                        except ImportError:
                            # Fallback for systems without pyperclip
                            self.window.clipboard_clear()
                            self.window.clipboard_append(validation_id)
                            import tkinter.messagebox as messagebox

                            messagebox.showinfo(
                                "Copied!",
                                f"Validation ID copied to clipboard:\n{validation_id}",
                            )
                        except Exception as e:
                            import tkinter.messagebox as messagebox

                            messagebox.showerror(
                                "Copy Error", f"Could not copy validation ID: {e}"
                            )

                    additional_buttons.append(
                        {
                            "text": "📋 Copy Validation ID",
                            "command": copy_validation_id,
                            "style": "git",
                        }
                    )

                # Add button to open results file if it exists
                from pathlib import Path

                results_file = Path("validation-tool/output/validation_results.csv")
                if results_file.exists():

                    def open_results():
                        try:
                            from services.platform_service import PlatformService

                            success, error_msg = (
                                PlatformService.open_file_with_default_application(
                                    str(results_file)
                                )
                            )
                            if not success:
                                import tkinter.messagebox as messagebox

                                messagebox.showerror(
                                    "Error", f"Could not open results file: {error_msg}"
                                )
                        except Exception as e:
                            import tkinter.messagebox as messagebox

                            messagebox.showerror(
                                "Error", f"Could not open results file: {e}"
                            )

                    additional_buttons.append(
                        {
                            "text": "📊 Open Results",
                            "command": open_results,
                            "style": "archive",
                        }
                    )

                # Use the full captured output as copy text for the main copy button
                # Get current terminal content for copying
                terminal_content = ""
                if self.terminal_window.text_area:
                    terminal_content = self.terminal_window.text_area.get(
                        "1.0", "end-1c"
                    )

                copy_text = terminal_content or raw_output
                self.terminal_window.add_final_buttons(
                    copy_text=copy_text, additional_buttons=additional_buttons
                )

            result_data = {
                "message": f"Validation completed for {self.project_group.name}",
                "project_group_name": self.project_group.name,
                "success": validation_result.is_success,
                "raw_output": raw_output,
                "validation_id": validation_id,
                "terminal_created": self.terminal_window is not None,
            }

            self._update_progress("Validation completed", "success")

            return AsyncResult.success_result(
                result_data, message=f"Successfully validated {self.project_group.name}"
            )

        except Exception as e:
            self.logger.exception(
                f"Validation command failed for {self.project_group.name}"
            )
            if self.terminal_window:
                self.terminal_window.update_status("Error occurred", "#e74c3c")
                self.terminal_window.append_output(f"\n❌ Error: {str(e)}\n")

            return AsyncResult.error_result(
                ProcessError(
                    f"Validation failed: {str(e)}", error_code="VALIDATION_ERROR"
                )
            )

    def _extract_validation_id(self, raw_output: str) -> str:
        """Extract validation ID from output"""
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


class BuildDockerFilesCommand(AsyncCommand):
    """Standardized command for building Docker files with complex file generation"""

    def __init__(
        self,
        project_group: ProjectGroup,
        docker_files_service,
        window=None,
        async_bridge=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.project_group = project_group
        self.docker_files_service = docker_files_service
        self.window = window
        self.async_bridge = async_bridge
        self.terminal_window = None

    def _restart_with_removal(self):
        """Restart the build process after removing existing files"""

        async def restart_async():
            import asyncio

            # Find the pre-edit version to remove files from
            pre_edit_project = self.docker_files_service._find_pre_edit_version(
                self.project_group
            )
            if not pre_edit_project:
                if self.window:
                    from tkinter import messagebox

                    self.window.after(
                        0,
                        lambda: messagebox.showerror(
                            "Error", "Could not find pre-edit version for file removal"
                        ),
                    )
                return

            # Create new terminal window for the removal and rebuild
            from gui import TerminalOutputWindow

            def create_new_window():
                self.terminal_window = TerminalOutputWindow(
                    self.window,
                    f"Build Docker Files - {self.project_group.name} (Removing existing)",
                )
                self.terminal_window.create_window()
                self.terminal_window.update_status(
                    "Removing existing files...", "#f39c12"
                )

            if self.window:
                self.window.after(0, create_new_window)
                await asyncio.sleep(0.1)  # Wait for window creation

            # Define callbacks for the removal and rebuild
            def progress_callback(message: str):
                if self.terminal_window:
                    self.terminal_window.append_output(message)

            def status_callback(status: str, color: str):
                if self.terminal_window:
                    self.terminal_window.update_status(status, color)

            try:
                # Remove existing Docker files
                removal_success = (
                    await self.docker_files_service.remove_existing_docker_files(
                        pre_edit_project, progress_callback
                    )
                )

                if not removal_success:
                    if self.terminal_window:
                        self.terminal_window.update_status("Removal failed", "#e74c3c")
                        self.terminal_window.append_output(
                            "\n❌ Failed to remove existing files.\n"
                        )
                    return

                # Now retry the build
                status_callback("Starting fresh build...", "#f39c12")
                build_result = await self.docker_files_service.build_docker_files_for_project_group(
                    self.project_group,
                    progress_callback,
                    status_callback,
                )

                # Handle the result
                if isinstance(build_result, tuple):
                    success, message = build_result
                    if success:
                        if self.terminal_window:
                            self.terminal_window.update_status(
                                "Build completed successfully", "#27ae60"
                            )
                            self.terminal_window.append_output(
                                "\n✅ Docker files build completed successfully!\n"
                            )

                            # Add final buttons
                            if self.terminal_window.text_area:
                                full_output = self.terminal_window.text_area.get(
                                    "1.0", "end-1c"
                                )
                                self.terminal_window.add_final_buttons(
                                    copy_text=full_output
                                )
                    else:
                        if self.terminal_window:
                            self.terminal_window.update_status(
                                "Build failed", "#e74c3c"
                            )
                            self.terminal_window.append_output(
                                f"\n❌ Build failed: {message}\n"
                            )
                else:
                    # Handle AsyncResult format
                    if hasattr(build_result, "is_success") and build_result.is_success:
                        if self.terminal_window:
                            self.terminal_window.update_status(
                                "Build completed successfully", "#27ae60"
                            )
                            self.terminal_window.append_output(
                                "\n✅ Docker files build completed successfully!\n"
                            )

                            # Add final buttons
                            if self.terminal_window.text_area:
                                full_output = self.terminal_window.text_area.get(
                                    "1.0", "end-1c"
                                )
                                self.terminal_window.add_final_buttons(
                                    copy_text=full_output
                                )
                    else:
                        if self.terminal_window:
                            self.terminal_window.update_status(
                                "Build failed", "#e74c3c"
                            )
                            self.terminal_window.append_output(
                                f"\n❌ Build failed: {build_result.error.message if hasattr(build_result, 'error') else 'Unknown error'}\n"
                            )

            except Exception as e:
                if self.terminal_window:
                    self.terminal_window.update_status("Error occurred", "#e74c3c")
                    self.terminal_window.append_output(
                        f"\n❌ Error during removal and rebuild: {str(e)}\n"
                    )

        # Start the async restart operation
        if hasattr(self, "_task_manager"):
            self._task_manager.run_task(
                restart_async(), task_name=f"rebuild-docker-{self.project_group.name}"
            )
        else:
            # Fallback to using the global task manager
            from utils.async_utils import task_manager

            task_manager.run_task(
                restart_async(), task_name=f"rebuild-docker-{self.project_group.name}"
            )

    async def execute(self) -> AsyncResult[Dict[str, Any]]:
        """Execute the build Docker files command with terminal window"""
        try:
            # Import here to avoid circular imports
            from gui import TerminalOutputWindow
            import asyncio

            self._update_progress("Building Docker files...", "info")

            # Create terminal window immediately if window is available
            if self.window and self.async_bridge:
                event_id, window_ready_event = self.async_bridge.create_sync_event()

                def create_window():
                    self.terminal_window = TerminalOutputWindow(
                        self.window, f"Build Docker Files - {self.project_group.name}"
                    )
                    self.terminal_window.create_window()
                    self.terminal_window.update_status(
                        "Starting Docker files build...", "#f39c12"
                    )
                    # Signal that window is ready
                    self.async_bridge.signal_from_gui(event_id)

                self.window.after(0, create_window)
                await window_ready_event.wait()
                self.async_bridge.cleanup_event(event_id)

            # Define progress callback that streams to terminal window
            def docker_files_progress_callback(message: str):
                if self.terminal_window:
                    self.terminal_window.append_output(message)
                self._update_progress(message, "info")

            # Define status callback
            def docker_files_status_callback(status: str, color: str):
                if self.terminal_window:
                    self.terminal_window.update_status(status, color)
                level = (
                    "success"
                    if color == "#27ae60"
                    else "warning" if color == "#f39c12" else "error"
                )
                self._update_progress(status, level)

            # Build Docker files
            build_result = (
                await self.docker_files_service.build_docker_files_for_project_group(
                    self.project_group,
                    docker_files_progress_callback,
                    docker_files_status_callback,
                )
            )

            # Handle different return formats - service might return tuple (success, message) or AsyncResult
            if isinstance(build_result, tuple):
                # Old format: (success: bool, message: str)
                success, message = build_result
                if not success:
                    # Check if the error is due to existing files
                    if "Existing Docker files found" in message:
                        # Handle existing files by prompting user
                        if self.terminal_window:
                            self.terminal_window.update_status(
                                "Existing files found", "#f39c12"
                            )
                            self.terminal_window.append_output(f"\n⚠️  {message}\n")
                            self.terminal_window.append_output("\nOptions:\n")
                            self.terminal_window.append_output(
                                "• Remove existing files and proceed\n"
                            )
                            self.terminal_window.append_output("• Cancel operation\n\n")

                            # Add buttons for user choice
                            def handle_remove_and_continue():
                                if self.terminal_window:
                                    # Close the terminal window and restart with removal
                                    self.terminal_window.destroy()
                                # Trigger a new build with removal
                                self._restart_with_removal()

                            def handle_cancel():
                                if self.terminal_window:
                                    self.terminal_window.update_status(
                                        "Operation cancelled", "#e74c3c"
                                    )
                                    self.terminal_window.append_output(
                                        "\n❌ Operation cancelled by user.\n"
                                    )

                            additional_buttons = [
                                {
                                    "text": "🗑️ Remove & Continue",
                                    "command": handle_remove_and_continue,
                                    "style": "cleanup",
                                },
                                {
                                    "text": "❌ Cancel",
                                    "command": handle_cancel,
                                    "style": "close",
                                },
                            ]

                            self.terminal_window.add_final_buttons(
                                copy_text="", additional_buttons=additional_buttons
                            )

                        return AsyncResult.error_result(
                            ProcessError(
                                f"Build cancelled due to existing files: {message}",
                                error_code="EXISTING_FILES",
                            )
                        )
                    else:
                        # Other type of error
                        if self.terminal_window:
                            self.terminal_window.update_status(
                                "Build failed", "#e74c3c"
                            )
                            self.terminal_window.append_output(
                                f"\n❌ Error: {message}\n"
                            )
                        return AsyncResult.error_result(
                            ProcessError(
                                f"Build failed: {message}",
                                error_code="DOCKER_FILES_ERROR",
                            )
                        )
                # Convert to standard format for success
                build_result = AsyncResult.success_result(
                    {"message": message, "success": True}
                )
            elif hasattr(build_result, "is_error") and build_result.is_error:
                # New format: AsyncResult
                if self.terminal_window:
                    self.terminal_window.update_status("Build failed", "#e74c3c")
                    self.terminal_window.append_output(
                        f"\n❌ Error: {build_result.error.message}\n"
                    )
                return AsyncResult.error_result(build_result.error)

            # Update terminal window with success
            if self.terminal_window:
                self.terminal_window.update_status(
                    "Docker files built successfully", "#27ae60"
                )
                self.terminal_window.append_output(
                    "\n✅ Docker files build completed successfully!\n"
                )

                # Add final buttons with copy functionality
                if self.terminal_window.text_area:
                    full_output = self.terminal_window.text_area.get("1.0", "end-1c")
                    self.terminal_window.add_final_buttons(copy_text=full_output)

            result_data = {
                "message": f"Docker files built for {self.project_group.name}",
                "project_group_name": self.project_group.name,
                "success": (
                    build_result.is_success
                    if hasattr(build_result, "is_success")
                    else True
                ),
                "details": (
                    build_result.data
                    if hasattr(build_result, "data") and build_result.data
                    else {}
                ),
                "terminal_created": self.terminal_window is not None,
            }

            self._update_progress("Docker files built successfully", "success")

            return AsyncResult.success_result(
                result_data,
                message=f"Successfully built Docker files for {self.project_group.name}",
            )

        except Exception as e:
            self.logger.exception(
                f"Build Docker files command failed for {self.project_group.name}"
            )
            if self.terminal_window:
                self.terminal_window.update_status("Error occurred", "#e74c3c")
                self.terminal_window.append_output(f"\n❌ Error: {str(e)}\n")

            return AsyncResult.error_result(
                ProcessError(
                    f"Build Docker files failed: {str(e)}",
                    error_code="DOCKER_FILES_ERROR",
                )
            )


class AsyncTaskManager:
    """Centralized async task management"""

    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}
        self._results: Dict[str, AsyncResult] = {}

    async def execute_command(self, command: AsyncCommand) -> str:
        """Execute a command and return a task ID for tracking"""
        task_id = str(uuid.uuid4())

        # Create and store the task
        task = asyncio.create_task(command.run_with_progress())
        self._tasks[task_id] = task

        # Add completion callback
        task.add_done_callback(lambda t: self._handle_task_completion(task_id, t))

        return task_id

    def _handle_task_completion(self, task_id: str, task: asyncio.Task):
        """Handle task completion and store results"""
        try:
            if task.exception():
                # Task failed with exception
                error = ProcessError(f"Task failed: {task.exception()}")
                self._results[task_id] = AsyncResult.error_result(error)
            else:
                # Task completed successfully
                self._results[task_id] = task.result()
        except Exception as e:
            # Error getting result
            error = ProcessError(f"Error getting task result: {e}")
            self._results[task_id] = AsyncResult.error_result(error)
        finally:
            # Clean up the task reference
            self._tasks.pop(task_id, None)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            return True
        return False

    def get_active_task_count(self) -> int:
        """Get the number of active tasks"""
        return len(self._tasks)

    def get_task_result(self, task_id: str) -> AsyncResult:
        """Get the result of a completed task"""
        return self._results.get(
            task_id, AsyncResult.error_result(ProcessError("Task result not found"))
        )


# Export main classes
__all__ = [
    "CleanupProjectCommand",
    "ArchiveProjectCommand",
    "DockerBuildAndTestCommand",
    "GitViewCommand",
    "GitCheckoutAllCommand",
    "SyncRunTestsCommand",
    "ValidateProjectGroupCommand",
    "BuildDockerFilesCommand",
    "AsyncTaskManager",
]
